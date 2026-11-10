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


def test_child_environment_drops_parent_secrets_and_keeps_runtime_config(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("ANIWORLD_INSTALL_FOLDER", "/tmp/aniworld")
    monkeypatch.setenv("ANIBRIDGE_GITHUB_TOKEN", "do-not-forward")
    monkeypatch.setenv("CATALOG_API_TOKEN", "do-not-forward")
    env = supervisor.child_environment(ANIBRIDGE_SUPERVISOR_PID="123")
    assert env["PATH"] == "/usr/bin"
    assert env["ANIWORLD_INSTALL_FOLDER"] == "/tmp/aniworld"
    assert env["ANIBRIDGE_SUPERVISOR_PID"] == "123"
    assert "ANIBRIDGE_GITHUB_TOKEN" not in env
    assert "CATALOG_API_TOKEN" not in env


def test_diagnostics_only_write_the_supervisor_temp_report(tmp_path, monkeypatch):
    from catalog_core import diagnostics

    monkeypatch.setattr(diagnostics, "_records", [])
    arbitrary = tmp_path / "arbitrary.json"
    monkeypatch.setenv("ANIBRIDGE_CHILD_REPORT", str(arbitrary))
    with diagnostics.phase("parse"):
        pass
    assert not arbitrary.exists()

    directory = tmp_path / "catalog-diagnostic-test"
    directory.mkdir()
    report = directory / "report.json"
    monkeypatch.setenv("ANIBRIDGE_CHILD_REPORT", str(report))
    with diagnostics.phase("parse"):
        pass
    assert diagnostics.read_report(report)[-1]["phase"] == "parse"


def test_diagnostics_refuse_a_symlinked_report(tmp_path, monkeypatch):
    from catalog_core import diagnostics

    monkeypatch.setattr(diagnostics, "_records", [])
    directory = tmp_path / "catalog-diagnostic-test"
    directory.mkdir()
    target = tmp_path / "outside.json"
    report = directory / "report.json"
    report.symlink_to(target)
    monkeypatch.setenv("ANIBRIDGE_CHILD_REPORT", str(report))
    with diagnostics.phase("parse"):
        pass
    assert not target.exists()


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


def test_incomplete_phase_never_masks_signal_as_success():
    record = {"phase": "validation", "reason": "ok", "duration_s": 0, "complete": False}
    failure = supervisor.ChildFailure(-9, [record])
    assert failure.reason == "child_signal" and failure.exit_code == -9
