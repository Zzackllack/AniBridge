import os
from pathlib import Path

IN_DOCKER = Path("/.dockerenv").exists()
DEFAULT_DIR = Path("/data/downloads/anime") if IN_DOCKER else (Path.cwd() / "data" / "downloads" / "anime")

# Wohin wird heruntergeladen
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", DEFAULT_DIR))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Generischer Datenordner (DB, Caches, HTML-Snapshots)
DATA_DIR = Path(os.getenv("DATA_DIR", Path.cwd() / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Optional: lokaler Snapshot von https://aniworld.to/animes-alphabet
# -> lege ihn z.B. unter ./data/aniworld-alphabeth.html ab oder setze Pfad per ENV
ANIWORLD_ALPHABET_HTML = Path(os.getenv("ANIWORLD_ALPHABET_HTML", DATA_DIR / "aniworld-alphabeth.html"))

# Tag für die Quelle im Release-Namen
# Üblich: "WEB" oder "WEB-DL"
SOURCE_TAG = os.getenv("SOURCE_TAG", "WEB")