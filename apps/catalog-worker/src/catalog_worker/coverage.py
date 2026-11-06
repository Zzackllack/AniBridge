"""Measure publication coverage after rights filtering, not before export."""

import sqlite3
from contextlib import closing
from pathlib import Path

from .signals import Signals
from .state import State


def measure(state: State, artifact: Path, now: int) -> tuple[dict, int | None, str]:
    with closing(sqlite3.connect(artifact.as_uri() + "?mode=ro", uri=True)) as db:
        details = (
            db.execute(
                "SELECT 1 FROM title WHERE detail_status<>'complete' LIMIT 1"
            ).fetchone()
            is None
        )
        mappings = (
            db.execute(
                "SELECT 1 FROM entity e WHERE (e.kind='episode' AND NOT EXISTS "
                "(SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)) "
                "OR (e.kind='movie' AND NOT EXISTS (SELECT 1 FROM canonical_title c "
                "WHERE c.title_id=e.title_id AND c.namespace IN ('tmdb-movie','imdb'))) LIMIT 1"
            ).fetchone()
            is None
        )
    # A never-checked active page is an unknown oldest check, not a recent one.
    active, checked, oldest = state.db.execute(
        "SELECT count(*),count(w.checked_at),min(w.checked_at) FROM work w "
        "JOIN title_schedule s USING(title_id) WHERE s.changed_at>? AND "
        "w.title_id NOT IN (SELECT id FROM omissions WHERE kind='title' AND tombstoned=1)",
        (now - 2592000,),
    ).fetchone()
    status = state.meta()["state"]
    if status in ("bootstrap", "partial", "healthy"):
        status = (
            "healthy"
            if details
            and mappings
            and Signals(state).status()["coverage"] == "window-overlap"
            else "partial"
        )
    return (
        {
            "titles": "complete",
            "details": "complete" if details else "partial",
            "mappings": "complete" if mappings else "partial",
        },
        oldest if active == checked else None,
        status,
    )
