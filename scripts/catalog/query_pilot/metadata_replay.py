"""Replay at most 32 saved metadata responses against a disposable ledger copy.

A cases file contains native paths; sibling 0.html, 1.html, ... hold the bounded
responses. No network or media request is made. Use Linux container CPU/RAM caps.
"""

import argparse
import asyncio
import json
import resource
import time
from pathlib import Path

from catalog_core.providers.transport import Fetch
from catalog_worker.collector import Collector, Plan
from catalog_worker.config import load
from catalog_worker.state import State


async def replay(config_path: Path, cases_path: Path, provider: str) -> dict:
    config = load(config_path)
    paths = json.loads(cases_path.read_text())
    if not isinstance(paths, list) or not 1 <= len(paths) <= 32:
        raise ValueError("one to 32 metadata cases required")
    started, cpu = time.monotonic(), time.process_time()
    state = State(config.state_dir / f"{provider}.sqlite", provider)
    cases, requests = [], 0
    before = state.db.execute("SELECT count(*) FROM release").fetchone()[0]
    # SQL saves only IDs/timestamps in an owned temporary table; Python never
    # retains the whole provider catalog. New positive offers may extend it.
    state.db.execute(
        "CREATE TEMP TABLE retained AS SELECT release_id,first_seen_at FROM release"
    )
    try:
        for index, path in enumerate(paths):
            signal = path == "/neue-episoden"
            row = (
                None
                if signal
                else state.db.execute(
                    "SELECT * FROM work WHERE path=?", (path,)
                ).fetchone()
            )
            if not signal and row is None:
                raise ValueError("case absent from disposable state")
            with (cases_path.parent / f"{index}.html").open("rb") as stream:
                body = stream.read(config.limits["body_bytes"] + 1)
            if len(body) > config.limits["body_bytes"]:
                raise ValueError("case body exceeds configured limit")

            async def fetcher(origin, target, *, replay_body=body, **options):
                return Fetch(
                    "ok", body=replay_body, status=200, requests=1, duration_s=0.001
                )

            collector = Collector(config, state, fetcher=fetcher)
            work = None if signal else {**dict(row), "incremental": True}
            begin = time.monotonic()
            ready = await collector.collect(
                Plan(int(time.time()), False, work, path, signal=signal)
            )
            collector.apply(ready)
            requests += ready.requests
            cases.append(
                {
                    "sample": index,
                    "kind": "recent" if signal else row["kind"],
                    "outcome": ready.outcome,
                    "reason": getattr(ready, "parser_reason", None),
                    "availability": getattr(ready.page, "availability", "available")
                    if ready.page
                    else None,
                    "batch_rows": len(ready.page.episodes) if ready.page else 0,
                    "positive_rows": sum(
                        bool(r.languages and not r.unknown_languages)
                        for r in ready.page.episodes
                    )
                    if ready.page
                    else 0,
                    "parser_s": round(ready.parser_s, 4),
                    "checkpoint_s": round(time.monotonic() - begin - ready.parser_s, 4),
                }
            )
        preserved = (
            state.db.execute(
                "SELECT count(*) FROM retained b LEFT JOIN release r USING(release_id) WHERE r.release_id IS NULL OR r.first_seen_at<>b.first_seen_at"
            ).fetchone()[0]
            == 0
        )
        result = {
            "cases": cases,
            "metadata_responses_replayed": requests,
            "new_releases": state.db.execute("SELECT count(*) FROM release").fetchone()[
                0
            ]
            - before,
            "all_old_release_identities_preserved": preserved,
            "duration_s": round(time.monotonic() - started, 4),
            "parent_cpu_s": round(time.process_time() - cpu, 4),
            "child_cpu_s": round(
                resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime
                + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
                4,
            ),
        }
        for name in ["memory.stat", "memory.events", "cpu.stat", "io.stat"]:
            result[name] = Path("/sys/fs/cgroup", name).read_text()
        result["memory_peak_bytes"] = int(
            Path("/sys/fs/cgroup/memory.peak").read_text()
        )
        return result
    finally:
        state.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--provider", choices=["aniworld.to", "s.to"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(
            asyncio.run(replay(args.config, args.cases, args.provider)), indent=2
        )
        + "\n"
    )
