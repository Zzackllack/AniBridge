"""A progress-checkpoint outage must not terminate a healthy local child."""

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.catalog.executor import SubprocessExecutor
from app.catalog import executor as executor_module
from app.catalog.child_status import read_finished_status


def _child(status):
    # Local status counters only: no provider requests or media are involved.
    return (
        "import json,time;from pathlib import Path;"
        "from catalog_core.files import atomic_write;"
        f"p=Path({str(status)!r});"
        "[(atomic_write(p,json.dumps({'phase':'downloading','progress':"
        "{'downloaded_bytes':n,'total_bytes':100}}).encode()),time.sleep(.3)) "
        "for n in [10,20,30,40]]"
    )


def test_busy_progress_checkpoint_is_retried_without_stopping_child(tmp_path):
    status = tmp_path / "status.json"
    diagnostic = tmp_path / "failure.json"
    executor = SubprocessExecutor({}, (), tmp_path)
    attempts, persisted = [], []

    def progress(update):
        attempts.append(update)
        if len(attempts) == 1:
            error = sqlite3.OperationalError("database is locked")
            error.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise error
        persisted.append(update)

    code = asyncio.run(
        executor._run(
            "timeit",
            ["-n", "1", "-r", "1", _child(status)],
            status=status,
            progress=progress,
            deadline=5,
            diagnostic=diagnostic,
        )
    )
    assert code == 0
    assert len(attempts) >= 2 and persisted
    assert persisted[-1]["downloaded_bytes"] > attempts[0]["downloaded_bytes"]
    assert not diagnostic.exists()


def test_missing_status_poll_does_not_stop_active_child(tmp_path, monkeypatch):
    status = tmp_path / "status.json"
    diagnostic = tmp_path / "failure.json"
    executor = SubprocessExecutor({}, (), tmp_path)
    persisted = []
    missed_after = []
    original_open = Path.open

    def open_status(path, *args, **kwargs):
        # Model a missed lookup after the child has already made progress.
        if path == status and persisted and not missed_after:
            missed_after.append(persisted[-1]["downloaded_bytes"])
            raise FileNotFoundError(status.name)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_status)
    code = asyncio.run(
        executor._run(
            "timeit",
            ["-n", "1", "-r", "1", _child(status)],
            status=status,
            progress=persisted.append,
            deadline=5,
            diagnostic=diagnostic,
        )
    )
    assert code == 0
    assert missed_after and persisted[-1]["downloaded_bytes"] > missed_after[0]
    assert not diagnostic.exists()


@pytest.mark.parametrize(
    ("initial_phase", "seconds", "reason"),
    [
        (None, 61, "startup_deadline"),
        ("resolving", 61, "resolution_deadline"),
        ("downloading", 121, "download_inactivity"),
    ],
)
def test_missing_status_does_not_disable_timeout(
    tmp_path, monkeypatch, initial_phase, seconds, reason
):
    status = tmp_path / "status.json"
    diagnostic = tmp_path / "failure.json"
    if initial_phase is not None:
        status.write_text(json.dumps({"phase": initial_phase}))
    started = time.monotonic()
    missing = False
    original_open = Path.open

    def open_status(path, *args, **kwargs):
        nonlocal missing
        if path != status:
            return original_open(path, *args, **kwargs)
        if missing:
            raise FileNotFoundError(status.name)
        missing = True
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_status)
    monkeypatch.setattr(
        executor_module,
        "time",
        SimpleNamespace(monotonic=lambda: started + (seconds if missing else 0)),
    )
    with pytest.raises(TimeoutError):
        asyncio.run(
            SubprocessExecutor({}, (), tmp_path)._run(
                "timeit",
                ["-n", "1", "-r", "1", "import time;time.sleep(5)"],
                status=status,
                diagnostic=diagnostic,
            )
        )
    assert json.loads(diagnostic.read_text())["reason"] == reason


def test_nonbusy_progress_failure_retains_operation_and_class_only(tmp_path):
    status = tmp_path / "status.json"
    diagnostic = tmp_path / "failure.json"
    executor = SubprocessExecutor({}, (), tmp_path)
    private_message = "private-label https://secret.invalid/player-token"

    def progress(update):
        error = sqlite3.OperationalError(private_message)
        error.sqlite_errorcode = sqlite3.SQLITE_IOERR
        raise error

    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(
            executor._run(
                "timeit",
                ["-n", "1", "-r", "1", _child(status)],
                status=status,
                progress=progress,
                deadline=5,
                diagnostic=diagnostic,
            )
        )
    record = json.loads(diagnostic.read_text())
    assert record["reason"] == "progress_write_failed"
    assert record["error_class"] == "OperationalError"
    assert private_message not in diagnostic.read_text()


def test_invalid_status_is_reported_as_a_parent_read_failure(tmp_path):
    status = tmp_path / "status.json"
    status.write_text("not json")
    diagnostic = tmp_path / "failure.json"
    executor = SubprocessExecutor({}, (), tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(
            executor._run(
                "timeit",
                ["-n", "1", "-r", "1", "import time;time.sleep(2)"],
                status=status,
                deadline=5,
                diagnostic=diagnostic,
            )
        )
    assert json.loads(diagnostic.read_text())["reason"] == "status_read_failed"


def test_finished_status_waits_for_terminal_receipt(tmp_path, monkeypatch):
    status = tmp_path / "status.json"
    terminal = {"phase": "finished", "outcome": "ok"}
    status.write_text(json.dumps(terminal))
    original_open = Path.open
    missed = False

    def open_status(path, *args, **kwargs):
        nonlocal missed
        if path == status and not missed:
            missed = True
            raise FileNotFoundError(status.name)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_status)
    assert asyncio.run(read_finished_status(status)) == terminal
    assert missed

    # A valid but stale status cannot stand in for a terminal receipt.
    status.write_text(json.dumps({"phase": "downloading", "outcome": "ok"}))
    assert asyncio.run(read_finished_status(status)) is None
