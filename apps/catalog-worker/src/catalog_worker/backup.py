"""One no-overwrite SQLite backup set, charged to the same worker budget."""

import sqlite3
from contextlib import closing
from pathlib import Path

from catalog_core.files import fsync_directory
from catalog_core.json_codec import require

from .config import Config
from .storage import check


def backup(config: Config) -> Path:
    root = config.state_dir / "backup"
    require(not root.exists(), "backup already exists; retain or remove it explicitly")
    files = [config.state_dir / f"{provider}.sqlite" for provider in config.providers]
    files = [path for path in files if path.exists()]
    require(bool(files), "no worker state")
    reserve = sum(
        path.stat().st_size + path.with_name(path.name + "-wal").stat().st_size
        if path.with_name(path.name + "-wal").exists()
        else path.stat().st_size
        for path in files
    )
    check(config, state_reserve=reserve + 512 * 1024**2)
    root.mkdir(mode=0o700)
    # Write the fence first: SIGKILL cannot run an exception handler.
    incomplete = root / "INCOMPLETE"
    incomplete.touch()
    fsync_directory(root)
    fsync_directory(config.state_dir)
    try:
        for path in files:
            with (
                closing(
                    sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
                ) as source,
                closing(sqlite3.connect(root / path.name)) as target,
            ):
                source.backup(target)
                require(
                    target.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                    "invalid backup",
                )
        incomplete.unlink()
        fsync_directory(root)
        return root
    except BaseException:
        # Incomplete sets are visibly incomplete and cannot look restorable.
        (root / "INCOMPLETE").touch()
        raise
