import sys
import os
from loguru import logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

from pathlib import Path

logger.debug("Checking if running in Docker...")
IN_DOCKER = Path("/.dockerenv").exists()
logger.debug(f"IN_DOCKER={IN_DOCKER}")

# Wohin wird heruntergeladen
DEFAULT_DIR = (
    Path("/data/downloads/anime")
    if IN_DOCKER
    else (Path.cwd() / "data" / "downloads" / "anime")
)
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", DEFAULT_DIR))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
logger.debug(f"DOWNLOAD_DIR set to {DOWNLOAD_DIR}")

# Generischer Datenordner (DB, Caches, HTML-Snapshots)
DATA_DIR = Path(os.getenv("DATA_DIR", Path.cwd() / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
logger.debug(f"DATA_DIR set to {DATA_DIR}")

# Titelquelle (Slug -> Display-Title)
# Option A: lokale HTML-Datei (Snapshot der Alphabet-Seite)
ANIWORLD_ALPHABET_HTML = Path(
    os.getenv("ANIWORLD_ALPHABET_HTML", DATA_DIR / "aniworld-alphabeth.html")
)
# Option B: Live von der Website holen (immer up-to-date)
ANIWORLD_ALPHABET_URL = os.getenv(
    "ANIWORLD_ALPHABET_URL", "https://aniworld.to/animes-alphabet"
).strip()
logger.debug(
    f"ANIWORLD_ALPHABET_HTML={ANIWORLD_ALPHABET_HTML}, ANIWORLD_ALPHABET_URL={ANIWORLD_ALPHABET_URL}"
)

# TTL (Stunden) für Live-Index; 0 = nie neu laden (nur einmal pro Prozess)
ANIWORLD_TITLES_REFRESH_HOURS = float(os.getenv("ANIWORLD_TITLES_REFRESH_HOURS", "24"))
logger.debug(f"ANIWORLD_TITLES_REFRESH_HOURS={ANIWORLD_TITLES_REFRESH_HOURS}")

# Quelle/Source-Tag im Release-Namen (typisch: WEB, WEB-DL)
SOURCE_TAG = os.getenv("SOURCE_TAG", "WEB")
logger.debug(f"SOURCE_TAG={SOURCE_TAG}")

# Release Group (am Ende nach Bindestrich angehängt)
RELEASE_GROUP = os.getenv("RELEASE_GROUP", "aniworld")
logger.debug(f"RELEASE_GROUP={RELEASE_GROUP}")

# ---- Provider-Fallback ----
# Kommagetrennte Liste, z. B. "VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza"
# Reihenfolge = Priorität
_default_order = (
    "VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza"
)
_raw = os.getenv("PROVIDER_ORDER", _default_order)
logger.debug(f"PROVIDER_ORDER raw string: {_raw}")

# normalisieren: split, trim, nur nicht-leere nehmen, Groß/Kleinschreibung egal
PROVIDER_ORDER = [p.strip() for p in _raw.split(",") if p.strip()]
logger.debug(f"PROVIDER_ORDER normalized: {PROVIDER_ORDER}")

# --- Parallelität ---
# Anzahl gleichzeitiger Downloads (Thread-Pool-Größe)
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "3"))
if MAX_CONCURRENCY < 1:
    MAX_CONCURRENCY = 1
logger.debug(f"MAX_CONCURRENCY={MAX_CONCURRENCY}")

# ---- Torznab / Indexer-Konfiguration ----
INDEXER_NAME = os.getenv("INDEXER_NAME", "AniBridge Torznab")
# Optionaler API-Key; wenn gesetzt, muss ?apikey=... passen
INDEXER_API_KEY = os.getenv("INDEXER_API_KEY", "").strip()
# Kategorien-IDs (Torznab/Newznab) – 5070 = TV/Anime (de-facto-Standard)
TORZNAB_CAT_ANIME = int(os.getenv("TORZNAB_CAT_ANIME", "5070"))

# Availability TTL (Stunden) für Semi-Cache (Qualität & Sprache je Episode)
AVAILABILITY_TTL_HOURS = float(os.getenv("AVAILABILITY_TTL_HOURS", "24"))
logger.debug(f"AVAILABILITY_TTL_HOURS={AVAILABILITY_TTL_HOURS}")

# ---- Fake Seeder/Leecher für Torznab-Items (für Prowlarr-Minimum) ----
TORZNAB_FAKE_SEEDERS = int(os.getenv("TORZNAB_FAKE_SEEDERS", "999"))
TORZNAB_FAKE_LEECHERS = int(os.getenv("TORZNAB_FAKE_LEECHERS", "787"))
logger.debug(
    f"TORZNAB_FAKE_SEEDERS={TORZNAB_FAKE_SEEDERS}, TORZNAB_FAKE_LEECHERS={TORZNAB_FAKE_LEECHERS}"
)
