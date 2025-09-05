import sys
import os
from loguru import logger
from app.utils.logger import config as configure_logger
from pathlib import Path

configure_logger()

logger.debug("Checking if running in Docker...")
IN_DOCKER = Path("/.dockerenv").exists()
logger.debug(f"IN_DOCKER={IN_DOCKER}")

def _str_to_path(val: str | os.PathLike[str] | None) -> Path | None:
    if not val:
        return None
    try:
        return Path(val).expanduser()
    except Exception:
        return None


def _ensure_dir(candidates: list[Path], label: str) -> Path:
    """Return first usable path from candidates, creating it if needed.

    Logs fallbacks and exits with a clear error if none are writable.
    """
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            resolved = p.resolve()
            logger.info(f"{label} using: {resolved}")
            return resolved
        except PermissionError as e:
            logger.warning(f"No permission to create {label} at {p}: {e}")
        except OSError as e:
            logger.warning(f"Cannot create {label} at {p}: {e}")

    logger.error(f"No writable candidate found for {label}. Tried: {candidates}")
    # Last resort: exit with a clear message so operators can fix mounts/permissions
    raise SystemExit(
        f"Fatal: {label} is not writable. Please fix your volume mounts or set"
        f" a writable {label} via environment variables. Tried:"
        f" {', '.join(str(c) for c in candidates)}"
    )


# Optional override: path reported to clients (e.g. Sonarr) as qBittorrent save path.
# Useful when AniBridge runs on host but Sonarr runs in a container with a different mount point.
QBIT_PUBLIC_SAVE_PATH = os.getenv("QBIT_PUBLIC_SAVE_PATH", "").strip()
if QBIT_PUBLIC_SAVE_PATH:
    QBIT_PUBLIC_SAVE_PATH = str(Path(QBIT_PUBLIC_SAVE_PATH).expanduser())
logger.debug(f"QBIT_PUBLIC_SAVE_PATH={QBIT_PUBLIC_SAVE_PATH or '<none>'}")

# Resolve configured paths (treat empty env as unset)
env_download = os.getenv("DOWNLOAD_DIR")
env_data = os.getenv("DATA_DIR")
env_download_path = _str_to_path(env_download.strip() if env_download else None)
env_data_path = _str_to_path(env_data.strip() if env_data else None)

# Default candidates differ for Docker vs local
default_download = Path("/data/downloads/anime") if IN_DOCKER else (Path.cwd() / "data" / "downloads" / "anime")
default_data = Path("/data") if IN_DOCKER else (Path.cwd() / "data")

# Provide sensible cross-image fallbacks: some deploys mount under /app/data
download_candidates: list[Path] = []
data_candidates: list[Path] = []

# If a public save path is provided, prefer it so Sonarr/Prowlarr can see files
if QBIT_PUBLIC_SAVE_PATH:
    download_candidates.append(Path(QBIT_PUBLIC_SAVE_PATH))
if env_download_path:
    download_candidates.append(env_download_path)
download_candidates.extend([
    default_download,
    Path("/app/data/downloads/anime"),
    Path.cwd() / "data" / "downloads" / "anime",
    Path("/tmp/anibridge/downloads/anime"),
])

if env_data_path:
    data_candidates.append(env_data_path)
data_candidates.extend([
    default_data,
    Path("/app/data"),
    Path.cwd() / "data",
    Path("/tmp/anibridge"),
])

# Create/validate
DOWNLOAD_DIR = _ensure_dir(download_candidates, "DOWNLOAD_DIR")
DATA_DIR = _ensure_dir(data_candidates, "DATA_DIR")

# Optional override: path reported to clients (e.g. Sonarr) as qBittorrent save path.
# Useful when AniBridge runs on host but Sonarr runs in a container with a different mount point.
# Normalize to absolute for reporting if it points into container
if QBIT_PUBLIC_SAVE_PATH:
    try:
        QBIT_PUBLIC_SAVE_PATH = str(Path(QBIT_PUBLIC_SAVE_PATH).resolve())
    except Exception:
        pass

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

# --- Torznab Test-Eintrag für t=search ohne q (Connectivity Check) ---
TORZNAB_RETURN_TEST_RESULT = (
    os.getenv("TORZNAB_RETURN_TEST_RESULT", "true").strip().lower() == "true"
)
TORZNAB_TEST_TITLE = os.getenv("TORZNAB_TEST_TITLE", "AniBridge Connectivity Test")
TORZNAB_TEST_SLUG = os.getenv("TORZNAB_TEST_SLUG", "connectivity-test")
TORZNAB_TEST_SEASON = int(os.getenv("TORZNAB_TEST_SEASON", "1"))
TORZNAB_TEST_EPISODE = int(os.getenv("TORZNAB_TEST_EPISODE", "1"))
TORZNAB_TEST_LANGUAGE = os.getenv("TORZNAB_TEST_LANGUAGE", "German Dub")
