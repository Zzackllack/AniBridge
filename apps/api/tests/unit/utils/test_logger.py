import importlib
import os
import subprocess
import sys
from pathlib import Path


def test_importing_logger_does_not_choose_log_path(monkeypatch):
    monkeypatch.delenv("ANIBRIDGE_LOG_PATH", raising=False)

    logger_module = importlib.import_module("app.utils.logger")
    importlib.reload(logger_module)

    assert "ANIBRIDGE_LOG_PATH" not in os.environ


def test_bootstrap_captures_loguru_output_in_terminal_log(tmp_path):
    env = os.environ.copy()
    env["DATA_DIR"] = str(tmp_path)
    env["DOWNLOAD_DIR"] = str(tmp_path / "downloads")
    env["LOG_LEVEL"] = "INFO"
    env.pop("ANIBRIDGE_LOG_PATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from loguru import logger; "
                "from app.core.bootstrap import init; "
                "init(); "
                "logger.info('terminal-log-regression-marker'); "
                "import sys; sys.stdout.flush()"
            ),
        ],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    log_files = list(tmp_path.glob("terminal-*.log"))
    assert len(log_files) == 1
    assert "terminal-log-regression-marker" in log_files[0].read_text()
    assert "terminal-log-regression-marker" in result.stdout
