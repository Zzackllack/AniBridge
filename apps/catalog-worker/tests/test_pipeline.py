"""Pipeline independence, bounded admission, publication independence and recovery."""

import asyncio
import sqlite3
import sys

import pytest
from catalog_worker.aniworld import Link, Page
from catalog_worker.collector import Collector, Plan, Ready
from catalog_worker.config import LIMITS, Config
from catalog_worker.pipeline import Pipeline
from catalog_worker.state import State

NOW = 1800000000


def collectors(tmp_path, **limits):
    defaults = {key: bounds[0] for key, bounds in LIMITS.items()}
    defaults.update(limits)
    origins = {
        p: "https://fixture.invalid" for p in ("aniworld.to", "s.to", "megakino")
    }
    config = Config(
        origins,
        {"tv": "off"},
        tmp_path,
        tmp_path / "output",
        tmp_path / "key",
        "fixture",
        "127.0.0.1",
        1,
        defaults,
    )
    result = []
    for provider in origins:
        state = State(tmp_path / f"{provider}.sqlite", provider)
        prefix = {
            "aniworld.to": "/anime/stream/",
            "s.to": "/serie/",
            "megakino": "/films/",
        }[provider]
        paths = [
            prefix + name if provider != "megakino" else prefix + f"{n + 1}-{name}.html"
            for n, name in enumerate(("first", "second"))
        ]
        state.listing(Page(tuple(Link(p, "Example") for p in paths), (), 0, None), NOW)
        # These tests isolate writer/circuit behavior; recent-route integration
        # is exercised by test_signal_collector with the default enabled.
        with state.db:
            state.db.execute(
                "UPDATE signal_meta SET next_due=?,origin=?",
                (NOW + 86400, "https://fixture.invalid"),
            )
        result.append(Collector(config, state, clock=lambda: NOW))
    return result


def test_slow_provider_and_writer_error_do_not_stop_others(tmp_path):
    group = collectors(tmp_path)
    events = []

    async def scenario():
        stalled = asyncio.Event()

        async def collect(collector, plan):
            if collector.state.provider == "aniworld.to":
                await stalled.wait()
            await asyncio.sleep(0.005)
            return Ready(plan, Page((), (), 0, "Observed"))

        for c in group:
            c.collect = lambda plan, c=c: collect(c, plan)
        original = group[1].apply
        failures = 0

        def failing(ready):
            nonlocal failures
            if failures == 0:
                failures += 1
                raise sqlite3.OperationalError("injected writer failure")
            original(ready)

        group[1].apply = failing
        pipeline = Pipeline(group, lambda *args: events.append(args))
        task = asyncio.create_task(pipeline.run())
        try:
            async with asyncio.timeout(2):
                while (
                    not group[2]
                    .state.db.execute("SELECT 1 FROM work WHERE checked_at IS NOT NULL")
                    .fetchone()
                ):
                    await asyncio.sleep(0.01)
            assert not task.done()
            assert failures == 1
            assert (
                group[0]
                .state.db.execute(
                    "SELECT count(*) FROM work WHERE checked_at IS NOT NULL"
                )
                .fetchone()[0]
                == 0
            )
            assert pipeline.max_fetching <= 4
            assert pipeline.max_ready <= 32
            assert all(n <= 2 for n in pipeline.busy.values())
            stalled.set()
            async with asyncio.timeout(2):
                while (
                    not group[0]
                    .state.db.execute("SELECT 1 FROM work WHERE checked_at IS NOT NULL")
                    .fetchone()
                ):
                    await asyncio.sleep(0.01)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert not any(pipeline.busy.values())
        # Failed transactions leave the durable lease, not an admitted checkpoint.
        row = (
            group[1]
            .state.db.execute("SELECT * FROM work WHERE checked_at IS NULL")
            .fetchone()
        )
        assert row and row["lease_until"] == NOW + 120
        assert group[1].state.claim(NOW + 121)

    try:
        asyncio.run(scenario())
    finally:
        for c in group:
            c.state.close()


