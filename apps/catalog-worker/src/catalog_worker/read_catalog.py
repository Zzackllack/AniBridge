"""One compact read catalog, atomically replaced after bounded validation."""

import fcntl
import hashlib
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from catalog_core import schema
from catalog_core.files import atomic_write, fsync_directory
from catalog_core.json_codec import dumps, loads
from catalog_core.manifest import TABLE_LIMITS

from .config import Config
from .export import copy
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


def publish(config: Config, state: State, now: int) -> dict:
    """Export metadata only. No signed/compressed consumer artifact is built."""
    root = provider_root(config.output_dir, state.provider)
    root.mkdir(parents=True, exist_ok=True)
    check(config, startup=True)
    destination = root / "staging.sqlite"
    destination.unlink(missing_ok=True)  # Owned scratch, under the worker owner lock.
    db = schema.create(destination, version=2)
    end = time.monotonic() + 300

    def exhausted() -> bool:
        check(config)
        return time.monotonic() >= end or destination.stat().st_size > 1024**3

    db.set_progress_handler(exhausted, 10000)
    try:
        copy(
            db,
            str(state.db.execute("PRAGMA database_list").fetchone()[2]),
            state.provider,
            config.publication_sources,
        )
        counts = {
            name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            for name in TABLE_LIMITS
        }
    finally:
        db.close()
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
            "listing_checked_at": state.meta()["listing_checked_at"],
            "coverage": {"details": "partial", "mappings": "partial"},
            "counts": counts,
            "artifact": {"sqlite_sha256": digest},
        }
        schema.validate(destination, metadata)
        with destination.open("rb") as stream:
            os.fsync(stream.fileno())
        with lease(root, write=True):
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
        with state.db:
            state.db.execute("UPDATE worker_meta SET dirty=0,published_at=?", (now,))
        return metadata
    finally:
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
