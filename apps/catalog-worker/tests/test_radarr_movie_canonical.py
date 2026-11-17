"""Synthetic contracts for the optional keyless Radarr movie adapter."""

import asyncio
import json

import pytest
from catalog_core.identity import title_id
from catalog_core.providers.transport import Fetch
from catalog_worker.canonical import Enricher
from catalog_worker.config import load
from catalog_worker.radarr_movie_canonical import MATCHER, ORIGIN, lookup
from catalog_worker.state import State

NOW = 1_800_000_000
PATH = "/films/1-example.html"
IMDB = "tt1234567"
MOVIE = {
    "TmdbId": 123,
    "ImdbId": IMDB,
    "Title": "Example",
    "OriginalTitle": "Example Original",
    "Year": 2020,
    "AlternativeTitles": [{"Title": "Another title"}],
    "Translations": [{"Title": "Übersetzung"}],
}


def ready(tmp_path, imdb=IMDB, provider="megakino"):
    filename = tmp_path / "worker.sqlite"
    state = State(filename, provider)
    path = "/movies/example" if provider == "filmo.to" else PATH
    tid = title_id(provider, path)
    with state.db:
        state.db.execute(
            "INSERT INTO title VALUES(?,?,?,'Example','example','movie',2020,?,?,'complete')",
            (tid, path, "example", path, NOW),
        )
        state.db.execute(
            "INSERT INTO title_schedule VALUES(?,?,?,?)", (tid, NOW, NOW, NOW)
        )
        state.db.execute(
            "INSERT INTO mapping_input(title_id,explicit_imdb) VALUES(?,?)",
            (tid, imdb),
        )
    return state, filename


def test_radarr_lookup_uses_explicit_imdb_then_exact_detail():
    calls = []

    async def request(path, params=None, **kwargs):
        calls.append((path, params, kwargs))
        if path.endswith("/imdb/" + IMDB):
            return [MOVIE]
        return MOVIE

    matched, details = asyncio.run(
        lookup(request, {"explicit_imdb": IMDB}, ("Different provider title",))
    )

    assert matched[0].namespace == "tmdb-movie"
    assert matched[0].external_id == "123"
    assert matched[0].titles == (
        "Example",
        "Example Original",
        "Another title",
        "Übersetzung",
    )
    assert matched[1] == "explicit_id"
    assert details == {"imdb_id": IMDB, "id": 123}
    assert [call[0] for call in calls] == ["/v1/movie/imdb/" + IMDB, "/v1/movie/123"]
    assert all(call[2] == {"origin": ORIGIN} for call in calls)
    assert "radarr.video" not in repr(matched)


def test_radarr_optional_title_rows_ignore_empty_titles_but_keep_valid_names():
    calls = []
    movie = {
        **MOVIE,
        "AlternativeTitles": [{"Title": ""}, {"Title": "Another title"}],
        "Translations": [{"Title": ""}, {"Title": "Übersetzung"}],
    }

    async def request(path, **kwargs):
        calls.append(path)
        return [movie] if "/imdb/" in path else movie

    matched, _ = asyncio.run(lookup(request, {"explicit_imdb": IMDB}, ()))

    assert matched[0].titles == (
        "Example",
        "Example Original",
        "Another title",
        "Übersetzung",
    )
    assert calls == ["/v1/movie/imdb/" + IMDB, "/v1/movie/123"]


@pytest.mark.parametrize(
    "optional_titles",
    [
        [{"Title": 123}],
        [{"Title": "x" * 513}],
    ],
)
def test_radarr_optional_title_rows_still_reject_invalid_or_oversized_names(
    optional_titles,
):
    movie = {**MOVIE, "AlternativeTitles": optional_titles}

    async def request(path, **kwargs):
        return [movie]

    with pytest.raises(ValueError, match="invalid alternative titles title"):
        asyncio.run(lookup(request, {"explicit_imdb": IMDB}, ()))


def test_radarr_movie_with_no_primary_or_optional_names_is_rejected():
    movie = {
        **MOVIE,
        "Title": None,
        "OriginalTitle": None,
        "AlternativeTitles": [],
        "Translations": [],
    }

    async def request(path, **kwargs):
        return [movie]

    with pytest.raises(ValueError, match="missing Radarr movie title"):
        asyncio.run(lookup(request, {"explicit_imdb": IMDB}, ()))


