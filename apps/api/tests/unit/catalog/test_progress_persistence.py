"""A progress-checkpoint outage must not terminate a healthy local child."""

import asyncio
import json
import sqlite3

import pytest

from app.catalog.executor import SubprocessExecutor


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
