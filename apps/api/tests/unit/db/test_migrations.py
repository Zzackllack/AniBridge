from __future__ import annotations

from pathlib import Path
from sqlalchemy import inspect


HEAD_REVISION = "20261003_0008"


def _load_db(tmp_path: Path, monkeypatch):
    """
    Prepare a temporary test database environment and return a fresh import of the app.db.models module.

    This configures DATA_DIR and DOWNLOAD_DIR to subdirectories under the provided tmp_path, disables automatic DB migration at startup by setting DB_MIGRATE_ON_STARTUP to "0", and clears any cached imports of app.config, app.db, and app.db.models so the models module is re-imported.

    Returns:
        models: The freshly imported `app.db.models` module configured to use the temporary directories.
    """
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
    """
    Verify that applying migrations to a fresh database creates the expected schema and sets the Alembic version.

    This test initializes a fresh database, runs models.apply_migrations(), and asserts that the tables `job`, `episodeavailability`, `clienttask`, `strmurlmapping`, and `alembic_version` exist and that the alembic version equals HEAD_REVISION.
    """
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
    """
    Verify that applying migrations to a database with an empty `alembic_version` table creates the expected schema and sets the Alembic version to HEAD_REVISION.

    Creates an empty `alembic_version` table, runs the migration routine, and asserts that the `job`, `strmurlmapping`, and `alembic_version` tables exist and that the recorded Alembic version equals HEAD_REVISION.
    """
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


def test_unknown_schema_is_rejected_without_stamping(tmp_path, monkeypatch):
    import pytest

    models = _load_db(tmp_path, monkeypatch)
    with models.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE experimental_catalog (value TEXT)")
        connection.exec_driver_sql(
            "INSERT INTO experimental_catalog VALUES ('keep me')"
        )
    filename = tmp_path / "data/anibridge_jobs.db"
    original = filename.read_bytes()
    with pytest.raises(RuntimeError, match="Unsupported private database"):
        models.apply_migrations()
    assert filename.read_bytes() == original
    assert not (tmp_path / "data/anibridge_jobs.db.pre-catalog-v3.backup").exists()


def test_legacy_backup_preserves_original_rows(tmp_path, monkeypatch):
    import sqlite3

    models = _load_db(tmp_path, monkeypatch)
    models.create_db_and_tables()
    with models.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO job(id,status,progress,downloaded_bytes,source_site,created_at,updated_at) VALUES ('preserved','blocked',12,123,'s.to','2026-01-01','2026-01-01')"
        )
    models.apply_migrations()
    backup = tmp_path / "data/anibridge_jobs.db.pre-catalog-v3.backup"
    assert backup.exists()
    with sqlite3.connect(backup) as db:
        assert (
            db.execute(
                "SELECT downloaded_bytes FROM job WHERE id='preserved'"
            ).fetchone()[0]
            == 123
        )
        assert (
            db.execute(
                "SELECT name FROM sqlite_schema WHERE name='durable_request'"
            ).fetchone()
            is None
        )
    with models.engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT downloaded_bytes FROM job WHERE id='preserved'"
            ).scalar()
            == 123
        )