@pytest.mark.parametrize(
    "results",
    [[], [MOVIE, {**MOVIE, "TmdbId": 456}]],
)
def test_radarr_lookup_does_not_guess_from_empty_or_ambiguous_id_results(results):
    calls = []

    async def request(path, **kwargs):
        calls.append(path)
        return results

    matched, details = asyncio.run(
        lookup(request, {"explicit_imdb": IMDB}, ("Example",))
    )

    assert matched is None and details == {}
    assert calls == ["/v1/movie/imdb/" + IMDB]


def test_radarr_detail_must_repeat_the_exact_imdb_association():
    responses = [[MOVIE], {**MOVIE, "ImdbId": "tt7654321"}]

    async def request(*args, **kwargs):
        return responses.pop(0)

    with pytest.raises(ValueError, match="IMDb mismatch"):
        asyncio.run(lookup(request, {"explicit_imdb": IMDB}, ("Example",)))


@pytest.mark.parametrize("provider", ["filmo.to", "megakino"])
def test_radarr_title_year_search_persists_a_verified_movie_without_a_token(
    tmp_path, provider
):
    state, _ = ready(tmp_path, imdb=None, provider=provider)
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append((origin, path, kwargs))
        assert origin == ORIGIN
        assert "bearer" not in kwargs
        if path == "/v1/search":
            assert kwargs["query"] == {"q": "Example", "year": "2020"}
            body = [MOVIE]
        else:
            assert path == "/v1/movie/123"
            body = MOVIE
        return Fetch("ok", json.dumps(body).encode())

    assert asyncio.run(
        Enricher({"tv": "off", "movie": "radarr"}, fetcher=fetch).tick(state, NOW)
    )
    row = state.db.execute(
        "SELECT * FROM canonical_title WHERE namespace='tmdb-movie'"
    ).fetchone()
    assert row is not None and row["external_id"] == "123"
    assert row["evidence"] == "exact_title_year"
    assert row["source"] == "radarr-skyhook-v1"
    assert [call[1] for call in calls] == ["/v1/search", "/v1/movie/123"]
    state.close()


@pytest.mark.parametrize("year", [None, 0, True, "2020"])
def test_title_search_without_a_valid_year_does_not_guess(year):
    calls = []

    async def request(*args, **kwargs):
        calls.append(args)
        raise AssertionError("invalid year must not initiate a lookup")

    matched, _ = asyncio.run(
        lookup(request, {"explicit_imdb": None, "year": year}, ("Example",))
    )
    assert matched is None and not calls


@pytest.mark.parametrize(
    "results",
    [[], [{**MOVIE, "Year": 2021}], [MOVIE, {**MOVIE, "TmdbId": 456}]],
)
def test_title_search_abstains_for_missing_wrong_year_or_ambiguous_candidates(results):
    calls = []

    async def request(path, params=None, **kwargs):
        calls.append(path)
        return results

    matched, _ = asyncio.run(
        lookup(request, {"explicit_imdb": None, "year": 2020}, ("Example",))
    )
    assert matched is None
    assert calls == ["/v1/search"]


def test_title_search_uses_distinct_aliases_and_verifies_translated_detail():
    calls = []
    movie = {**MOVIE, "Title": "English Title", "Translations": [{"Title": "Beispiel"}]}

    async def request(path, params=None, **kwargs):
        calls.append((path, params))
        assert kwargs == {"origin": ORIGIN}
        return [movie] if path == "/v1/search" else movie

    matched, _ = asyncio.run(
        lookup(
            request,
            {"explicit_imdb": None, "year": 2020},
            ("Beispiel", "BEISPIEL", "English Title", "Ignored fourth name"),
        )
    )
    assert matched[0].external_id == "123" and matched[1] == "exact_title_year"
    assert calls == [
        ("/v1/search", {"q": "Beispiel", "year": "2020"}),
        ("/v1/search", {"q": "English Title", "year": "2020"}),
        ("/v1/movie/123", None),
    ]


@pytest.mark.parametrize(
    "detail,reason",
    [
        ({**MOVIE, "TmdbId": 456}, "TMDb ID mismatch"),
        ({**MOVIE, "Year": 2021}, "title/year mismatch"),
        (
            {
                **MOVIE,
                "Title": "Other",
                "OriginalTitle": "Other",
                "AlternativeTitles": [],
                "Translations": [],
            },
            "title/year mismatch",
        ),
        ({**MOVIE, "ImdbId": "tt7654321"}, "IMDb mismatch"),
    ],
)
def test_title_lookup_rejects_a_detail_that_contradicts_the_search(detail, reason):
    async def request(path, params=None, **kwargs):
        return [MOVIE] if path == "/v1/search" else detail

    with pytest.raises(ValueError, match=reason):
        asyncio.run(
            lookup(request, {"explicit_imdb": None, "year": 2020}, ("Example",))
        )


