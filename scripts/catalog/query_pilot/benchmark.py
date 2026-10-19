"""Short fixed generated-data workload; not a capacity or WAN promise."""

import asyncio
import importlib.metadata
import json
import resource
import tempfile
import time
from pathlib import Path

from catalog_core.query_client import Cache, Client
from app.catalog.config import load
from app.catalog.query_local import Search


def percentile(values: list[float], fraction: float) -> float:
    return round(sorted(values)[max(0, int(len(values) * fraction) - 1)], 3)


async def main() -> None:
    config = load("/config/client.json")
    with tempfile.TemporaryDirectory(prefix="query-benchmark-") as temporary:
        root = Path(temporary)
        client = Client(
            config.origin,
            config.source_id,
            config.token_file.read_text().strip(),
            Cache(root / "cache.sqlite"),
            allow_private_http=config.allow_private_http,
        )
        search = Search(client, Path("/data/anibridge_jobs.db"), root)
        cases = [
            {"t": "tvsearch", "tvdbid": "81189", "season": "1"},
            {"t": "search", "q": "Breaking Bad"},
            {"t": "search", "limit": "20"},
            {"t": "tvsearch", "tvdbid": "99999999"},
        ]
        timings = []
        started = time.monotonic()
        cpu = time.process_time()

        async def one(params):
            at = time.perf_counter()
            rows, total, _ = await search.search(
                params,
                now=int(time.time()),
                languages={"aniworld.to": {"de-dub", "en-sub"}},
            )
            timings.append((time.perf_counter() - at) * 1000)
            return len(rows), total

        try:
            # Eight identical cold season misses must share candidate + native fetch.
            coalesced = await asyncio.gather(*(one(cases[0]) for _ in range(8)))
            assert client.requests == 2 and all(
                value == (40, 40) for value in coalesced
            )
            cold_bytes = client.response_bytes
            for _ in range(16):
                await asyncio.gather(*(one(cases[i % 4]) for i in range(8)))
            result = {
                "dataset": {
                    "titles": 1,
                    "episodes": 20,
                    "observed_languages": 2,
                    "releases": 40,
                },
                "logical_queries": len(timings),
                "concurrency": 8,
                "duration_s": round(time.monotonic() - started, 3),
                "consumer_cpu_s": round(time.process_time() - cpu, 3),
                "p50_ms": percentile(timings, 0.5),
                "p95_ms": percentile(timings, 0.95),
                "p99_ms": percentile(timings, 0.99),
                "remote_requests": client.requests,
                "remote_response_body_bytes": client.response_bytes,
                "cold_season_request_count": 2,
                "cold_season_body_bytes": cold_bytes,
                "cache_bytes": sum(
                    p.stat().st_size for p in root.iterdir() if p.is_file()
                ),
                "consumer_process_peak_rss_bytes": resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
                * 1024,
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in ("fastapi", "pydantic", "httpx", "uvicorn")
                },
                "limits": "1-GiB/2-vCPU container; warm generated catalog; no WAN delay, TLS or media",
            }
            print(json.dumps(result, sort_keys=True))
        finally:
            await client.close()


asyncio.run(main())
