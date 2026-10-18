"""Verify v6 copied-state preservation and finite rollback/resume, never live state."""

import argparse
import hashlib
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from catalog_worker.config import load
from catalog_worker.publication_state import pending
from catalog_worker.state import State
from catalog_worker.state_migrations import preflight, rollback_publication
from mapping_replay import metrics


def differences(db: sqlite3.Connection, table: str, columns: str = "*") -> int:
    return sum(
        db.execute(
            f"SELECT count(*) FROM (SELECT {columns} FROM {a}.{table} EXCEPT SELECT {columns} FROM {b}.{table})"
        ).fetchone()[0]
        for a, b in [("main", "prior"), ("prior", "main")]
    )


def verify(root: Path, state_dir: Path) -> dict:
    config = load(root / "modern.json")
    now = json.loads((root / "clock.json").read_text())
    result = {}
    for provider in config.providers:
        filename = state_dir / (provider + ".sqlite")
        state = State(filename, provider)
        db = state.db
        try:
            db.execute("PRAGMA temp_store=MEMORY")
            backup = filename.with_name(filename.name + ".pre-v6.backup")
            db.execute(
                "ATTACH DATABASE ? AS prior",
                (backup.as_uri() + "?mode=ro&immutable=1",),
            )
            tables = [
                r[0]
                for r in db.execute(
                    "SELECT name FROM prior.sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            unchanged = {
                t: differences(db, t)
                for t in tables
                if t not in {"entity", "worker_meta", "worker_schema"}
            }
            assert not any(unchanged.values())
            entity_columns = ",".join(
                r[1]
                for r in db.execute("PRAGMA table_info(entity)")
                if r[1] not in {"display_title", "observed_at"}
            )
            worker_columns = ",".join(
                r[1]
                for r in db.execute("PRAGMA table_info(worker_meta)")
                if r[1] not in {"dirty", "published_at"}
            )
            assert (
                differences(db, "entity", entity_columns)
                == differences(db, "worker_meta", worker_columns)
                == 0
            )
            entity_changes = db.execute(
                "SELECT count(*) FROM entity e JOIN prior.entity p USING(entity_id) WHERE e.display_title IS NOT p.display_title OR e.observed_at IS NOT p.observed_at"
            ).fetchone()[0]
            assert entity_changes == 2
            with closing(
                sqlite3.connect(backup.as_uri() + "?mode=ro&immutable=1", uri=True)
            ) as prior:
                before = metrics(prior)
            after = metrics(db)
            assert before == after
            age = db.execute(
                "SELECT max(0,?-min(due)) FROM work WHERE due<=? AND lease_until<=?",
                (now, now, now),
            ).fetchone()[0]
            prior_age = db.execute(
                "SELECT max(0,?-min(due)) FROM prior.work WHERE due<=? AND lease_until<=?",
                (now, now, now),
            ).fetchone()[0]
            assert age == prior_age
            generation = tuple(db.execute("SELECT * FROM publication_meta").fetchone())
            admitted = bool(generation[-1])
            eid = db.execute(
                "SELECT entity_id FROM entity ORDER BY entity_id LIMIT 1"
            ).fetchone()[0]
            timings = {}
            # Rolled-back SQL isolates journal cost. It excludes durable commit
            # cost and is not a provider/collector throughput benchmark.
            for enabled in (False, True):
                db.execute("BEGIN")
                try:
                    if not enabled:
                        for (name,) in db.execute(
                            "SELECT name FROM sqlite_schema WHERE type='trigger' AND name LIKE 'pub_%'"
                        ).fetchall():
                            db.execute(f'DROP TRIGGER "{name}"')
                    started, cpu = time.monotonic(), time.process_time()
                    for _ in range(500):
                        db.execute(
                            "UPDATE entity SET observed_at=observed_at+1 WHERE entity_id=?",
                            (eid,),
                        )
                    timings["v6_journal" if enabled else "without_journal"] = {
                        "updates": 500,
                        "wall_s": round(time.monotonic() - started, 6),
                        "cpu_s": round(time.process_time() - cpu, 6),
                        "durable_commit": False,
                    }
                    if enabled and admitted:
                        assert not pending(config, state, now + 300)
                        assert pending(config, state, now + 3600)
                finally:
                    db.rollback()
            assert (
                tuple(db.execute("SELECT * FROM publication_meta").fetchone())
                == generation
            )
            with backup.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            result[provider] = {
                "tables_compared": len(tables),
                "unchanged_table_differences": unchanged,
                "generated_entity_edits": entity_changes,
                "other_entity_or_worker_fields_changed": 0,
                "before": before,
                "after": after,
                "raw_due_work_oldest_age_s": age,
                "raw_due_age_preserved": True,
                "timestamp_only_pending_at_300_s": False if admitted else None,
                "timestamp_only_pending_at_3600_s": True if admitted else None,
                "initial_full_required": not admitted,
                "write_cost": timings,
                "pre_v6_backup_sha256": digest,
            }
        finally:
            state.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("verify", "downgrade", "reopen"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    if (
        not (args.root / "COPY_ONLY").is_file()
        or not (args.state / "COPY_ONLY").is_file()
    ):
        raise ValueError("explicit disposable copies required")
    if args.mode == "verify":
        result = verify(args.root, args.state)
    else:
        result = {}
        for provider in ("aniworld.to", "s.to"):
            path = args.state / (provider + ".sqlite")
            if args.mode == "downgrade":
                rollback_publication(path, provider)
                assert preflight(path, provider) == 5
            else:
                state = State(path, provider)
                state.close()
                # A second open verifies restart with the retained no-overwrite backup.
                state = State(path, provider)
                state.close()
                assert preflight(path, provider) == 6
            result[provider] = "passed"
    (args.root / (args.mode + "-preservation.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps({"mode": args.mode, "status": "passed"}))


if __name__ == "__main__":
    main()
