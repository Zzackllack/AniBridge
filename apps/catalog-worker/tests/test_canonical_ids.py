"""Secondary IDs are observed identities, never inferred from names."""

import asyncio
import json

import pytest
from catalog_core.identity import mapping_id, title_id
from catalog_worker.canonical import Enricher
from catalog_worker.canonical_ids import identifiers
from catalog_worker.mapping import CanonicalTitle
from catalog_worker.transport import Fetch
from test_canonical import NOW, TITLE, ready


def test_secondary_ids_preserve_namespaces_and_reject_malformed_values():
    candidate = CanonicalTitle("tvdb", "123", ("Example",), 2020, "series")
    assert identifiers(candidate, {"imdbId": "tt1234567", "tmdbId": 456}, False) == {
        "tvdb": "123",
        "tmdb-tv": "456",
        "imdb": "tt1234567",
    }
    for fields in (
        {"imdbId": "1234567"},
        {"tmdbId": "456"},
        {"tmdbId": True},
        {"imdbId": False},
    ):
        with pytest.raises(ValueError):
            identifiers(candidate, fields, False)
    assert identifiers(candidate, {"imdbId": "", "tmdbId": 0}, False) == {"tvdb": "123"}


def test_secondary_conflict_does_not_partially_replace_title_maps(tmp_path):
    state = ready(tmp_path)
    tid = title_id("aniworld.to", TITLE)
    with state.db:
        state.db.execute(
            "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
            (
                mapping_id("aniworld.to", tid, "imdb", "tt9999999"),
                tid,
                "imdb",
                "tt9999999",
                "skyhook-v1",
                "explicit_id",
                NOW,
            ),
        )

    async def fetch(origin, path, **kwargs):
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "imdbId": "tt1234567",
            "tmdbId": 456,
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    try:
        asyncio.run(Enricher({}, fetcher=fetch).tick(state, NOW))
        assert dict(
            state.db.execute("SELECT namespace,external_id FROM canonical_title")
        ) == {"imdb": "tt9999999"}
        assert (
            state.db.execute("SELECT outcome FROM mapping_input").fetchone()[0]
            == "conflict"
        )
    finally:
        state.close()