def test_released_revision_matrix_preserves_state_and_backup(tmp_path, monkeypatch):
    import sqlite3
    from alembic import command

    for revision in ("20260203_0001", "20260203_0002", "20260204_0003", "unversioned"):
        models = _load_db(tmp_path / revision, monkeypatch)
        command.upgrade(
            models._get_alembic_config(),
            "20260204_0003" if revision == "unversioned" else revision,
        )
        with models.engine.begin() as connection:
            if revision == "unversioned":
                connection.exec_driver_sql("DROP TABLE alembic_version")
            for status in (
                "queued",
                "resolving",
                "downloading",
                "retry_wait",
                "paused",
                "blocked",
                "cancelling",
                "cancelled",
                "failed",
                "completed",
            ):
                connection.exec_driver_sql(
                    "INSERT INTO job(id,status,progress,downloaded_bytes,result_path,created_at,updated_at) VALUES (?,?,37,123,?,'2026-01-01','2026-01-01')",
                    (status, status, "/synthetic/" + status),
                )
                connection.exec_driver_sql(
                    "INSERT INTO clienttask(hash,name,slug,season,episode,language,site,job_id,added_on,state) VALUES (?,?,?,0,1,'German Dub','aniworld.to',?,'2026-01-01',?)",
                    ((status * 40)[:40], status, "example", status, status),
                )
            if revision == "20260203_0001":
                connection.exec_driver_sql(
                    "INSERT INTO episodeavailability(slug,season,episode,language,available,checked_at) VALUES('same',1,1,'German Dub',1,'2026-01-01')"
                )
            else:
                for site in ("aniworld.to", "s.to"):
                    connection.exec_driver_sql(
                        "INSERT INTO episodeavailability(slug,season,episode,language,site,available,checked_at) VALUES('same',1,1,'German Dub',?,1,'2026-01-01')",
                        (site,),
                    )
            before = connection.exec_driver_sql(
                "SELECT * FROM clienttask ORDER BY hash"
            ).fetchall()
        models.apply_migrations()
        filename = tmp_path / revision / "data/anibridge_jobs.db"
        with models.engine.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT * FROM clienttask ORDER BY hash"
                ).fetchall()
                == before
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT sum(downloaded_bytes) FROM job"
                ).scalar()
                == 1230
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT count(*) FROM job WHERE result_path LIKE '/synthetic/%'"
                ).scalar()
                == 10
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT status FROM job WHERE id='completed'"
                ).scalar()
                == "completed"
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT count(*) FROM durable_request WHERE error_code='legacy_request_incomplete'"
                ).scalar()
                == 7
            )
            assert connection.exec_driver_sql(
                "SELECT count(*) FROM episodeavailability"
            ).scalar() == (1 if revision == "20260203_0001" else 2)
        with sqlite3.connect(str(filename) + ".pre-catalog-v3.backup") as backup:
            if revision == "unversioned":
                assert not backup.execute(
                    "SELECT 1 FROM sqlite_schema WHERE name='alembic_version'"
                ).fetchone()
            else:
                assert (
                    backup.execute(
                        "SELECT version_num FROM alembic_version"
                    ).fetchone()[0]
                    == revision
                )
            assert (
                backup.execute("SELECT status FROM job WHERE id='queued'").fetchone()[0]
                == "queued"
            )
        with models.engine.connect() as connection:
            assert {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT prior_state FROM durable_request"
                )
            } == {
                "queued",
                "resolving",
                "downloading",
                "retry_wait",
                "paused",
                "blocked",
                "cancelling",
            }
            assert {
                row[0]: row[1]
                for row in connection.exec_driver_sql(
                    "SELECT id,status FROM job WHERE id IN ('cancelled','failed','completed')"
                )
            } == {
                "cancelled": "cancelled",
                "failed": "failed",
                "completed": "completed",
            }
        # Running again validates the new schema and does not replace the backup.
        models.apply_migrations()
        models.dispose_engine()


def test_startup_migrates_only_preflight_database(tmp_path, monkeypatch):
    import sqlite3

    models = _load_db(tmp_path, monkeypatch)
    unrelated = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(unrelated) as db:
        db.execute("CREATE TABLE untouched(value TEXT)")
        db.execute("INSERT INTO untouched VALUES ('preserve')")
    before = unrelated.read_bytes()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(unrelated))
    models.apply_migrations()
    assert _get_version(models) == HEAD_REVISION
    assert unrelated.read_bytes() == before


