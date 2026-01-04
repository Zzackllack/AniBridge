from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse
import os
import threading

from loguru import logger

from app.utils.http_client import get as http_get
from app.utils.logger import config as configure_logger

configure_logger()

MEGAKINO_DEFAULT_DOMAIN = "megakino.lol"
MEGAKINO_DOMAIN_CANDIDATES = [
    "megakino.lol",
    "megakino.cx",
    "megakino.ms",
    "megakino.video",
    "megakino.to",
]
MEGAKINO_TOKEN_PATH = "/index.php?yg=token"
USER_AGENT = "Mozilla/5.0 (AniBridge; +https://github.com/Zzackllack/AniBridge)"

_resolved_megakino_base_url: Optional[str] = None
_resolved_megakino_source: Optional[str] = None


def _normalize_domain(value: str) -> str:
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    domain = parsed.netloc or parsed.path
    return domain.strip().strip("/").lower()


def _build_base_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.netloc:
        scheme = parsed.scheme or "https"
        return f"{scheme}://{parsed.netloc}"
    return raw


def check_megakino_domain_validity(
    base_url: str, timeout: float | int = 15
) -> bool:
    """
    Probe a megakino base URL for reachability using the token endpoint.

    The Megakino-Downloader project primes sessions using `/index.php?yg=token`.
    Reusing that endpoint here provides a lightweight availability check.
    """
    if not base_url:
        logger.warning("Megakino domain check skipped (empty base_url).")
        return False
    probe_url = f"{base_url.rstrip('/')}{MEGAKINO_TOKEN_PATH}"
    try:
        resp = http_get(
            probe_url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code >= 400:
            logger.warning(
                "Megakino domain probe returned {} for {}", resp.status_code, probe_url
            )
            return False
        return True
    except Exception as exc:
        logger.warning("Megakino domain probe failed for {}: {}", probe_url, exc)
        return False


def fetch_megakino_domain(timeout: float | int = 15) -> Optional[str]:
    """
    Resolve the current megakino domain by following redirects from known candidates.

    Returns:
        The resolved domain (without scheme) or None if resolution fails.
    """
    logger.info("Resolving megakino domain via redirect checks.")
    seen: set[str] = set()
    for candidate in MEGAKINO_DOMAIN_CANDIDATES:
        domain = _normalize_domain(candidate)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        base_url = _build_base_url(domain)
        try:
            resp = http_get(
                base_url,
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            final_domain = _normalize_domain(resp.url)
            if not final_domain:
                logger.warning(
                    "Megakino resolution: empty final domain for {}", base_url
                )
                continue
            logger.info("Megakino resolution: {} -> {}", domain, final_domain)
            final_base_url = _build_base_url(final_domain)
            if check_megakino_domain_validity(final_base_url, timeout=timeout):
                logger.success("Megakino domain resolved: {}", final_domain)
                return final_domain
            logger.warning("Megakino candidate failed validation: {}", final_domain)
        except Exception as exc:
            logger.warning("Megakino candidate check failed for {}: {}", base_url, exc)
    logger.warning("Megakino domain resolution failed; no candidate succeeded.")
    return None


def _apply_megakino_base_url(base_url: str, source: str) -> None:
    global _resolved_megakino_base_url, _resolved_megakino_source
    _resolved_megakino_base_url = base_url
    _resolved_megakino_source = source

    try:
        from app import config

        config.MEGAKINO_BASE_URL = base_url
        if "megakino" in config.CATALOG_SITE_CONFIGS:
            config.CATALOG_SITE_CONFIGS["megakino"]["base_url"] = base_url
        logger.info("Megakino base URL set to {} (source={})", base_url, source)
    except Exception as exc:
        logger.warning("Failed to apply megakino base URL to config: {}", exc)


def resolve_megakino_base_url() -> str:
    """
    Resolve and store the megakino base URL using redirect checks and fallbacks.

    Resolution order:
      1) Redirect-based resolution
      2) MEGAKINO_BASE_URL env var
      3) Default "megakino.lol"
    """
    env_override = os.getenv("MEGAKINO_BASE_URL", "").strip()
    resolved_domain = fetch_megakino_domain()
    if resolved_domain:
        base_url = _build_base_url(resolved_domain)
        source = "resolved"
    elif env_override:
        base_url = _build_base_url(env_override)
        source = "env"
    else:
        base_url = _build_base_url(MEGAKINO_DEFAULT_DOMAIN)
        source = "default"

    _apply_megakino_base_url(base_url, source)
    return base_url


def get_megakino_base_url() -> str:
    if _resolved_megakino_base_url:
        return _resolved_megakino_base_url
    try:
        from app import config

        return config.MEGAKINO_BASE_URL
    except Exception:
        return _build_base_url(MEGAKINO_DEFAULT_DOMAIN)


def start_megakino_domain_check_thread(
    stop_event: "threading.Event",
) -> Optional["threading.Thread"]:
    import threading

    try:
        from app.config import MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN
    except Exception:
        logger.warning("Megakino domain monitor disabled (config unavailable).")
        return None

    interval = max(0, int(MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN))
    if interval == 0:
        logger.debug("Megakino domain monitor disabled (interval=0).")
        return None

    def _loop() -> None:
        logger.info("Starting megakino domain monitor: interval={} min", interval)
        while not stop_event.wait(interval * 60):
            base_url = get_megakino_base_url()
            if not check_megakino_domain_validity(base_url):
                logger.warning("Megakino domain check failed; re-resolving.")
                resolve_megakino_base_url()

    t = threading.Thread(target=_loop, name="megakino-domain", daemon=True)
    t.start()
    return t
