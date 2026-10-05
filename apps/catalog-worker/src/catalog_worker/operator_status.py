"""Read-only operator counters; no query log, credentials or response bodies."""

import sqlite3
import time
from contextlib import closing

from .config import Config
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
            mapping = {
                row[0]: row[1]
                for row in db.execute(
                    "SELECT outcome,count(*) FROM mapping_input GROUP BY outcome"
                )
            }
            ambiguous = db.execute(
                "SELECT count(*) FROM (SELECT namespace,external_id FROM canonical_title GROUP BY namespace,external_id HAVING count(DISTINCT title_id)>1)"
            ).fetchone()[0]
            result["providers"][provider] = {
                **meta,
                "counts": counts,
                "pending_pages": pending or 0,
                "failed_pages": failures or 0,
                "checked_pages": checked,
                "oldest_check_age_s": None if oldest is None else max(0, now - oldest),
                "mapping": {
                    "title_mapped": title_mapped,
                    "title_unresolved": counts["title"] - title_mapped,
                    "episodes": episode_total,
                    "episode_mapped": episode_mapped or 0,
                    "ambiguous_ids": ambiguous,
                    "outcomes": mapping,
                },
                "recent": signal,
                "complete": False,  # No bounded run claims a complete current provider.
            }
    return result
