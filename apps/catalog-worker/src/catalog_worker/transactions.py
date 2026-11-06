"""Nestable page checkpoints: sqlite connection contexts commit inner callers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def atomic(db: sqlite3.Connection) -> Iterator[None]:
    # SQLite permits nested savepoints with the same name; RELEASE and ROLLBACK
    # address the nearest one. The outermost release durably commits the page.
    db.execute("SAVEPOINT page_checkpoint")
    try:
        yield
        db.execute("RELEASE page_checkpoint")
    except BaseException:
        # SQLITE_FULL/INTERRUPT can already have rolled back the whole transaction.
        if db.in_transaction:
            db.execute("ROLLBACK TO page_checkpoint")
            db.execute("RELEASE page_checkpoint")
        raise
