from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from loguru import logger

from app.config import DATA_DIR


@lru_cache(maxsize=1)
def prepare_aniworld_home() -> Path:
    """Ensure aniworld imports see a writable HOME directory."""

    current_home = os.getenv("HOME", "").strip()
    if current_home:
        try:
            home_path = Path(current_home).expanduser()
            home_path.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=home_path, delete=False) as probe_file:
                probe_path = Path(probe_file.name)
                probe_file.write(b"ok")
            probe_path.unlink()
            os.environ["HOME"] = str(home_path)
            os.environ.setdefault("USERPROFILE", str(home_path))
            return home_path
        except OSError:
            logger.debug(
                "Configured HOME is not writable for aniworld: {}", current_home
            )

    fallback_candidates = [
        DATA_DIR / "aniworld-home",
        Path(tempfile.gettempdir()) / "anibridge-aniworld-home",
    ]
    last_error: OSError | None = None

    for fallback_home in fallback_candidates:
        try:
            fallback_home.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=fallback_home, delete=False
            ) as probe_file:
                probe_path = Path(probe_file.name)
                probe_file.write(b"ok")
            probe_path.unlink()
            os.environ["HOME"] = str(fallback_home)
            os.environ.setdefault("USERPROFILE", str(fallback_home))
            logger.debug("Using AniWorld runtime HOME fallback: {}", fallback_home)
            return fallback_home
        except OSError as exc:
            last_error = exc
            logger.debug(
                "AniWorld runtime HOME fallback is not writable: {} ({})",
                fallback_home,
                exc,
            )

    raise RuntimeError(
        "Could not create a writable HOME for aniworld imports"
    ) from last_error
