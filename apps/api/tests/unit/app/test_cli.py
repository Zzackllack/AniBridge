"""Reload selection and access logging must reach the actual Uvicorn boundary."""

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("reload_value", ["true", "1", "false", "0"])
def test_server_honors_explicit_reload_without_enabling_query_access_logs(
    monkeypatch, reload_value
):
    import uvicorn
    import app.cli as cli

    calls = []
    monkeypatch.setenv("ANIBRIDGE_RELOAD", reload_value)
    monkeypatch.setattr(cli, "CATALOG_CONFIG", SimpleNamespace(mode="query"))
    monkeypatch.setattr(
        uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    application = object()
    cli.run_server(application)
    ((args, options),) = calls
    enabled = reload_value in {"true", "1"}
    assert options["reload"] is enabled
    assert args == (("app.main:app",) if enabled else (application,))
    assert options["access_log"] is False
