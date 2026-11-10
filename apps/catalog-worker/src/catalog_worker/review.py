"""Explicit operator season correspondence; ordinal equality is never inferred."""

from catalog_core.identity import validate_external_id
from catalog_core.json_codec import fields, integer, require

from .state import State


def season(state: State, body: dict) -> None:
    fields(
        body,
        {
            "title_id",
            "namespace",
            "external_id",
            "native_season",
            "canonical_season",
            "expected_old",
        },
    )
    require(body["namespace"] in ("tvdb", "tmdb-tv"), "TV namespace required")
    validate_external_id(body["namespace"], body["external_id"])
    integer(body["native_season"], 0, 2**31 - 1)
    integer(body["canonical_season"], 0, 2**31 - 1)
    if body["expected_old"] is not None:
        integer(body["expected_old"], 0, 2**31 - 1)
    with state.db:
        state.db.execute("BEGIN IMMEDIATE")
        mapping = state.db.execute(
            "SELECT mapping_id FROM canonical_title WHERE title_id=? AND namespace=? AND external_id=?",
            (body["title_id"], body["namespace"], body["external_id"]),
        ).fetchone()
        require(mapping is not None, "validated title mapping required")
        require(
            state.db.execute(
                "SELECT 1 FROM entity WHERE title_id=? AND kind='episode' AND native_season=? LIMIT 1",
                (body["title_id"], body["native_season"]),
            ).fetchone()
            is not None,
            "unknown native season",
        )
        key = (
            body["title_id"],
            body["namespace"],
            body["external_id"],
            body["native_season"],
        )
        previous = state.db.execute(
            "SELECT canonical_season FROM season_correspondence WHERE title_id=? AND namespace=? AND external_id=? AND native_season=?",
            key,
        ).fetchone()
        require(
            (previous[0] if previous else None) == body["expected_old"],
            "correspondence changed",
        )
        if previous and previous[0] == body["canonical_season"]:
            return
        state.db.execute(
            "INSERT OR REPLACE INTO season_correspondence VALUES(?,?,?,?,?,'reviewed')",
            (*key, body["canonical_season"]),
        )
        # A reviewed change invalidates only correspondence derived for this
        # native season. Re-enrichment must prove episode titles again.
        state.db.execute(
            "DELETE FROM canonical_episode WHERE mapping_id=? AND entity_id IN "
            "(SELECT entity_id FROM entity WHERE title_id=? AND native_season=?)",
            (mapping[0], body["title_id"], body["native_season"]),
        )
        state.db.execute(
            "UPDATE mapping_input SET next_due=0 WHERE title_id=?", (body["title_id"],)
        )
        state.db.execute("UPDATE worker_meta SET dirty=1")
