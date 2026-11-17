"""Publication retries have one fixed wall budget and a bounded backoff."""

import asyncio

from catalog_core.supervisor import ChildDeadline, ChildFailure

from catalog_worker.publication_retry import (
    BACKOFF_CAP_S,
    ESCALATION_FAILURES,
    PUBLISH_DEADLINE_S,
    PublicationGate,
    publish_loop,
    publish_once,
)


class RecordingEvents:
    def __init__(self) -> None:
        self.children = []
        self.emitted = []
        self.publications = []

    def child(self, provider, records, exit_code=None, reason=None) -> None:
        self.children.append((provider, records, exit_code, reason))

    def emit(self, provider, stage, outcome, duration) -> None:
        self.emitted.append((provider, stage, outcome))

    def publication(self, provider, telemetry) -> None:
        self.publications.append((provider, telemetry))


async def until(predicate) -> None:
    """Yield turns of the event loop; no wall-clock sleep decides outcomes."""
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0)


def test_failures_back_off_from_the_publish_interval_and_cap():
    gate = PublicationGate(300)
    assert gate.ready(1_000)
    assert gate.failed(1_000) == 300
    assert not gate.ready(1_299) and gate.ready(1_300)
    assert gate.failed(1_300) == 600
    for _ in range(10):
        gate.failed(1_300)
    assert gate.next_attempt == 1_300 + BACKOFF_CAP_S


def test_deadline_stays_one_fixed_named_wall_budget():
    gate = PublicationGate(600)
    assert gate.deadline() == PUBLISH_DEADLINE_S == 420
    gate.failed(0, "deadline")
    gate.failed(0, "child_failure")
    assert gate.deadline() == PUBLISH_DEADLINE_S
    gate.succeeded()
    assert gate.deadline() == PUBLISH_DEADLINE_S
    # No success/timeout path may grow the child's resource budget.
    assert not hasattr(gate, "_deadline")


def test_telemetry_reports_consecutive_failures_and_operator_escalation():
    gate = PublicationGate(300)
    assert gate.telemetry(0) == {
        "outcome": "ok",
        "consecutive_failures": 0,
        "retry_in_s": 0,
        "backoff_s": 0,
        "deadline_s": PUBLISH_DEADLINE_S,
        "operator_escalation": False,
    }
    for _ in range(ESCALATION_FAILURES):
        gate.failed(1_000, "child_failure")
    report = gate.telemetry(1_000)
    assert report["consecutive_failures"] == ESCALATION_FAILURES
    assert report["retry_in_s"] == BACKOFF_CAP_S
    assert report["backoff_s"] == BACKOFF_CAP_S
    assert report["deadline_s"] == PUBLISH_DEADLINE_S
    assert report["operator_escalation"] is True
    gate.succeeded()
    assert gate.telemetry(1_000)["operator_escalation"] is False


def test_restart_forgets_in_memory_backoff_but_not_the_durable_cadence():
    """Honest restart contract: only publication_meta survives, not the gate."""
    gate = PublicationGate(300)
    gate.failed(10_000, "child_failure")
    assert not gate.ready(10_000)
    restarted = PublicationGate(300)
    assert restarted.ready(10_000)
    assert restarted.failures == 0 and restarted.backoff_s == 0
    assert restarted.deadline() == PUBLISH_DEADLINE_S


