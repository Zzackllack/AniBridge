"""Bounded publication retries with one named, non-negotiable wall budget.

A deterministically failing export used to be respawned once per maintain tick
because only a successful child advances ``published_at``. That is an unbounded
fork/exec loop of a large child. Every failure now doubles the wait between
attempts up to a finite cap, while the child itself always receives the same
explicit wall budget.

The budget is deliberately *not* recalibrated from observed durations: the old
"three times the last complete export" headroom was never measured against a
production-size catalog, and a longer deadline does not make memory or I/O
safe. If a full export genuinely needs more than 420 s, raise the named budget
after measuring a real catalog instead of growing it silently per attempt.

The gate is in-memory by design. A restart forgets backoff and consecutive
failures, so a fresh process may retry at the normal publish interval; durable
cadence still comes from ``publication_meta``/``published_at``. Backoff
timestamps use the monotonic clock, so a wall-clock rollback cannot postpone a
retry for hours.
"""

import asyncio
import math
import sqlite3
import time

from catalog_core.supervisor import ChildDeadline, ChildFailure

# One export child always gets this guarded wall budget. Keep it named instead
# of a bare literal at the call site; it is a bound, not a proof that every
# catalog size fits.
PUBLISH_DEADLINE_S = 420
# Retry delay doubles from the configured publish interval up to one hour.
BACKOFF_CAP_S = 3600
# Consecutive failures at which the event log asks an operator to look.
ESCALATION_FAILURES = 5


class PublicationGate:
    """Per-provider in-memory retry clock; restart cadence stays in publication_meta."""

    def __init__(self, interval_s: int) -> None:
        self.interval = max(1, int(interval_s))
        self.failures = 0
        self.next_attempt = 0.0
        self.backoff_s = 0
        self.last_outcome = "ok"

    def deadline(self) -> int:
        """Named guarded child budget; never the unbounded supervisor default."""
        return PUBLISH_DEADLINE_S

    def ready(self, now: float) -> bool:
        return now >= self.next_attempt

    def failed(self, now: float, outcome: str = "failure") -> int:
        """Retry no sooner than one publish interval, then exponential."""
        self.failures += 1
        delay = min(BACKOFF_CAP_S, self.interval * 2 ** min(self.failures - 1, 8))
        self.backoff_s = delay
        self.next_attempt = now + delay
        self.last_outcome = outcome
        return delay

    def succeeded(self) -> None:
        self.failures = 0
        self.backoff_s = 0
        self.last_outcome = "ok"

    def telemetry(self, now: float) -> dict:
        """Bounded retry counters only; no child output, artifact or paths."""
        return {
            "outcome": self.last_outcome,
            "consecutive_failures": self.failures,
            "retry_in_s": max(0, math.ceil(self.next_attempt - now))
            if self.failures
            else 0,
            "backoff_s": self.backoff_s,
            "deadline_s": PUBLISH_DEADLINE_S,
            "operator_escalation": self.failures >= ESCALATION_FAILURES,
        }


async def publish_once(
    events,
    provider: str,
    run_child,
    gate: PublicationGate,
    clock=time.monotonic,
) -> None:
    """Run one guarded export and classify its outcome; never raise to callers."""
    started = time.monotonic()
    try:
        records = await run_child(gate.deadline())
        events.child(provider, records, exit_code=0)
    except ChildDeadline as exc:
        events.child(provider, exc.records, exc.exit_code, exc.reason)
        gate.failed(clock(), "deadline")
    except ChildFailure as exc:
        events.child(provider, exc.records, exc.exit_code, exc.reason)
        gate.failed(clock(), "child_failure")
    except (ValueError, OSError, sqlite3.Error) as exc:
        # No exception text: only the fixed class name reaches the event log.
        events.emit(provider, "publish", type(exc).__name__, time.monotonic() - started)
        gate.failed(clock(), "local_failure")
    else:
        gate.succeeded()
    # The rotated child record above is raw provider evidence. This bounded
    # line carries the retry decision that operators actually need.
    events.publication(provider, gate.telemetry(clock()))


async def publish_loop(
    events,
    provider: str,
    run_child,
    gate: PublicationGate,
    wakeup: asyncio.Event,
    slot: asyncio.Lock,
    clock=time.monotonic,
) -> None:
    """Serve publication wakeups without ever blocking provider enrichment.

    The maintain coroutine only sets an event. The export child (up to its
    guarded deadline) runs here, so enrichment and collection keep ticking.
    """
    while True:
        await wakeup.wait()
        wakeup.clear()
        if not gate.ready(clock()):
            # Backoff elapsed only after a later maintain tick re-signals.
            continue
        async with slot:
            await publish_once(events, provider, run_child, gate, clock)
        # Maintain signals every eligible second while an export is running.
        # Discard those stale sets; if a new generation is still pending the
        # next maintain tick re-signals it within one second.
        wakeup.clear()
