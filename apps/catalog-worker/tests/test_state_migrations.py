"""Worker-only disposable migrations; no user installation or provider traffic."""

import os
import signal
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest
from catalog_core import schema
from catalog_worker.state import State
from catalog_worker.state_schema import PRIVATE_DDL


def legacy(filename):
    with closing(sqlite3.connect(filename)) as db:
        db.executescript(schema.DDL + PRIVATE_DDL)
        db.execute("INSERT INTO catalog VALUES(1,'aniworld.to',1,1,123)")
        db.execute("UPDATE worker_meta SET revision=17,wall=1800000000")
        db.commit()


def test_private_upgrade_preserves_state_and_original_backup(tmp_path):
    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    state = State(filename, "aniworld.to")
    assert state.meta()["revision"] == 17
    assert state.db.execute("SELECT version FROM worker_schema").fetchone()[0] == 7
    state.close()
    backup = filename.with_name(filename.name + ".pre-v2.backup")
    before = backup.read_bytes()
    State(filename, "aniworld.to").close()
    assert backup.read_bytes() == before
    with closing(sqlite3.connect(backup)) as db:
        assert db.execute("SELECT version FROM worker_schema").fetchone()[0] == 1


@pytest.mark.parametrize(
    "change",
    [
        "ALTER TABLE work ADD COLUMN foreign_data TEXT",
        "CREATE TRIGGER foreign_trigger AFTER DELETE ON title BEGIN SELECT 1; END",
        "UPDATE catalog SET provider='s.to'",
    ],
)
def test_foreign_schema_or_provider_is_rejected_before_mutation(tmp_path, change):
    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    with closing(sqlite3.connect(filename)) as db, db:
        db.execute(change)
    original = filename.read_bytes()
    with pytest.raises(ValueError):
        State(filename, "aniworld.to")
    assert filename.read_bytes() == original
    assert not filename.with_name(filename.name + ".pre-v2.backup").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX kill gate")
@pytest.mark.parametrize("point", ["tables", "version", "commit"])
def test_sigkill_upgrade_is_atomic_and_resumable(tmp_path, point):
    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    program = "\n".join(
        [
            "import os,signal",
            "from pathlib import Path",
            "from catalog_worker.state_migrations import initialize",
            f"def checkpoint(stage):\n if stage == {point!r}: os.kill(os.getpid(), signal.SIGKILL)",
            f"initialize(Path({str(filename)!r}), 'aniworld.to', checkpoint)",
        ]
    )
    child = subprocess.run([sys.executable, "-c", program], timeout=10, check=False)
    assert child.returncode == -signal.SIGKILL
    with closing(sqlite3.connect(filename)) as db:
        assert db.execute("SELECT version FROM worker_schema").fetchone()[0] == (
            2 if point == "commit" else 1
        )
    state = State(filename, "aniworld.to")
    assert state.meta()["revision"] == 17
    assert state.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    state.close()


@pytest.mark.parametrize("kind", ["corrupt", "foreign", "wrong-provider", "symlink"])
def test_invalid_existing_backup_refuses_upgrade_unchanged(tmp_path, kind):
    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    saved = filename.with_name(filename.name + ".pre-v2.backup")
    if kind == "corrupt":
        saved.write_bytes(b"not sqlite")
    elif kind == "symlink":
        saved.symlink_to(filename)
    else:
        legacy(saved)
        with closing(sqlite3.connect(saved)) as db, db:
            db.execute(
                "CREATE TABLE unrelated(value TEXT)"
                if kind == "foreign"
                else "UPDATE catalog SET provider='s.to'"
            )
    before = filename.read_bytes()
    saved_before = saved.read_bytes()
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        State(filename, "aniworld.to")
    assert filename.read_bytes() == before
    assert saved.read_bytes() == saved_before
    assert saved.is_symlink() == (kind == "symlink")


def test_racing_backup_is_verified_and_never_overwritten(tmp_path, monkeypatch):
    from catalog_worker import state_migrations

    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    saved = filename.with_name(filename.name + ".pre-v2.backup")
    original_link = os.link
    expected = []

    def race(source, target):
        legacy(saved)
        with closing(sqlite3.connect(saved)) as db, db:
            db.execute("UPDATE worker_meta SET revision=9")
        expected.append(saved.read_bytes())
        original_link(source, target)

    monkeypatch.setattr(state_migrations.os, "link", race)
    State(filename, "aniworld.to").close()
    assert saved.read_bytes() == expected[0]
    assert not list(tmp_path.glob(".worker-backup-*"))


