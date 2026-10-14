"""Read-only operator counters; no query log, credentials or response bodies."""

import sqlite3
import time
from contextlib import closing

from .config import Config
from .progress import measure
from .storage import status


def report(config: Config) -> dict:
    result = {"storage": status(config), "providers": {}}
    now = int(time.time())
    for provider in config.providers:
        filename = config.state_dir / f"{provider}.sqlite"
        if not filename.exists():
            result["providers"][provider] = {"state": "not_started"}
            continue
        with closing(
            sqlite3.connect(
                filename.resolve().as_uri() + "?mode=ro", uri=True, timeout=1
            )
        ) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            meta = dict(db.execute("SELECT * FROM worker_meta").fetchone())
            counts = {
                name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in (
                    "title",
                    "entity",
                    "release",
                    "canonical_title",
                    "canonical_episode",
                )
            }
            title_mapped = db.execute(
                "SELECT count(DISTINCT title_id) FROM canonical_title"
            ).fetchone()[0]
            episode_total, episode_mapped = db.execute(
                "SELECT count(*),sum(EXISTS(SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)) FROM entity e WHERE kind='episode'"
            ).fetchone()
            pending, failures, checked, oldest = db.execute(
                "SELECT sum(checked_at IS NULL),sum(failures>0),count(checked_at),min(checked_at) FROM work"
            ).fetchone()
            signal = dict(db.execute("SELECT * FROM signal_meta").fetchone())
            if provider == "megakino":
                signal["coverage"] = "unsupported"
            ambiguous_hints = db.execute(
                "SELECT count(*) FROM canonical_hint WHERE episode IS NULL"
            ).fetchone()[0]
            unsupported = db.execute(
                "SELECT count(*) FROM title WHERE media_type='unknown'"
            ).fetchone()[0]
            mapping = {
                row[0]: row[1]
                for row in db.execute(
                    "SELECT outcome,count(*) FROM mapping_input GROUP BY outcome"
                )
            }
            ambiguous = db.execute(
                "SELECT count(*) FROM (SELECT namespace,external_id FROM canonical_title GROUP BY namespace,external_id HAVING count(DISTINCT title_id)>1)"
            ).fetchone()[0]
            signal["gap_parents_pending"] = db.execute(
                "SELECT count(*) FROM work WHERE kind IN ('title','season') AND ? IS NOT NULL AND (checked_at IS NULL OR checked_at<=?)",
                (signal["gap_since"], signal["gap_since"]),
            ).fetchone()[0]
            signal["reconciliation_request_budget_per_hour"] = max(
                1, config.provider_limits(provider)["provider_requests_per_hour"] // 5
            )
            progress = measure(db, meta, now)
            result["providers"][provider] = {
                **meta,
                "state_semantics": "last retained worker fault; blocked_until controls provider cooldown",
                "operational_state": "blocked"
                if meta["blocked_until"] > now
                else "coverage_gaps"
                if failures
                or progress["unknown_language_observations"]
                or progress["unavailable_episode_observations"]
                else "first_pass_complete"
                if progress["first_pass_complete"]
                else "collecting",
                "counts": counts,
                "pending_pages": pending or 0,
                "failed_pages": failures or 0,
                "unsupported_titles": unsupported,
                "checked_pages": checked,
                "oldest_check_age_s": None if oldest is None else max(0, now - oldest),
                "mapping": {
                    "title_mapped": title_mapped,
                    "title_unresolved": counts["title"] - title_mapped,
                    "episodes": episode_total,
                    "episode_mapped": episode_mapped or 0,
                    "ambiguous_ids": ambiguous,
                    "ambiguous_episode_hints": ambiguous_hints,
                    "outcomes": mapping,
                },
                "recent": signal,
                "progress": progress,
                "complete": progress["detail_evidence_complete"],
            }
    return result
