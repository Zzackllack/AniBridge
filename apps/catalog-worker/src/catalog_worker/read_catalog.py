"""One compact read catalog, atomically replaced after bounded validation."""

import fcntl
import hashlib
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from catalog_core import schema
from catalog_core.compact import release_summary
from catalog_core.diagnostics import phase
from catalog_core.files import ProcessLock, atomic_write, fsync_directory
from catalog_core.json_codec import dumps, loads, require
from catalog_core.manifest import TABLE_LIMITS
from catalog_core.validation_scope import capture, captured

from .config import Config
from .export import RebuildRequired, copy
from .publication_base import clone, receipt
from .publication_state import acknowledge
from .state import State
from .storage import check


@contextmanager
def lease(root: Path, *, write: bool = False, deadline_s: float = 2) -> Iterator[None]:
    """Readers own bytes until SQL settles; a writer never unlinks leased data."""
    with (root / "read.lock").open("a+b") as handle:
        end = time.monotonic() + deadline_s
        while True:
            try:
                fcntl.flock(
                    handle, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB
                )
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise TimeoutError("catalog_busy") from None
                time.sleep(0.01)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def provider_root(root: Path, provider: str) -> Path:
    return root if provider == "aniworld.to" else root / provider


def publish(config: Config, state: State, now: int, *, full: bool = False) -> dict:
    """A provider has one staging owner; its readers/collector remain independent."""
    root = provider_root(config.output_dir, state.provider)
    root.mkdir(parents=True, exist_ok=True)
    owner = ProcessLock(root / "publish.lock")
    try:
        return _publish(config, state, now, full=full)
    finally:
        owner.close()


def _publish(config: Config, state: State, now: int, *, full: bool = False) -> dict:
    """Export metadata only. No signed/compressed consumer artifact is built."""
    root = provider_root(config.output_dir, state.provider)
    root.mkdir(parents=True, exist_ok=True)
    # SQLite unlinks sort files while they remain open. Keep them under the
    # charged worker root so storage.used can account for their /proc descriptors.
    os.environ["SQLITE_TMPDIR"] = str(config.state_dir)
    destination = root / "staging.sqlite"
    # The staging owner lock proves no publisher still uses these names. Remove
    # abandoned SQLite sidecars too, before quota admission or opening a new DB:
    # a killed child can leave a hot rollback journal beside the old staging file.
    for suffix in ("", "-journal", "-wal", "-shm"):
        destination.with_name(destination.name + suffix).unlink(missing_ok=True)
    check(config, startup=True, public_reserve=1024**3)
    incremental = not full and clone(config, state, root, destination, now)
    db = (
        sqlite3.connect(destination)
        if incremental
        else schema.create(destination, version=2)
    )
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA temp_store=FILE")
    data_version = db.execute("PRAGMA data_version").fetchone()[0]
    if incremental:
        capture(db)
    end = time.monotonic() + 300
    last_storage_check = 0.0

    def exhausted() -> bool:
        nonlocal last_storage_check
        current = time.monotonic()
        # Quota accounting walks owned files and /proc descriptors. Doing that
        # every 10,000 VM instructions made it part of SQL's inner loop. Retain
        # the wall/file caps per callback and account storage four times/second.
        if current - last_storage_check >= 0.25:
            check(config)
            last_storage_check = current
        return current >= end or destination.stat().st_size > 1024**3

    db.set_progress_handler(exhausted, 10000)
    try:
        with phase("export"):
            snapshot = copy(
                db,
                str(state.db.execute("PRAGMA database_list").fetchone()[2]),
                state.provider,
                config.publication_sources,
                incremental=incremental,
            )
            with phase("export_summary"):
                counts = {name: schema.row_count(db, name, 2) for name in TABLE_LIMITS}
                # Exact compact groups replace repeated whole-catalog TV/language
                # counts while a poll's cutoff includes the entire group. A later
                # cutoff still uses SQL; bootstrap timestamps are not release dates.
                summary = release_summary(db)
    except (RebuildRequired, sqlite3.IntegrityError):
        db.close()
        destination.unlink(missing_ok=True)
        if not incremental:
            raise
        return _publish(config, state, now, full=True)
    except BaseException:
        db.close()
        destination.unlink(missing_ok=True)
        raise
    try:
        with destination.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        metadata = {
            "provider": state.provider,
            "source_id": config.source_id,
            "revision": 1,
            "catalog_schema_version": 2,
            "identity_version": 1,
            "published_at": now,
            "listing_checked_at": snapshot.listing_checked_at,
            "coverage": {"details": "partial", "mappings": "partial"},
            "counts": counts,
            "release_summary": summary,
            "artifact": {"sqlite_sha256": digest},
        }
        with phase("validation"):
            if incremental:
                schema.validate(destination, metadata, scope=captured(db))
            else:
                schema.validate(destination, metadata)
        require(
            db.execute("PRAGMA data_version").fetchone()[0] == data_version,
            "staging changed outside publisher",
        )
        with destination.open("rb") as stream:
            os.fsync(stream.fileno())
        with phase("publication_lock"), lease(root, write=True):  # noqa: SIM117 -- time lock acquisition before commit
            with phase("publication"):
                previous = (
                    loads((root / "current.json").read_bytes(), 65536)
                    if (root / "current.json").exists()
                    else {}
                )
                metadata["revision"] = previous.get("revision", 0) + 1
                # The pointer is the sole commit point. A crash leaves either the old
                # complete version or an unreferenced owned file for later cleanup.
                metadata["database"] = f"read-{digest}.sqlite"
                target = root / metadata["database"]
                # Replacing identical bytes also repairs an existing corrupted file.
                # The exclusive lease ensures no reader still owns the old inode.
                os.replace(destination, target)
                atomic_write(root / "current.json", dumps(metadata))
                fsync_directory(root)
                for old in root.glob("read-*.sqlite"):
                    if old.name != metadata["database"]:
                        old.unlink()
        acknowledge(
            state.db,
            snapshot.generation,
            snapshot.content_generation,
            receipt(config, metadata),
            now,
        )
        return metadata
    finally:
        db.close()
        destination.unlink(missing_ok=True)


def verify(root: Path) -> dict:
    """One startup digest check, never a full file read per search."""
    with lease(root):
        metadata = loads((root / "current.json").read_bytes(), 65536)
        with (root / metadata["database"]).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != metadata["artifact"]["sqlite_sha256"]:
            raise ValueError("catalog_pair_mismatch")
        return metadata