@pytest.mark.parametrize("queue_size", [1, 32])
def test_acknowledgement_and_queue_bound_stop_reservation(tmp_path, queue_size):
    group = collectors(tmp_path, ready_queue_size=queue_size)

    async def scenario():
        parsed = []

        async def collect(c, plan):
            parsed.append((c.state.provider, plan.path))
            return Ready(plan, Page((), (), 0, "Observed"))

        for c in group:
            c.collect = lambda plan, c=c: collect(c, plan)
        pipeline = Pipeline(group, lambda *args: None)
        # No writer yet: all admitted producers must await acknowledgement.
        tasks = [
            asyncio.create_task(pipeline.producer(c, True))
            for c in group
            for _ in range(2)
        ]
        await asyncio.sleep(0.05)
        assert len(parsed) == min(4, queue_size)
        assert pipeline.ready.qsize() <= queue_size
        assert all(not t.done() for t in tasks)
        writer = asyncio.create_task(pipeline.writer())
        try:
            async with asyncio.timeout(2):
                await asyncio.gather(*tasks)
            await pipeline.ready.join()
        finally:
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)

    try:
        asyncio.run(scenario())
    finally:
        for c in group:
            c.state.close()


def test_providers_can_keep_collecting_with_an_independent_publisher(tmp_path):
    group = collectors(tmp_path)

    async def scenario():
        pipeline = Pipeline(group, lambda *args: None)
        for collector in group:
            collector.collect = lambda plan: asyncio.sleep(
                0, result=Ready(plan, Page((), (), 0, "Observed"))
            )
        writer = asyncio.create_task(pipeline.writer())
        try:
            assert all(await asyncio.gather(*(pipeline.page(c) for c in group)))
        finally:
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)

    try:
        asyncio.run(scenario())
    finally:
        for c in group:
            c.state.close()


def test_page_slice_deadline_and_redirect_request_budget(tmp_path):
    group = collectors(tmp_path, title_deadline_s=0.02, title_requests_per_slice=2)
    c = group[0]
    calls = []

    async def start(**kwargs):
        calls.append(True)

    c.before_request = start

    async def redirects(origin, path, **kwargs):
        for _ in range(3):
            await kwargs["before_request"]()

    c.fetcher = redirects
    plan = Plan(NOW, False, c.state.claim(NOW), "/anime/stream/first")
    try:
        with pytest.raises(ValueError, match="title_request_limit"):
            asyncio.run(c.collect(plan))
        assert len(calls) == 2
        c.fetcher = lambda *args, **kwargs: asyncio.sleep(1)
        with pytest.raises(TimeoutError):
            asyncio.run(c.collect(plan))
    finally:
        for c in group:
            c.state.close()


@pytest.mark.skipif(sys.platform != "linux", reason="supervised parser enforcement")
def test_concurrent_real_parser_children(tmp_path):
    from catalog_worker.transport import Fetch

    group = collectors(tmp_path)

    async def fetcher(origin, path, **kwargs):
        await kwargs["before_request"]()
        if path.startswith("/films/"):
            body = '<h1>Example</h1><iframe src="https://host.invalid/private" data-language-label="Deutsch"></iframe>'
        else:
            body = f'<h1>Example</h1><a href="{path}/staffel-1">Season</a>'
        await asyncio.sleep(0.02)
        return Fetch("ok", ("<html><body>" + body + "</body></html>").encode())

    for c in group:
        c.fetcher = fetcher
    pipeline = Pipeline(group, lambda *args: None)
    try:
        asyncio.run(pipeline.run(once=True))
        for c in group:
            assert (
                c.state.db.execute(
                    "SELECT count(*) FROM work WHERE checked_at IS NOT NULL"
                ).fetchone()[0]
                == 1
            )
        assert pipeline.max_fetching == 3
    finally:
        for c in group:
            c.state.close()
