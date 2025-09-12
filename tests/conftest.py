import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Disable external update checks during tests to avoid network flakiness
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "0")
    data_dir = tmp_path / "data"
    download_dir = tmp_path / "downloads"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DOWNLOAD_DIR", str(download_dir))

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import types, argparse

    stub_parser = types.ModuleType("aniworld.parser")
    stub_parser.parse_arguments = lambda: argparse.Namespace()
    stub_parser.arguments = argparse.Namespace()
    sys.modules["aniworld.parser"] = stub_parser

    from sqlmodel import SQLModel

    SQLModel.metadata.clear()

    modules = [
        "app.config",
        "app.models",
        "app.api.torznab",
        "app.api.qbittorrent",
        "app.main",
    ]
    for m in modules:
        if m in sys.modules:
            del sys.modules[m]

    from app.main import app
    from app.models import create_db_and_tables
    # Patch scheduler calls where they are used (torrents module)
    import app.api.qbittorrent.torrents as qb_torrents

    create_db_and_tables()

    monkeypatch.setattr(qb_torrents, "schedule_download", lambda req: "job-1")
    monkeypatch.setattr(qb_torrents, "cancel_job", lambda job_id: None)

    with TestClient(app) as c:
        yield c
