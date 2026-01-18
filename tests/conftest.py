import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


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


@pytest.fixture
def client(tmp_path, monkeypatch):
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
    sys.modules["aniworld.parser"] = stub_parser

    from sqlmodel import SQLModel

    SQLModel.metadata.clear()

    # Ensure a clean import state including qbittorrent submodules, otherwise
    # FastAPI routes may attach to a stale router instance and return 404.
    modules = [
        "app.config",
        "app.db",
        "app.db.models",
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
