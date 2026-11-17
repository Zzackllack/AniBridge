"""Disk-backed TTL ownership snapshot without a set growing with job history."""

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from itertools import batched
from pathlib import Path


class DirectoryGuard:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def protects(self, directory: Path) -> bool:
        # Ancestor count depends on filesystem depth, never on job count. Exact
        # indexed lookup avoids prefix collisions and SQL LIKE wildcard paths.
        for parent in (directory, *directory.parents):
            if self.db.execute(
                "SELECT 1 FROM protected_directory WHERE path=?", (str(parent),)
            ).fetchone():
                return True
        return False


@contextmanager
def directory_guard(paths: Iterable[Path]) -> Iterator[DirectoryGuard]:
    with closing(sqlite3.connect("")) as db:
        # Empty filename creates an automatically deleted temporary database.
        # The spool lives outside user data and is closed after the cleanup pass.
        db.execute("PRAGMA cache_size=-2048")
        db.execute("PRAGMA mmap_size=0")
        db.execute(
            "CREATE TABLE protected_directory(path TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        with db:
            for batch in batched(paths, 100):
                db.executemany(
                    "INSERT OR IGNORE INTO protected_directory VALUES(?)",
                    ((str(path),) for path in batch),
                )
        yield DirectoryGuard(db)
