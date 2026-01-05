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
    """
    Normalize an input URL or host string into a lowercase domain without surrounding slashes.
    
    Parameters:
        value (str): A URL or domain-like string that may include a scheme, path, or surrounding whitespace.
    
    Returns:
        str: The cleaned domain (host) in lowercase with no leading or trailing slashes, or an empty string if the input is empty or contains no domain.
    """
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    domain = parsed.netloc or parsed.path
    return domain.strip().strip("/").lower()


def _build_base_url(value: str) -> str:
    """
    Constructs a normalized base URL from an input string.
    
    If the input contains a network location, returns a URL with a scheme and netloc (defaults scheme to `https` when missing). If the input is empty, returns an empty string. If the input cannot be parsed into a netloc, returns the stripped original input.
    
    Parameters:
        value (str): A domain or URL string to normalize.
    
    Returns:
        str: A base URL like `https://example.com`, the stripped original input if no netloc is found, or an empty string for empty input.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.netloc:
        scheme = parsed.scheme or "https"
        return f"{scheme}://{parsed.netloc}"
    return raw


def check_megakino_domain_validity(base_url: str, timeout: float | int = 15) -> bool:
    """
    Check whether a Megakino base URL is reachable by probing its token endpoint.
    
    Probes the base URL's token endpoint (MEGAKINO_TOKEN_PATH) with a GET request to determine availability.
    
    Parameters:
        base_url (str): Base URL to probe; an empty value causes the function to return `False`.
        timeout (float | int): Request timeout in seconds.
    
    Returns:
        bool: `true` if the probe returned an HTTP status code less than 400, `false` otherwise.
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
    Resolve the active Megakino domain by following redirects from configured candidate domains.
    
    Parameters:
    	timeout (float | int): Request timeout in seconds for HTTP probes.
    
    Returns:
    	resolved_domain (str | None): The resolved domain without a URL scheme (for example, "example.com"), or `None` if no candidate could be validated.
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
    """
    Apply and persist the resolved Megakino base URL to module state and application configuration.
    
    Sets the module-level resolved URL and source, updates app.config values (MEGAKINO_BASE_URL and MEGAKINO_SITEMAP_URL) and the "megakino" entry in CATALOG_SITE_CONFIGS when present, and attempts to reset the default Megakino client. Failures while applying configuration are logged and suppressed; client-reset errors are ignored.
    
    Parameters:
        base_url (str): The base URL to apply (e.g., "https://example.com").
        source (str): Identifier of how the URL was determined (for example, "resolved", "env", or "default").
    """
    global _resolved_megakino_base_url, _resolved_megakino_source
    _resolved_megakino_base_url = base_url
    _resolved_megakino_source = source

    try:
        from app import config

        config.MEGAKINO_BASE_URL = base_url
        config.MEGAKINO_SITEMAP_URL = f"{base_url.rstrip('/')}/sitemap.xml"
        if "megakino" in config.CATALOG_SITE_CONFIGS:
            config.CATALOG_SITE_CONFIGS["megakino"]["base_url"] = base_url
        logger.info("Megakino base URL set to {} (source={})", base_url, source)
        try:
            from app.providers.megakino.client import reset_default_client

            reset_default_client()
        except Exception:
            pass
    except Exception as exc:
        logger.warning("Failed to apply megakino base URL to config: {}", exc)


def resolve_megakino_base_url() -> str:
    """
    Resolve and store the Megakino base URL by attempting redirect-based discovery, then an environment override, then a default.
    
    The chosen base URL is applied to module state and the application configuration.
    
    Returns:
        base_url (str): The applied Megakino base URL.
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
    """
    Retrieve the currently resolved Megakino base URL.
    
    If a cached resolved base URL exists, it is returned. Otherwise the function reads MEGAKINO_BASE_URL from app.config; if that access fails, it falls back to a base URL built from the default Megakino domain.
    
    Returns:
        The Megakino base URL: the cached resolved URL if set, `config.MEGAKINO_BASE_URL` if available, or a URL constructed from the default domain.
    """
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
    """
    Start a background daemon thread that periodically verifies the Megakino domain and triggers a re-resolution if the check fails.
    
    Parameters:
        stop_event (threading.Event): Event used to stop the monitoring loop; when set, the thread will exit.
    
    Returns:
        threading.Thread | None: The started daemon thread if monitoring was enabled, `None` if monitoring is disabled (config unavailable or interval set to 0). The check interval is read from app.config.MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN in minutes.
    """
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
        """
        Background loop that periodically verifies the configured Megakino base URL and triggers re-resolution on failure.
        
        This function logs startup, then repeatedly waits for the configured interval (in minutes) until `stop_event` is set. On each iteration it retrieves the current Megakino base URL, checks its validity, and calls `resolve_megakino_base_url()` if the check fails.
        """
        logger.info("Starting megakino domain monitor: interval={} min", interval)
        while not stop_event.wait(interval * 60):
            base_url = get_megakino_base_url()
            if not check_megakino_domain_validity(base_url):
                logger.warning("Megakino domain check failed; re-resolving.")
                resolve_megakino_base_url()

    t = threading.Thread(target=_loop, name="megakino-domain", daemon=True)
    t.start()
    return t