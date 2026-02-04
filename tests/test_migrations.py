from __future__ import annotations

from pathlib import Path
from sqlalchemy import inspect


HEAD_REVISION = "20260204_0003"


def _load_db(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    download_dir = tmp_path / "downloads"
    data_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DOWNLOAD_DIR", str(download_dir))
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "0")

    import sys

    for mod in ("app.config", "app.db", "app.db.models"):
        if mod in sys.modules:
            del sys.modules[mod]

    import app.db.models as models

    return models


def _get_version(models) -> str | None:
    with models.engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
    versions = [row[0] for row in rows if row and row[0]]
    return versions[0] if versions else None


def test_apply_migrations_fresh_db(tmp_path, monkeypatch):
    models = _load_db(tmp_path, monkeypatch)

    models.apply_migrations()

    inspector = inspect(models.engine)
    tables = set(inspector.get_table_names())
    assert "job" in tables
    assert "episodeavailability" in tables
    assert "clienttask" in tables
    assert "strmurlmapping" in tables
    assert "alembic_version" in tables
    assert _get_version(models) == HEAD_REVISION


def test_apply_migrations_legacy_db(tmp_path, monkeypatch):
    models = _load_db(tmp_path, monkeypatch)

    models.create_db_and_tables()
    models.apply_migrations()

    inspector = inspect(models.engine)
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    assert _get_version(models) == HEAD_REVISION


def test_apply_migrations_empty_version_table(tmp_path, monkeypatch):
    models = _load_db(tmp_path, monkeypatch)

    with models.engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )

    models.apply_migrations()

    inspector = inspect(models.engine)
    tables = set(inspector.get_table_names())
    assert "job" in tables
    assert "strmurlmapping" in tables
    assert "alembic_version" in tables
    assert _get_version(models) == HEAD_REVISION
