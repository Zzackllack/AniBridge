"""Short canonical-only enrichment on disposable copies, never provider crawling.

Pause the normal collector before running this tool so its requests cannot add
an unmeasured second budget. Metadata serving can remain running. Use 2 CPU/2 GiB.
This measures a finite backlog, not an upstream quota or sustainable capacity.
"""

import argparse
import asyncio
import json
import shutil
import time
from collections import Counter
from pathlib import Path

from catalog_core.providers.transport import Session
from mapping_replay import metrics, resources

from catalog_worker import canonical_cache
from catalog_worker.canonical import Enricher
from catalog_worker.state import State

PROVIDERS = ("aniworld.to", "s.to")


def eligible(state: State, enricher: Enricher, now: int) -> dict:
    kinds = []
    if enricher.sources.get("tv", "skyhook") != "off":
        kinds.append("series")
    if enricher.sources.get("movie", "off") == "tmdb":
        kinds.append("movie")
    if not kinds:
        return {"parents": 0, "oldest_due_age_s": None, "unknown_eligibility_age": 0}
    row = state.db.execute(
        "SELECT count(*),min(CASE WHEN m.next_due>0 AND m.next_due<=? THEN m.next_due END),"
        "coalesce(sum(m.next_due<=0 OR m.next_due>?),0) FROM mapping_input m JOIN title t USING(title_id) "
        "WHERE (m.next_due<=? OR (m.failures=0 AND (m.matcher IS NULL OR m.matcher<>? OR "
        "(EXISTS(SELECT 1 FROM canonical_cache c WHERE c.title_id=m.title_id) AND "
        "NOT EXISTS(SELECT 1 FROM matching_replay r WHERE r.title_id=m.title_id AND r.matcher=?))))) "
        f"AND t.media_type IN ({','.join('?' for _ in kinds)})",
        (now, now, now, enricher.matcher, canonical_cache.EPISODE_MATCHER, *kinds),
    ).fetchone()
    return {
        "parents": row[0],
        "oldest_due_age_s": max(0, now - row[1]) if row[1] else None,
        # A changed matcher or next_due=0 has no trustworthy eligibility clock.
        # Last attempted time is not an eligibility age.
        "unknown_eligibility_age": row[2],
    }


def preservation(state: State, baseline: Path) -> dict:
    state.db.execute(
        "ATTACH DATABASE ? AS baseline", (baseline.as_uri() + "?mode=ro&immutable=1",)
    )
    queries = {
        "release_identity_or_first_seen_changed": "SELECT count(*) FROM baseline.release b LEFT JOIN main.release r USING(release_id) WHERE r.release_id IS NULL OR r.first_seen_at<>b.first_seen_at",
        "old_maps_removed_or_repointed": "SELECT count(*) FROM baseline.canonical_episode b LEFT JOIN main.canonical_episode c USING(mapping_id,entity_id) WHERE c.mapping_id IS NULL OR c.season<>b.season OR c.episode<>b.episode",
        "work_retry_or_lease_changed": "SELECT count(*) FROM baseline.work b JOIN main.work w USING(path) WHERE b.failures<>w.failures OR b.due<>w.due OR b.lease_until<>w.lease_until",
    }
    return {
        name: state.db.execute(query).fetchone()[0] for name, query in queries.items()
    }


class Probe:
    def __init__(self):
        self.sessions = {}
        self.starts = []
        self.records = []
        self.rate = 30
        self.stop = None
        self.errors = 0

    async def admit(self):
        # Smooth actual HTTP starts, including redirects. A rolling window alone
        # permits a burst; that is unhelpful when measuring a public dependency.
        while True:
            now = time.monotonic()
            recent = [at for at in self.starts if at > now - 60]
            wait = max(0, self.starts[-1] + 60 / self.rate - now) if self.starts else 0
            if len(recent) >= self.rate:
                wait = max(wait, recent[-self.rate] + 60 - now + 0.01)
            if not wait:
                self.starts.append(now)
                return
            await asyncio.sleep(wait)

    async def fetch(self, origin, path, **options):
        if self.stop:
            raise asyncio.CancelledError
        admission = options.pop("before_request")
        admission_wait = 0

        async def before_request():
            nonlocal admission_wait
            started = time.monotonic()
            await admission()
            await self.admit()
            admission_wait += time.monotonic() - started

        if origin not in self.sessions:
            self.sessions[origin] = Session(origin, 1)
        response = await self.sessions[origin].fetch(
            origin, path, before_request=before_request, **options
        )
        self.records.append(
            {
                "outcome": response.outcome,
                "status": response.status,
                "requests": response.requests,
                "network_s": max(0, response.duration_s - admission_wait),
                "admission_wait_s": admission_wait,
                "decoded_bytes": len(response.body),
                "retry_after_s": response.retry_after,
            }
        )
        self.errors = self.errors + 1 if response.outcome != "ok" else 0
        if (
            response.outcome in {"rate_limited", "challenge_or_block"}
            or self.errors >= 3
        ):
            self.stop = response.outcome
        return response

    async def close(self):
        for session in self.sessions.values():
            await session.close()


