"""Ownership requires actual exclusion, including on shared Docker filesystems."""

import os

import pytest

from catalog_core.files import ProcessLock


@pytest.mark.skipif(os.name == "nt", reason="POSIX flock exclusion")
def test_process_lock_rejects_another_open_handle_and_releases_on_close(tmp_path):
    path = tmp_path / "owner.lock"
    owner = ProcessLock(path)
    try:
        with pytest.raises(RuntimeError, match="already owned"):
            ProcessLock(path)
    finally:
        owner.close()
    reopened = ProcessLock(path)
    reopened.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX flock exclusion")
def test_process_lock_refuses_a_filesystem_that_ignores_exclusion(
    tmp_path, monkeypatch
):
    import fcntl

    path = tmp_path / "owner.lock"
    with monkeypatch.context() as patch:
        patch.setattr(fcntl, "flock", lambda *args: None)
        with pytest.raises(RuntimeError, match="does not enforce process locks"):
            ProcessLock(path)
    # Refusal must close every handle; an ordinary lock can still be acquired.
    owner = ProcessLock(path)
    owner.close()
