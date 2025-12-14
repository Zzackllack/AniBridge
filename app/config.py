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


# --- Networking / Proxy configuration ---
def _as_bool(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    v = val.strip().lower()
    return v in ("1", "true", "yes", "on")


"""Proxy configuration

We support either a full URL with embedded credentials (PROXY_URL) or a split
form via PROXY_HOST/PROXY_PORT/PROXY_SCHEME and optional PROXY_USERNAME/
PROXY_PASSWORD. Per-protocol overrides (HTTP_PROXY_URL/HTTPS_PROXY_URL/
ALL_PROXY_URL) are also supported and will inherit global credentials if they
lack their own.
"""

# Top-level toggle to enable proxying outbound requests and downloads.
PROXY_ENABLED = _as_bool(os.getenv("PROXY_ENABLED", None), False)

# Split fields (optional builders)
PROXY_HOST = os.getenv("PROXY_HOST", "").strip()
PROXY_PORT = os.getenv("PROXY_PORT", "").strip()
PROXY_SCHEME = os.getenv(
    "PROXY_SCHEME", "socks5"
).strip()  # socks5 / socks5h / http / https
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip()

# A single URL to apply to all protocols unless overridden below.
# Examples:
#  - http://user:pass@127.0.0.1:8080
#  - socks5://127.0.0.1:1080  (use socks5h for remote DNS)
PROXY_URL = os.getenv("PROXY_URL", "").strip()

# Per-protocol overrides. If empty, falls back to PROXY_URL when PROXY_ENABLED.
HTTP_PROXY_URL = os.getenv("HTTP_PROXY_URL", "").strip()
HTTPS_PROXY_URL = os.getenv("HTTPS_PROXY_URL", "").strip()
ALL_PROXY_URL = os.getenv("ALL_PROXY_URL", "").strip()
NO_PROXY = os.getenv("NO_PROXY", "").strip()

# Force remote DNS resolution for SOCKS5 by switching to socks5h scheme.
# Default to remote DNS for SOCKS to maximize compatibility with blocked DNS
PROXY_FORCE_REMOTE_DNS = _as_bool(os.getenv("PROXY_FORCE_REMOTE_DNS", None), True)

# Requests TLS certificate verification (set false to allow corporate MITM proxies).
PROXY_DISABLE_CERT_VERIFY = _as_bool(
    os.getenv("PROXY_DISABLE_CERT_VERIFY", None), False
)

# Apply to process environment so libraries (including 3rd-party) respect proxies.
PROXY_APPLY_ENV = _as_bool(os.getenv("PROXY_APPLY_ENV", None), True)

# Interval for periodic public IP checks when proxy is enabled (minutes). 0 disables.
PROXY_IP_CHECK_INTERVAL_MIN = int(os.getenv("PROXY_IP_CHECK_INTERVAL_MIN", "30") or 0)

# Scope of proxying: 'all' (default), 'requests' (HTTP clients only), 'ytdlp' (downloads only)
PROXY_SCOPE = os.getenv("PROXY_SCOPE", "all").strip().lower()
if PROXY_SCOPE not in ("all", "requests", "ytdlp"):
    PROXY_SCOPE = "all"

# Always-on public IP monitor (even when proxy is disabled)
PUBLIC_IP_CHECK_ENABLED = _as_bool(os.getenv("PUBLIC_IP_CHECK_ENABLED", None), False)
PUBLIC_IP_CHECK_INTERVAL_MIN = int(
    os.getenv("PUBLIC_IP_CHECK_INTERVAL_MIN", str(PROXY_IP_CHECK_INTERVAL_MIN)) or 0
)


# Internal helper to promote socks5 → socks5h when remote DNS is requested.
def _normalize_proxy_scheme(url: str | None) -> str | None:
    if not url:
        return None
    try:
        u = url.strip()
        ul = u.lower()
        if ul.startswith("socks5://"):
            # Prefer remote DNS when downloads may hit geo/CDN rules.
            # Force socks5h for scopes that affect downloads unless explicitly disabled.
            if PROXY_FORCE_REMOTE_DNS or PROXY_SCOPE in ("all", "ytdlp"):
                return "socks5h://" + u[9:]
        return url
    except Exception:
        return url


def _effective_proxy_url(explicit: str | None, fallback: str | None) -> str | None:
    return _normalize_proxy_scheme(explicit.strip() if explicit else fallback)


# Build base PROXY_URL from split fields if not provided
def _build_from_parts() -> str | None:
    if PROXY_URL:
        return PROXY_URL
    if not (PROXY_HOST and PROXY_PORT):
        return None
    scheme = PROXY_SCHEME or "socks5"
    auth = ""
    if PROXY_USERNAME:
        auth = PROXY_USERNAME
        if PROXY_PASSWORD:
            auth += f":{PROXY_PASSWORD}"
        auth += "@"
    return f"{scheme}://{auth}{PROXY_HOST}:{PROXY_PORT}"


def _inject_auth(url: str | None, username: str, password: str) -> str | None:
    """Insert credentials into a proxy URL if not already present.

    Keeps host/port/scheme intact. Returns the same URL when no change needed.
    """
    if not url:
        return None
    try:
        from urllib.parse import urlsplit, urlunsplit

        p = urlsplit(url)
        if "@" in (p.netloc or ""):
            return url  # credentials already present
        netloc = p.netloc
        if not netloc:
            return url
        if username:
            creds = username
            if password:
                creds += f":{password}"
            netloc = f"{creds}@{netloc}"
        p2 = (p.scheme, netloc, p.path or "", p.query or "", p.fragment or "")
        return urlunsplit(p2)
    except Exception:
        return url


# Resolve the base PROXY_URL including optional credentials and scheme normalization
_base_proxy_url = _build_from_parts() or PROXY_URL
if PROXY_USERNAME or PROXY_PASSWORD:
    _base_proxy_url = (
        _inject_auth(_base_proxy_url, PROXY_USERNAME, PROXY_PASSWORD) or _base_proxy_url
    )

# Normalized effective values used throughout the app.
EFFECTIVE_HTTP_PROXY = _effective_proxy_url(
    _inject_auth(HTTP_PROXY_URL, PROXY_USERNAME, PROXY_PASSWORD), _base_proxy_url
)
EFFECTIVE_HTTPS_PROXY = _effective_proxy_url(
    _inject_auth(HTTPS_PROXY_URL, PROXY_USERNAME, PROXY_PASSWORD), _base_proxy_url
)
EFFECTIVE_ALL_PROXY = _effective_proxy_url(
    _inject_auth(ALL_PROXY_URL, PROXY_USERNAME, PROXY_PASSWORD), _base_proxy_url
)
EFFECTIVE_NO_PROXY = NO_PROXY or None


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
    Path("/data/downloads/anime")
    if IN_DOCKER
    else (Path.cwd() / "data" / "downloads" / "anime")
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
        Path("/app/data/downloads/anime"),
        Path.cwd() / "data" / "downloads" / "anime",
        Path("/tmp/anibridge/downloads/anime"),
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
# Comma-separated list of enabled catalogues (aniworld.to, s.to)
CATALOG_SITES = os.getenv("CATALOG_SITES", "aniworld.to,s.to").strip()
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
    "STO_ALPHABET_URL", f"{STO_BASE_URL}/serien-alphabet"
).strip()

