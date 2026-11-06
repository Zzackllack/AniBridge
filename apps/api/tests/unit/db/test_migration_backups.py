"""Backup durability boundaries use disposable released databases only."""

import os
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from test_migrations import HEAD_REVISION, _get_version, _load_db


@pytest.mark.skipif(os.name != "posix", reason="SIGKILL requires POSIX")
@pytest.mark.parametrize(
    "stage", ["verified_copy", "file_sync", "linked", "directory_sync"]
)
def test_backup_kill_preserves_original_and_restart(stage, tmp_path, monkeypatch):
    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260204_0003")
    with models.engine.begin() as db:
        db.exec_driver_sql(
            "INSERT INTO job(id,status,progress,downloaded_bytes,created_at,updated_at) VALUES ('retained','completed',100,123,'2026-01-01','2026-01-01')"
        )
    models.dispose_engine()
    filename = tmp_path / "data/anibridge_jobs.db"
    original = filename.read_bytes()
    script = """
import os, signal
from app.db import preflight
from app.db.models import apply_migrations
stage = os.environ['BACKUP_KILL_STAGE']
def kill():
    os.kill(os.getpid(), signal.SIGKILL)
def wrap(function):
    def invoke(*args, **kwargs):
        result = function(*args, **kwargs)
        kill()
        return result
    return invoke
if stage == 'verified_copy':
    preflight.verify_backup = wrap(preflight.verify_backup)
elif stage == 'file_sync':
    preflight.os.fsync = wrap(preflight.os.fsync)
elif stage == 'linked':
    preflight.os.link = wrap(preflight.os.link)
elif stage == 'directory_sync':
    preflight.fsync_directory = wrap(preflight.fsync_directory)
apply_migrations()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        env={**os.environ, "BACKUP_KILL_STAGE": stage},
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == -signal.SIGKILL, result.stderr.decode()
    assert filename.read_bytes() == original
    backup = filename.with_name(filename.name + ".pre-catalog-v3.backup")
    before = backup.read_bytes() if backup.exists() else None
    models.apply_migrations()
    assert _get_version(models) == HEAD_REVISION
    if before is not None:
        assert backup.read_bytes() == before
    with sqlite3.connect(backup) as db:
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert db.execute(
            "SELECT status,downloaded_bytes FROM job WHERE id='retained'"
        ).fetchone() == ("completed", 123)
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "20260204_0003"
        )
    models.dispose_engine()


@pytest.mark.parametrize("stage", ["file_sync", "directory_sync"])
def test_failed_backup_sync_stops_upgrade_and_retry_preserves_backup(
    stage, tmp_path, monkeypatch
):
    from app.db import preflight

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260204_0003")
    models.dispose_engine()
    filename = tmp_path / "data/anibridge_jobs.db"
    original = filename.read_bytes()

    def failure(*args):
        raise OSError("injected backup sync failure")

    with monkeypatch.context() as patch:
        if stage == "file_sync":
            patch.setattr(preflight.os, "fsync", failure)
        else:
            patch.setattr(preflight, "fsync_directory", failure)
        with pytest.raises(OSError, match="injected backup sync failure"):
            models.apply_migrations()
    assert filename.read_bytes() == original
    assert not list(filename.parent.glob(".catalog-backup-*"))
    backup = filename.with_name(filename.name + ".pre-catalog-v3.backup")
    retained = backup.read_bytes() if backup.exists() else None
    models.apply_migrations()
    if retained is not None:
        assert backup.read_bytes() == retained
    assert _get_version(models) == HEAD_REVISION
    models.dispose_engine()
