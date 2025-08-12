import os
from pathlib import Path

IN_DOCKER = Path("/.dockerenv").exists()
DEFAULT_DIR = Path("/data/downloads/anime") if IN_DOCKER else (Path.cwd() / "data" / "downloads" / "anime")

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", DEFAULT_DIR))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
