from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from app.config import DATA_DIR


def prepare_aniworld_home() -> Path:
    """Ensure aniworld imports see a writable HOME directory."""

    current_home = os.getenv("HOME", "").strip()
    if current_home:
        try:
            home_path = Path(current_home).expanduser()
            home_path.mkdir(parents=True, exist_ok=True)
            return home_path
        except OSError:
            logger.debug("Configured HOME is not writable for aniworld: {}", current_home)

    fallback_home = DATA_DIR / "aniworld-home"
    fallback_home.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(fallback_home)
    os.environ.setdefault("USERPROFILE", str(fallback_home))
    logger.debug("Using AniWorld runtime HOME fallback: {}", fallback_home)
    return fallback_home
