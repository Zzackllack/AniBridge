"""Read-only, bounded accounting of marked consistent private ledger copies.

No network or State initialization: even migration/preflight writes are excluded.
Each unresolved usable episode contributes to exactly one primary bucket. Retry
state takes precedence; correspondence reasons are evidence gaps, not accuracy
labels. Raw metadata and paths never enter the report.
"""

import argparse
import json
import sqlite3
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

from mapping_replay import metrics

from catalog_worker.correspondence import decisions
from catalog_worker.progress import canonical_queue
from catalog_worker.state import State


def inspect(root: Path, now: int, seconds: int = 180) -> dict:
    if not (root / "COPY_ONLY").is_file() or not 1 <= seconds <= 300:
        raise ValueError("marked snapshot and 1–300 second deadline required")
    result = {"clock": now, "providers": {}}
    deadline = time.monotonic() + seconds
    for provider in ("aniworld.to", "s.to"):
        path = root / (provider + ".sqlite")
        if not path.is_file() or path.with_name(path.name + "-wal").exists():
            raise ValueError("WAL-free consistent backup required")
        with closing(
            sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        ) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA cache_size=-32768")
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
            totals = metrics(db)
            release_maps = db.execute(
                "SELECT count(*) FROM release r WHERE EXISTS "
                "(SELECT 1 FROM canonical_episode c WHERE c.entity_id=r.entity_id)"
            ).fetchone()[0]
            totals.update(
                mapped_releases=release_maps,
                unresolved_releases=totals["releases"] - release_maps,
                unresolved_usable_episodes=totals["usable_episodes"]
                - totals["usable_mapped"],
            )
            unmapped = {}
            for row in db.execute(
                "SELECT e.entity_id,e.title_id FROM entity e WHERE e.kind='episode' "
                "AND EXISTS(SELECT 1 FROM release r WHERE r.entity_id=e.entity_id) "
                "AND NOT EXISTS(SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)"
            ):
                unmapped.setdefault(row["title_id"], set()).add(row["entity_id"])
            view = State.__new__(State)
            view.db, view.provider = db, provider
            buckets = Counter()
            for tid, entities in unmapped.items():
                if time.monotonic() > deadline:
                    raise TimeoutError("snapshot accounting deadline")
                attempt = db.execute(
                    "SELECT checked_at,failures FROM mapping_input WHERE title_id=?",
                    (tid,),
                ).fetchone()
                if not attempt or attempt[0] is None:
                    buckets["waiting_never_attempted"] += len(entities)
                elif attempt[1] > 0:
                    buckets["retrying_canonical_failure"] += len(entities)
                else:
                    for decision in decisions(view, tid, contextual=True):
                        if decision.entity_id in entities:
                            buckets[decision.reason] += 1
            assert sum(buckets.values()) == totals["unresolved_usable_episodes"]
            failures = dict(
                db.execute(
                    "SELECT count(*) AS count,min(checked_at) AS oldest_checked_at,"
                    "min(due) AS earliest_retry_due,max(failures) AS max_attempts,"
                    "min(failures) AS min_attempts,sum(due<=?) AS scheduled_due,"
                    "sum(lease_until>?) AS leased FROM work WHERE failures>0",
                    (now, now),
                ).fetchone()
            )
            failures["attempt_buckets"] = dict(
                db.execute(
                    "SELECT CASE WHEN failures<10 THEN '1-9' WHEN failures<100 THEN '10-99' "
                    "WHEN failures<1000 THEN '100-999' ELSE '1000+' END,count(*) "
                    "FROM work WHERE failures>0 GROUP BY 1"
                )
            )
            result["providers"][provider] = {
                "schema": db.execute("SELECT version FROM worker_schema").fetchone()[0],
                "totals": totals,
                "unresolved_usable_partition": dict(sorted(buckets.items())),
                "canonical_queue": canonical_queue(db, now),
                "page_failures": failures,
                "expired_leases": db.execute(
                    "SELECT count(*) FROM work WHERE lease_until>0 AND lease_until<=?",
                    (now,),
                ).fetchone()[0],
                "unknown_language_observations": db.execute(
                    "SELECT coalesce(sum(unknown_languages),0) FROM observation_gap"
                ).fetchone()[0],
                "unavailable_observations": db.execute(
                    "SELECT count(*) FROM work WHERE fingerprint LIKE 'unavailable:%'"
                ).fetchone()[0],
                "unapproved_quarantines": db.execute(
                    "SELECT count(*) FROM quarantine WHERE approved=0"
                ).fetchone()[0],
                "publication": dict(
                    db.execute(
                        "SELECT generation,content_generation,published_generation,published_content_generation FROM publication_meta"
                    ).fetchone()
                ),
            }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=180)
    args = parser.parse_args()
    print(json.dumps(inspect(args.root, args.now, args.seconds), indent=2))
