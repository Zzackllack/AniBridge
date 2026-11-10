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


def test_exception_logging_does_not_disclose_env_only_catalog_credentials(tmp_path):
    program = """
from loguru import logger
from app.utils.logger import config
config()
def fail():
    secret = 'sensitive-local-value-for-regression'
    assert secret is None, 'expected-error-marker'
try:
    fail()
except AssertionError:
    logger.exception('handled-error-marker')
"""
    env = {
        **os.environ,
        "CATALOG_MODE": "query",
        "CATALOG_API_TOKEN": "synthetic-env-catalog-token",
        "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
    }
    script = tmp_path / "exception_logging.py"
    script.write_text(program)
    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    output = result.stdout + result.stderr
    assert "handled-error-marker" in output and "expected-error-marker" in output
    assert "sensitive-local-value-for-regression" not in output
    assert "synthetic-env-catalog-token" not in output


def test_catalog_token_has_no_visible_fragment_in_system_diagnostics(monkeypatch):
    from app.infrastructure import system_info

    messages = []
    monkeypatch.setenv("CATALOG_API_TOKEN", "sensitive-catalog-secret-XY")
    monkeypatch.setenv("STRM_PROXY_SECRET", "sensitive-proxy-secret-AB")
    monkeypatch.setattr(system_info.logger, "debug", messages.append)
    monkeypatch.setattr(system_info, "_default_route_ip", lambda: None)
    system_info.log_full_system_report()
    report = next(
        message for message in messages if message.startswith("SysInfo: env=")
    )
    assert "'CATALOG_API_TOKEN': '[redacted]'" in report
    assert "sensitive-catalog-secret-XY" not in report
    assert "sen****XY" not in report
    assert "'STRM_PROXY_SECRET': '[redacted]'" in report
    assert "sensitive-proxy-secret-AB" not in report