def test_racing_invalid_backup_refuses_upgrade(tmp_path, monkeypatch):
    from catalog_worker import state_migrations

    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    saved = filename.with_name(filename.name + ".pre-v2.backup")
    original_link = os.link
    before = filename.read_bytes()

    def race(source, target):
        saved.write_bytes(b"racing corrupt backup")
        original_link(source, target)

    monkeypatch.setattr(state_migrations.os, "link", race)
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        State(filename, "aniworld.to")
    assert filename.read_bytes() == before
    assert saved.read_bytes() == b"racing corrupt backup"
    assert not list(tmp_path.glob(".worker-backup-*"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX kill gate")
@pytest.mark.parametrize(
    "point", ["backup-copy", "backup-file-sync", "backup-link", "backup-directory-sync"]
)
def test_sigkill_backup_keeps_original_and_resumes(tmp_path, point):
    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    before = filename.read_bytes()
    saved = filename.with_name(filename.name + ".pre-v2.backup")
    program = "\n".join(
        [
            "import os,signal",
            "from pathlib import Path",
            "from catalog_worker.state_migrations import initialize",
            f"def checkpoint(stage):\n if stage == {point!r}: os.kill(os.getpid(), signal.SIGKILL)",
            f"initialize(Path({str(filename)!r}), 'aniworld.to', checkpoint)",
        ]
    )
    child = subprocess.run([sys.executable, "-c", program], timeout=10, check=False)
    assert child.returncode == -signal.SIGKILL
    assert filename.read_bytes() == before
    retained = saved.read_bytes() if saved.exists() else None
    State(filename, "aniworld.to").close()
    if retained is not None:
        assert saved.read_bytes() == retained
    with closing(sqlite3.connect(saved)) as db:
        assert db.execute("SELECT version FROM worker_schema").fetchone()[0] == 1
        assert db.execute("SELECT revision FROM worker_meta").fetchone()[0] == 17


@pytest.mark.parametrize("function", ["fsync", "fsync_directory"])
def test_backup_sync_failure_refuses_upgrade_and_retry_preserves_backup(
    tmp_path, monkeypatch, function
):
    from catalog_worker import state_migrations

    filename = tmp_path / "worker.sqlite"
    legacy(filename)
    before = filename.read_bytes()
    saved = filename.with_name(filename.name + ".pre-v2.backup")

    def refuse(*args):
        raise OSError("injected sync failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            state_migrations.os if function == "fsync" else state_migrations,
            function,
            refuse,
        )
        with pytest.raises(OSError, match="injected sync"):
            State(filename, "aniworld.to")
    assert filename.read_bytes() == before
    retained = saved.read_bytes() if saved.exists() else None
    State(filename, "aniworld.to").close()
    if retained is not None:
        assert saved.read_bytes() == retained


def version_two(filename):
    from catalog_worker.state_migrations import upgrade

    legacy(filename)
    with closing(sqlite3.connect(filename)) as db:
        upgrade(db, lambda stage: None)


@pytest.mark.parametrize(
    "point", ["incremental-tables", "incremental-version", "incremental-commit"]
)
def test_version_two_signal_upgrade_sigkill_preserves_ledger_and_backup(
    tmp_path, point
):
    filename = tmp_path / "worker.sqlite"
    version_two(filename)
    program = "\n".join(
        [
            "import os,signal",
            "from pathlib import Path",
            "from catalog_worker.state_migrations import initialize",
            f"def checkpoint(stage):\n if stage == {point!r}: os.kill(os.getpid(),signal.SIGKILL)",
            f'initialize(Path({str(filename)!r}),"aniworld.to",checkpoint)',
        ]
    )
    child = subprocess.run([sys.executable, "-c", program], timeout=10, check=False)
    assert child.returncode == -signal.SIGKILL
    saved = filename.with_name(filename.name + ".pre-v3.backup")
    original = saved.read_bytes()
    with closing(sqlite3.connect(saved)) as db:
        assert db.execute("SELECT version FROM worker_schema").fetchone()[0] == 2
        assert db.execute("SELECT revision FROM worker_meta").fetchone()[0] == 17
    State(filename, "aniworld.to").close()
    assert saved.read_bytes() == original
    with closing(sqlite3.connect(filename)) as db:
        assert db.execute("SELECT version FROM worker_schema").fetchone()[0] == 7
        assert db.execute("SELECT count(*) FROM signal_pending").fetchone()[0] == 0


def test_version_three_upgrade_retains_failures_budgets_and_backup(tmp_path):
    from catalog_worker.state_migrations import preflight, upgrade_incremental

    filename = tmp_path / "worker.sqlite"
    version_two(filename)
    with closing(sqlite3.connect(filename)) as db:
        upgrade_incremental(db, lambda stage: None)
        with db:
            db.execute("INSERT INTO request_start VALUES(1800000000)")
            db.execute("UPDATE worker_meta SET blocked_until=1800000123,block_count=2")
    assert preflight(filename, "aniworld.to") == 3
    state = State(filename, "aniworld.to")
    try:
        assert state.meta()["revision"] == 17
        assert (
            state.meta()["blocked_until"] == 1800000123
            and state.meta()["block_count"] == 2
        )
        assert state.db.execute("SELECT count(*) FROM request_start").fetchone()[0] == 1
        assert preflight(filename, "aniworld.to") == 7
        saved = filename.with_name(filename.name + ".pre-v4.backup")
        assert preflight(saved, "aniworld.to") == 3
        original = saved.read_bytes()
    finally:
        state.close()
    State(filename, "aniworld.to").close()
    assert saved.read_bytes() == original


@pytest.mark.parametrize("point", ["matching-version", "matching-commit"])
def test_v4_matching_upgrade_interruption_retains_original_backup(tmp_path, point):
    from catalog_worker.state_migrations import initialize, preflight, rollback_matching

    filename = tmp_path / "worker.sqlite"
    State(filename, "aniworld.to").close()
    rollback_matching(filename, "aniworld.to")
    with sqlite3.connect(filename) as db:
        original = list(db.iterdump())

    def checkpoint(stage):
        if stage == point:
            raise RuntimeError("controlled upgrade interruption")

    with pytest.raises(RuntimeError):
        initialize(filename, "aniworld.to", checkpoint)
    assert preflight(filename, "aniworld.to") == (
        5 if point == "matching-commit" else 4
    )
    backup = filename.with_name(filename.name + ".pre-v5.backup")
    with sqlite3.connect(backup) as db:
        assert list(db.iterdump()) == original
    retained = backup.read_bytes()
    State(filename, "aniworld.to").close()
    assert preflight(filename, "aniworld.to") == 7
    assert backup.read_bytes() == retained
