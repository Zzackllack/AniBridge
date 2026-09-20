from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from loguru import logger

from app.config import (
    CATALOG_SITE_CONFIGS,
    PROVIDER_CHALLENGE_BACKOFF_SECONDS,
    PROVIDER_REDIRECT_TIMEOUT_SECONDS,
)
from app.core.downloader.errors import (
    ProviderResolutionError,
    ProviderTransportError,
    ProviderVerificationRequiredError,
)
from app.core.downloader.provider_policy import (
    describe_url,
    fetch_verified_response,
    host_is_public,
    looks_like_verification_page,
)
from app.utils.aniworld_compat import prepare_aniworld_home

_URL_PATTERN = re.compile(r"https?://[^'\"<>\s]+")
_IGNORED_REDIRECT_HOSTS = {
    "challenges.cloudflare.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
}
_IGNORED_REDIRECT_SUFFIXES = (
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".png",
    ".svg",
    ".webp",
)
_MAX_PROVIDER_PAGES = 8
_TRANSIENT_ERROR_MARKERS = (
    "connection aborted",
    "connection reset",
    "input/output error",
    "remote end closed connection",
    "temporarily unavailable",
    "timed out",
)

__all__ = [
    "build_provider_headers",
    "choose_redirect_candidate",
    "fetch_provider_page",
    "is_transient_error",
    "looks_like_turnstile_page",
    "resolve_direct_link_fallback",
    "resolve_direct_link_from_redirect",
]


def choose_redirect_candidate(html: str, current_url: str) -> Optional[str]:
    """
    Pick the most likely next redirect target from a provider page.

    The upstream pages often include many unrelated asset URLs. This prefers
    actual embed/watch targets and filters static assets or challenge scripts.
    """
    current = urlparse(current_url)
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_url in _URL_PATTERN.findall(html):
        candidate = raw_url.rstrip(");,")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
        if not host or host in _IGNORED_REDIRECT_HOSTS:
            continue
        if path.endswith(_IGNORED_REDIRECT_SUFFIXES):
            continue
        if not host_is_public(host):
            continue
        if candidate == current_url:
            continue
        candidates.append(candidate)

    if not candidates:
        return None

    def _score(candidate: str) -> tuple[int, int, int]:
        """
        Compute a three-part score for a URL candidate to rank redirect targets.

        Parameters:
            candidate (str): The URL string to evaluate.

        Returns:
            tuple[int, int, int]: A tuple of three integers (has_e_segment, host_differs, has_permanent_token):
                - has_e_segment: 1 if the candidate's path contains "/e/", 0 otherwise.
                - host_differs: 1 if the candidate's hostname differs from the current request's netloc, 0 otherwise.
                - has_permanent_token: 1 if the candidate contains "permanenttoken=" (case-insensitive), 0 otherwise.
        """
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
        return (
            1 if "/e/" in path else 0,
            1 if host != (current.netloc or "").lower() else 0,
            1 if "permanenttoken=" in candidate.lower() else 0,
        )

    return max(candidates, key=_score)


def build_provider_headers(*, provider_name: str, site: str) -> dict[str, str]:
    """
    Build HTTP request headers for the given provider and site.

    Parameters:
        provider_name (str): Identifier used to select provider-specific header mappings from configuration.
        site (str): Site identifier; when "s.to" adds navigation-like headers and a Referer suitable for Serienstream.

    Returns:
        headers (dict[str, str]): Headers to use for requests to the provider.
    """
    prepare_aniworld_home()
    import aniworld.config as aniworld_config  # type: ignore

    default_user_agent = getattr(aniworld_config, "DEFAULT_USER_AGENT", "Mozilla/5.0")
    provider_headers = getattr(aniworld_config, "PROVIDER_HEADERS_D", {})
    headers = dict(
        provider_headers.get(provider_name, {"User-Agent": default_user_agent})
    )
    if site == "s.to":
        site_config = CATALOG_SITE_CONFIGS.get(site, {})
        referer = str(site_config.get("base_url") or "https://serienstream.to").rstrip(
            "/"
        )
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Priority": "u=0, i",
                "Referer": f"{referer}/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1",
            }
        )
    return headers


def looks_like_turnstile_page(html: str) -> bool:
    """
    Detect Serienstream/DDOS-Guard challenge pages that block provider access.
    """
    return looks_like_verification_page(html)


def fetch_provider_page(*, url: str, headers: dict[str, str]) -> tuple[str, str]:
    """
    Fetches the given URL following redirects and returns the final URL and the page HTML.

    Parameters:
        url (str): The initial URL to request.
        headers (dict[str, str]): HTTP headers to include with the request.

    Returns:
        tuple[str, str]: Final URL after redirects and the response HTML text.

    Raises:
        requests.RequestException: On network errors or non-successful HTTP responses.
    """
    response = fetch_verified_response(
        url,
        stage="VOE page",
        headers=headers,
        timeout_seconds=PROVIDER_REDIRECT_TIMEOUT_SECONDS,
    )
    return str(response.url), response.text


