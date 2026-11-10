"""Sanitized diagnostics for supervised child failures."""

import asyncio
import json
import sys

import pytest

from app.catalog.executor import SubprocessExecutor


pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Linux child enforcement"
)


def _diagnostic(path):
    return json.loads(path.read_text())


def test_deadline_writes_bounded_failure_diagnostic_and_log(tmp_path, caplog):
    executor = SubprocessExecutor({}, (), tmp_path)
    diagnostic = tmp_path / "failure.json"
    job_id = "a" * 32

    with pytest.raises(TimeoutError):
        asyncio.run(
            executor._run(
                "timeit",
                ["-n", "1", "-r", "1", "import time; time.sleep(60)"],
                deadline=0.1,
                diagnostic=diagnostic,
                job_id=job_id,
            )
        )

    record = _diagnostic(diagnostic)
    assert record == {
        "outcome": "extraction_error",
        "failed_stage": "timeit",
        "error_class": "timeout",
        "child_exit_code": -9,
        "reason": "phase_deadline",
    }
    assert "stage=timeit" in caplog.text
    assert "error_class=timeout" in caplog.text
    assert "reason=phase_deadline" in caplog.text
    assert "job_id=" + job_id in caplog.text


def test_child_exit_diagnostic_and_log_never_contain_stderr(tmp_path, caplog):
    executor = SubprocessExecutor({}, (), tmp_path)
    diagnostic = tmp_path / "failure.json"
    private_detail = "private_release https://secret.invalid/token /srv/private"
    job_id = "b" * 32

    code = asyncio.run(
        executor._run(
            "timeit",
            [
                "-n",
                "1",
                "-r",
                "1",
                f"import sys; sys.stderr.write({private_detail!r}); raise SystemExit(7)",
            ],
            diagnostic=diagnostic,
            job_id=job_id,
        )
    )

    assert code != 0
    contents = diagnostic.read_text()
    record = json.loads(contents)
    assert record == {
        "outcome": "extraction_error",
        "failed_stage": "timeit",
        "error_class": "process_exit",
        "child_exit_code": code,
        "reason": "child_process_failed",
    }
    assert all(value not in contents for value in private_detail.split())
    assert "stage=timeit" in caplog.text
    assert "error_class=process_exit" in caplog.text
    assert "reason=child_process_failed" in caplog.text
    assert f"exit_code={code}" in caplog.text
    assert "job_id=" + job_id in caplog.text
    assert all(value not in caplog.text for value in private_detail.split())


@pytest.mark.parametrize("channel", ["stdout", "stderr"])
def test_output_overflow_writes_bounded_failure_diagnostic(tmp_path, channel):
    executor = SubprocessExecutor({}, (), tmp_path)
    diagnostic = tmp_path / "failure.json"

    code = asyncio.run(
        executor._run(
            "timeit",
            [
                "-n",
                "1",
                "-r",
                "1",
                f"import sys; sys.{channel}.write('x' * 70000)",
            ],
            deadline=5,
            diagnostic=diagnostic,
        )
    )

    assert code != 0
    record = _diagnostic(diagnostic)
    assert {
        key: value for key, value in record.items() if key != "child_exit_code"
    } == {
        "outcome": "extraction_error",
        "failed_stage": "timeit",
        "error_class": "output_limit",
        "reason": "diagnostic_limit",
    }
    assert record["child_exit_code"] in (-9, 0)