logger.debug(
    f"ANIWORLD_ALPHABET_HTML={ANIWORLD_ALPHABET_HTML}, ANIWORLD_ALPHABET_URL={ANIWORLD_ALPHABET_URL}"
)
logger.debug(
    f"STO_ALPHABET_HTML={STO_ALPHABET_HTML}, STO_ALPHABET_URL={STO_ALPHABET_URL}"
)

# TTL (Stunden) für Live-Index; 0 = nie neu laden (nur einmal pro Prozess)
ANIWORLD_TITLES_REFRESH_HOURS = float(os.getenv("ANIWORLD_TITLES_REFRESH_HOURS", "24"))
STO_TITLES_REFRESH_HOURS = float(os.getenv("STO_TITLES_REFRESH_HOURS", "24"))
logger.debug(f"ANIWORLD_TITLES_REFRESH_HOURS={ANIWORLD_TITLES_REFRESH_HOURS}")
logger.debug(f"STO_TITLES_REFRESH_HOURS={STO_TITLES_REFRESH_HOURS}")

# (Removed) Built-in VPN control has been removed. Use an external VPN
# (e.g., system-level or Gluetun) instead. See README for guidance.

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
    logger.warning(
        f"Invalid STRM_FILES_MODE={STRM_FILES_MODE!r}; defaulting to 'no'."
    )
    STRM_FILES_MODE = "no"
logger.debug(f"STRM_FILES_MODE={STRM_FILES_MODE}")

# --- Progress rendering ---
PROGRESS_FORCE_BAR = _as_bool(os.getenv("PROGRESS_FORCE_BAR", None), False)
PROGRESS_STEP_PERCENT = max(1, int(os.getenv("PROGRESS_STEP_PERCENT", "5")))
logger.debug(
    f"PROGRESS_FORCE_BAR={PROGRESS_FORCE_BAR}, PROGRESS_STEP_PERCENT={PROGRESS_STEP_PERCENT}"
)

ANIBRIDGE_RELOAD = _as_bool(os.getenv("ANIBRIDGE_RELOAD", None), False)
ANIBRIDGE_HOST = os.getenv("ANIBRIDGE_HOST", "0.0.0.0").strip() or "0.0.0.0"
ANIBRIDGE_PORT = int(os.getenv("ANIBRIDGE_PORT", "8000") or 8000)
