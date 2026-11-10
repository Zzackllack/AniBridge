"""One finite worker budget, including state, backups, logs and build output."""

import os
import shutil
import stat as file_stat
import sys
from pathlib import Path

from catalog_core.json_codec import require

from .config import Config

MIB = 1024**2
BUILD_RESERVE = 1280 * MIB + 65536
STATE_HEADROOM = 512 * MIB
# Covers the installed worker image, config/key mount and bounded daemon logs.
# Persistent writable worker data must stay under state/output, not elsewhere.
RUNTIME_ALLOWANCE = 1_000_000_000


def inventory_error(error: OSError) -> None:
    if not isinstance(error, FileNotFoundError):
        # Permission/I/O failures are unknown usage, not empty directories.
        # Atomic retirement during traversal may legitimately remove a path.
        # Unavailable inventory is not a caller type error; keep the contract
        # reason used by storage admission and tests.
        raise ValueError("storage_inventory_unavailable") from None  # noqa: TRY004


def used(directory: Path) -> int:
    """Count logical or allocated bytes, whichever is larger; deduplicate links.

    Sparse files cannot hide their eventual capacity cost. Count WAL, temporary
    files, directories and backups too; do not follow operator symlinks.
    """
    total, seen = 0, set()
    for root, directories, files in os.walk(
        directory, followlinks=False, onerror=inventory_error
    ):
        for path in [
            Path(root),
            *(Path(root) / n for n in files),
            *(Path(root) / n for n in directories if (Path(root) / n).is_symlink()),
        ]:
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue  # Concurrent atomic publication/rotation.
            key = (stat.st_dev, stat.st_ino)
            if key not in seen:
                total += max(stat.st_size, getattr(stat, "st_blocks", 0) * 512)
                seen.add(key)
    # SQLite unlinks temporary sort files while keeping descriptors open. Linux
    # /proc metadata keeps those allocated bytes visible to quota accounting.
    # Other platforms have no equivalent walk; --publish refuses to claim the
    # quota was enforced there. Inspect descriptor metadata only, never content.
    proc = Path("/proc")
    if sys.platform.startswith("linux") and proc.is_dir():
        try:
            processes = list(proc.iterdir())
        except OSError:
            raise ValueError("storage_inventory_unavailable") from None
        for process in processes:
            if not process.name.isdecimal():
                continue
            try:
                descriptors = list((process / "fd").iterdir())
            except PermissionError, FileNotFoundError, ProcessLookupError:
                continue  # Exited process or hidden descriptor table.
            for descriptor in descriptors:
                try:
                    target = os.readlink(descriptor)
                    if not target.endswith(" (deleted)"):
                        continue
                    target_path = Path(target.removesuffix(" (deleted)"))
                    if not target_path.is_relative_to(directory.resolve()):
                        continue
                    stat = descriptor.stat()
                    key = (stat.st_dev, stat.st_ino)
                    if file_stat.S_ISREG(stat.st_mode) and key not in seen:
                        total += max(stat.st_size, getattr(stat, "st_blocks", 0) * 512)
                        seen.add(key)
                except PermissionError, FileNotFoundError, ProcessLookupError:
                    continue  # Descriptor/process raced with the walk.
    return total


def filesystem(directory: Path) -> Path:
    while not directory.exists():
        directory = directory.parent
    return directory


def status(config: Config) -> dict:
    state_used, public_used = used(config.state_dir), used(config.output_dir)
    result = {
        "state_used_bytes": state_used,
        "public_used_bytes": public_used,
        "managed_used_bytes": state_used + public_used,
        "runtime_reserved_bytes": RUNTIME_ALLOWANCE,
        "total_used_bytes": state_used + public_used + RUNTIME_ALLOWANCE,
        "state_quota_bytes": config.limits["state_disk_bytes"],
        "public_quota_bytes": config.limits["public_disk_bytes"],
        "total_quota_bytes": config.limits["total_disk_bytes"],
        "state_free_bytes": shutil.disk_usage(filesystem(config.state_dir)).free,
        "public_free_bytes": shutil.disk_usage(filesystem(config.output_dir)).free,
    }
    result["warning"] = (
        state_used * 5 >= result["state_quota_bytes"] * 4
        or public_used * 5 >= result["public_quota_bytes"] * 4
        or result["total_used_bytes"] * 5 >= result["total_quota_bytes"] * 4
        or min(result["state_free_bytes"], result["public_free_bytes"])
        < BUILD_RESERVE + STATE_HEADROOM
    )
    return result


def check(
    config: Config,
    *,
    startup: bool = False,
    public_reserve: int = 0,
    state_reserve: int = STATE_HEADROOM,
) -> dict:
    current = status(config)
    require(
        current["state_used_bytes"] + state_reserve <= current["state_quota_bytes"]
        and current["public_used_bytes"] + public_reserve
        <= current["public_quota_bytes"]
        and current["total_used_bytes"] + state_reserve + public_reserve
        <= current["total_quota_bytes"],
        "storage_full",
    )
    # Free space is admission headroom, not a claim about thin physical backing.
    same = (
        filesystem(config.state_dir).stat().st_dev
        == filesystem(config.output_dir).stat().st_dev
    )
    require(
        current["public_free_bytes"] >= BUILD_RESERVE + (state_reserve if same else 0)
        and current["state_free_bytes"] >= state_reserve,
        "storage_full",
    )
    return current


def migration_reserve(config: Config) -> int:
    """Admit existing no-overwrite pilot backups before starting any upgrade."""
    import sqlite3
    from contextlib import closing

    reserve = STATE_HEADROOM
    for provider in config.providers:
        filename = config.state_dir / f"{provider}.sqlite"
        if not filename.is_file():
            continue
        with closing(
            sqlite3.connect(filename.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            version = db.execute("SELECT version FROM worker_schema").fetchone()[0]
            # The backup includes committed WAL pages too; the main file alone
            # can understate the migration reserve on an active WAL database.
            backup_bytes = (
                db.execute("PRAGMA page_count").fetchone()[0]
                * db.execute("PRAGMA page_size").fetchone()[0]
            )
        # An interrupted Filmo v6->v8 chain can leave a valid v7 database plus
        # the earlier .pre-v7 backup. The next run adds .pre-v8, so version 7
        # also needs a reserve; older code stopped at v6 and under-counted the
        # second backup. Existing backups are already charged by used().
        target = 8 if provider == "filmo.to" else 7
        if (
            version < target
            and not filename.with_name(
                filename.name + f".pre-v{version + 1}.backup"
            ).exists()
        ):
            reserve += backup_bytes
    return reserve


def recover_scratch(directory: Path) -> None:
    """Remove only reserved abandoned private scratch after the worker lock."""
    import re

    from catalog_core.files import fsync_directory

    changed = False
    for path in directory.iterdir():
        if path.is_symlink():
            continue
        if re.fullmatch(r"parse-[a-z0-9_]{8}", path.name) and path.is_dir():
            shutil.rmtree(path)
            changed = True
        elif (
            re.fullmatch(r"\.worker-(?:backup|create)-[a-z0-9_]{8}", path.name)
            and path.is_file()
        ):
            path.unlink()
            changed = True
    if changed:
        fsync_directory(directory)
