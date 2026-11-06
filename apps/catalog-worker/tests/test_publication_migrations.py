"""Publication migration interruptions, no-overwrite rollback and WAL reserve."""

import sqlite3
from pathlib import Path

import pytest
from catalog_worker.state import State
from catalog_worker.state_migrations import initialize, preflight, rollback_publication
from test_query import NOW, seed


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
