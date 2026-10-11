import os
import subprocess
import threading
import time

import pytest

from catalog_core import supervisor


def test_cancellation_kills_and_reaps_child(monkeypatch):
    original = subprocess.Popen
    launched = []

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(supervisor.subprocess, "Popen", launch)
    cancel = threading.Event()
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(InterruptedError):
            supervisor.run_child(
                "timeit",
                ["-n", "1", "-r", "1", "import time; time.sleep(60)"],
                60,
                cancel=cancel,
            )
    finally:
        timer.join()
    assert time.monotonic() - started < 2
    assert launched[0].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.kill(launched[0].pid, 0)


def test_typed_report_rejects_untrusted_text_and_is_bounded(tmp_path):
    import json
    from catalog_core.diagnostics import read_report, reason

    path = tmp_path / "report"
    record = {
        "phase": "parse",
        "reason": "video_section_missing",
        "duration_s": 0.1,
        "complete": True,
    }
    path.write_text(json.dumps([record]))
    assert read_report(path) == [record]
    path.write_text(
        json.dumps([{**record, "reason": "https://private.invalid?token=secret"}])
    )
    assert read_report(path) == []
    path.write_text("x" * 4097)
    assert read_report(path) == []
    assert reason(ValueError("secret-query")) == "contract_rejected"


def test_async_child_exit_and_deadline_keep_safe_information():
    import asyncio

    async def run():
        with pytest.raises(supervisor.ChildFailure) as failure:
            await supervisor.run_child_async(
                "timeit", ["-n", "1", "-r", "1", 'raise ValueError("private-term")'], 3
            )
        assert failure.value.exit_code != 0
        assert failure.value.reason == "child_exit"
        assert "private-term" not in str(failure.value)
        with pytest.raises(supervisor.ChildDeadline) as timeout:
            await supervisor.run_child_async(
                "timeit", ["-n", "1", "-r", "1", "import time; time.sleep(10)"], 0.1
            )
        assert timeout.value.reason == "deadline"

    asyncio.run(run())
