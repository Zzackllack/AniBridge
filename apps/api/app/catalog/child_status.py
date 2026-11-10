"""Read atomically replaced status snapshots from supervised children."""

import asyncio
from pathlib import Path

from catalog_core.json_codec import loads, require

MAX_STATUS_BYTES = 65536


def read_status(path: Path) -> dict | None:
    """Read one bounded snapshot; a missing name can be a visibility gap."""
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_STATUS_BYTES + 1)
    except FileNotFoundError:
        return None
    status = loads(data, MAX_STATUS_BYTES)
    require(isinstance(status, dict), "invalid child status")
    require(
        status.get("phase") in ("resolving", "downloading", "finished"),
        "invalid child status phase",
    )
    return status


async def read_finished_status(path: Path) -> dict | None:
    """A successful exit needs a terminal receipt, even on a shared mount."""
    for poll in range(3):
        if poll:
            await asyncio.sleep(0.2)
        status = read_status(path)
        if status is not None and status.get("phase") == "finished":
            return status
    return None
