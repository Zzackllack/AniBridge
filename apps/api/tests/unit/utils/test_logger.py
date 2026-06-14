import importlib
import os


def test_importing_logger_does_not_choose_log_path(monkeypatch):
    monkeypatch.delenv("ANIBRIDGE_LOG_PATH", raising=False)

    logger_module = importlib.import_module("app.utils.logger")
    importlib.reload(logger_module)

    assert "ANIBRIDGE_LOG_PATH" not in os.environ
