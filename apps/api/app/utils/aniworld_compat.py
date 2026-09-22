from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from loguru import logger

from app.config import DATA_DIR


@lru_cache(maxsize=1)
def prepare_aniworld_home() -> Path:
    """Configure an isolated writable directory before importing ``aniworld``."""

    configured = os.getenv("ANIWORLD_INSTALL_FOLDER", "").strip()
    install_dir = Path(configured).expanduser() if configured else DATA_DIR / "aniworld"
    if not install_dir.is_absolute():
        install_dir = (Path.cwd() / install_dir).resolve()
    else:
        install_dir = install_dir.resolve()

    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=install_dir, delete=False) as probe_file:
            probe_path = Path(probe_file.name)
            probe_file.write(b"ok")
        probe_path.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"ANIWORLD_INSTALL_FOLDER is not writable: {install_dir}"
        ) from exc

    # Upstream reads and may merge its own .env during import. Point it at
    # AniBridge-owned persistent storage without changing process HOME.
    os.environ["ANIWORLD_INSTALL_FOLDER"] = str(install_dir)
    logger.debug("AniWorld runtime directory: {}", install_dir)
    return install_dir