def test_killed_upgrade_rolls_back_ddl_and_can_resume(tmp_path, monkeypatch):
    """Kill SQLite between migration statements, using only disposable DBs."""
    import os
    import signal
    import sqlite3
    import subprocess
    import sys
    from alembic import command

    if os.name != "posix":
        import pytest

        pytest.skip("SIGKILL rehearsal requires POSIX")
    for statement in (
        "CREATE TABLE catalog_source",
        "CREATE TABLE durable_request",
        "CREATE TABLE catalog_cache",
        "CREATE TABLE catalog_control",
        "CREATE INDEX catalog_override_identity",
        "ALTER TABLE catalog_version ADD COLUMN validation_version",
        "ALTER TABLE catalog_version ADD COLUMN validation_context",
    ):
        root = tmp_path / statement.rsplit(" ", 1)[-1]
        models = _load_db(root, monkeypatch)
        command.upgrade(models._get_alembic_config(), "20260204_0003")
        models.dispose_engine()
        script = """
import os, signal
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.db.models import apply_migrations
@event.listens_for(Engine, "after_cursor_execute")
def kill_at_boundary(conn, cursor, statement, parameters, context, executemany):
    if statement.lstrip().startswith(os.environ["MIGRATION_KILL_STATEMENT"]):
        os.kill(os.getpid(), signal.SIGKILL)
apply_migrations()
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[3],
            env={**os.environ, "MIGRATION_KILL_STATEMENT": statement},
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == -signal.SIGKILL, result.stderr.decode()
        filename = root / "data/anibridge_jobs.db"
        with sqlite3.connect(filename) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert (
                db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                == "20260204_0003"
            )
            assert not db.execute(
                "SELECT name FROM sqlite_schema WHERE name LIKE 'catalog_%'"
            ).fetchall()
        assert filename.with_name(filename.name + ".pre-catalog-v3.backup").exists()
        models.apply_migrations()
        assert _get_version(models) == HEAD_REVISION
        models.dispose_engine()


def test_private_v5_upgrade_adds_indexes_without_rewriting_corrections(
    tmp_path, monkeypatch
):
    from alembic import command

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260928_0005")
    with models.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO catalog_override VALUES('retained','aniworld.to','title',NULL,'tvdb','{}',7,100,200)"
        )
        before = connection.exec_driver_sql("SELECT * FROM catalog_override").fetchall()
    models.apply_migrations()
    with models.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT * FROM catalog_override").fetchall()
            == before
        )
        indexes = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA index_list(catalog_override)")
        }
        assert {
            "catalog_override_identity",
            "catalog_override_entity",
            "catalog_override_namespace",
        } <= indexes
    assert _get_version(models) == HEAD_REVISION
    models.apply_migrations()
    models.dispose_engine()


def test_private_v6_upgrade_preserves_snapshot_receipt_and_marks_recheck(
    tmp_path, monkeypatch
):
    from alembic import command

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260929_0006")
    row = (
        "source",
        "aniworld.to",
        7,
        b"retained signed bytes",
        "retained.sqlite",
        "a" * 64,
    )
    with models.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO catalog_version VALUES(?,?,?,?,?,?)", row
        )
    models.apply_migrations()
    with models.engine.connect() as connection:
        assert tuple(
            connection.exec_driver_sql("SELECT * FROM catalog_version").fetchone()
        ) == (*row, 0, None)
    assert _get_version(models) == HEAD_REVISION
    models.apply_migrations()
    models.dispose_engine()


def test_mainline_files_strm_rows_hashes_and_backup_rollback(tmp_path, monkeypatch):
    """Rehearse upgrade/restore on disposable data; these files are not playback proof."""
    import hashlib
    import shutil
    import sqlite3
    from contextlib import closing
    from alembic import command
    from app.db.legacy_catalog import INTERRUPTED
    from app.catalog.jobs import Jobs, JobError
    import pytest

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260204_0003")
    media = tmp_path / "downloads" / "preserved.mkv"
    media.write_bytes(b"generated ownership fixture\0" * 1024)
    strm = tmp_path / "downloads" / "preserved.strm"
    strm.write_text("https://media.invalid/original\n")
    file_bytes = {path: path.read_bytes() for path in (media, strm)}
    statuses = (*INTERRUPTED, "failed", "cancelled", "completed")
    legacy_hash = hashlib.sha1(b"same|S1E1").hexdigest()
    with models.engine.begin() as db:
        for status in statuses:
            db.exec_driver_sql(
                "INSERT INTO job(id,status,progress,downloaded_bytes,result_path,source_site,created_at,updated_at) VALUES (?,?,37,123,?,'aniworld.to','2026-01-01','2026-01-01')",
                (status, status, str(strm if status == "completed" else media)),
            )
            db.exec_driver_sql(
                "INSERT INTO clienttask(hash,name,slug,season,episode,language,site,job_id,save_path,added_on,state) VALUES (?,?,'same',1,1,'German Dub','aniworld.to',?,?,'2026-01-01',?)",
                (
                    legacy_hash
                    if status == "completed"
                    else hashlib.sha1(status.encode()).hexdigest(),
                    "Display.STRM" if status == "paused" else "Display",
                    status,
                    str(media.parent),
                    status,
                ),
            )
        for site in ("aniworld.to", "s.to", "megakino"):
            db.exec_driver_sql(
                "INSERT INTO strmurlmapping(site,slug,season,episode,language,provider,resolved_url,resolved_at,updated_at) VALUES (?,'same',1,1,'German Dub','VOE','https://media.invalid/original','2026-01-01','2026-01-01')",
                (site,),
            )
        before = {
            table: db.exec_driver_sql(
                f"SELECT * FROM {table} ORDER BY rowid"
            ).fetchall()
            for table in ("job", "clienttask", "strmurlmapping")
        }
    models.apply_migrations()
    backup_path = tmp_path / "data/anibridge_jobs.db.pre-catalog-v3.backup"
    backup_bytes = backup_path.read_bytes()
    with models.engine.connect() as db:
        for table in ("clienttask", "strmurlmapping"):
            assert (
                db.exec_driver_sql(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                == before[table]
            )
        incomplete = db.exec_driver_sql(
            "SELECT job_id,prior_state,error_code FROM durable_request ORDER BY job_id"
        ).fetchall()
        assert incomplete == sorted(
            (state, state, "legacy_request_incomplete") for state in INTERRUPTED
        )
        for state in ("failed", "cancelled", "completed"):
            assert (
                db.exec_driver_sql(
                    "SELECT status FROM job WHERE id=?", (state,)
                ).scalar()
                == state
            )
    jobs = Jobs(
        tmp_path / "data/anibridge_jobs.db",
        media.parent,
        {"aniworld.to", "s.to", "megakino"},
    )
    # The historical hash omits provider. A cross-site retry cannot silently
    # attach to a completed mainline job whose frozen inputs were never recorded.
    uri = f"magnet:?xt=urn:btih:{legacy_hash}&dn=Display&sto_slug=same&sto_s=1&sto_e=1&sto_lang=German%20Dub&sto_site=s.to"
    with pytest.raises(JobError) as exc:
        jobs.admit(uri, 1800000000)
    assert exc.value.code == "identity_conflict"
    models.apply_migrations()
    assert backup_path.read_bytes() == backup_bytes
    assert all(path.read_bytes() == content for path, content in file_bytes.items())
    # Supported rollback is restoring the retained original DB while stopped,
    # never downgrading the private schema in place. Rehearse on another copy.
    restored = tmp_path / "rollback.sqlite"
    shutil.copyfile(backup_path, restored)
    with closing(sqlite3.connect(restored)) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "20260204_0003"
        )
        for table, rows in before.items():
            assert db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() == [
                tuple(row) for row in rows
            ]
        assert not db.execute(
            "SELECT name FROM sqlite_schema WHERE name='durable_request'"
        ).fetchone()
    models.dispose_engine()


def test_unusable_retained_backup_blocks_upgrade_without_replacement(
    tmp_path, monkeypatch
):
    from alembic import command
    import pytest

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260204_0003")
    models.dispose_engine()
    filename = tmp_path / "data/anibridge_jobs.db"
    original = filename.read_bytes()
    backup = filename.with_name(filename.name + ".pre-catalog-v3.backup")
    backup.write_bytes(b"damaged retained fixture")
    with pytest.raises(RuntimeError, match="Retained migration backup"):
        models.apply_migrations()
    assert filename.read_bytes() == original
    assert backup.read_bytes() == b"damaged retained fixture"
    assert not list(filename.parent.glob(".catalog-backup-*"))


def test_migration_startup_has_exclusive_ownership(tmp_path, monkeypatch):
    from alembic import command
    from catalog_core.files import ProcessLock
    from contextlib import closing
    import pytest

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260204_0003")
    models.dispose_engine()
    filename = tmp_path / "data/anibridge_jobs.db"
    original = filename.read_bytes()
    with closing(ProcessLock(filename.with_name(filename.name + ".migration.lock"))):
        with pytest.raises(RuntimeError, match="already owned"):
            models.apply_migrations()
        assert filename.read_bytes() == original
        assert not filename.with_name(filename.name + ".pre-catalog-v3.backup").exists()
    models.apply_migrations()
    assert _get_version(models) == HEAD_REVISION
    models.dispose_engine()


def test_backup_publication_never_overwrites_racing_backup(tmp_path, monkeypatch):
    from alembic import command
    import os
    import shutil

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260204_0003")
    filename = tmp_path / "data/anibridge_jobs.db"
    backup = filename.with_name(filename.name + ".pre-catalog-v3.backup")
    captured = []
    link = os.link

    def publish_race(source, destination):
        shutil.copyfile(source, destination)
        captured.append(destination.read_bytes())
        return link(source, destination)

    import importlib

    preflight = importlib.import_module("app.db.preflight")
    monkeypatch.setattr(preflight.os, "link", publish_race)
    models.apply_migrations()
    assert backup.read_bytes() == captured[0]
    assert not list(filename.parent.glob(".catalog-backup-*"))
    assert _get_version(models) == HEAD_REVISION
    models.dispose_engine()


def test_private_v7_upgrade_preserves_receipt_and_requires_context_recheck(
    tmp_path, monkeypatch
):
    from alembic import command

    models = _load_db(tmp_path, monkeypatch)
    command.upgrade(models._get_alembic_config(), "20260930_0007")
    row = (
        "source",
        "aniworld.to",
        7,
        b"retained signed bytes",
        "retained.sqlite",
        "a" * 64,
        3,
    )
    with models.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO catalog_version VALUES(?,?,?,?,?,?,?)", row
        )
    models.apply_migrations()
    with models.engine.connect() as connection:
        assert tuple(
            connection.exec_driver_sql("SELECT * FROM catalog_version").fetchone()
        ) == (*row, None)
    assert _get_version(models) == HEAD_REVISION
    models.apply_migrations()
    models.dispose_engine()