async def step(args, probe: Probe, rate: int) -> dict:
    work = args.candidate / str(rate)
    work.mkdir()
    states = []
    for provider in PROVIDERS:
        filename = provider + ".sqlite"
        shutil.copyfile(args.baseline / filename, work / filename)
        states.append(State(work / filename, provider))
    enricher = Enricher(
        args.sources, states=states, fetcher=probe.fetch, requests_per_minute=rate
    )
    probe.rate = rate
    offset = len(probe.records)
    start_offset = len(probe.starts)
    before = {
        s.provider: {
            "ledger": metrics(s.db),
            "eligible": eligible(s, enricher, int(time.time())),
        }
        for s in states
    }
    usage = resources()
    start = time.monotonic()
    examined = {provider: Counter() for provider in PROVIDERS}
    try:
        async with asyncio.timeout(args.seconds):
            while not probe.stop:
                for state in states:
                    await enricher.tick(state, int(time.time()))
                    examined[state.provider][enricher.last_work] += 1
                    if probe.stop:
                        break
                await asyncio.sleep(0.05)
    except TimeoutError:
        pass
    elapsed = time.monotonic() - start
    records = probe.records[offset:]
    durations = sorted(row["network_s"] for row in records)
    after = {
        s.provider: {
            "ledger": metrics(s.db),
            "eligible": eligible(s, enricher, int(time.time())),
            "preservation": preservation(
                s, (args.baseline / (s.provider + ".sqlite")).resolve()
            ),
            "examined": dict(examined[s.provider]),
        }
        for s in states
    }
    useful = sum(
        after[p]["ledger"]["usable_mapped"] - before[p]["ledger"]["usable_mapped"]
        for p in PROVIDERS
    )
    requests = len(probe.starts) - start_offset
    result = {
        "configured_requests_per_minute": rate,
        "duration_s": round(elapsed, 4),
        "requests": requests,
        "completed_requests": sum(row["requests"] for row in records),
        "max_actual_starts_in_rolling_60s": max(
            (
                sum(at - 60 < prior <= at for prior in probe.starts)
                for at in probe.starts[start_offset:]
            ),
            default=0,
        ),
        "useful_new_maps": useful,
        "requests_per_useful_new_map": requests / useful if useful else None,
        "outcomes": dict(Counter(row["outcome"] for row in records)),
        "statuses": dict(Counter(str(row["status"]) for row in records)),
        "network_p50_s": durations[len(durations) // 2] if durations else None,
        "network_p95_s": durations[min(len(durations) - 1, int(len(durations) * 0.95))]
        if durations
        else None,
        "decoded_bytes": sum(row["decoded_bytes"] for row in records),
        "stop_reason": probe.stop or "bounded_window",
        "before": before,
        "after": after,
        "resources_before": usage,
        "resources_after": resources(),
    }
    await enricher.close()
    for state in states:
        state.close()
    return result


async def run(args):
    if (
        args.baseline.resolve() == args.candidate.resolve()
        or not (args.candidate / "COPY_ONLY").is_file()
    ):
        raise ValueError("explicit disposable candidate required")
    if not (args.baseline / "COPY_ONLY").is_file():
        raise ValueError("consistent disposable baseline required")
    if args.output.exists() or not args.output.resolve().is_relative_to(
        args.candidate.resolve()
    ):
        raise ValueError("new output must be inside disposable candidate")
    probe = Probe()
    results = []
    try:
        for rate in args.rates:
            result = await step(args, probe, rate)
            results.append(result)
            args.output.write_text(
                json.dumps(
                    {
                        "evidence": "live canonical metadata on consistent disposable copies; no provider fetches or publication",
                        "steps": results,
                    },
                    indent=2,
                )
                + "\n"
            )
            if probe.stop:
                break
            # Stop escalation on a marked latency increase as well as errors.
            first = results[0]["network_p95_s"]
            if (
                len(results) > 1
                and first
                and result["network_p95_s"] > max(2, first * 2)
            ):
                result["stop_reason"] = "latency_increase"
                args.output.write_text(json.dumps({"steps": results}, indent=2) + "\n")
                break
    finally:
        await probe.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "config", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--seconds", type=int, choices=range(60, 181), default=130)
    parser.add_argument(
        "--rates", type=int, nargs="+", choices=range(4, 121), default=[30, 60, 90]
    )
    args = parser.parse_args()
    args.sources = json.loads(args.config.read_text())["canonical_sources"]
    asyncio.run(run(args))
