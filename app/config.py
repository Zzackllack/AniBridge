import os
from copy import deepcopy
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from app.utils.logger import config as configure_logger

# Load .env as early as possible so all downstream imports see the intended env
load_dotenv()

# Configure logger after env is loaded (LOG_LEVEL honored)
configure_logger()

logger.debug("Checking if running in Docker...")
IN_DOCKER = Path("/.dockerenv").exists()
logger.debug(f"IN_DOCKER={IN_DOCKER}")


# --- Networking / transport policy ---
# Legacy in-app outbound proxy support has been removed on purpose.
# AniBridge now expects traffic shaping/anonymization to happen externally
# (for example via host VPN, container VPN sidecar, or network namespace).
# STRM proxying is a separate feature and remains supported.
def _as_bool(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    v = val.strip().lower()
    return v in ("1", "true", "yes", "on")


def _as_non_negative_int(val: str | None, default: int) -> int:
    """Parse *val* as a non-negative integer, returning *default* on failure."""
    if val is None:
        return default
    try:
        parsed = int(val.strip())
    except (TypeError, ValueError):
        logger.warning(
            "Invalid non-negative integer value {!r}; using {}", val, default
        )
        return default
    if parsed < 0:
        logger.warning("Negative value {} is not allowed; using {}", parsed, default)
        return default
    return parsed


# Always-on public IP monitor.
PUBLIC_IP_CHECK_ENABLED = _as_bool(os.getenv("PUBLIC_IP_CHECK_ENABLED", None), False)
PUBLIC_IP_CHECK_INTERVAL_MIN = int(os.getenv("PUBLIC_IP_CHECK_INTERVAL_MIN", "30") or 0)

# Hard deprecation warnings for removed in-app proxy settings.
# We keep explicit logging so operators immediately know why these values are
# ignored after upgrading.
_REMOVED_PROXY_ENV_VARS = (
    "PROXY_ENABLED",
    "PROXY_URL",
    "HTTP_PROXY_URL",
    "HTTPS_PROXY_URL",
    "ALL_PROXY_URL",
    "PROXY_HOST",
    "PROXY_PORT",
    "PROXY_SCHEME",
    "PROXY_USERNAME",
    "PROXY_PASSWORD",
    "NO_PROXY",
    "PROXY_FORCE_REMOTE_DNS",
    "PROXY_DISABLE_CERT_VERIFY",
    "PROXY_APPLY_ENV",
    "PROXY_IP_CHECK_INTERVAL_MIN",
    "PROXY_SCOPE",
)
for _env_name in _REMOVED_PROXY_ENV_VARS:
    if _env_name in os.environ:
        logger.warning(
            "{} is set but ignored: outbound in-app proxy support was removed. "
            "Use an external VPN tunnel or VPN sidecar instead.",
            _env_name,
        )


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
default_download = (
    Path("/data/downloads") if IN_DOCKER else (Path.cwd() / "data" / "downloads")
)
default_data = Path("/data") if IN_DOCKER else (Path.cwd() / "data")

# Provide sensible cross-image fallbacks: some deploys mount under /app/data
download_candidates: list[Path] = []
data_candidates: list[Path] = []

# Note: QBIT_PUBLIC_SAVE_PATH is only for publishing paths to indexers (e.g.,
# Sonarr/Radarr) and must NOT affect our internal download directory selection.
# Do not add it to download_candidates to avoid attempting to create container
# paths on the host (e.g., /downloads) when running outside Docker.
if env_download_path:
    download_candidates.append(env_download_path)
download_candidates.extend(
    [
        default_download,
        Path("/app/data/downloads"),
        Path.cwd() / "data" / "downloads",
        Path("/tmp/anibridge/downloads"),
    ]
)

if env_data_path:
    data_candidates.append(env_data_path)
data_candidates.extend(
    [
        default_data,
        Path("/app/data"),
        Path.cwd() / "data",
        Path("/tmp/anibridge"),
    ]
)

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

# ---- Multi-Site Catalogue Configuration ----
# Comma-separated list of enabled catalogues (aniworld.to, s.to, megakino)
CATALOG_SITES = os.getenv("CATALOG_SITES", "aniworld.to,s.to,megakino").strip()
CATALOG_SITES_LIST = list(
    dict.fromkeys(s.strip() for s in CATALOG_SITES.split(",") if s.strip())
)
logger.debug(f"CATALOG_SITES={CATALOG_SITES_LIST}")

# Site-specific configuration
# AniWorld (anime)
ANIWORLD_BASE_URL = os.getenv("ANIWORLD_BASE_URL", "https://aniworld.to").strip()
ANIWORLD_ALPHABET_HTML = Path(
    os.getenv("ANIWORLD_ALPHABET_HTML", DATA_DIR / "aniworld-alphabeth.html")
)
ANIWORLD_ALPHABET_URL = os.getenv(
    "ANIWORLD_ALPHABET_URL", f"{ANIWORLD_BASE_URL}/animes-alphabet"
).strip()

# S.to (series)
STO_BASE_URL = os.getenv("STO_BASE_URL", "https://s.to").strip()
STO_ALPHABET_HTML = Path(
    os.getenv("STO_ALPHABET_HTML", DATA_DIR / "sto-alphabeth.html")
)
STO_ALPHABET_URL = os.getenv(
    "STO_ALPHABET_URL", f"{STO_BASE_URL}/serien?by=alpha"
).strip()

# Megakino (series/movies)
MEGAKINO_BASE_URL = os.getenv("MEGAKINO_BASE_URL", "https://megakino1.to").strip()
MEGAKINO_TITLES_REFRESH_HOURS = float(os.getenv("MEGAKINO_TITLES_REFRESH_HOURS", "12"))
MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN = int(
    os.getenv("MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN", "100")
)

logger.debug(
    f"ANIWORLD_ALPHABET_HTML={ANIWORLD_ALPHABET_HTML}, ANIWORLD_ALPHABET_URL={ANIWORLD_ALPHABET_URL}"
)
logger.debug(
    f"STO_ALPHABET_HTML={STO_ALPHABET_HTML}, STO_ALPHABET_URL={STO_ALPHABET_URL}"
)
logger.debug(f"MEGAKINO_BASE_URL={MEGAKINO_BASE_URL}")
logger.debug(f"MEGAKINO_TITLES_REFRESH_HOURS={MEGAKINO_TITLES_REFRESH_HOURS}")
logger.debug(f"MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN={MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN}")

# TTL (Stunden) für Live-Index; 0 = nie neu laden (nur einmal pro Prozess)
ANIWORLD_TITLES_REFRESH_HOURS = float(os.getenv("ANIWORLD_TITLES_REFRESH_HOURS", "24"))
STO_TITLES_REFRESH_HOURS = float(os.getenv("STO_TITLES_REFRESH_HOURS", "24"))
logger.debug(f"ANIWORLD_TITLES_REFRESH_HOURS={ANIWORLD_TITLES_REFRESH_HOURS}")
logger.debug(f"STO_TITLES_REFRESH_HOURS={STO_TITLES_REFRESH_HOURS}")

# Quelle/Source-Tag im Release-Namen (typisch: WEB, WEB-DL)
SOURCE_TAG = os.getenv("SOURCE_TAG", "WEB")
logger.debug(f"SOURCE_TAG={SOURCE_TAG}")

# Release Group (am Ende nach Bindestrich angehängt)
# Can be site-specific: RELEASE_GROUP_ANIWORLD, RELEASE_GROUP_STO
RELEASE_GROUP = os.getenv("RELEASE_GROUP", "aniworld")
RELEASE_GROUP_ANIWORLD = os.getenv("RELEASE_GROUP_ANIWORLD", RELEASE_GROUP)
RELEASE_GROUP_STO = os.getenv("RELEASE_GROUP_STO", "sto")
logger.debug(f"RELEASE_GROUP={RELEASE_GROUP}")
logger.debug(
    f"RELEASE_GROUP_ANIWORLD={RELEASE_GROUP_ANIWORLD}, RELEASE_GROUP_STO={RELEASE_GROUP_STO}"
)

_DEFAULT_SITE_CONFIGS: dict[str, dict[str, Any]] = {
    "aniworld.to": {
        "base_url": ANIWORLD_BASE_URL,
        "alphabet_html": ANIWORLD_ALPHABET_HTML,
        "alphabet_url": ANIWORLD_ALPHABET_URL,
        "titles_refresh_hours": ANIWORLD_TITLES_REFRESH_HOURS,
        "default_languages": ["German Dub", "German Sub", "English Sub"],
        "release_group": RELEASE_GROUP_ANIWORLD,
    },
    "s.to": {
        "base_url": STO_BASE_URL,
        "alphabet_html": STO_ALPHABET_HTML,
        "alphabet_url": STO_ALPHABET_URL,
        "titles_refresh_hours": STO_TITLES_REFRESH_HOURS,
        "default_languages": ["German Dub", "English Dub", "German Sub"],
        "release_group": RELEASE_GROUP_STO,
    },
    "megakino": {
        "base_url": MEGAKINO_BASE_URL,
        "alphabet_html": None,
        "alphabet_url": None,
        "titles_refresh_hours": MEGAKINO_TITLES_REFRESH_HOURS,
        "default_languages": ["Deutsch", "German Dub"],
        "release_group": "megakino",
    },
}

CATALOG_SITE_CONFIGS: dict[str, dict[str, Any]] = {}
for site in CATALOG_SITES_LIST:
    base_cfg = _DEFAULT_SITE_CONFIGS.get(site)
    if not base_cfg:
        logger.warning(
            f"No built-in configuration for catalogue site '{site}'. Provide environment overrides to enable it."
        )
        continue
    CATALOG_SITE_CONFIGS[site] = deepcopy(base_cfg)

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

# Per-download bandwidth cap for yt-dlp in bytes/second. 0 = unlimited.
DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC = _as_non_negative_int(
    os.getenv("DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC"), 0
)
logger.debug("DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC={}", DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC)

# ---- Torznab / Indexer-Konfiguration ----
INDEXER_NAME = os.getenv("INDEXER_NAME", "AniBridge Torznab")
# Optionaler API-Key; wenn gesetzt, muss ?apikey=... passen
INDEXER_API_KEY = os.getenv("INDEXER_API_KEY", "").strip()
# Kategorien-IDs (Torznab/Newznab) – 5070 = TV/Anime (de-facto-Standard)
TORZNAB_CAT_ANIME = int(os.getenv("TORZNAB_CAT_ANIME", "5070"))
TORZNAB_CAT_MOVIE = int(os.getenv("TORZNAB_CAT_MOVIE", "2000"))

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
TORZNAB_SEASON_SEARCH_MAX_EPISODES = max(
    1, _as_non_negative_int(os.getenv("TORZNAB_SEASON_SEARCH_MAX_EPISODES"), 60)
)
TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES = max(
    1,
    _as_non_negative_int(os.getenv("TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES"), 3),
)
logger.debug(
    "Torznab season-search guardrails: max_episodes={} max_consecutive_misses={}",
    TORZNAB_SEASON_SEARCH_MAX_EPISODES,
    TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES,
)

# Metadata-backed specials mapping (Option C)
SPECIALS_METADATA_ENABLED = _as_bool(
    os.getenv("SPECIALS_METADATA_ENABLED", "true"), True
)
try:
    SPECIALS_METADATA_TIMEOUT_SECONDS = float(
        os.getenv("SPECIALS_METADATA_TIMEOUT_SECONDS", "8")
    )
except ValueError:
    SPECIALS_METADATA_TIMEOUT_SECONDS = 8.0
if SPECIALS_METADATA_TIMEOUT_SECONDS <= 0:
    SPECIALS_METADATA_TIMEOUT_SECONDS = 8.0

try:
    SPECIALS_METADATA_CACHE_TTL_MINUTES = int(
        os.getenv("SPECIALS_METADATA_CACHE_TTL_MINUTES", "360")
    )
except ValueError:
    SPECIALS_METADATA_CACHE_TTL_MINUTES = 360
if SPECIALS_METADATA_CACHE_TTL_MINUTES < 0:
    SPECIALS_METADATA_CACHE_TTL_MINUTES = 0

try:
    SPECIALS_MATCH_CONFIDENCE_THRESHOLD = float(
        os.getenv("SPECIALS_MATCH_CONFIDENCE_THRESHOLD", "0.50")
    )
except ValueError:
    SPECIALS_MATCH_CONFIDENCE_THRESHOLD = 0.50
SPECIALS_MATCH_CONFIDENCE_THRESHOLD = min(
    1.0, max(0.0, SPECIALS_MATCH_CONFIDENCE_THRESHOLD)
)
logger.debug(
    "SPECIALS metadata config: enabled={} timeout={} cache_ttl_minutes={} threshold={}",
    SPECIALS_METADATA_ENABLED,
    SPECIALS_METADATA_TIMEOUT_SECONDS,
    SPECIALS_METADATA_CACHE_TTL_MINUTES,
    SPECIALS_MATCH_CONFIDENCE_THRESHOLD,
)

# --- Cleanup behavior ---


DELETE_FILES_ON_TORRENT_DELETE = _as_bool(
    os.getenv("DELETE_FILES_ON_TORRENT_DELETE", "true"), True
)
DOWNLOADS_TTL_HOURS = float(
    os.getenv("DOWNLOADS_TTL_HOURS", "0")
)  # 0 disables TTL cleanup
CLEANUP_SCAN_INTERVAL_MIN = int(os.getenv("CLEANUP_SCAN_INTERVAL_MIN", "30"))
logger.debug(
    f"DELETE_FILES_ON_TORRENT_DELETE={DELETE_FILES_ON_TORRENT_DELETE}, DOWNLOADS_TTL_HOURS={DOWNLOADS_TTL_HOURS}, CLEANUP_SCAN_INTERVAL_MIN={CLEANUP_SCAN_INTERVAL_MIN}"
)

# --- STRM support ---
# Controls whether Torznab emits STRM variants and whether the qBittorrent shim
# turns those variants into .strm files instead of downloading media.
STRM_FILES_MODE = os.getenv("STRM_FILES_MODE", "no").strip().lower()
if STRM_FILES_MODE not in ("no", "both", "only"):
    logger.warning(f"Invalid STRM_FILES_MODE={STRM_FILES_MODE!r}; defaulting to 'no'.")
    STRM_FILES_MODE = "no"
logger.debug(f"STRM_FILES_MODE={STRM_FILES_MODE}")

# --- STRM proxy streaming ---
# Controls whether STRM files point to AniBridge proxy URLs or direct provider URLs.
STRM_PROXY_MODE = os.getenv("STRM_PROXY_MODE", "direct").strip().lower()
if STRM_PROXY_MODE not in ("direct", "proxy", "redirect"):
    logger.warning(
        f"Invalid STRM_PROXY_MODE={STRM_PROXY_MODE!r}; defaulting to 'direct'."
    )
    STRM_PROXY_MODE = "direct"
if STRM_PROXY_MODE == "redirect":
    logger.warning(
        "STRM_PROXY_MODE=redirect is not implemented; using proxy streaming."
    )
    STRM_PROXY_MODE = "proxy"

# Public base URL used to build stable STRM proxy URLs (required for proxy mode).
STRM_PUBLIC_BASE_URL = os.getenv("STRM_PUBLIC_BASE_URL", "").strip()

# Auth mode for proxy endpoints: none, token (HMAC), or apikey.
STRM_PROXY_AUTH = os.getenv("STRM_PROXY_AUTH", "token").strip().lower()
if STRM_PROXY_AUTH not in ("none", "token", "apikey"):
    logger.warning(
        f"Invalid STRM_PROXY_AUTH={STRM_PROXY_AUTH!r}; defaulting to 'token'."
    )
    STRM_PROXY_AUTH = "token"

# Shared secret for STRM proxy auth. Used for token signatures and API key mode.
STRM_PROXY_SECRET = os.getenv("STRM_PROXY_SECRET", "").strip()

# Optional allowlist of upstream hosts for STRM proxying (comma-separated).
_strm_upstream_allowlist_raw = os.getenv("STRM_PROXY_UPSTREAM_ALLOWLIST", "").strip()
STRM_PROXY_UPSTREAM_ALLOWLIST = {
    host.strip().lower()
    for host in _strm_upstream_allowlist_raw.split(",")
    if host.strip()
}

# Cache TTL (seconds) for resolved STRM URLs. 0 disables expiration.
_strm_cache_ttl_raw = os.getenv("STRM_PROXY_CACHE_TTL_SECONDS", "0").strip()
try:
    STRM_PROXY_CACHE_TTL_SECONDS = int(_strm_cache_ttl_raw or 0)
except ValueError:
    logger.warning(
        f"Invalid STRM_PROXY_CACHE_TTL_SECONDS={_strm_cache_ttl_raw!r}; defaulting to 0."
    )
    STRM_PROXY_CACHE_TTL_SECONDS = 0

# Token TTL (seconds) for signed STRM proxy URLs.
_strm_token_ttl_raw = os.getenv("STRM_PROXY_TOKEN_TTL_SECONDS", "900").strip()
try:
    STRM_PROXY_TOKEN_TTL_SECONDS = int(_strm_token_ttl_raw or 0)
except ValueError:
    logger.warning(
        f"Invalid STRM_PROXY_TOKEN_TTL_SECONDS={_strm_token_ttl_raw!r}; defaulting to 900."
    )
    STRM_PROXY_TOKEN_TTL_SECONDS = 900
if STRM_PROXY_TOKEN_TTL_SECONDS <= 0:
    logger.warning("STRM_PROXY_TOKEN_TTL_SECONDS must be positive; defaulting to 900.")
    STRM_PROXY_TOKEN_TTL_SECONDS = 900

STRM_PROXY_ENABLED = STRM_PROXY_MODE == "proxy"
if STRM_PROXY_ENABLED and not STRM_PUBLIC_BASE_URL:
    logger.error("STRM proxy mode is enabled but STRM_PUBLIC_BASE_URL is not set.")
    raise RuntimeError("STRM_PUBLIC_BASE_URL is required when STRM_PROXY_MODE=proxy.")
if STRM_PROXY_ENABLED and STRM_PROXY_AUTH != "none" and not STRM_PROXY_SECRET:
    logger.error("STRM proxy auth enabled but STRM_PROXY_SECRET is not set.")
    raise RuntimeError("STRM_PROXY_SECRET is required when STRM_PROXY_AUTH is enabled.")
logger.debug(
    "STRM proxy config: mode={} auth={} cache_ttl_seconds={} token_ttl_seconds={} allowlist_count={}",
    STRM_PROXY_MODE,
    STRM_PROXY_AUTH,
    STRM_PROXY_CACHE_TTL_SECONDS,
    STRM_PROXY_TOKEN_TTL_SECONDS,
    len(STRM_PROXY_UPSTREAM_ALLOWLIST),
)

# --- Progress rendering ---
PROGRESS_FORCE_BAR = _as_bool(os.getenv("PROGRESS_FORCE_BAR", None), False)
PROGRESS_STEP_PERCENT = max(1, int(os.getenv("PROGRESS_STEP_PERCENT", "5")))
logger.debug(
    f"PROGRESS_FORCE_BAR={PROGRESS_FORCE_BAR}, PROGRESS_STEP_PERCENT={PROGRESS_STEP_PERCENT}"
)

ANIBRIDGE_RELOAD = _as_bool(os.getenv("ANIBRIDGE_RELOAD", None), False)
ANIBRIDGE_TEST_MODE = _as_bool(os.getenv("ANIBRIDGE_TEST_MODE", None), False)
DB_MIGRATE_ON_STARTUP = _as_bool(os.getenv("DB_MIGRATE_ON_STARTUP", None), True)
ANIBRIDGE_HOST = os.getenv("ANIBRIDGE_HOST", "0.0.0.0").strip() or "0.0.0.0"
ANIBRIDGE_PORT = int(os.getenv("ANIBRIDGE_PORT", "8000") or 8000)

# --- CORS ---
# Browser-based API clients (like the docs "try it out") need CORS enabled.
#
# Values:
# - Unset/empty: allow all origins ("*") (default)
# - "*": allow all origins
# - Comma-separated list: allow only these origins
# - "off" / "none": disable CORS entirely (no middleware)
_cors_raw = os.getenv("ANIBRIDGE_CORS_ORIGINS", "").strip()
_cors_raw_lower = _cors_raw.lower()
if _cors_raw_lower in {"off", "none"}:
    ANIBRIDGE_CORS_ORIGINS: list[str] = []
elif not _cors_raw or _cors_raw == "*":
    ANIBRIDGE_CORS_ORIGINS = ["*"]
else:
    ANIBRIDGE_CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
logger.debug(f"ANIBRIDGE_CORS_ORIGINS={ANIBRIDGE_CORS_ORIGINS}")

# Controls Access-Control-Allow-Credentials when CORS is enabled and origins are
# not a wildcard. For wildcard origins, credentials are always disabled.
ANIBRIDGE_CORS_ALLOW_CREDENTIALS = _as_bool(
    os.getenv("ANIBRIDGE_CORS_ALLOW_CREDENTIALS", "true"), True
)
logger.debug(f"ANIBRIDGE_CORS_ALLOW_CREDENTIALS={ANIBRIDGE_CORS_ALLOW_CREDENTIALS}")
