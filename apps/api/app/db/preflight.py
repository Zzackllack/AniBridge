"""Reject foreign databases before stamping; retain a durable upgrade backup."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from catalog_core.files import fsync_directory

HEAD = "20261003_0008"
REVISIONS = {
    "20260203_0001",
    "20260203_0002",
    "20260204_0003",
    "20260927_0004",
    "20260928_0005",
    "20260929_0006",
    "20260930_0007",
    HEAD,
}
BASE = {
    "job": {
        "id",
        "status",
        "progress",
        "downloaded_bytes",
        "total_bytes",
        "speed",
        "eta",
        "message",
        "result_path",
        "source_site",
        "created_at",
        "updated_at",
    },
    "clienttask": {
        "hash",
        "name",
        "slug",
        "season",
        "episode",
        "language",
        "site",
        "job_id",
        "save_path",
        "category",
        "added_on",
        "completion_on",
        "state",
    },
    "episodeavailability": {
        "slug",
        "season",
        "episode",
        "language",
        "site",
        "available",
        "height",
        "vcodec",
        "provider",
        "checked_at",
        "extra",
    },
    "strmurlmapping": {
        "site",
        "slug",
        "season",
        "episode",
        "language",
        "provider",
        "resolved_url",
        "provider_used",
        "resolved_headers",
        "resolved_at",
        "updated_at",
    },
}
ADDITIONS = {
    "catalog_source",
    "catalog_clock",
    "catalog_trust",
    "catalog_version",
    "catalog_active",
    "durable_request",
    "grab_alias",
    "catalog_override",
    "catalog_task",
    "management_idempotency",
    "catalog_cache",
}


def verify_backup(filename: Path) -> None:
    """Refuse an unusable retained backup instead of silently replacing it."""
    if filename.is_symlink() or not filename.is_file():
        raise RuntimeError("Retained migration backup is not a regular file")
    try:
        with closing(
            sqlite3.connect(
                filename.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
            )
        ) as db:
            if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise RuntimeError("Retained migration backup failed integrity check")
            tables = {
                r[0]
                for r in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            versions = (
                db.execute("SELECT version_num FROM alembic_version").fetchall()
                if "alembic_version" in tables
                else []
            )
            revision = versions[0][0] if len(versions) == 1 else None
            if len(versions) > 1 or revision is not None and revision not in REVISIONS:
                raise RuntimeError(
                    "Retained migration backup has an unsupported revision"
                )
            expected = set(BASE)
            if revision in ("20260203_0001", "20260203_0002"):
                expected.remove("strmurlmapping")
            if revision in (
                "20260927_0004",
                "20260928_0005",
                "20260929_0006",
                "20260930_0007",
                HEAD,
            ):
                expected |= ADDITIONS
            if revision in ("20260928_0005", "20260929_0006", "20260930_0007", HEAD):
                expected |= {"catalog_control", "catalog_update"}
            if tables - {"alembic_version"} != expected:
                raise RuntimeError(
                    "Retained migration backup has an unsupported schema"
                )
    except sqlite3.Error:
        raise RuntimeError("Retained migration backup cannot be read") from None


def backup_before_upgrade(filename: Path) -> None:
    """Inspect read-only first. Backups are never replaced or removed automatically."""
    if not filename.exists() or filename.stat().st_size == 0:
        return
    source = sqlite3.connect(filename.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        objects = source.execute(
            "SELECT type,name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if any(kind in ("trigger", "view") for kind, _ in objects):
            raise RuntimeError("Unsupported private database schema: views/triggers")
        tables = {name for kind, name in objects if kind == "table"}
        versions = (
            source.execute("SELECT version_num FROM alembic_version").fetchall()
            if "alembic_version" in tables
            else []
        )
        if len(versions) > 1 or (versions and versions[0][0] not in REVISIONS):
            raise RuntimeError("Unsupported private database revision")
        revision = versions[0][0] if versions else None
        data = tables - {"alembic_version"}
        if not data:
            return
        expected = set(BASE)
        if revision in ("20260203_0001", "20260203_0002"):
            expected.remove("strmurlmapping")
        if revision in (
            "20260927_0004",
            "20260928_0005",
            "20260929_0006",
            "20260930_0007",
            HEAD,
        ):
            expected |= ADDITIONS
        if revision in ("20260928_0005", "20260929_0006", "20260930_0007", HEAD):
            expected |= {"catalog_control", "catalog_update"}
        if data != expected:
            raise RuntimeError(
                "Unsupported private database tables; no schema was changed"
            )
        for table, columns in BASE.items():
            if table not in data:
                continue
            expected_columns = (
                columns - {"site"}
                if table == "episodeavailability" and revision == "20260203_0001"
                else columns
            )
            actual = {row[1] for row in source.execute(f"PRAGMA table_info({table})")}
            if actual != expected_columns:
                raise RuntimeError(
                    "Unsupported private database columns; no schema was changed"
                )
            from app.db.models import ModelBase

            model = ModelBase.metadata.tables[table]
            primary = [
                column.name
                for column in model.primary_key
                if column.name in expected_columns
            ]
            for _, name, declared_type, not_null, default, pk in source.execute(
                f"PRAGMA table_info({table})"
            ):
                column = model.columns[name]
                actual_type = declared_type.upper().split("(")[0]
                expected_type = str(column.type).upper().split("(")[0]
                if actual_type in ("TEXT", "VARCHAR"):
                    actual_type = "TEXT"
                if expected_type in ("TEXT", "VARCHAR"):
                    expected_type = "TEXT"
                expected_pk = primary.index(name) + 1 if name in primary else 0
                allowed_defaults = (
                    (None, "'aniworld.to'")
                    if table == "episodeavailability" and name == "site"
                    else (None,)
                )
                if (
                    actual_type != expected_type
                    or bool(not_null) != (not column.nullable)
                    or pk != expected_pk
                    or default not in allowed_defaults
                ):
                    raise RuntimeError("Unsupported private database column contract")
            if source.execute(f"PRAGMA foreign_key_list({table})").fetchall():
                raise RuntimeError("Unsupported private database foreign keys")
        if revision in (
            "20260927_0004",
            "20260928_0005",
            "20260929_0006",
            "20260930_0007",
            HEAD,
        ):
            from app.catalog.state_schema import (
                STATEMENTS,
                V4_STATEMENTS,
                V5_STATEMENTS,
                V6_STATEMENTS,
                V7_STATEMENTS,
            )

            with closing(sqlite3.connect(":memory:")) as expected_db:
                statements = {
                    "20260927_0004": V4_STATEMENTS,
                    "20260928_0005": V5_STATEMENTS,
                    "20260929_0006": V6_STATEMENTS,
                    "20260930_0007": V7_STATEMENTS,
                    HEAD: STATEMENTS,
                }[revision]
                for statement in statements:
                    expected_db.execute(statement)
                expected_sql = dict(
                    expected_db.execute(
                        "SELECT name,sql FROM sqlite_schema WHERE type='table'"
                    )
                )
            for table in expected - set(BASE):
                actual_sql = source.execute(
                    "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()[0]
                if " ".join(actual_sql.split()) != " ".join(
                    expected_sql[table].split()
                ):
                    raise RuntimeError("Unsupported catalog private table contract")
            if revision == HEAD:
                return
        backup = filename.with_name(filename.name + ".pre-catalog-v3.backup")
        if backup.exists():
            verify_backup(backup)
            return
        descriptor, name = tempfile.mkstemp(
            prefix=".catalog-backup-", dir=backup.parent
        )
        os.close(descriptor)
        temporary = Path(name)
        try:
            with closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
            verify_backup(temporary)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            try:
                # Never overwrite a backup created by another startup or by an
                # operator between the existence check and publication.
                os.link(temporary, backup)
            except FileExistsError:
                verify_backup(backup)
            fsync_directory(backup.parent)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        source.close()
