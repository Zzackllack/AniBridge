"""Publication migration interruptions, no-overwrite rollback and WAL reserve."""

import sqlite3
from pathlib import Path

import pytest
from test_query import NOW, seed

from catalog_worker.state import State
from catalog_worker.state_migrations import initialize, preflight, rollback_publication


@pytest.mark.parametrize(
    "point", ["publication-tables", "publication-version", "publication-commit"]
)
def test_v6_upgrade_interruption_and_code_rollback_preserve_v5(tmp_path, point):
    state, _config = seed(tmp_path)
    filename = Path(state.db.execute("PRAGMA database_list").fetchone()[2])
    state.close()
    rollback_publication(filename, "aniworld.to")
    assert preflight(filename, "aniworld.to") == 5
    with sqlite3.connect(filename) as db:
        before = {
            t: db.execute(f"SELECT * FROM {t}").fetchall()
            for t in ("release", "canonical_episode", "work", "mapping_input")
        }

    def checkpoint(stage):
        if stage == point:
            raise RuntimeError("controlled interruption")

    with pytest.raises(RuntimeError):
        initialize(filename, "aniworld.to", checkpoint)
    assert preflight(filename, "aniworld.to") == (
        6 if point == "publication-commit" else 5
    )
    backup = filename.with_name(filename.name + ".pre-v6.backup")
    preserved = backup.read_bytes()
    state = State(filename, "aniworld.to")
    assert backup.read_bytes() == preserved
    assert {
        t: [tuple(r) for r in state.db.execute(f"SELECT * FROM {t}")] for t in before
    } == before
    state.close()
    rollback_publication(filename, "aniworld.to")
    assert preflight(filename, "aniworld.to") == 5


def test_v6_migration_reserve_includes_committed_wal_pages(tmp_path):
    from catalog_worker.storage import STATE_HEADROOM, migration_reserve

    state, config = seed(tmp_path)
    filename = config.state_dir / "aniworld.to.sqlite"
    state.close()
    rollback_publication(filename, "aniworld.to")
    with sqlite3.connect(filename) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO canonical_descriptor VALUES(?,?,?,?,?)",
            ("123", "0" * 64, "x" * 2**20, NOW, NOW),
        )
        writer.commit()
        pages = writer.execute("PRAGMA page_count").fetchone()[0]
        size = writer.execute("PRAGMA page_size").fetchone()[0]
        assert pages * size > filename.stat().st_size
        assert migration_reserve(config) == STATE_HEADROOM + pages * size


@pytest.mark.parametrize(
    "provider,reserves_new_backup", [("filmo.to", True), ("aniworld.to", False)]
)
def test_v7_reserve_counts_only_a_pending_upgrade_backup(
    tmp_path, provider, reserves_new_backup
):
    from catalog_worker.config import LIMITS, Config
    from catalog_worker.storage import STATE_HEADROOM, migration_reserve

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    filename = state_dir / f"{provider}.sqlite"
    with sqlite3.connect(filename) as db:
        db.execute("CREATE TABLE worker_schema(version INTEGER)")
        db.execute("INSERT INTO worker_schema VALUES(7)")
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        size = db.execute("PRAGMA page_size").fetchone()[0]
    config = Config(
        {provider: "https://fixture.invalid"},
        {"tv": "off"},
        state_dir,
        tmp_path / "output",
        tmp_path / "key",
        "fixture",
        "127.0.0.1",
        1,
        {key: bounds[0] for key, bounds in LIMITS.items()},
    )
    expected = STATE_HEADROOM + pages * size if reserves_new_backup else STATE_HEADROOM
    assert migration_reserve(config) == expected
