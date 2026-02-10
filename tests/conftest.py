import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def stub_aniworld_parser(monkeypatch):
    """Provide a temporary stub for ``aniworld.parser`` in ``sys.modules``."""
    import argparse
    import types

    stub_parser = types.ModuleType("aniworld.parser")
    stub_parser.parse_arguments = lambda: argparse.Namespace()
    stub_parser.arguments = argparse.Namespace()
    monkeypatch.setitem(sys.modules, "aniworld.parser", stub_parser)
    return stub_parser


@pytest.fixture(autouse=True)
def _fast_test_env(monkeypatch):
    """Set up a fast test environment by disabling slow operations.

    This fixture ensures tests run quickly by disabling external checks,
    network operations, and automatic title index refreshes.
    """
    monkeypatch.setenv("ANIBRIDGE_TEST_MODE", "1")
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "0")
    monkeypatch.setenv("ANIWORLD_TITLES_REFRESH_HOURS", "0")
    monkeypatch.setenv("STO_TITLES_REFRESH_HOURS", "0")
    monkeypatch.setenv("ANIWORLD_ALPHABET_URL", "")
    monkeypatch.setenv("STO_ALPHABET_URL", "")
    monkeypatch.setenv("ANIWORLD_ALPHABET_HTML", "")
    monkeypatch.setenv("STO_ALPHABET_HTML", "")
    monkeypatch.setenv("PUBLIC_IP_CHECK_ENABLED", "0")
    monkeypatch.setenv("PROXY_ENABLED", "0")
    monkeypatch.setenv("MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN", "0")
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "0")
    monkeypatch.setenv("STRM_PROXY_AUTH", "none")
    monkeypatch.setenv("STRM_PUBLIC_BASE_URL", "http://testserver")
    monkeypatch.setenv("STRM_PROXY_UPSTREAM_ALLOWLIST", "upstream")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    Provide a configured TestClient connected to a freshly initialized, isolated test application.

    This fixture prepares an isolated environment for FastAPI tests by setting DATA_DIR and DOWNLOAD_DIR to temporary locations, ensuring the repository root is on sys.path, installing a minimal stub for `aniworld.parser`, clearing SQLModel metadata, removing relevant app modules from sys.modules to force clean imports, initializing the test database schema, and patching qbittorrent scheduler calls to deterministic no-op/test values before yielding the TestClient.

    Parameters:
        tmp_path (pathlib.Path): Temporary directory provided by pytest for creating per-test filesystem paths.
        monkeypatch (pytest.MonkeyPatch): Pytest fixture used to set environment variables and patch attributes.

    Returns:
        TestClient: A TestClient instance for the FastAPI app backed by the prepared test environment and database.
    """
    data_dir = tmp_path / "data"
    download_dir = tmp_path / "downloads"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DOWNLOAD_DIR", str(download_dir))

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import types
    import argparse
    from typing import Any, cast

    stub_parser = types.ModuleType("aniworld.parser")
    stub_parser_any = cast(Any, stub_parser)
    stub_parser_any.parse_arguments = lambda: argparse.Namespace()
    stub_parser_any.arguments = argparse.Namespace()
    monkeypatch.setitem(sys.modules, "aniworld.parser", stub_parser)

    from sqlmodel import SQLModel

    SQLModel.metadata.clear()

    # Ensure a clean import state including qbittorrent submodules, otherwise
    # FastAPI routes may attach to a stale router instance and return 404.
    modules = [
        "app.config",
        "app.db",
        "app.db.models",
        "app.core.strm_proxy",
        "app.core.strm_proxy.auth",
        "app.core.strm_proxy.cache",
        "app.core.strm_proxy.hls",
        "app.core.strm_proxy.resolver",
        "app.core.strm_proxy.types",
        "app.core.strm_proxy.urls",
        "app.api.torznab",
        "app.api.torznab.api",
        "app.api.torznab.utils",
        "app.api.qbittorrent",
        "app.api.qbittorrent.auth",
        "app.api.qbittorrent.app_meta",
        "app.api.qbittorrent.categories",
        "app.api.qbittorrent.sync",
        "app.api.qbittorrent.torrents",
        "app.api.qbittorrent.transfer",
        "app.api.strm",
        "app.main",
    ]
    for m in modules:
        if m in sys.modules:
            del sys.modules[m]

    from app.main import app
    from app.db import create_db_and_tables

    # Patch scheduler calls where they are used (torrents module)
    import app.api.qbittorrent.torrents as qb_torrents

    create_db_and_tables()

    monkeypatch.setattr(qb_torrents, "schedule_download", lambda req: "job-1")
    monkeypatch.setattr(qb_torrents, "cancel_job", lambda job_id: None)

    with TestClient(app) as c:
        yield c
