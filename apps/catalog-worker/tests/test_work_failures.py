"""Failure receipts survive restart and roll back with their queue mutation."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from test_pipeline import NOW, collectors

from catalog_worker.aniworld import Page
from catalog_worker.collector import Plan, Ready
from catalog_worker.state import State
from catalog_worker.state_migrations import initialize, preflight, rollback_failures
from catalog_worker.work_failures import summary


def test_failures_keep_bounded_classes_clocks_and_deadlines_across_restart(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    try:
        work = c.state.claim(NOW)
        for offset, outcome, status, reason in (
            (0, "http_error", 500, None),
            (3600, "unexpected_structure", 200, "parent_children_missing"),
        ):
            current = dict(
                c.state.db.execute(
                    "SELECT * FROM work WHERE path=?", (work["path"],)
                ).fetchone()
            )
            c.apply(
                Ready(
                    Plan(NOW + offset, False, current, work["path"]),
                    None,
                    outcome,
                    status=status,
                    parser_reason=reason,
                )
            )
        filename = Path(c.state.db.execute("PRAGMA database_list").fetchone()[2])
        c.state.close()
        c.state = State(filename, "aniworld.to")
        row = summary(c.state.db, NOW + 3600)["groups"][0]
        assert row["count"] == 1 and row["outcome"] == "unexpected_structure"
        assert (
            row["http_status"] == 200
            and row["parser_reason"] == "parent_children_missing"
        )
        assert (
            row["oldest_first_failure_at"] == NOW
            and row["oldest_last_failure_at"] == NOW + 3600
        )
        assert (
            row["first_failure_unknown"] == 0
            and row["attempts_min"] == row["attempts_max"] == 2
        )
        assert row["next_due_min"] > NOW + 3600 and c.state.meta()["blocked_until"] == 0
        assert (
            c.state.db.execute("SELECT count(*) FROM work_failure").fetchone()[0] == 1
        )
        before = tuple(c.state.db.execute("SELECT * FROM work_failure").fetchone())
        c.apply(
            Ready(
                Plan(NOW + 3601, False, work, work["path"]),
                None,
                "admission_deferred",
                10,
            )
        )
        assert (
            tuple(c.state.db.execute("SELECT * FROM work_failure").fetchone()) == before
        )
        c.state.detail(
            work, Page((), (), 0, "Example", availability="unavailable"), NOW + 3602
        )
        assert (
            tuple(c.state.db.execute("SELECT * FROM work_failure").fetchone()) == before
        )
        c.state.detail(work, Page((), (), 0, "Example"), NOW + 3603)
        assert not c.state.db.execute("SELECT 1 FROM work_failure").fetchone()
        assert summary(c.state.db, NOW + 3603)["groups"] == []
    finally:
        for collector in group:
            collector.state.close()


def test_old_retries_have_unknown_first_failure_and_do_not_leak_inputs(tmp_path):
    group = collectors(tmp_path)
    state = group[0].state
    try:
        work = state.claim(NOW)
        with state.db:
            state.db.execute("UPDATE work SET failures=8 WHERE path=?", (work["path"],))
        assert summary(state.db, NOW)["groups"][0]["first_failure_unknown"] == 1
        work["failures"] = 8
        state.failure(
            work, "transport_failure", NOW, status=999, parser_reason="secret URL"
        )
        row = summary(state.db, NOW)["groups"][0]
        assert row["oldest_first_failure_at"] is None and row["observed_since"] == NOW
        assert (
            row["attempts_max"] == 9
            and row["http_status"] is None
            and row["parser_reason"] is None
        )
        assert "secret" not in str(row) and "path" not in row
        with state.db:
            state.db.execute(
                "CREATE TRIGGER refuse_failure BEFORE UPDATE ON title BEGIN SELECT RAISE(ABORT, 'injected'); END"
            )
        before = tuple(state.db.execute("SELECT * FROM work_failure").fetchone())
        queue = tuple(
            state.db.execute(
                "SELECT * FROM work WHERE path=?", (work["path"],)
            ).fetchone()
        )
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            state.failure(work, "http_error", NOW + 100, status=500)
        assert (
            tuple(state.db.execute("SELECT * FROM work_failure").fetchone()) == before
        )
        assert (
            tuple(
                state.db.execute(
                    "SELECT * FROM work WHERE path=?", (work["path"],)
                ).fetchone()
            )
            == queue
        )
    finally:
        for collector in group:
            collector.state.close()


@pytest.mark.parametrize(
    "point", ["failure-tables", "failure-version", "failure-commit"]
)
def test_v7_interruption_backup_and_rollback_preserve_every_v6_table(tmp_path, point):
    from test_query import seed

    filename = tmp_path / "worker.sqlite"
    state, _ = seed(tmp_path)
    filename = Path(state.db.execute("PRAGMA database_list").fetchone()[2])
    state.close()
    rollback_failures(filename, "aniworld.to")
    with sqlite3.connect(filename) as db:
        tables = [
            r[0]
            for r in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")
        ]
        before = {
            t: db.execute(f'SELECT * FROM "{t}"').fetchall()
            for t in tables
            if t != "worker_schema"
        }

    def checkpoint(stage):
        if stage == point:
            raise RuntimeError("interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        initialize(filename, "aniworld.to", checkpoint)
    assert preflight(filename, "aniworld.to") == (7 if point == "failure-commit" else 6)
    backup = filename.with_name(filename.name + ".pre-v7.backup")
    saved = backup.read_bytes()
    assert preflight(backup, "aniworld.to") == 6
    State(filename, "aniworld.to").close()
    State(filename, "aniworld.to").close()
    assert backup.read_bytes() == saved
    from catalog_worker.aniworld import Link

    # A code downgrade keeps observations committed after the upgrade too.
    state = State(filename, "aniworld.to")
    state.discover(Link("/anime/stream/later", "Later"), NOW + 1)
    state.db.commit()
    after = {
        t: [tuple(r) for r in state.db.execute(f'SELECT * FROM "{t}"')] for t in before
    }
    state.close()
    rollback_failures(filename, "aniworld.to")
    with sqlite3.connect(filename) as db:
        assert {
            t: db.execute(f'SELECT * FROM "{t}"').fetchall() for t in before
        } == after
        for table, rows in before.items():
            if table not in {"worker_meta", "publication_meta", "publication_change"}:
                assert set(rows) <= set(after[table])
    assert preflight(filename, "aniworld.to") == 6


def test_v7_reserves_a_wal_consistent_v6_backup_before_migration(tmp_path):
    from test_query import seed

    from catalog_worker.storage import STATE_HEADROOM, migration_reserve

    state, config = seed(tmp_path)
    filename = Path(state.db.execute("PRAGMA database_list").fetchone()[2])
    state.close()
    rollback_failures(filename, "aniworld.to")
    with sqlite3.connect(filename) as db:
        db.execute("PRAGMA wal_autocheckpoint=0")
        db.execute(
            "INSERT INTO canonical_descriptor VALUES(?,?,?,?,?)",
            ("777", "0" * 64, "x" * 2**20, NOW, NOW),
        )
        db.commit()
        size = (
            db.execute("PRAGMA page_count").fetchone()[0]
            * db.execute("PRAGMA page_size").fetchone()[0]
        )
        assert size > filename.stat().st_size
        assert migration_reserve(config) == STATE_HEADROOM + size


def test_v7_backup_is_self_contained_without_temporary_wal_sidecars(tmp_path):
    from test_query import seed

    state, _ = seed(tmp_path)
    filename = Path(state.db.execute("PRAGMA database_list").fetchone()[2])
    state.close()
    rollback_failures(filename, "aniworld.to")
    with closing(sqlite3.connect(filename)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE worker_meta SET revision=73")
        writer.commit()
        assert filename.with_name(filename.name + "-wal").stat().st_size > 0
        initialize(filename, "aniworld.to")
        assert writer.execute("PRAGMA journal_mode").fetchone() == ("wal",)

    backup = filename.with_name(filename.name + ".pre-v7.backup")
    assert preflight(backup, "aniworld.to") == 6
    with closing(sqlite3.connect(backup)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert db.execute("SELECT revision FROM worker_meta").fetchone() == (73,)
    assert not list(tmp_path.glob(".worker-backup-*"))
    assert not backup.with_name(backup.name + "-wal").exists()
    assert not backup.with_name(backup.name + "-shm").exists()