def test_publish_loop_backs_off_and_never_awaits_the_export_inline():
    async def scenario():
        events = RecordingEvents()
        gate = PublicationGate(300)
        wakeup = asyncio.Event()
        slot = asyncio.Lock()
        clock = [1_000]
        calls = []
        started = asyncio.Event()
        release = asyncio.Event()

        async def run_child(deadline):
            calls.append(deadline)
            started.set()
            await release.wait()
            raise ChildFailure(1, [])

        task = asyncio.create_task(
            publish_loop(
                events,
                "aniworld.to",
                run_child,
                gate,
                wakeup,
                slot,
                clock=lambda: clock[0],
            )
        )
        try:
            wakeup.set()
            await until(lambda: started.is_set())
            # A maintain-style coroutine still progresses while the child waits;
            # the export lives in its own task, not in the enrichment loop.
            ticks = 0
            for _ in range(5):
                ticks += 1
                await asyncio.sleep(0)
            assert ticks == 5 and len(calls) == 1
            release.set()
            await until(lambda: gate.failures == 1)
            assert len(calls) == 1 and gate.next_attempt == 1_300
            # A wakeup during backoff must not fork another 512-MB child.
            wakeup.set()
            await until(lambda: not wakeup.is_set())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert len(calls) == 1
            clock[0] = 1_300
            wakeup.set()
            await until(lambda: len(calls) == 2)
            assert calls == [PUBLISH_DEADLINE_S, PUBLISH_DEADLINE_S]
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # One bounded retry record per attempt, never a raw child body.
        assert [p[1]["consecutive_failures"] for p in events.publications] == [1, 2]

    asyncio.run(scenario())


def test_failing_provider_does_not_stop_the_other_provider_loop():
    async def scenario():
        first = RecordingEvents()
        second = RecordingEvents()
        first_gate, second_gate = PublicationGate(300), PublicationGate(300)
        first_wakeup, second_wakeup = asyncio.Event(), asyncio.Event()
        second_calls = []

        async def failing(deadline):
            raise ChildFailure(1, [])

        async def healthy(deadline):
            second_calls.append(deadline)
            return []

        tasks = [
            asyncio.create_task(
                publish_loop(
                    first,
                    "aniworld.to",
                    failing,
                    first_gate,
                    first_wakeup,
                    asyncio.Lock(),
                    clock=lambda: 1_000,
                )
            ),
            asyncio.create_task(
                publish_loop(
                    second,
                    "s.to",
                    healthy,
                    second_gate,
                    second_wakeup,
                    asyncio.Lock(),
                    clock=lambda: 1_000,
                )
            ),
        ]
        try:
            first_wakeup.set()
            second_wakeup.set()
            await until(lambda: first_gate.failures == 1 and len(second_calls) == 1)
            assert second.children == [("s.to", [], 0, None)]
            assert second_gate.failures == 0
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(scenario())


def test_successful_export_discards_a_stale_inflight_wakeup():
    async def scenario():
        events = RecordingEvents()
        gate = PublicationGate(300)
        wakeup = asyncio.Event()
        calls = []

        async def run_child(deadline):
            calls.append(deadline)
            # The maintain loop keeps signalling eligibility during the export.
            wakeup.set()
            return []

        task = asyncio.create_task(
            publish_loop(
                events,
                "aniworld.to",
                run_child,
                gate,
                wakeup,
                asyncio.Lock(),
                clock=lambda: 1_000,
            )
        )
        try:
            wakeup.set()
            await until(lambda: len(calls) == 1)
            for _ in range(5):
                await asyncio.sleep(0)
            assert len(calls) == 1 and gate.failures == 0
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert events.children == [("aniworld.to", [], 0, None)]
        assert events.publications[-1][1]["outcome"] == "ok"

    asyncio.run(scenario())


def test_publish_once_reports_deadline_without_raising():
    async def scenario():
        events = RecordingEvents()
        gate = PublicationGate(300)

        async def timed_out(deadline):
            assert deadline == PUBLISH_DEADLINE_S
            raise ChildDeadline([])

        await publish_once(events, "aniworld.to", timed_out, gate, clock=lambda: 0)
        assert gate.failures == 1 and gate.last_outcome == "deadline"
        assert events.children == [("aniworld.to", [], None, "deadline")]
        assert events.publications == [
            (
                "aniworld.to",
                {
                    "outcome": "deadline",
                    "consecutive_failures": 1,
                    "retry_in_s": 300,
                    "backoff_s": 300,
                    "deadline_s": PUBLISH_DEADLINE_S,
                    "operator_escalation": False,
                },
            )
        ]

    asyncio.run(scenario())
