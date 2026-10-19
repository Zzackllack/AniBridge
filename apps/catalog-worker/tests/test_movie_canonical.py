"""Synthetic TMDb contracts; no credentials or live movie lookup proof."""

import asyncio
import json

import pytest
from catalog_core.identity import title_id

from catalog_worker.canonical import Enricher
from catalog_worker.movie_canonical import lookup
from catalog_worker.state import State
from catalog_worker.transport import Fetch

NOW = 1800000000
MOVIE = {
    "id": 123,
    "title": "Example",
    "original_title": "Example",
    "release_date": "2020-01-01",
    "imdb_id": "tt1234567",
}


def test_movie_lookup_has_distinct_endpoints_and_exact_detail_validation():
    responses = [{"movie_results": [MOVIE], "tv_results": [{"id": 999}]}, MOVIE]
    calls = []

    async def request(path, params=None, **kwargs):
        calls.append((path, params, kwargs))
        return responses.pop(0)

    result, _ = asyncio.run(
        lookup(
            request,
            {"explicit_imdb": "tt1234567", "year": None},
            ("Example",),
            "fixture-token",
        )
    )
    assert result[0].namespace == "tmdb-movie" and result[1] == "explicit_id"
    assert calls[0][0] == "/3/find/tt1234567" and calls[1][0] == "/3/movie/123"
    assert all(
        kwargs["origin"] == "https://api.themoviedb.org"
        and kwargs["bearer"] == "fixture-token"
        for _, _, kwargs in calls
    )
    responses[:] = [{"movie_results": [MOVIE]}, {**MOVIE, "imdb_id": "tt9999999"}]
    with pytest.raises(ValueError, match="IMDb mismatch"):
        asyncio.run(
            lookup(
                request,
                {"explicit_imdb": "tt1234567", "year": None},
                ("Example",),
                "fixture-token",
            )
        )


@pytest.mark.parametrize(
    "response",
    [
        {"total_pages": 2, "results": [MOVIE]},
        {"total_pages": 1, "results": [MOVIE, {**MOVIE, "id": 456}]},
        {"total_pages": 1, "results": [{**MOVIE, "release_date": "2021-01-01"}]},
    ],
)
def test_partial_ambiguous_or_wrong_year_never_maps(response):
    async def request(*args, **kwargs):
        return response

    if response["total_pages"] == 2:
        with pytest.raises(ValueError, match="incomplete"):
            asyncio.run(
                lookup(
                    request,
                    {"explicit_imdb": None, "year": 2020},
                    ("Example",),
                    "fixture-token",
                )
            )
    else:
        assert (
            asyncio.run(
                lookup(
                    request,
                    {"explicit_imdb": None, "year": 2020},
                    ("Example",),
                    "fixture-token",
                )
            )[0]
            is None
        )


def test_movie_enrichment_persists_only_compact_mapping_and_survives_restart(tmp_path):
    token = tmp_path / "credential"
    token.write_text("fixture-token")
    filename = tmp_path / "worker.sqlite"
    state = State(filename, "megakino")
    path = "/films/1-example.html"
    tid = title_id("megakino", path)
    with state.db:
        state.db.execute(
            "INSERT INTO title VALUES(?,?,?,'Example','example','movie',2020,?,?,'complete')",
            (tid, path, "example", path, NOW),
        )
        state.db.execute(
            "INSERT INTO title_schedule VALUES(?,?,?,?)", (tid, NOW, NOW, NOW)
        )
        state.db.execute("INSERT INTO mapping_input(title_id) VALUES(?)", (tid,))
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        assert (
            origin == "https://api.themoviedb.org"
            and kwargs["bearer"] == "fixture-token"
        )
        body = (
            {"total_pages": 1, "results": [MOVIE]}
            if path.endswith("/search/movie")
            else MOVIE
        )
        return Fetch("ok", json.dumps(body).encode())

    sources = {"tv": "off", "movie": "tmdb", "tmdb_token_file": str(token)}
    enricher = Enricher(sources, fetcher=fetch)
    assert asyncio.run(enricher.tick(state, NOW))
    row = dict(state.db.execute("SELECT * FROM canonical_title").fetchone())
    assert (
        row["namespace"] == "tmdb-movie"
        and row["external_id"] == "123"
        and row["source"] == "tmdb-v3"
    )
    assert state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0] == 0
    assert dict(
        state.db.execute("SELECT namespace,external_id FROM canonical_title")
    ) == {
        "tmdb-movie": "123",
        "imdb": "tt1234567",
    }
    state.close()
    state = State(filename, "megakino")
    assert not asyncio.run(Enricher(sources, fetcher=fetch).tick(state, NOW + 1))
    assert len(calls) == 2
    state.close()
    assert b"fixture-token" not in filename.read_bytes()


@pytest.mark.parametrize(
    "details",
    [
        {**MOVIE, "release_date": "2021-01-01"},
        {**MOVIE, "release_date": ""},
        {**MOVIE, "title": "Different", "original_title": "Different"},
    ],
)
def test_detail_correction_cannot_contradict_title_year_binding(details):
    async def request(path, params=None, **kwargs):
        return (
            {"total_pages": 1, "results": [MOVIE]}
            if path.endswith("/search/movie")
            else details
        )

    with pytest.raises(ValueError, match="movie title/year mismatch"):
        asyncio.run(
            lookup(
                request,
                {"explicit_imdb": None, "year": 2020},
                ("Example",),
                "fixture-token",
            )
        )


def test_proven_explicit_id_does_not_require_matching_provider_title_year():
    async def request(path, params=None, **kwargs):
        return (
            {"movie_results": [MOVIE]}
            if "/find/" in path
            else {
                **MOVIE,
                "title": "Changed title",
                "original_title": "Changed title",
                "release_date": "2021-01-01",
            }
        )

    matched, _ = asyncio.run(
        lookup(
            request,
            {"explicit_imdb": "tt1234567", "year": 2020},
            ("Example",),
            "fixture-token",
        )
    )
    assert matched[1] == "explicit_id"
