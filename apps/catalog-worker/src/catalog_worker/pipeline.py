"""Fixed fetch workers and an acknowledged queue feeding one SQLite writer.

SQLite stays on the owning event loop. A producer cannot reserve another page
until its prior checkpoint settles, so queue pressure never grows a task list.
Publication uses a separate WAL snapshot; neither provider is fenced.
"""

import asyncio
import sqlite3
import time
from dataclasses import replace

from .collector import Collector, Ready
from .fetch_slot import FetchSlot


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
        self.busy = {c.state.provider: 0 for c in collectors}
        self.max_fetching = self.fetching = self.max_ready = 0

    def fetching_changed(self, delta: int) -> None:
        self.fetching += delta
        self.max_fetching = max(self.max_fetching, self.fetching)

    async def writer(self) -> None:
        while True:
            collector, ready, settled = await self.ready.get()
            try:
                collector.apply(ready)
                owner = getattr(self.report, "__self__", None)
                if owner is not None and hasattr(owner, "page"):
                    owner.page(collector.state.provider, ready, collector.state)
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
        delay = collector.admission_delay()
        if delay:
            owner = getattr(self.report, "__self__", None)
            now = int(collector.clock())
            if delay >= 10 and now >= getattr(collector, "admission_report_after", 0):
                collector.admission_report_after = now + delay
                if owner is not None and hasattr(owner, "admission"):
                    owner.admission(provider, delay)
            return False
        slot = FetchSlot(self.fetch_slots, self.fetching_changed)
        # Reserve retained-result capacity first. Otherwise a producer waiting
        # for a small ready queue can hold the slot a paused redirect must regain.
        async with self.ready_slots, slot:
            async with self.condition:
                # One listing traversal has one in-flight page. The other slot
                # can service durable detail work while that request is slow.
                listing_allowed = not getattr(collector, "listing_busy", False)
                plan = collector.prepare(
                    listing_allowed, not getattr(collector, "signal_busy", False)
                )
                if plan is None:
                    return False
                plan = replace(plan, fetch_slot=slot)
                self.busy[provider] += 1
                if plan.listing:
                    collector.listing_busy = True
                if plan.signal:
                    collector.signal_busy = True
            try:
                try:
                    ready = await collector.collect(plan)
                except TimeoutError:
                    ready = Ready(
                        plan, None, "local_deadline", error_class="TimeoutError"
                    )
                except ValueError, UnicodeError:
                    ready = Ready(plan, None, "unexpected_structure")
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
                self.report(
                    provider,
                    "collect",
                    ready.outcome if "ready" in locals() else "cancelled",
                    time.monotonic() - started,
                )

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
            for _ in range(
                1
                if once
                else c.config.provider_limits(c.state.provider)["provider_concurrency"]
            )
        ]
        producers_done = asyncio.gather(*producers)
        try:
            # The writer is long-lived. If it dies unexpectedly, producers may
            # wait forever for acknowledgements it can no longer deliver.
            done, _ = await asyncio.wait(
                (writer, producers_done), return_when=asyncio.FIRST_COMPLETED
            )
            if writer in done:
                await writer
                raise RuntimeError("catalog writer stopped unexpectedly")
            await producers_done
            await self.ready.join()
        finally:
            for task in producers:
                task.cancel()
            await asyncio.gather(*producers, return_exceptions=True)
            producers_done.cancel()
            await asyncio.gather(producers_done, return_exceptions=True)
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)
