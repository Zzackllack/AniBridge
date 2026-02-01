from __future__ import annotations

from typing import Dict

from app.config import DOWNLOAD_DIR, QBIT_PUBLIC_SAVE_PATH


def public_save_path() -> str:
    """Return the path clients should see as the save location.

    If `QBIT_PUBLIC_SAVE_PATH` is set, always use it to avoid host-only paths
    leaking into containerized indexers. Otherwise fall back to our internal
    `DOWNLOAD_DIR`.
    """
    return QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR)


# Categories map compatible with qBittorrent format
CATEGORIES: Dict[str, dict] = {
    "prowlarr": {
        "name": "prowlarr",
        "savePath": QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR),
    }
}
