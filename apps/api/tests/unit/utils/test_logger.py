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
    # Positive control: a real traceback was rendered, so the negative assertions
    # above cannot pass because the handler silently dropped the exception.
    assert "Traceback (most recent call last)" in output
    assert "AssertionError" in output


def test_every_secret_environment_value_is_fully_redacted_in_system_diagnostics(
    monkeypatch,
):
    from app.infrastructure import system_info

    secrets = {
        "CATALOG_API_TOKEN": "sensitive-catalog-secret-XY",
        "STRM_PROXY_SECRET": "sensitive-proxy-secret-AB",
        "MANAGEMENT_API_TOKEN": "sensitive-management-token-Z9",
        "QBIT_PASSWORD": "sensitive-qbit-password-12",
        "QBIT_SESSION_SECRET": "sensitive-qbit-session-secret-34",
        "INDEXER_API_KEY": "sensitive-indexer-key-56",
        "UNUSUAL_APIKEY": "sensitive-unknown-key-78",
        "SHORT_PWD": "abc",
        "SIGNING_KEY": "sensitive-signing-key-90",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ORDINARY_SETTING", "visible-positive-control")
    messages = []
    monkeypatch.setattr(system_info.logger, "debug", messages.append)
    monkeypatch.setattr(system_info, "_default_route_ip", lambda: None)
    system_info.log_full_system_report()
    report = next(
        message for message in messages if message.startswith("SysInfo: env=")
    )
    for name, value in secrets.items():
        assert f"'{name}': '[redacted]'" in report
        assert value not in report
        # The old partial mask leaked the first three and last two characters.
        if len(value) > 6:
            assert value[:3] + "****" + value[-2:] not in report
    # Positive control: redaction stays scoped to secret-shaped keys instead of
    # silently dropping the whole environment report.
    assert "'ORDINARY_SETTING': 'visible-positive-control'" in report


def test_secret_mask_is_safe_for_short_and_non_string_values():
    from app.infrastructure.system_info import _mask_env_value

    assert _mask_env_value("QBIT_PASSWORD", "abc") == "[redacted]"
    assert _mask_env_value("QBIT_PASSWORD", b"synthetic-bytes") == "[redacted]"
    assert _mask_env_value("QBIT_PASSWORD", 12345) == "[redacted]"
    assert _mask_env_value("QBIT_PASSWORD", "") == ""
    assert _mask_env_value("ORDINARY_SETTING", 12345) == 12345
    assert _mask_env_value("ORDINARY_SETTING", "visible") == "visible"