def resolve_direct_link_from_redirect(*, redirect_url: str, site: str) -> str:
    """
    Resolve a VOE direct video URL from a catalogue redirect token.

    Follow the provider redirect chain starting from `redirect_url` until a VOE source URL is extracted or resolution fails.

    Parameters:
        redirect_url (str): Starting catalogue redirect URL or token that leads into the VOE redirect chain.
        site (str): Catalogue site identifier used to build provider request headers.

    Returns:
        str: The resolved direct VOE video URL.

    Raises:
        ValueError: If an HTTP fetch fails, if the redirect chain remains blocked by a Turnstile challenge after retries, or if no VOE source is found.
    """
    prepare_aniworld_home()
    from aniworld.extractors.provider.voe import extract_voe_source_from_html  # type: ignore

    headers = build_provider_headers(provider_name="VOE", site=site)
    pending: list[str] = [redirect_url]
    visited: set[str] = set()
    pages_fetched = 0
    while pending and pages_fetched < _MAX_PROVIDER_PAGES:
        current_url = pending.pop(0).strip()
        if not current_url or current_url in visited:
            continue
        visited.add(current_url)
        pages_fetched += 1

        try:
            final_url, html = fetch_provider_page(url=current_url, headers=headers)
        except ProviderVerificationRequiredError as exc:
            raise ProviderVerificationRequiredError(
                "Provider access requires interactive verification; browser "
                "solving is disabled. Retry later or use a different network path.",
                stage=exc.stage,
                status_code=exc.status_code,
                host=exc.host,
                retry_after_seconds=PROVIDER_CHALLENGE_BACKOFF_SECONDS,
            ) from exc

        if final_url != current_url:
            visited.add(final_url)

        source = extract_voe_source_from_html(html)
        if source:
            logger.success("VOE direct URL resolved via {}", describe_url(final_url))
            return source

        if looks_like_turnstile_page(html):
            raise ProviderVerificationRequiredError(
                "Provider access requires interactive verification; browser "
                "solving is disabled. Retry later or use a different network path.",
                stage="VOE page",
                status_code=200,
                host=urlparse(final_url).hostname,
                retry_after_seconds=PROVIDER_CHALLENGE_BACKOFF_SECONDS,
            )

        candidate = choose_redirect_candidate(html, final_url)
        logger.debug(
            "VOE redirect step: current={}, next={}",
            describe_url(final_url),
            describe_url(candidate or ""),
        )
        if candidate and candidate not in visited:
            pending.append(candidate)

    if pending:
        raise ProviderTransportError(
            f"VOE resolution exceeded the {_MAX_PROVIDER_PAGES}-page limit.",
            stage="VOE page",
            host=urlparse(pending[0]).hostname,
        )
    raise ValueError("No VOE video source found in page.")


def resolve_direct_link_fallback(*, initial_urls: list[str]) -> Optional[str]:
    """
    Follow nested HTML/JavaScript redirect chains from a list of starting URLs to resolve a direct VOE video source.

    Attempts to fetch each start URL (using the global session and VOE provider headers), extracts a direct VOE source from the response HTML if present, and otherwise follows the next redirect candidate found in the page until a direct source is found or the chain ends.

    Parameters:
        initial_urls (list[str]): Starting URLs to try, processed in order.

    Returns:
        Optional[str]: A direct VOE video URL if one is resolved, `None` if no direct source is found.
    """
    prepare_aniworld_home()
    import aniworld.config as aniworld_config  # type: ignore
    from aniworld.extractors.provider.voe import extract_voe_source_from_html  # type: ignore

    default_user_agent = getattr(aniworld_config, "DEFAULT_USER_AGENT", "Mozilla/5.0")
    provider_headers = getattr(aniworld_config, "PROVIDER_HEADERS_D", {})
    headers = provider_headers.get("VOE", {"User-Agent": default_user_agent})
    visited: set[str] = set()

    for start_url in initial_urls:
        next_url = (start_url or "").strip()
        pages_fetched = 0
        while (
            next_url and next_url not in visited and pages_fetched < _MAX_PROVIDER_PAGES
        ):
            visited.add(next_url)
            pages_fetched += 1
            try:
                response = fetch_verified_response(
                    next_url,
                    stage="VOE fallback page",
                    headers=headers,
                    timeout_seconds=PROVIDER_REDIRECT_TIMEOUT_SECONDS,
                )
            except ProviderResolutionError as err:
                logger.warning(
                    "VOE fallback failed at {}: {}",
                    describe_url(next_url),
                    err,
                )
                break

            html = response.text
            direct_url = extract_voe_source_from_html(html)
            if direct_url:
                logger.success(
                    "VOE fallback resolved direct URL via {}",
                    describe_url(next_url),
                )
                return direct_url

            candidate = choose_redirect_candidate(html, str(response.url))
            logger.debug(
                "VOE fallback redirect step: current={}, next={}",
                describe_url(str(response.url)),
                describe_url(candidate or ""),
            )
            if not candidate:
                break
            next_url = candidate

    return None


def is_transient_error(err: Exception) -> bool:
    """
    Determine whether an exception represents a transient VOE fetch error that is likely retryable.

    Returns:
        True if the exception message contains any configured transient error marker, False otherwise.
    """
    if isinstance(err, ProviderTransportError):
        return True
    message = str(err).lower()
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS)
