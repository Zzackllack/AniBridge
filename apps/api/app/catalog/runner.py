"""Durable job scheduling and cancellation, independent of HTTP request lifetimes."""

import asyncio
import json
import sqlite3
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from .async_database import call as database_call
from .child_budget import CONSUMER_CHILDREN, ChildBudget, Lease
from .jobs import Jobs


@dataclass(frozen=True)
class Outcome:
    code: str
    output: Path | None = None
    evidence: dict | None = None


# An executor owns/reaps its subprocess before cancellation is allowed to finish.
Executor = Callable[[dict, Callable[[dict], None]], Awaitable[Outcome]]


class Runner:
    def __init__(
        self,
        jobs: Jobs,
        execute: Executor,
        concurrency: int = 2,
        clock=time.time,
        children: ChildBudget = CONSUMER_CHILDREN,
    ) -> None:
        if not 1 <= concurrency <= 2:
            raise ValueError("private profile permits at most two downloads")
        self.jobs, self.execute, self.concurrency, self.clock = (
            jobs,
            execute,
            concurrency,
            clock,
        )
        self.children = children
        self.running: dict[str, tuple[dict, asyncio.Task, Lease]] = {}
        self.stopping = False

    async def tick(self) -> None:
        now = int(self.clock())
        for job_id, (claim, task, lease) in list(self.running.items()):
            current = await database_call(self.jobs.get, job_id)
            if current["generation"] != claim["generation"] or current[
                "status"
            ] not in ("resolving", "downloading"):
                task.cancel()
            if task.done():
                lease.close()
                try:
                    result = task.result()
                except asyncio.CancelledError:
                    result = None
                except Exception:  # noqa: BLE001 -- isolate one executor's failure from other jobs
                    # One executor failure must not stop unrelated durable jobs.
                    result = Outcome("extraction_error")
                if result:
                    await database_call(
                        self.jobs.finish,
                        job_id,
                        claim["generation"],
                        result.code,
                        now,
                        result.output,
                        result.evidence,
                    )
                await database_call(self.jobs.settle_cancel, job_id, now)
                del self.running[job_id]
            else:
                await database_call(
                    self.jobs.heartbeat, job_id, claim["generation"], now
                )
        while not self.stopping and len(self.running) < self.concurrency:
            lease = self.children.try_acquire("download")
            if lease is None:
                break
            try:
                claim = await database_call(self.jobs.claim, now)
            except BaseException:
                lease.close()
                raise
            if claim is None:
                lease.close()
                break
            try:
                payload = json.loads(claim["payload"])
                payload.update(job_id=claim["job_id"], generation=claim["generation"])

                def progress(update: dict, claim=claim) -> None:
                    self.jobs.heartbeat(
                        claim["job_id"], claim["generation"], int(self.clock()), update
                    )

                task = asyncio.create_task(self.execute(payload, progress))
            except Exception:  # noqa: BLE001 -- release admission if executor construction fails
                lease.close()
                await database_call(
                    self.jobs.finish,
                    claim["job_id"],
                    claim["generation"],
                    "extraction_error",
                    now,
                )
                continue
            except BaseException:
                lease.close()
                raise
            self.running[claim["job_id"]] = (claim, task, lease)

    async def run(self) -> None:
        needs_recovery = True
        try:
            while not self.stopping:
                try:
                    if needs_recovery:
                        await database_call(
                            self.jobs.recover, int(self.clock()), startup=True
                        )
                        needs_recovery = False
                    await self.tick()
                except sqlite3.Error, OSError:
                    # Ownership and completed executor results stay in memory;
                    # retry their durable transactions when storage recovers.
                    # Startup recovery must succeed before claiming any job.
                    await asyncio.sleep(1)
                    continue
                await asyncio.sleep(0.1)
        finally:
            await self.close()

    async def close(self) -> None:
        self.stopping = True
        tasks = [task for _, task, _ in self.running.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
        for _, _, lease in self.running.values():
            lease.close()
        # Actual state is already durable. Shutdown consumes an interrupted
        # attempt, while pause/block/cancel desired states stay untouched.
        await database_call(self.jobs.recover, int(self.clock()), startup=True)
        self.running.clear()
