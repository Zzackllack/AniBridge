"""Finite Linux metadata comparison; never open the pilot ledger for writes.

Baseline saves bounded season/detail bodies in a private disposable directory.
Candidate verifies row observations against the same details and profiles child
startup separately. Results contain counts/timings only; bodies stay uncommitted.
"""

import argparse
import asyncio
import json
import resource
import tempfile
import time
from pathlib import Path

from catalog_core.providers.adapters import adapter
from catalog_core.providers.transport import fetch
from catalog_core.supervisor import run_child_async

COHORT = {
    "aniworld.to": [
        "/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-1"
    ],
    "s.to": [
        "/serie/breaking-bad/staffel-1",
        "/serie/arthur-und-die-freunde-der-tafelrunde/staffel-1",
    ],
}
ORIGINS = {"aniworld.to": "https://aniworld.to", "s.to": "https://serienstream.to"}


async def child(body: bytes, path: str, provider: str):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "body").write_bytes(body)
        started = time.monotonic()
        await run_child_async(
            "catalog_worker.parse_child",
            [
                str(root / "body"),
                str(root / "page"),
                "detail",
                path,
                provider,
                ORIGINS[provider],
            ],
            30,
        )
        return json.loads((root / "page").read_bytes()), time.monotonic() - started


async def baseline(root: Path) -> dict:
    result, stored, requests = {}, [], 0
    for provider, seasons in COHORT.items():
        started = time.monotonic()
        rows, releases, errors, parser_s, network_s = 0, 0, {}, 0, 0
        for season in seasons:
            r = await fetch(ORIGINS[provider], season)
            requests += 1
            if r.outcome != "ok":
                errors[r.outcome] = errors.get(r.outcome, 0) + 1
                continue
            page, elapsed = await child(r.body, season, provider)
            parser_s += elapsed
            season_file = f"season-{len(stored)}.html"
            (root / season_file).write_bytes(r.body)
            item = {
                "provider": provider,
                "path": season,
                "body_file": season_file,
                "details": [],
            }
            paths = sorted(
                {
                    link["path"]
                    for link in page["links"]
                    if adapter(provider).EPISODE.fullmatch(link["path"])
                }
            )[:6]
            for path in paths:
                await asyncio.sleep(2)
                before = time.monotonic()
                detail = await fetch(ORIGINS[provider], path)
                network_s += time.monotonic() - before
                requests += 1
                if detail.outcome != "ok":
                    errors[detail.outcome] = errors.get(detail.outcome, 0) + 1
                    continue
                parsed, elapsed = await child(detail.body, path, provider)
                parser_s += elapsed
                body_file = f"detail-{len(stored)}-{len(item['details'])}.html"
                (root / body_file).write_bytes(detail.body)
                item["details"].append(
                    {"path": path, "body_file": body_file, "page": parsed}
                )
                rows += 1
                releases += len(parsed["languages"])
            stored.append(item)
        result[provider] = {
            "detail_rows": rows,
            "language_variants": releases,
            "errors": errors,
            "elapsed_s": time.monotonic() - started,
            "parser_s": parser_s,
            "network_s": network_s,
            "requests": len(seasons) + rows,
            "rows_per_request": rows / (len(seasons) + rows),
        }
    (root / "inputs.json").write_text(json.dumps(stored))
    return {"providers": result, "requests_total": requests}


async def candidate(root: Path) -> dict:
    from catalog_core.providers.transport import Session

    result = {}
    for item in json.loads((root / "inputs.json").read_bytes()):
        provider, season = item["provider"], item["path"]
        body = (root / item["body_file"]).read_bytes()
        page, elapsed = await child(body, season, provider)
        rows = {r["path"]: r for r in page["episodes"]}
        complete = sum(
            bool(r["title"] and r["languages"] and not r["unknown_languages"])
            for r in rows.values()
        )
        agreement, mismatches, title_gain = 0, [], 0
        for detail in item["details"]:
            actual = adapter(provider).parse(
                (root / detail["body_file"]).read_bytes(), "detail", detail["path"]
            )
            row = rows.get(detail["path"])
            if row and set(row["languages"]) == set(actual.languages):
                agreement += 1
            else:
                mismatches.append(
                    {
                        "row_languages": row["languages"] if row else [],
                        "detail_languages": actual.languages,
                    }
                )
            title_gain += int(
                detail["page"]["episode_title"] is None
                and actual.episode_title is not None
            )
        session = Session(ORIGINS[provider], 2)
        try:
            start = time.monotonic()
            live = await session.fetch(ORIGINS[provider], season)
            live_seconds = time.monotonic() - start
        finally:
            await session.close()
        result[item["body_file"]] = {
            "provider": provider,
            "batch_rows": len(rows),
            "complete_batch_rows": complete,
            "child_parser_s": elapsed,
            "verified_detail_rows": len(item["details"]),
            "language_agreements": agreement,
            "language_mismatches": mismatches,
            "new_detail_titles": title_gain,
            "batch_rows_per_request": complete,
            "baseline_requests_for_full_season": 1 + len(rows),
            "candidate_requests_for_full_season": 1 + len(rows) - complete,
            "live_outcome": live.outcome,
            "live_status": live.status,
            "live_s": live_seconds,
        }
    return {"cohorts": result}


async def profiles(root: Path) -> dict:
    from catalog_core.providers.transport import Session

    results = {}
    # Repeat the same season twice per profile. This is a small response check,
    # not evidence of browser TLS parity or a sustained safe request ceiling.
    for provider, seasons in COHORT.items():
        profiles = {
            "collector": {
                "User-Agent": "AniBridge-Metadata/1.0",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de,en;q=0.8",
            },
            "browser": {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de,en;q=0.8",
                "Referer": ORIGINS[provider] + "/",
            },
        }
        for name, headers in profiles.items():
            for concurrency in (1, 2):
                session = Session(ORIGINS[provider], concurrency, headers)
                samples = []

                async def request(
                    session=session, provider=provider, seasons=seasons, samples=samples
                ):
                    start = time.monotonic()
                    r = await session.fetch(ORIGINS[provider], seasons[0])
                    samples.append(
                        {
                            "status": r.status,
                            "outcome": r.outcome,
                            "seconds": time.monotonic() - start,
                        }
                    )

                start = time.monotonic()
                try:
                    if concurrency == 1:
                        await request()
                        await asyncio.sleep(1)
                        await request()
                    else:
                        await asyncio.gather(request(), request())
                finally:
                    await session.close()
                results[f"{provider}/{name}/{concurrency}"] = {
                    "samples": samples,
                    "wall_s": time.monotonic() - start,
                }
                await asyncio.sleep(2)
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("baseline", "candidate", "profiles"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    async with asyncio.timeout(240):
        result = await globals()[args.mode](args.directory)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result.update(
        mode=args.mode,
        elapsed_s=time.monotonic() - started,
        cpu_s=usage.ru_utime + usage.ru_stime,
        max_rss_kib=usage.ru_maxrss,
        child_max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        cgroup_peak_bytes=int(Path("/sys/fs/cgroup/memory.peak").read_text()),
        scratch_bytes=sum(
            p.stat().st_size for p in args.directory.iterdir() if p.is_file()
        ),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
