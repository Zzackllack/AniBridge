"""Synthetic contracts for the optional keyless Radarr movie adapter."""

import asyncio
import json

import pytest
from catalog_core.identity import title_id
from catalog_core.providers.transport import Fetch

from catalog_worker.canonical import Enricher
from catalog_worker.config import load
from catalog_worker.radarr_movie_canonical import ORIGIN, lookup
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


def ready(tmp_path, imdb=IMDB):
    filename = tmp_path / "worker.sqlite"
    state = State(filename, "megakino")
    tid = title_id("megakino", PATH)
    with state.db:
        state.db.execute(
            "INSERT INTO title VALUES(?,?,?,'Example','example','movie',2020,?,?,'complete')",
            (tid, PATH, "example", PATH, NOW),
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


def test_radarr_title_year_without_explicit_id_abstains_without_search(tmp_path):
    state, _ = ready(tmp_path, imdb=None)
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append((origin, path))
        return Fetch("ok", json.dumps([MOVIE]).encode())

    assert asyncio.run(
        Enricher({"tv": "off", "movie": "radarr"}, fetcher=fetch).tick(state, NOW)
    )
    assert calls == []
    assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    state.close()


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
