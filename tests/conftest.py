import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
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
        "app.torznab",
        "app.qbittorrent",
        "app.main",
    ]
    for m in modules:
        if m in sys.modules:
            del sys.modules[m]

    from app.main import app
    from app.models import create_db_and_tables
    import app.qbittorrent as qb

    create_db_and_tables()

    monkeypatch.setattr(qb, "schedule_download", lambda req: "job-1")
    monkeypatch.setattr(qb, "cancel_job", lambda job_id: None)

    with TestClient(app) as c:
        yield c
