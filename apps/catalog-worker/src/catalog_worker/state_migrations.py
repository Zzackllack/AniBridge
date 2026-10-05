"""Read-only preflight and atomic upgrades for the worker's own SQLite state.

No downloaded artifact or API database is accepted as a worker database. The
Recognised private pilot v1/v2 upgrades retain each original backup untouched.
"""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from catalog_core import schema
from catalog_core.files import fsync_directory
from catalog_core.json_codec import require

from .incremental_schema import DDL as INCREMENTAL_DDL
from .incremental_schema import VERSION_DDL as INCREMENTAL_VERSION_DDL
from .listing import DDL as LISTING_DDL
from .state_schema import PRIVATE_DDL

VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=2))"


def definitions(db: sqlite3.Connection) -> dict[str, tuple]:
    return {
        name: (kind, table, " ".join(sql.split()) if sql else None)
        for kind, name, table, sql in db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
        )
    }


def preflight(filename: Path, provider: str) -> int:
    with closing(
        sqlite3.connect(filename.resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        # Match the documented fixed pager budget during integrity/reference
        # checks too; the default 2-MiB cache thrashes large relationship indexes.
        db.execute("PRAGMA cache_size=-32768")
        db.execute("PRAGMA mmap_size=0")
        tables = definitions(db)
        require("worker_schema" in tables, "unrecognized worker database")
        rows = db.execute("SELECT version FROM worker_schema").fetchall()
        require(rows in ([(1,)], [(2,)], [(3,)]), "unsupported worker state version")
        version = rows[0][0]
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.executescript(schema.DDL + PRIVATE_DDL)
            if version >= 2:
                expected.execute("DROP TABLE worker_schema")
                expected.execute(VERSION_DDL)
            expected.executescript(LISTING_DDL)
            if version == 3:
                expected.executescript(INCREMENTAL_DDL)
                expected.execute("DROP TABLE worker_schema")
                expected.execute(INCREMENTAL_VERSION_DDL)
            contract = definitions(expected)
        # Early version-1 state created traversal tables on its first listing.
        if version == 1 and not {"listing_page", "listing_record"} & tables.keys():
            for name in ("listing_page", "listing_record"):
                del contract[name]
        require(tables == contract, "unsupported worker table contract")
        require(
            db.execute("SELECT provider FROM catalog").fetchall() == [(provider,)],
            "wrong worker state",
        )
        require(
            db.execute("PRAGMA quick_check").fetchone() == ("ok",),
            "corrupt worker state",
        )
        require(
            not db.execute("PRAGMA foreign_key_check").fetchone(),
            "broken worker references",
        )
        return version


def verify_backup(filename: Path, provider: str, version: int = 1) -> None:
    require(filename.is_file() and not filename.is_symlink(), "unsafe worker backup")
    require(preflight(filename, provider) == version, "wrong worker backup version")


def backup(
    filename: Path, provider: str, checkpoint=lambda stage: None, version: int = 1
) -> None:
    saved = filename.with_name(filename.name + f".pre-v{version + 1}.backup")
    if saved.exists() or saved.is_symlink():
        verify_backup(saved, provider, version)
        return
    descriptor, temporary = tempfile.mkstemp(
        prefix=".worker-backup-", dir=filename.parent
    )
    os.close(descriptor)
    path = Path(temporary)
    try:
        with (
            closing(sqlite3.connect(filename)) as source,
            closing(sqlite3.connect(path)) as target,
        ):
            source.backup(target)
        verify_backup(path, provider, version)
        checkpoint("backup-copy")
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
        checkpoint("backup-file-sync")
        # A restart/racing backup must never replace the original recovery copy.
        # Hard-link publication fails atomically when the destination exists.
        try:
            os.link(path, saved)
        except FileExistsError:
            verify_backup(saved, provider, version)
        checkpoint("backup-link")
        fsync_directory(filename.parent)
        checkpoint("backup-directory-sync")
    finally:
        path.unlink(missing_ok=True)


def upgrade(db: sqlite3.Connection, checkpoint) -> None:
    db.execute("BEGIN IMMEDIATE")
    try:
        for statement in LISTING_DDL.split(";"):
            if statement.strip():
                db.execute(statement)
        checkpoint("tables")
        db.execute("DROP TABLE worker_schema")
        db.execute(VERSION_DDL)
        db.execute("INSERT INTO worker_schema VALUES(2)")
        checkpoint("version")
        db.commit()
        checkpoint("commit")
    except BaseException:
        db.rollback()
        raise


def upgrade_incremental(db: sqlite3.Connection, checkpoint) -> None:
    db.execute("BEGIN IMMEDIATE")
    try:
        for statement in INCREMENTAL_DDL.split(";"):
            if statement.strip():
                db.execute(statement)
        checkpoint("incremental-tables")
        db.execute("DROP TABLE worker_schema")
        db.execute(INCREMENTAL_VERSION_DDL)
        db.execute("INSERT INTO worker_schema VALUES(3)")
        checkpoint("incremental-version")
        db.commit()
        checkpoint("incremental-commit")
    except BaseException:
        db.rollback()
        raise


def initialize(filename: Path, provider: str, checkpoint=lambda stage: None) -> None:
    if filename.exists():
        version = preflight(filename, provider)
        if version == 3:
            return
        backup(filename, provider, checkpoint, version)
        with closing(sqlite3.connect(filename)) as db:
            db.execute("PRAGMA synchronous=FULL")
            if version == 1:
                upgrade(db, checkpoint)
            upgrade_incremental(db, checkpoint)
        return
    descriptor, temporary = tempfile.mkstemp(
        prefix=".worker-create-", dir=filename.parent
    )
    os.close(descriptor)
    path = Path(temporary)
    try:
        with closing(sqlite3.connect(path)) as db:
            db.executescript(schema.DDL + PRIVATE_DDL)
            db.execute("INSERT INTO catalog VALUES(1,?,1,1,0)", (provider,))
            db.commit()
            upgrade(db, checkpoint)
            upgrade_incremental(db, checkpoint)
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
        os.rename(path, filename)
        fsync_directory(filename.parent)
    finally:
        path.unlink(missing_ok=True)
