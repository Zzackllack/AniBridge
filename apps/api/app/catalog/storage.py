"""Admission checks shared by optional private metadata writers."""

import shutil
from pathlib import Path


def writable(database: Path, limit: int, additional: int = 0) -> bool:
    # Account for WAL growth too. Leave room for a small transaction rather than
    # consuming the reserve merely because its serialized payload is tiny.
    reserve = max(65536, additional * 2)
    used = sum(
        path.stat().st_size
        for path in (database, database.with_name(database.name + "-wal"))
        if path.exists()
    )
    return (
        used + reserve <= limit
        and shutil.disk_usage(database.parent).free >= 512 * 1024**2 + reserve
    )
