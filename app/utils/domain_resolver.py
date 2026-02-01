from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from requests.exceptions import RequestException

from app.utils.http_client import get as http_get
from app.utils.logger import config as configure_logger

configure_logger()

MEGAKINO_DEFAULT_DOMAIN = "megakino1.to"
MEGAKINO_DOMAIN_CANDIDATES = [
    "megakino1.to",
    "megakino.live",
    "megakino.lol",
    "megakino1.fit",
    "megakino.cloud",
    "megakino.cx",
    "megakino.ms",
    "megakino.video",
    "megakino.to",
]
MEGAKINO_MIRRORS_PATH = "/mirrors.txt"
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


def _get_max_workers() -> int:
    """Resolve MAX_CONCURRENCY from config with fallback default."""
    try:
        from app.config import MAX_CONCURRENCY

        return max(1, int(MAX_CONCURRENCY))
    except Exception:
        return 3


def _build_base_url(value: str) -> str:
    """
    Create a normalized base URL from an input domain or URL.

    Parameters:
        value (str): A domain or URL string to normalize.

    Returns:
        str: "scheme://netloc" (scheme defaults to "https" when missing) if a network location is present; the stripped original input if no netloc is found; or an empty string for empty input.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.netloc:
        scheme = parsed.scheme or "https"
        return f"{scheme}://{parsed.netloc}"
    return raw


def _is_sitemap_payload(text: str) -> bool:
    """
    Determine whether a string is a valid sitemap XML payload.

    Parameters:
        text (str): Candidate sitemap content (raw response text).

    Returns:
        bool: `True` if the text is valid sitemap XML whose root element is `urlset` or `sitemapindex`, `False` otherwise.
    """
    if not text:
        return False
    lowered = text.lower()
    if "<urlset" not in lowered and "<sitemapindex" not in lowered:
        return False
    try:
        from defusedxml import ElementTree as ET

        root = ET.fromstring(text)
    except Exception as exc:
        logger.warning("Megakino sitemap parse failed: {}", exc)
        return False
    tag = root.tag.split("}", 1)[1] if "}" in root.tag else root.tag
    return tag in ("urlset", "sitemapindex")


# Validates DNS-style hostnames: total length 1-253 chars, labels separated by
# dots, each label starting and ending with an alphanumeric character and
# optionally containing hyphens, and a final label (TLD) of at least 2 chars.
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]{2,}$"
)


def _looks_like_html(text: str) -> bool:
    """
    Detect whether the given text resembles an HTML document.

    Parameters:
        text (str): Text to inspect.

    Returns:
        True if the text starts with `<!doctype` or `<html` (ignoring leading whitespace and case), or contains a `<script` tag; `False` otherwise.
    """
    if not text:
        return False
    sample = text.lstrip().lower()
    return (
        sample.startswith("<!doctype")
        or sample.startswith("<html")
        or "<script" in sample
    )


def _probe_megakino_sitemap(
    base_url: str,
    timeout: float | int = 15,
) -> Optional[str]:
    """
    Probe a Megakino base URL by fetching its /sitemap.xml and return the resolved domain when the sitemap is valid.

    Parameters:
        base_url (str): Base URL or host to probe (e.g. "https://example.com" or "example.com").
        timeout (float | int): Request timeout in seconds.

    Returns:
        str: The normalized domain extracted from the final response URL when a valid sitemap payload is returned.
        None: If the probe fails, the response is not a valid sitemap, or the base_url is empty.
    """
    if not base_url:
        logger.warning("Megakino domain check skipped (empty base_url).")
        return None
    probe_url = f"{base_url.rstrip('/')}/sitemap.xml"
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
            return None
        if not _is_sitemap_payload(resp.text or ""):
            logger.warning("Megakino sitemap probe returned non-XML for {}", probe_url)
            return None
        return _normalize_domain(resp.url) or _normalize_domain(base_url)
    except RequestException as exc:
        logger.warning("Megakino domain probe failed for {}: {}", probe_url, exc)
        return None


def check_megakino_domain_validity(base_url: str, timeout: float | int = 15) -> bool:
    """
    Determine whether the given Megakino base URL serves a valid sitemap and does not redirect to a different domain.

    Parameters:
        base_url (str): Base URL or host to verify; empty values are treated as invalid.
        timeout (float | int): HTTP request timeout in seconds.

    Returns:
        bool: `True` if a sitemap payload was retrieved and the final domain matches `base_url`, `False` otherwise.
    """
    final_domain = _probe_megakino_sitemap(base_url, timeout=timeout)
    if not final_domain:
        return False
    base_domain = _normalize_domain(base_url)
    if base_domain and final_domain != base_domain:
        logger.warning(
            "Megakino sitemap redirect detected: {} -> {}",
            base_domain,
            final_domain,
        )
        return False
    return True


def _parse_mirror_domains(text: str) -> list[str]:
    """
    Parse the contents of a mirrors file and return a list of candidate domain names.

    Lines that are empty or start with '#' are ignored. Lines containing '<' or '>' are skipped. Each remaining line is interpreted either as a full URL (http/https) or as a host; URLs are normalized to their domain form and hosts are lowercased. Valid, non-empty domains are returned in the order they appear.

    Parameters:
        text (str): Raw text content of a mirrors file (multiple lines).

    Returns:
        list[str]: Ordered list of parsed domain names (lowercased, normalized).
    """
    domains: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "<" in line or ">" in line:
            continue
        if line.startswith("http://") or line.startswith("https://"):
            domain = _normalize_domain(line)
        elif _HOST_RE.match(line.lower()):
            domain = _normalize_domain(f"https://{line.lower()}")
        else:
            continue
        if domain:
            domains.append(domain)
    return domains


def fetch_megakino_mirror_domains(timeout: float | int = 15) -> list[str]:
    """
    Attempt to retrieve Megakino mirror domains from candidate mirrors files.

    Fetches each candidate's /mirrors.txt and returns the first non-empty list of parsed domains. HTML responses, HTTP errors, and malformed mirror files are ignored; if no valid mirrors are found, the function falls back to sitemap probes for all candidates and returns any resolved domains.

    Parameters:
        timeout (float | int): Request timeout in seconds.

    Returns:
        list[str]: A list of mirror domains parsed from the first valid mirrors file, or an empty list if none were found.
    """
    logger.info("Fetching megakino mirror list.")

    def _fetch_mirrors(idx: int, candidate: str) -> tuple[int, Optional[list[str]]]:
        base_url = _build_base_url(candidate)
        if not base_url:
            return (idx, None)
        mirrors_url = f"{base_url.rstrip('/')}{MEGAKINO_MIRRORS_PATH}"
        try:
            resp = http_get(
                mirrors_url,
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code >= 400:
                logger.debug(
                    "Megakino mirrors fetch returned {} for {}",
                    resp.status_code,
                    mirrors_url,
                )
                return (idx, None)
            if _looks_like_html(resp.text or ""):
                logger.debug("Megakino mirrors file returned HTML at {}", mirrors_url)
                return (idx, None)
            domains: list[str] = _parse_mirror_domains(resp.text or "")
            if domains:
                logger.info(
                    "Megakino mirrors loaded from {} ({} entries)",
                    mirrors_url,
                    len(domains),
                )
                return (idx, domains)
            logger.debug("Megakino mirrors file empty at {}", mirrors_url)
        except RequestException as exc:
            logger.debug("Megakino mirrors fetch failed for {}: {}", mirrors_url, exc)
        return (idx, None)

    candidates = list(MEGAKINO_DOMAIN_CANDIDATES)
    if candidates:
        max_workers = _get_max_workers()

        mirror_results: dict[int, list[str]] = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(candidates))) as ex:
            futures = [
                ex.submit(_fetch_mirrors, idx, candidate)
                for idx, candidate in enumerate(candidates)
            ]
            for fut in as_completed(futures):
                idx, domains = fut.result()
                if domains:
                    mirror_results[idx] = domains
        for idx in range(len(candidates)):
            if idx in mirror_results:
                return mirror_results[idx]

    logger.info(
        "Megakino mirrors unavailable; falling back to sitemap probes for {} candidates.",
        len(MEGAKINO_DOMAIN_CANDIDATES),
    )
    resolved: list[str] = []
    seen: set[str] = set()
    if not candidates:
        return resolved

    def _probe_candidate(idx: int, candidate: str) -> tuple[int, Optional[str]]:
        base_url = _build_base_url(candidate)
        if not base_url:
            return (idx, None)
        domain = _probe_megakino_sitemap(base_url, timeout=timeout)
        return (idx, domain)

    max_workers = _get_max_workers()

    probe_results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(candidates))) as ex:
        futures = [
            ex.submit(_probe_candidate, idx, candidate)
            for idx, candidate in enumerate(candidates)
        ]
        for fut in as_completed(futures):
            idx, domain = fut.result()
            if domain:
                probe_results[idx] = domain

    for idx in range(len(candidates)):
        domain = probe_results.get(idx)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        resolved.append(domain)
    return resolved


def fetch_megakino_domain(timeout: float | int = 15) -> Optional[str]:
    """
    Resolve the active Megakino domain by probing candidate and mirror hosts' sitemap.xml files.

    Parameters:
        timeout (float | int): Request timeout in seconds used for HTTP probes.

    Returns:
        The resolved domain without a URL scheme (for example, "example.com"), or `None` if no candidate could be validated.
    """
    logger.info("Resolving megakino domain via sitemap checks.")
    seen: set[str] = set()
    candidates: list[str] = []
    mirror_timeout = min(timeout, 8)
    mirror_domains = fetch_megakino_mirror_domains(timeout=mirror_timeout)
    if mirror_domains:
        candidates.extend(mirror_domains)
    candidates.extend(MEGAKINO_DOMAIN_CANDIDATES)
    for candidate in candidates:
        domain = _normalize_domain(candidate)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        base_url = _build_base_url(domain)
        try:
            final_domain = _probe_megakino_sitemap(base_url, timeout=timeout)
            if final_domain:
                logger.success("Megakino domain resolved: {}", final_domain)
                return final_domain
            logger.warning("Megakino candidate failed validation: {}", domain)
        except Exception as exc:
            logger.warning("Megakino candidate check failed for {}: {}", base_url, exc)
    logger.warning("Megakino domain resolution failed; no candidate succeeded.")
    return None


def _apply_megakino_base_url(base_url: str, source: str) -> None:
    """
    Apply and persist the resolved Megakino base URL to module state and application configuration.

    Sets the module-level resolved URL and source, updates app.config values (MEGAKINO_BASE_URL) and the "megakino" entry in CATALOG_SITE_CONFIGS when present, and attempts to reset the default Megakino client. Failures while applying configuration are logged and suppressed; client-reset errors are ignored.

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
        if "megakino" in config.CATALOG_SITE_CONFIGS:
            config.CATALOG_SITE_CONFIGS["megakino"]["base_url"] = base_url
        logger.info("Megakino base URL set to {} (source={})", base_url, source)
        try:
            from app.providers.megakino.client import reset_default_client

            reset_default_client()
        except Exception as exc:
            logger.warning(
                "Failed to reset default Megakino client after base URL update: {}",
                exc,
            )
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
