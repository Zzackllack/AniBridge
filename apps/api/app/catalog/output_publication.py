"""Publish an owned verified file without overwriting a concurrently created path."""

import os
from pathlib import Path

from catalog_core.files import fsync_directory


def publish(staged: Path, target: Path) -> None:
    # Both paths live below one job directory. link is atomic and fails with
    # EEXIST; rename would overwrite a file created after our ownership check.
    os.link(staged, target, follow_symlinks=False)
    fsync_directory(target.parent)
    staged.unlink()
    fsync_directory(staged.parent)
