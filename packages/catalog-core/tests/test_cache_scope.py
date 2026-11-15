"""Private cache migrations and revision floors stay crash- and churn-safe."""

import sqlite3

import pytest

from catalog_core import query_client
from catalog_core.query_client import Cache


def legacy_scoped_cache(path):
    """A cache file from before per-provider scope existed."""
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE entry(key TEXT PRIMARY KEY,body BLOB NOT NULL,fetched REAL NOT NULL,used REAL NOT NULL)"
    )
    db.execute("INSERT INTO entry VALUES('old',?,0,0)", (b"{}",))
    db.commit()
    db.close()


def test_pre_scope_upgrade_serializes_with_another_process(tmp_path, monkeypatch):
    path = tmp_path / "cache.sqlite"
    legacy_scoped_cache(path)
    other = sqlite3.connect(path, timeout=0.05)
    attempts = []
    real_connect = sqlite3.connect

    class Cursor:
        """Trigger the other process once the stale schema read is complete."""

        def __init__(self, cursor):
            self.cursor = cursor

        def fetchall(self):
            rows = self.cursor.fetchall()
            try:
                other.execute(
                    "ALTER TABLE entry ADD COLUMN scope TEXT NOT NULL DEFAULT ''"
                )
                other.execute("DELETE FROM entry")
                other.commit()
            except sqlite3.OperationalError as exc:
                attempts.append(str(exc))
            else:
                attempts.append("migrated")
            return rows

        def __getattr__(self, name):
            return getattr(self.cursor, name)

    def racing_connection():
        class Racing(sqlite3.Connection):
            def execute(self, sql, *args):
                cursor = super().execute(sql, *args)
                if sql.startswith("PRAGMA table_info(entry)") and not attempts:
                    return Cursor(cursor)
                return cursor

        return Racing

    def connect(*args, **kwargs):
        kwargs["factory"] = racing_connection()
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(query_client.sqlite3, "connect", connect)
    try:
        cache = Cache(path)
    finally:
        other.close()
    # The migration held the write lock while it decided, so the other process
    # could not add the column behind its back. Without that lock the loser
    # observes a pre-scope snapshot and dies on "duplicate column name".
    assert attempts and "locked" in attempts[0]
    assert cache.get("old", 1) is None


def test_active_revision_floor_survives_scope_churn(tmp_path):
    cache = Cache(tmp_path / "cache.sqlite")
    for index in range(128):
        cache.accept(f"scope-{index}", 1)
    assert cache.floor("scope-0") == 1  # Actively read again.
    cache.accept("scope-new", 1)
    assert cache.floor("scope-0") == 1
    assert cache.floor("scope-1") == 0
    assert cache.floor("scope-new") == 1


def test_existing_revision_floors_survive_the_used_column_migration(tmp_path):
    path = tmp_path / "cache.sqlite"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE revision_floor(scope TEXT PRIMARY KEY,revision INTEGER NOT NULL)"
    )
    db.execute("INSERT INTO revision_floor VALUES('scope',42)")
    db.commit()
    db.close()
    cache = Cache(path)
    assert cache.floor("scope") == 42
    cache.accept("scope", 43)
    assert cache.floor("scope") == 43
    with pytest.raises(ValueError, match="regressed"):
        cache.accept("scope", 42)
