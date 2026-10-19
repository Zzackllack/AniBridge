"""Snapshot or compare stopped worker ledgers using the installed worker image.

The operator must stop both collector and metadata first. This helper never
opens State, migrates a ledger, restores a backup, or changes collection work.
"""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from catalog_worker.config import load
from catalog_worker.state_migrations import preflight


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compare(current: Path, prior: Path, *, local_rematches: int = 0) -> dict:
    if type(local_rematches) is not int or not 0 <= local_rematches <= 32:
        raise ValueError("bounded local rematch count required")
    result = {}
    with closing(sqlite3.connect(current.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA cache_size=-32768")
        db.execute(
            "ATTACH DATABASE ? AS prior", (prior.as_uri() + "?mode=ro&immutable=1",)
        )
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM prior.sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        # Only publication clocks/schema and local matcher receipts may change.
        # All prior map rows and release rows (including first_seen_at) must stay.
        mutable = {"worker_schema"}
        for table in tables:
            if table in mutable or table.startswith("publication_"):
                continue
            if table == "canonical_scheduler" and local_rematches:
                before = db.execute(
                    "SELECT singleton,slot FROM prior.canonical_scheduler"
                ).fetchall()
                after = db.execute(
                    "SELECT singleton,slot FROM main.canonical_scheduler"
                ).fetchall()
                # The real Enricher.tick advances one fairness slot even for a
                # cached rematch. Verify the declared advancement, never reset it
                # or exempt collection/retry deadlines from comparison.
                if len(before) != 1 or after != [
                    (1, (before[0][1] + local_rematches) % 5)
                ]:
                    raise ValueError("unexpected canonical scheduler advancement")
                result[table] = {"verified_local_rematches": local_rematches}
                continue
            quoted = '"' + table.replace('"', '""') + '"'
            columns = "*"
            if table == "worker_meta":
                columns = ",".join(
                    '"' + row[1] + '"'
                    for row in db.execute("PRAGMA table_info(worker_meta)")
                    if row[1] not in {"dirty", "published_at"}
                )
            if table == "matching_replay" and local_rematches:
                fingerprints = "title_id,source_hash,descriptor_hash"
                missing = db.execute(
                    f"SELECT count(*) FROM (SELECT {fingerprints} FROM prior.matching_replay EXCEPT SELECT {fingerprints} FROM main.matching_replay)"
                ).fetchone()[0]
                changed = db.execute(
                    "SELECT count(*) FROM (SELECT * FROM main.matching_replay EXCEPT SELECT * FROM prior.matching_replay)"
                ).fetchone()[0]
                if missing or changed > local_rematches:
                    raise ValueError("unexpected matching receipt change")
                result[table] = {
                    "retained_input_fingerprints": True,
                    "changed_receipts": changed,
                }
                continue
            missing = db.execute(
                f"SELECT count(*) FROM (SELECT {columns} FROM prior.{quoted} EXCEPT SELECT {columns} FROM main.{quoted})"
            ).fetchone()[0]
            added = db.execute(
                f"SELECT count(*) FROM (SELECT {columns} FROM main.{quoted} EXCEPT SELECT {columns} FROM prior.{quoted})"
            ).fetchone()[0]
            if missing or (added and table != "canonical_episode"):
                raise ValueError(f"stopped-state preservation failed: {table}")
            result[table] = {"old_rows_missing_or_changed": missing, "added": added}
        result["totals"] = {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("entity", "release", "canonical_episode")
        }
    return result


def run(
    mode: str, config_path: Path, directory: Path, *, rematches: list[str] | None = None
) -> dict:
    config = load(config_path)
    rematches = rematches or []
    if (
        len(rematches) > 32
        or set(rematches) - config.providers.keys()
        or (mode == "snapshot" and rematches)
    ):
        raise ValueError("declare at most 32 cached rematches for configured providers")
    plan = json.loads((directory / "plan.json").read_text())
    if digest(config_path) != plan["original_worker_sha256"]:
        raise ValueError("worker configuration changed since this plan was prepared")
    receipt = directory / "baseline.json"
    if mode == "snapshot" and receipt.exists():
        raise ValueError("baseline already exists; never replace rollback evidence")
    baselines = {} if mode == "snapshot" else json.loads(receipt.read_text())
    results = {}
    for provider in config.providers:
        filename = config.state_dir / (provider + ".sqlite")
        version = preflight(filename, provider)
        if version not in (5, 6):
            raise ValueError("this workflow supports private worker state v5/v6 only")
        baseline = directory / (provider + ".before.sqlite")
        if mode == "snapshot":
            # SQLite backup includes committed WAL data; copying the main file
            # alone can silently discard the newest observations.
            with baseline.open("xb"):
                baseline.chmod(0o600)
            with (
                closing(
                    sqlite3.connect(filename.as_uri() + "?mode=ro", uri=True)
                ) as source,
                closing(sqlite3.connect(baseline)) as destination,
            ):
                source.backup(destination)
            baselines[provider] = {"sha256": digest(baseline), "version": version}
            results[provider] = "snapshotted"
        else:
            if digest(baseline) != baselines[provider]["sha256"]:
                raise ValueError("baseline fingerprint changed")
            results[provider] = compare(
                filename, baseline, local_rematches=rematches.count(provider)
            )
    target = receipt if mode == "snapshot" else directory / "preservation.json"
    with target.open("x") as stream:
        target.chmod(0o600)
        json.dump(baselines if mode == "snapshot" else results, stream, indent=2)
        stream.write("\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("snapshot", "verify"))
    parser.add_argument("--config", type=Path, default=Path("/config/worker.json"))
    parser.add_argument("--directory", type=Path, default=Path("/plan"))
    parser.add_argument(
        "--local-rematch",
        action="append",
        default=[],
        choices=("aniworld.to", "s.to", "megakino"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.mode, args.config, args.directory, rematches=args.local_rematch)
        )
    )
