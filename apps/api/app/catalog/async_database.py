"""Wait for bounded SQLite work without blocking HTTP or abandoning a writer."""

import asyncio
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


async def call(function: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """Keep transaction ownership until its thread exits, including cancellation."""
    work = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        # SQLite has a finite busy timeout. Let the pending transaction settle
        # before shutdown recovery touches the same durable ownership records.
        try:
            await asyncio.shield(work)
        except Exception:  # noqa: BLE001 -- cancellation takes precedence over a failed transaction
            pass
        raise
