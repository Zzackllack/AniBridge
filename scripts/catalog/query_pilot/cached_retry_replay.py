"""Bounded offline scheduler replay on frozen full-ledger backups.

Run the same script against baseline and candidate code at 2 CPU/2 GiB with
network disabled. HTTP 500 responses are simulated, not live outage evidence.
No failures, leases or deadlines are cleared to make the queue advance.
"""

import argparse
import asyncio
import json
import shutil
import sqlite3
import time
from collections import Counter
from pathlib import Path

from catalog_core.providers.transport import Fetch
from catalog_worker.canonical import Enricher
from catalog_worker.state import State
from mapping_replay import metrics, resources

PROTECTED = (
    "release",
    "entity",
    "entity_alias",
    "title",
    "alias",
    "work",
    "omissions",
    "quarantine",
    "title_schedule",
    "signal_meta",
    "signal_pending",
    "season_batch_checkpoint",
    "observation_gap",
    "season_correspondence",
    "canonical_episode",
    "request_start",
    "transport_failure",
)


def queue(db: sqlite3.Connection, now: int) -> dict:
    row = db.execute(
        "SELECT count(*),min(next_due) FROM mapping_input "
        "WHERE failures>0 AND next_due<=?",
        (now,),
    ).fetchone()
    return {"failed_due": row[0], "oldest_age_s": now - row[1] if row[0] else None}


async def replay(root: Path, phase: str, now: int, ticks: int) -> dict:
    baseline, candidate = root / "baseline", root / phase
    if not (baseline / "COPY_ONLY").is_file() or not 1 <= ticks <= 60:
        raise ValueError("marked frozen backups and 1–60 ticks required")
    candidate.mkdir(mode=0o700, exist_ok=False)
    (candidate / "COPY_ONLY").touch()
    result = {
        "phase": phase,
        "simulated_http_status": 500,
        "ticks": ticks,
        "network_requests": 0,
        "resources_before": resources(),
        "providers": {},
    }
    states, before = [], {}
    for provider in ("aniworld.to", "s.to"):
        source = baseline / (provider + ".sqlite")
        if source.with_name(source.name + "-wal").exists():
            raise ValueError("WAL-free consistent backups required")
        shutil.copyfile(source, candidate / source.name)
        state = State(candidate / source.name, provider)
        states.append(state)
        before[provider] = {"counts": metrics(state.db), "queue": queue(state.db, now)}
        state.db.execute("PRAGMA temp_store=MEMORY")
        state.db.execute(
            "ATTACH DATABASE ? AS baseline",
            (source.resolve().as_uri() + "?mode=ro&immutable=1",),
        )
    clock, requests, outcomes = (
        [now],
        Counter(),
        {s.provider: Counter() for s in states},
    )

    async def unavailable(origin: str, path: str, **kwargs) -> Fetch:
        requests[worker.current_state.provider] += 1
        return Fetch("http_error", status=500, requests=1)

    def enrich() -> Enricher:
        return Enricher(
            {"tv": "skyhook", "movie": "off", "episode_languages": ["deu"]},
            fetcher=unavailable,
            clock=lambda: clock[0],
            states=states,
            requests_per_minute=90,
        )

    worker = enrich()
    cpu, started = time.process_time(), time.monotonic()
    try:
        for tick in range(ticks):
            clock[0] = now + tick
            if tick == ticks // 2:
                await worker.close()
                worker = enrich()  # Exercise durable admission and retry resume.
            for state in states:
                await worker.tick(state, clock[0])
                outcomes[state.provider][worker.last_work] += 1
        result["scheduler_wall_s"] = round(time.monotonic() - started, 6)
        result["scheduler_cpu_s"] = round(time.process_time() - cpu, 6)
        for state in states:
            db, provider = state.db, state.provider
            unchanged = {}
            for table in PROTECTED:
                removed = db.execute(
                    f"SELECT count(*) FROM (SELECT * FROM baseline.{table} EXCEPT SELECT * FROM main.{table})"
                ).fetchone()[0]
                added = db.execute(
                    f"SELECT count(*) FROM (SELECT * FROM main.{table} EXCEPT SELECT * FROM baseline.{table})"
                ).fetchone()[0]
                assert removed == 0 and (added == 0 or table == "canonical_episode"), (
                    table
                )
                unchanged[table] = {"old_rows_changed": removed, "added_rows": added}
            parents = db.execute(
                "SELECT count(*) FROM baseline.canonical_title b LEFT JOIN main.canonical_title c "
                "USING(mapping_id) WHERE c.mapping_id IS NULL OR c.title_id<>b.title_id "
                "OR c.namespace<>b.namespace OR c.external_id<>b.external_id"
            ).fetchone()[0]
            assert parents == 0
            advanced = db.execute(
                "SELECT count(*) FROM main.mapping_input m JOIN baseline.mapping_input b USING(title_id) "
                "WHERE m.checked_at>b.checked_at"
            ).fetchone()[0]
            result["providers"][provider] = {
                "before": before[provider],
                "after": {"counts": metrics(db), "queue": queue(db, clock[0])},
                "outcomes": dict(outcomes[provider]),
                "simulated_requests": requests[provider],
                "distinct_lookup_attempts": advanced,
                "preservation": unchanged,
                "parent_identities_changed": parents,
            }
        result["resources_after"] = resources()
        return result
    finally:
        await worker.close()
        for state in states:
            state.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--ticks", type=int, default=30)
    args = parser.parse_args()
    result = asyncio.run(replay(args.root, args.phase, args.now, args.ticks))
    (args.root / (args.phase + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
