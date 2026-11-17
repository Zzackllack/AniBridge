"""The pinned PR119 layout is rejection data, never an upgrade source."""

import json
import sqlite3
from pathlib import Path

import pytest
from test_migrations import _load_db


@pytest.mark.parametrize("versioned", [True, False])
def test_pinned_pr119_schema_is_rejected_without_changes(
    tmp_path, monkeypatch, versioned
):
    models = _load_db(tmp_path, monkeypatch)
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[2] / "fixtures/private_schemas/pr119.json"
        ).read_text()
    )
    assert fixture["source_ref"] == "61351bbcbfc1295ab597f8385f063598c25f3191"
    assert fixture["revision"] == "20260625_0008"
    filename = tmp_path / "data/anibridge_jobs.db"
    with sqlite3.connect(filename) as db:
        db.executescript(";\n".join(fixture["statements"]) + ";")
        db.execute("INSERT INTO alembic_version VALUES(?)", (fixture["revision"],))
        db.execute(
            "INSERT INTO job(id,status,progress,downloaded_bytes,created_at,updated_at) VALUES ('retained','completed',100,123,'2026-01-01','2026-01-01')"
        )
        if not versioned:
            db.execute("DROP TABLE alembic_version")
    original = filename.read_bytes()
    with pytest.raises(RuntimeError, match="Unsupported private database"):
        models.apply_migrations()
    assert filename.read_bytes() == original
    assert not filename.with_name(filename.name + ".pre-catalog-v3.backup").exists()
    assert not list(filename.parent.glob(".catalog-backup-*"))
    models.dispose_engine()
