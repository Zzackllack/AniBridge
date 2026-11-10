"""Catalog progress must be visible without announcing unpublished output."""

import pytest
from loguru import logger

from app.catalog.progress_log import JobProgressLog
from app.utils import terminal as terminal_module


@pytest.fixture
def messages():
    collected = []
    handler = logger.add(collected.append, level="INFO", format="{message}")
    try:
        yield collected
    finally:
        logger.remove(handler)


def _steps(messages):
    return [message for message in messages if "% (" in message]


def test_step_logging_defers_completion_until_publication(messages, monkeypatch):
    monkeypatch.setattr(terminal_module, "PROGRESS_FORCE_BAR", False)
    monkeypatch.setattr(terminal_module, "PROGRESS_STEP_PERCENT", 5)
    log = JobProgressLog()
    job_id = "a" * 32
    log.start(job_id)

    for downloaded in (0, 10, 50, 95, 100):
        log.update(
            job_id,
            {
                "downloaded_bytes": downloaded,
                "total_bytes": 100,
                "speed": 10,
                "eta": 1,
            },
        )

    lines = _steps(messages)
    assert lines and not any("100%" in line for line in lines)
    assert any("50%" in line and job_id in line for line in lines)

    log.finish(job_id, published=True, size=100)
    assert any("100%" in line and job_id in line for line in _steps(messages))

    # A finished job does not keep rendering late or duplicate snapshots.
    before = list(_steps(messages))
    log.update(job_id, {"downloaded_bytes": 100, "total_bytes": 100})
    assert _steps(messages) == before


def test_failed_attempt_never_fills_the_bar(messages, monkeypatch):
    monkeypatch.setattr(terminal_module, "PROGRESS_FORCE_BAR", False)
    monkeypatch.setattr(terminal_module, "PROGRESS_STEP_PERCENT", 5)
    log = JobProgressLog()
    job_id = "b" * 32
    log.start(job_id)
    log.update(job_id, {"downloaded_bytes": 40, "total_bytes": 100})
    log.finish(job_id, published=False, size=100)

    assert not any("100%" in line for line in _steps(messages))


def test_concurrent_jobs_keep_separate_progress(messages, monkeypatch):
    monkeypatch.setattr(terminal_module, "PROGRESS_FORCE_BAR", False)
    monkeypatch.setattr(terminal_module, "PROGRESS_STEP_PERCENT", 5)
    log = JobProgressLog()
    first, second = "c" * 32, "d" * 32
    log.start(first)
    log.start(second)

    log.update(first, {"downloaded_bytes": 50, "total_bytes": 100})
    log.update(second, {"downloaded_bytes": 10, "total_bytes": 100})
    log.finish(first, published=True, size=100)
    log.update(second, {"downloaded_bytes": 60, "total_bytes": 100})

    first_lines = [line for line in _steps(messages) if first in line]
    second_lines = [line for line in _steps(messages) if second in line]
    assert any("100%" in line for line in first_lines)
    assert not any("100%" in line for line in second_lines)
    assert any("60%" in line for line in second_lines)


def test_forced_bar_retains_step_logs_and_updates_estimated_total(
    messages, monkeypatch
):
    import io
    import sys

    monkeypatch.setattr(sys, "__stdout__", io.StringIO())
    monkeypatch.setattr(terminal_module, "PROGRESS_FORCE_BAR", True)
    log = JobProgressLog()
    job_id = "e" * 32
    log.start(job_id)
    # No step-log line exists until an actual byte update, and the forced TTY
    # path is chosen exactly as the legacy scheduler chose it.
    assert log._jobs[job_id]._interactive is True
    log.update(job_id, {"downloaded_bytes": 25, "total_bytes": 100})
    log.update(job_id, {"downloaded_bytes": 50, "total_bytes": 200})
    bar = log._jobs[job_id]._bar
    assert bar.total == 200 and bar.n == 50
    assert any("25%" in line for line in _steps(messages))
    log.finish(job_id)
    assert bar.n == 50  # Failed/cancelled output is never filled to completion.


def test_invalid_progress_fields_do_not_break_the_display(messages, monkeypatch):
    monkeypatch.setattr(terminal_module, "PROGRESS_FORCE_BAR", False)
    monkeypatch.setattr(terminal_module, "PROGRESS_STEP_PERCENT", 5)
    log = JobProgressLog()
    job_id = "f" * 32
    log.start(job_id)
    log.update(
        job_id,
        {
            "downloaded_bytes": True,
            "total_bytes": "unknown",
            "speed": None,
            "eta": object(),
        },
    )
    log.finish(job_id)
    assert not _steps(messages)
