"""Offline Linux checkpoint/publication comparison using the same bounded inputs."""

import asyncio
import json
import resource
import sys
import tempfile
import time
from pathlib import Path

from catalog_core.protocol import Request
from catalog_core.providers.transport import Fetch
from catalog_worker.aniworld import Link, Page
from catalog_worker.collector import Collector, Plan
from catalog_worker.config import LIMITS, Config
from catalog_worker.query_reader import execute
from catalog_worker.read_catalog import publish
from catalog_worker.state import State


async def main():
    root = Path(sys.argv[1])
    mode = sys.argv[2]
    result = []
    started = time.monotonic()
    for item in json.loads((root / "inputs.json").read_bytes()):
        provider = item["provider"]
        season = item["path"]
        title = season.rsplit("/", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "state").mkdir()
            config = Config(
                {
                    provider: "https://aniworld.to"
                    if provider == "aniworld.to"
                    else "https://serienstream.to"
                },
                {"tv": "off"},
                base / "state",
                base / "read",
                base / "key",
                "benchmark",
                "127.0.0.1",
                1,
                {k: v[0] for k, v in LIMITS.items()},
            )
            filename = base / "state" / f"{provider}.sqlite"
            state = State(filename, provider)
            now = int(time.time())
            # Seed only the parent coordinates to isolate the measured season
            # work. This is not a provider title enumeration benchmark.
            state.listing(Page((Link(title, "Benchmark"),), (), 0, None), now)
            state.detail(
                state.claim(now),
                Page((Link(season, "Season"),), (), 0, "Benchmark"),
                now,
            )
            bodies = {
                season: (root / item["body_file"]).read_bytes(),
                **{
                    d["path"]: (root / d["body_file"]).read_bytes()
                    for d in item["details"]
                },
            }
            calls = []

            async def fetch(origin, path, bodies=bodies, calls=calls, **options):
                calls.append(path)
                return Fetch("ok", bodies[path])

            collector = Collector(
                config, state, fetcher=fetch, clock=lambda now=now: now
            )
            parser_s = writer_s = 0
            paths = [season] + (
                [d["path"] for d in item["details"]] if mode == "baseline" else []
            )
            for path in paths:
                work = dict(
                    state.db.execute(
                        "SELECT * FROM work WHERE path=?", (path,)
                    ).fetchone()
                )
                begin = time.monotonic()
                ready = await collector.collect(Plan(now, False, work, path))
                parser_s += time.monotonic() - begin
                assert ready.outcome == "ok"
                begin = time.monotonic()
                collector.apply(ready)
                writer_s += time.monotonic() - begin
            counts = {
                name: state.db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in ("entity", "release")
            }
            first_seen = [
                tuple(r)
                for r in state.db.execute(
                    "SELECT release_id,first_seen_at FROM release ORDER BY release_id"
                )
            ]
            begin = time.monotonic()
            publish(config, state, now)
            publication_s = time.monotonic() - begin
            response = execute(
                config.output_dir,
                Request(
                    operation="recent",
                    provider=provider,
                    params={"t": "search"},
                    limit=100,
                ),
                now,
            )
            assert response.total == counts["release"]
            state.close()
            state = State(filename, provider)
            assert first_seen == [
                tuple(r)
                for r in state.db.execute(
                    "SELECT release_id,first_seen_at FROM release ORDER BY release_id"
                )
            ]
            checked = state.db.execute(
                "SELECT count(*) FROM work WHERE checked_at IS NOT NULL"
            ).fetchone()[0]
            state.close()
            result.append(
                {
                    "provider": provider,
                    "requests": len(calls),
                    "rows": counts["entity"],
                    "releases": counts["release"],
                    "rows_per_request": counts["entity"] / len(calls),
                    "parser_s": parser_s,
                    "writer_s": writer_s,
                    "publication_s": publication_s,
                    "query_total": response.total,
                    "restart_first_seen_preserved": True,
                    "checked_pages": checked,
                    "disk_bytes": sum(
                        p.stat().st_size for p in base.rglob("*") if p.is_file()
                    ),
                }
            )
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print(
        json.dumps(
            {
                "mode": mode,
                "cohorts": result,
                "elapsed_s": time.monotonic() - started,
                "cpu_s": usage.ru_utime + usage.ru_stime,
                "peak_bytes": int(Path("/sys/fs/cgroup/memory.peak").read_text()),
                "limits": {"memory_bytes": 536870912, "cpus": 2, "pids": 64},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
