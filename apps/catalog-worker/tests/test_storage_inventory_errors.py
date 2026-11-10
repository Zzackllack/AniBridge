"""Unknown storage cannot be counted as zero bytes for quota admission."""

import os

import pytest

from catalog_worker.storage import used


def test_unreadable_subdirectory_refuses_storage_accounting(tmp_path, monkeypatch):
    root = tmp_path / "state"
    root.mkdir()
    (root / "ledger").write_bytes(b"retained")
    original = os.walk

    def inaccessible(directory, *args, **kwargs):
        if kwargs.get("onerror"):
            kwargs["onerror"](PermissionError(13, "private-path", str(root / "backup")))
        yield from original(directory, *args, **kwargs)

    monkeypatch.setattr(os, "walk", inaccessible)
    with pytest.raises(ValueError, match="storage_inventory_unavailable"):
        used(root)


def test_concurrent_directory_removal_is_not_an_unreadable_inventory(
    tmp_path, monkeypatch
):
    original = os.walk

    def rotated(directory, *args, **kwargs):
        if kwargs.get("onerror"):
            kwargs["onerror"](
                FileNotFoundError(2, "rotation", str(tmp_path / "retired"))
            )
        yield from original(directory, *args, **kwargs)

    monkeypatch.setattr(os, "walk", rotated)
    assert used(tmp_path) >= 0


def test_non_linux_storage_walk_does_not_require_proc(tmp_path, monkeypatch):
    monkeypatch.setattr("catalog_worker.storage.sys.platform", "darwin")
    (tmp_path / "ledger").write_bytes(b"retained")
    assert used(tmp_path) >= len(b"retained")


def test_proc_inventory_io_failure_is_not_counted_as_empty(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.setattr("catalog_worker.storage.sys.platform", "linux")
    original_is_dir, original_iterdir = Path.is_dir, Path.iterdir

    def is_dir(path):
        return True if path == Path("/proc") else original_is_dir(path)

    def iterdir(path):
        if path == Path("/proc"):
            raise OSError(5, "synthetic inventory I/O failure")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    monkeypatch.setattr(Path, "iterdir", iterdir)
    with pytest.raises(ValueError, match="storage_inventory_unavailable"):
        used(tmp_path)
