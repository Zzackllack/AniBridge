"""Finite synthetic scheduler trace; no network, no production state input."""

import argparse
import asyncio
import json
import tempfile
from collections import Counter
from pathlib import Path

from catalog_core.providers.transport import Fetch
from catalog_worker.aniworld import Link
from catalog_worker.canonical import Enricher
from catalog_worker.state import State


async def trace(root: Path) -> dict:
    start = 1800000000
    clock = [start]
    states, classes, requests, examined = [], {}, [], Counter()
    for provider in ("aniworld.to", "s.to"):
        state = State(root / (provider + ".sqlite"), provider)
        states.append(state)
        for kind in ("first", "changed", "retry", "old"):
            for index in range(12):
                path = "/anime/stream/" if provider == "aniworld.to" else "/serie/"
                tid = state.discover(
                    Link(path + kind + str(index), kind + str(index)), start
                )
                checked = None if kind == "first" else start - 86400
                due = 0 if kind in ("first", "changed") else start - 7200
                with state.db:
                    state.db.execute(
                        "UPDATE title SET year=2020 WHERE title_id=?", (tid,)
                    )
                    state.db.execute(
                        "INSERT INTO mapping_input(title_id,checked_at,next_due,failures,matcher) VALUES(?,?,?,?,?)",
                        (tid, checked, due, int(kind == "retry"), "old-matcher"),
                    )
                classes[(provider, tid)] = kind

    async def fetch(origin: str, path: str, **kwargs) -> Fetch:
        requests.append(clock[0])
        return Fetch("ok", body=b"[]", requests=1, status=200)

    def enricher() -> Enricher:
        return Enricher(
            {"tv": "skyhook", "movie": "off"},
            fetcher=fetch,
            clock=lambda: clock[0],
            states=states,
        )

    worker = enricher()
    deferred = 0
    for tick in range(180):
        clock[0] = start + tick
        if tick == 90:
            await worker.close()
            worker = enricher()  # Durable admission survives process restart.
        for state in states:
            before = {
                r[0]: r[1]
                for r in state.db.execute(
                    "SELECT title_id,checked_at FROM mapping_input"
                )
            }
            await worker.tick(state, clock[0])
            deferred += worker.last_work == "admission_deferred"
            for tid, checked in state.db.execute(
                "SELECT title_id,checked_at FROM mapping_input"
            ):
                if checked != before[tid]:
                    examined[(state.provider, classes[(state.provider, tid)])] += 1
    await worker.close()
    rolling = max(sum(now - 60 < at <= now for at in requests) for now in requests)
    result = {
        "evidence": "synthetic controlled clock, empty canonical responses",
        "elapsed_simulated_s": 180,
        "requests": len(requests),
        "max_requests_in_rolling_60s": rolling,
        "admission_deferrals": deferred,
        "restart_at_s": 90,
        "examined": {},
        "remaining_due_age_s": {},
    }
    assert rolling <= 30
    for state in states:
        result["examined"][state.provider] = {
            kind: examined[(state.provider, kind)]
            for kind in ("first", "changed", "retry", "old")
        }
        assert all(result["examined"][state.provider].values())
        oldest = state.db.execute(
            "SELECT min(next_due) FROM mapping_input WHERE next_due>0 AND next_due<=?",
            (clock[0],),
        ).fetchone()[0]
        result["remaining_due_age_s"][state.provider] = (
            clock[0] - oldest if oldest else None
        )
        state.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mapping-trace-") as scratch:
        args.output.write_text(
            json.dumps(asyncio.run(trace(Path(scratch))), indent=2) + "\n"
        )
