"""Finite offline publication/query replay on a disposable copied pilot ledger.

Run inside a network-disabled Linux container with explicit CPU/memory caps.
This opens the supplied COPY as a worker; never point it at a live volume.
"""

import argparse
import asyncio
import json
import resource
import time
from pathlib import Path

import httpx
from catalog_core.protocol import Request
from catalog_core.supervisor import run_child_async
from catalog_worker.config import load
from catalog_worker.query_server import create_app


def counters(name: str) -> dict[str, int]:
    path = Path("/sys/fs/cgroup") / name
    return {
        key: int(value)
        for key, value in (line.split() for line in path.read_text().splitlines())
    }


async def replay(path: Path) -> dict:
    config = load(path)
    app = create_app(config.output_dir, "disposable-replay-token")
    result = {"queries": [], "publications": [], "cpu_before": counters("cpu.stat")}
    started = time.monotonic()

    async def publish():
        for provider in config.providers:
            begin = time.monotonic()
            try:
                records = await run_child_async(
                    "catalog_worker.query_publish", [str(path), provider], 420
                )
                item = {"status": "ok", "records": records or []}
            except (ValueError, OSError, TimeoutError) as exc:
                item = {
                    "status": type(exc).__name__,
                    "reason": getattr(exc, "reason", "rejected"),
                    "exit_code": getattr(exc, "exit_code", None),
                    "records": getattr(exc, "records", []),
                }
            result["publications"].append(
                {
                    "provider": provider,
                    "duration_s": round(time.monotonic() - begin, 4),
                    **item,
                }
            )

    publication = asyncio.create_task(publish())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        headers={"Authorization": "Bearer disposable-replay-token"},
    ) as http:

        async def request(req: Request):
            begin = time.monotonic()
            response = await http.post("/catalog/v1/query", json=req.model_dump())
            body = response.json()
            item = {
                "provider": req.provider,
                "operation": req.operation,
                "mode": req.params["t"],
                "status": response.status_code,
                "duration_s": round(time.monotonic() - begin, 4),
            }
            if response.status_code == 200:
                item.update(
                    total=body["total"],
                    rows=len(body["rows"]),
                    revision=body["revision"],
                )
            result["queries"].append(item)
            return body

        # Twelve finite rounds, up to 96 metadata calls during publication.
        # Post-publication targeted checks are recorded separately.
        for _ in range(12):
            for provider, name in [
                ("aniworld.to", "One Piece"),
                ("s.to", "Breaking Bad"),
            ]:
                if provider not in config.providers:
                    continue
                for mode in ["search", "tvsearch"]:
                    await request(
                        Request(
                            provider=provider,
                            operation="recent",
                            params={"t": mode},
                            limit=100,
                        )
                    )
                titles = await request(
                    Request(
                        provider=provider,
                        operation="titles",
                        params={"t": "tvsearch", "q": name},
                    )
                )
                if titles.get("titles"):
                    await request(
                        Request(
                            provider=provider,
                            operation="native",
                            params={"t": "search"},
                            title_ids=[t["title_id"] for t in titles["titles"]],
                            season=1,
                            episode=1,
                            limit=500,
                        )
                    )
            if publication.done():
                break
            await asyncio.sleep(1)
    await publication
    result.update(
        duration_s=round(time.monotonic() - started, 4),
        cpu_after=counters("cpu.stat"),
        memory_peak_bytes=int(Path("/sys/fs/cgroup/memory.peak").read_text()),
        memory=counters("memory.stat"),
        memory_events=counters("memory.events"),
        io=Path("/sys/fs/cgroup/io.stat").read_text(),
        largest_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(asyncio.run(replay(args.config)), indent=2) + "\n"
    )