def test_radarr_enrichment_persists_distinct_provenance_and_survives_restart(
    tmp_path,
):
    state, filename = ready(tmp_path)
    calls = []
    sources = {"tv": "off", "movie": "radarr"}

    async def fetch(origin, path, **kwargs):
        calls.append((origin, path, kwargs))
        assert origin == ORIGIN
        assert "bearer" not in kwargs
        body = [MOVIE] if path.endswith("/imdb/" + IMDB) else MOVIE
        return Fetch("ok", json.dumps(body).encode())

    assert asyncio.run(Enricher(sources, fetcher=fetch).tick(state, NOW))
    row = state.db.execute("SELECT * FROM canonical_title").fetchone()
    assert row["namespace"] == "tmdb-movie"
    assert row["external_id"] == "123"
    assert row["source"] == "radarr-skyhook-v1"
    assert dict(
        state.db.execute("SELECT namespace,external_id FROM canonical_title")
    ) == {"tmdb-movie": "123", "imdb": IMDB}
    assert [call[1] for call in calls] == ["/v1/movie/imdb/" + IMDB, "/v1/movie/123"]
    state.close()

    state = State(filename, "megakino")
    assert not asyncio.run(Enricher(sources, fetcher=fetch).tick(state, NOW + 1))
    assert len(calls) == 2
    state.close()


def test_worker_config_accepts_radarr_without_a_tmdb_token(tmp_path):
    config_path = tmp_path / "worker.json"
    config_path.write_text(
        json.dumps(
            {
                "providers": {"megakino": "https://megakino.example"},
                "canonical_sources": {"tv": "off", "movie": "radarr"},
                "state_dir": str(tmp_path / "state"),
                "output_dir": str(tmp_path / "read"),
                "source_id": "radarr-test",
            }
        )
    )

    assert load(config_path).canonical_sources["movie"] == "radarr"


def test_new_title_matcher_retries_a_previous_id_only_miss_before_its_deadline(
    tmp_path,
):
    state, _ = ready(tmp_path, imdb=None, provider="filmo.to")
    enricher = Enricher({"tv": "off", "movie": "radarr"})
    old_matcher = enricher.matcher.removesuffix(":" + MATCHER)
    assert old_matcher != enricher.matcher
    with state.db:
        state.db.execute(
            "UPDATE mapping_input SET matcher=?,checked_at=?,next_due=?,outcome='not_found'",
            (old_matcher, NOW, NOW + 86400),
        )
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        return Fetch(
            "ok", json.dumps([MOVIE] if path == "/v1/search" else MOVIE).encode()
        )

    enricher.fetcher, enricher.pooled = fetch, False
    assert asyncio.run(enricher.tick(state, NOW + 1))
    assert calls == ["/v1/search", "/v1/movie/123"]
    assert (
        state.db.execute("SELECT matcher FROM mapping_input").fetchone()[0]
        == enricher.matcher
    )
    assert state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    state.close()


def test_title_search_conflict_does_not_replace_a_previously_valid_movie_map(tmp_path):
    state, _ = ready(tmp_path, imdb=None, provider="filmo.to")
    movie = dict(MOVIE)

    async def fetch(origin, path, **kwargs):
        return Fetch(
            "ok", json.dumps([movie] if path == "/v1/search" else movie).encode()
        )

    enricher = Enricher({"tv": "off", "movie": "radarr"}, fetcher=fetch)
    assert asyncio.run(enricher.tick(state, NOW))
    before = [
        tuple(row)
        for row in state.db.execute("SELECT * FROM canonical_title ORDER BY namespace")
    ]
    movie["TmdbId"] = 456
    with state.db:
        state.db.execute("UPDATE mapping_input SET next_due=0")
    assert asyncio.run(enricher.tick(state, NOW + 1))
    assert [
        tuple(row)
        for row in state.db.execute("SELECT * FROM canonical_title ORDER BY namespace")
    ] == before
    assert (
        state.db.execute("SELECT outcome FROM mapping_input").fetchone()[0]
        == "conflict"
    )
    state.close()
