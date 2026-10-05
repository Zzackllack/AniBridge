"""One durable half-open page probes a cooled-down provider circuit."""

import asyncio
import sys

import pytest

from catalog_worker.aniworld import Page
from catalog_worker.collector import Ready
from catalog_worker.state import State
from catalog_worker.transport import Fetch
from test_pipeline import NOW, collectors


def test_half_open_reservation_persists_and_success_closes_circuit(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    try:
        c.state.failure(None, "challenge_or_block", NOW)
        now = c.state.meta()["blocked_until"]
        c.clock = lambda: now
        first = c.prepare(listing_allowed=False, signal_allowed=False)
        assert first is not None
        assert c.prepare(listing_allowed=False, signal_allowed=False) is None
        filename = tmp_path / "aniworld.to.sqlite"
        c.state.close()
        c.state = State(filename, "aniworld.to")
        assert c.prepare(listing_allowed=False, signal_allowed=False) is None
        c.apply(Ready(first, Page((), (), 0, "Observed")))
        assert c.state.meta()["blocked_until"] == 0
        assert c.state.meta()["block_count"] == 0
        assert c.prepare(listing_allowed=False, signal_allowed=False) is not None
    finally:
        for collector in group:
            collector.state.close()


def test_failed_half_open_does_not_erase_a_new_block(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    try:
        c.state.failure(None, "challenge_or_block", NOW)
        now = c.state.meta()["blocked_until"]
        c.clock = lambda: now
        first = c.prepare(listing_allowed=False, signal_allowed=False)
        c.apply(Ready(first, None, "challenge_or_block"))
        assert c.state.meta()["blocked_until"] == now + 43200
        assert c.state.meta()["block_count"] == 2
        assert c.prepare(listing_allowed=False, signal_allowed=False) is None
    finally:
        for collector in group:
            collector.state.close()


def test_positive_probe_cannot_clear_a_later_block(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    try:
        c.state.failure(None, "challenge_or_block", NOW)
        now = c.state.meta()["blocked_until"]
        c.clock = lambda: now
        first = c.prepare(listing_allowed=False, signal_allowed=False)
        c.state.failure(None, "challenge_or_block", now + 1)
        deadline = c.state.meta()["blocked_until"]
        c.apply(Ready(first, Page((), (), 0, "Observed")))
        assert c.state.meta()["blocked_until"] == deadline
        assert c.state.meta()["block_count"] == 2
        assert c.state.meta()["state"] == "blocked"
    finally:
        for collector in group:
            collector.state.close()


@pytest.mark.skipif(sys.platform != "linux", reason="supervised parser enforcement")
def test_probe_runs_rate_limited_transport_and_real_parser(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    starts = []

    async def fetcher(origin, path, **kwargs):
        await kwargs["before_request"]()
        starts.append(path)
        assert c.prepare(listing_allowed=False, signal_allowed=False) is None
        return Fetch(
            "ok",
            f'<html><body><h1>Example</h1><a href="{path}/staffel-1">Season</a></body></html>'.encode(),
        )

    c.fetcher = fetcher
    try:
        c.state.failure(None, "challenge_or_block", NOW)
        now = c.state.meta()["blocked_until"]
        c.clock = lambda: now
        plan = c.prepare(listing_allowed=False, signal_allowed=False)
        ready = asyncio.run(c.collect(plan))
        c.apply(ready)
        assert ready.outcome == "ok"
        assert starts == [plan.path]
        assert (
            c.state.db.execute("SELECT count(*) FROM request_start").fetchone()[0] == 1
        )
        assert c.state.meta()["blocked_until"] == 0
        assert c.prepare(listing_allowed=False, signal_allowed=False) is not None
    finally:
        for collector in group:
            collector.state.close()
