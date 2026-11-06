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
