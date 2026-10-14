"""Recheck fixed v1 row constraints without trusting publisher write settings."""

import sqlite3

from . import identity
from .json_codec import require


def validate(
    table: str,
    row: sqlite3.Row,
    columns: list[tuple[str, str, bool]],
    published_at: int,
) -> None:
    # Read-only integrity_check does not evaluate CHECK constraints. These
    # checks also reject malformed storage types without rewriting the artifact.
    for name, declared_type, nonnull in columns:
        value = row[name]
        if value is None:
            require(not nonnull, "unexpected null")
        else:
            expected = int if declared_type == "INTEGER" else str
            require(type(value) is expected, "invalid stored type")
            if name in ("observed_at", "checked_at", "first_seen_at"):
                require(0 <= value <= published_at + 300, "invalid row timestamp")
    if table == "title":
        require(
            row["media_type"] in {"series", "movie", "unknown"}, "invalid title kind"
        )
        require(row["year"] is None or 1800 <= row["year"] <= 2200, "invalid year")
        require(
            row["detail_status"] in {"pending", "partial", "complete", "stale"},
            "invalid detail state",
        )
    elif table == "entity":
        if row["kind"] == "movie":
            require(
                row["native_season"] is None and row["native_episode"] is None,
                "movie coordinates",
            )
        else:
            require(
                row["kind"] == "episode"
                and row["native_season"] is not None
                and row["native_episode"] is not None
                and row["native_season"] >= 0
                and row["native_episode"] >= 1,
                "invalid episode coordinates",
            )
    elif table == "release":
        require(row["language"] in identity.LANGUAGES, "invalid release language")
        require(
            row["observed_at"] >= row["first_seen_at"], "observation before discovery"
        )
    elif table == "canonical_title":
        identity.validate_external_id(row["namespace"], row["external_id"])
        require(
            row["evidence"] in {"explicit_id", "exact_title_year", "reviewed"},
            "invalid title evidence",
        )
    elif table == "canonical_episode":
        require(
            row["season"] >= 0 and row["episode"] >= 1, "invalid canonical coordinates"
        )
        require(
            row["evidence"] in {"explicit_id", "exact_title", "reviewed"},
            "invalid episode evidence",
        )
    elif table == "identity_alias":
        require(row["kind"] in {"title", "entity"}, "invalid alias kind")
        require(row["old_id"] != row["current_id"], "self alias")
