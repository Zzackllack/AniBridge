import os
from pathlib import Path

IN_DOCKER = Path("/.dockerenv").exists()

# Wohin wird heruntergeladen
DEFAULT_DIR = Path("/data/downloads/anime") if IN_DOCKER else (Path.cwd() / "data" / "downloads" / "anime")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", DEFAULT_DIR))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Generischer Datenordner (DB, Caches, HTML-Snapshots)
DATA_DIR = Path(os.getenv("DATA_DIR", Path.cwd() / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Titelquelle (Slug -> Display-Title)
# Option A: lokale HTML-Datei (Snapshot der Alphabet-Seite)
ANIWORLD_ALPHABET_HTML = Path(os.getenv("ANIWORLD_ALPHABET_HTML", DATA_DIR / "aniworld-alphabeth.html"))
# Option B: Live von der Website holen (immer up-to-date)
ANIWORLD_ALPHABET_URL = os.getenv("ANIWORLD_ALPHABET_URL", "https://aniworld.to/animes-alphabet").strip()

# TTL (Stunden) für Live-Index; 0 = nie neu laden (nur einmal pro Prozess)
ANIWORLD_TITLES_REFRESH_HOURS = float(os.getenv("ANIWORLD_TITLES_REFRESH_HOURS", "24"))

# Quelle/Source-Tag im Release-Namen (typisch: WEB, WEB-DL)
SOURCE_TAG = os.getenv("SOURCE_TAG", "WEB")

# Release Group (am Ende nach Bindestrich angehängt)
RELEASE_GROUP = os.getenv("RELEASE_GROUP", "aniworld")

# ---- Provider-Fallback ----
# Kommagetrennte Liste, z. B. "VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza"
# Reihenfolge = Priorität
_default_order = "VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza"
_raw = os.getenv("PROVIDER_ORDER", _default_order)

# normalisieren: split, trim, nur nicht-leere nehmen, Groß/Kleinschreibung egal
PROVIDER_ORDER = [p.strip() for p in _raw.split(",") if p.strip()]