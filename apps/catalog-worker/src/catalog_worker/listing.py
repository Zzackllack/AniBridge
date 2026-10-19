"""Persist a bounded listing traversal without admitting partial observations."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from itertools import batched

from catalog_core.json_codec import dumps, require

from .aniworld import Link, Page

DDL = """
CREATE TABLE IF NOT EXISTS listing_page(path TEXT PRIMARY KEY, complete INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS listing_record(path TEXT PRIMARY KEY, name TEXT NOT NULL, aliases TEXT NOT NULL);
"""
from .transactions import atomic


class Links:
    """Reiterable SQL cursor for final acceptance; never materialize the catalog."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def __len__(self) -> int:
        return self.db.execute("SELECT count(*) FROM listing_record").fetchone()[0]

    def __iter__(self) -> Iterator[Link]:
        for row in self.db.execute("SELECT * FROM listing_record ORDER BY path"):
            yield Link(row[0], row[1], tuple(json.loads(row[2])))

    def digest(self) -> str:
        value = hashlib.sha256()
        for link in self:
            value.update(dumps([link.path, link.name, link.aliases]) + b"\n")
        return value.hexdigest()


class Traversal:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def next_path(self, initial: str) -> str | None:
        with atomic(self.db):
            if not self.db.execute("SELECT 1 FROM listing_page").fetchone():
                self.db.execute("INSERT INTO listing_page(path) VALUES(?)", (initial,))
        row = self.db.execute(
            "SELECT path FROM listing_page WHERE complete=0 ORDER BY path LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def add(self, path: str, page: Page, batch_size: int = 100) -> bool:
        """Only the final complete traversal may count toward disappearance."""
        with atomic(self.db):
            for target in page.next_pages:
                # A next-page cycle is malformed, not a complete enumeration.
                existing = self.db.execute(
                    "SELECT complete FROM listing_page WHERE path=?", (target,)
                ).fetchone()
                require(
                    target != path and not (existing and existing[0]),
                    "listing pagination cycle",
                )
                self.db.execute(
                    "INSERT OR IGNORE INTO listing_page(path) VALUES(?)", (target,)
                )
            require(
                self.db.execute("SELECT count(*) FROM listing_page").fetchone()[0]
                <= 100,
                "listing page overflow",
            )
            # Buffer at most the configured row batch, but keep page acceptance
            # atomic. Committing individual batches would admit truncated pages.
            for batch in batched(page.links, batch_size):
                self.db.executemany(
                    "INSERT INTO listing_record VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET name=excluded.name,aliases=excluded.aliases",
                    (
                        (link.path, link.name, json.dumps(link.aliases))
                        for link in batch
                    ),
                )
            self.db.execute("UPDATE listing_page SET complete=1 WHERE path=?", (path,))
        return (
            self.db.execute("SELECT 1 FROM listing_page WHERE complete=0").fetchone()
            is None
        )

    def clear(self) -> None:
        # Caller owns the transaction so acceptance and removal are atomic.
        self.db.execute("DELETE FROM listing_page")
        self.db.execute("DELETE FROM listing_record")
