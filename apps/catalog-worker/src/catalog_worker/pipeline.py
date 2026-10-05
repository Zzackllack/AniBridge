"""Fixed fetch workers and an acknowledged queue feeding one SQLite writer.

SQLite stays on the owning event loop. A producer cannot reserve another page
until its prior checkpoint settles, so queue pressure never grows a task list.
Publication fences only its provider while other providers continue collecting.
"""

import asyncio
import sqlite3
import time
from contextlib import asynccontextmanager

from .collector import Collector, Ready


class Pipeline:
    def __init__(self, collectors: list[Collector], report) -> None:
        self.collectors, self.report = collectors, report
        limits = collectors[0].config.limits
        self.fetch_slots = asyncio.Semaphore(limits["fetch_concurrency"])
        self.ready = asyncio.Queue(maxsize=limits["ready_queue_size"])
        # Reserve before parsing too: waiting putters must not hide retained
        # Page objects beyond the configured queue/future bound.
        self.ready_slots = asyncio.Semaphore(limits["ready_queue_size"])
        self.condition = asyncio.Condition()
        self.paused: set[str] = set()
        self.busy = {c.state.provider: 0 for c in collectors}
        self.max_fetching = self.fetching = self.max_ready = 0

    @asynccontextmanager
    async def publication(self, provider: str):
        """Avoid clearing dirty state for observations absent from the export."""
        try:
            async with self.condition:
                self.paused.add(provider)
                await self.condition.wait_for(lambda: self.busy[provider] == 0)
            yield
        finally:
            async with self.condition:
                self.paused.discard(provider)
                self.condition.notify_all()

    async def writer(self) -> None:
        while True:
            collector, ready, settled = await self.ready.get()
            try:
                collector.apply(ready)
            except (ValueError, OSError, sqlite3.Error) as exc:
                if not settled.done():
                    settled.set_exception(exc)
            else:
                if not settled.done():
                    settled.set_result(None)
            finally:
                self.ready.task_done()
            # A large atomic checkpoint must finish before another writer runs.
            # Yield between checkpoints so already-ready providers are not starved.
            await asyncio.sleep(0)

    async def page(self, collector: Collector) -> bool:
        provider = collector.state.provider
        started = time.monotonic()
        async with self.fetch_slots, self.ready_slots:
            async with self.condition:
                if provider in self.paused:
                    return False
                # One listing traversal has one in-flight page. The other slot
                # can service durable detail work while that request is slow.
                listing_allowed = not getattr(collector, "listing_busy", False)
                plan = collector.prepare(
                    listing_allowed, not getattr(collector, "signal_busy", False)
                )
                if plan is None:
                    return False
                self.busy[provider] += 1
                if plan.listing:
                    collector.listing_busy = True
                if plan.signal:
                    collector.signal_busy = True
            try:
                self.fetching += 1
                self.max_fetching = max(self.max_fetching, self.fetching)
                try:
                    ready = await collector.collect(plan)
                except TimeoutError:
                    ready = Ready(plan, None, "transport_failure")
                except (ValueError, UnicodeError):
                    ready = Ready(plan, None, "unexpected_structure")
                finally:
                    self.fetching -= 1
                settled = asyncio.get_running_loop().create_future()
                await self.ready.put((collector, ready, settled))
                self.max_ready = max(self.max_ready, self.ready.qsize())
                await settled
                return True
            finally:
                async with self.condition:
                    self.busy[provider] -= 1
                    if plan.listing:
                        collector.listing_busy = False
                    if plan.signal:
                        collector.signal_busy = False
                    self.condition.notify_all()
                self.report(provider, "collect", "settled", time.monotonic() - started)

    async def producer(self, collector: Collector, once: bool) -> None:
        while True:
            try:
                progressed = await self.page(collector)
            except (ValueError, OSError, sqlite3.Error) as exc:
                self.report(collector.state.provider, "collect", type(exc).__name__, 0)
                progressed = False
            if once:
                return
            await asyncio.sleep(0 if progressed else 1)

    async def run(self, once: bool = False) -> None:
        writer = asyncio.create_task(self.writer())
        producers = [
            asyncio.create_task(self.producer(c, once))
            for c in self.collectors
            for _ in range(1 if once else c.config.limits["provider_concurrency"])
        ]
        try:
            await asyncio.gather(*producers)
            await self.ready.join()
        finally:
            for task in producers:
                task.cancel()
            await asyncio.gather(*producers, return_exceptions=True)
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)
