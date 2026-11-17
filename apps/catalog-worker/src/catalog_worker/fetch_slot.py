"""A cancellable fetch lease that can release capacity during local admission."""

import asyncio
from collections.abc import Callable
from typing import Self


class FetchSlot:
    def __init__(
        self, semaphore: asyncio.Semaphore, changed: Callable[[int], None]
    ) -> None:
        self.semaphore, self.changed = semaphore, changed
        self.held = False

    async def acquire(self) -> None:
        await self.semaphore.acquire()
        self.held = True
        self.changed(1)

    def release(self) -> None:
        if self.held:
            self.held = False
            self.changed(-1)
            self.semaphore.release()

    async def pause(self, seconds: float) -> None:
        # Cancellation leaves the lease released. __aexit__ must not release a
        # second time or wait for another provider merely to finish cancellation.
        self.release()
        await asyncio.sleep(seconds)
        await self.acquire()

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, *exc) -> None:
        self.release()
