from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import urlparse

from loguru import logger
import requests

from app.config import (
    PROVIDER_CHALLENGE_BACKOFF_SECONDS,
    PROVIDER_REDIRECT_RETRIES,
    PROVIDER_REDIRECT_TIMEOUT_SECONDS,
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
_TRANSIENT_ERROR_MARKERS = (
    "connection aborted",
    "connection reset",
    "failed to fetch voe page",
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
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if not host or host in _IGNORED_REDIRECT_HOSTS:
            continue
        if path.endswith(_IGNORED_REDIRECT_SUFFIXES):
            continue
        if candidate == current_url:
            continue
        candidates.append(candidate)

    if not candidates:
        return None

    def _score(candidate: str) -> tuple[int, int, int]:
        parsed = urlparse(candidate)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        return (
            1 if "/e/" in path else 0,
            1 if host != (current.netloc or "").lower() else 0,
            1 if "permanenttoken=" in candidate.lower() else 0,
        )

    return max(candidates, key=_score)


def build_provider_headers(*, provider_name: str, site: str) -> dict[str, str]:
    """
    Build request headers for provider fetches.

    Serienstream is more likely to allow redirect-token fetches when the request
    resembles a normal document navigation instead of a bare script client.
    """
    prepare_aniworld_home()
    import aniworld.config as aniworld_config  # type: ignore

    default_user_agent = getattr(aniworld_config, "DEFAULT_USER_AGENT", "Mozilla/5.0")
    provider_headers = getattr(aniworld_config, "PROVIDER_HEADERS_D", {})
    headers = dict(
        provider_headers.get(provider_name, {"User-Agent": default_user_agent})
    )
    if site == "s.to":
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Priority": "u=0, i",
                "Referer": "https://serienstream.to/",
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
    lowered = html.lower()
    return all(marker in lowered for marker in ("cf-turnstile", "captcha-form")) or (
        "stream wird vorbereitet" in lowered and "captcha" in lowered
    )


def fetch_provider_page(*, url: str, headers: dict[str, str]) -> tuple[str, str]:
    """
    Fetch a provider page with redirect handling and return final URL + HTML.
    """
    response = requests.get(
        url,
        headers=headers,
        timeout=PROVIDER_REDIRECT_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    response.raise_for_status()
    return str(response.url), response.text


def resolve_direct_link_from_redirect(*, redirect_url: str, site: str) -> str:
    """
    Resolve a VOE direct URL starting from the catalogue redirect token itself.

    This avoids the upstream extractor's shared niquests session and follows the
    current VOE redirect chain explicitly: catalogue token -> voe.sx -> final
    mirror host -> encoded source.
    """
    prepare_aniworld_home()
    from aniworld.extractors.provider.voe import extract_voe_source_from_html  # type: ignore

    headers = build_provider_headers(provider_name="VOE", site=site)
    pending: list[str] = [redirect_url]
    visited: set[str] = set()
    challenge_attempts: dict[str, int] = {}

    while pending:
        current_url = pending.pop(0).strip()
        if not current_url or current_url in visited:
            continue
        visited.add(current_url)

        try:
            final_url, html = fetch_provider_page(url=current_url, headers=headers)
        except requests.RequestException as exc:
            raise ValueError(f"Failed to fetch VOE page: {exc}") from exc

        if final_url != current_url and final_url not in visited:
            pending.insert(0, final_url)

        source = extract_voe_source_from_html(html)
        if source:
            logger.success("VOE direct URL resolved via {}", final_url)
            return source

        if looks_like_turnstile_page(html):
            attempts = challenge_attempts.get(current_url, 0) + 1
            challenge_attempts[current_url] = attempts
            if attempts <= PROVIDER_REDIRECT_RETRIES:
                wait_seconds = max(PROVIDER_CHALLENGE_BACKOFF_SECONDS, 1) * attempts
                logger.warning(
                    "Serienstream challenge page detected at {}. Backing off for {}s before retry {}/{}.",
                    current_url,
                    wait_seconds,
                    attempts,
                    PROVIDER_REDIRECT_RETRIES,
                )
                visited.discard(current_url)
                time.sleep(wait_seconds)
                pending.insert(0, current_url)
                continue
            raise ValueError(
                "Serienstream redirect stayed behind a Turnstile challenge after automatic backoff retries."
            )

        candidate = choose_redirect_candidate(html, final_url)
        logger.debug(
            "VOE redirect step: current={}, next={}",
            final_url,
            candidate,
        )
        if candidate and candidate not in visited:
            pending.append(candidate)

    raise ValueError("No VOE video source found in page.")


def resolve_direct_link_fallback(*, initial_urls: list[str]) -> Optional[str]:
    """
    Resolve VOE embeds by following nested HTML/JS redirects until a source exists.

    This supplements the upstream extractor, which only follows one redirect hop.
    """
    prepare_aniworld_home()
    import aniworld.config as aniworld_config  # type: ignore
    from aniworld.extractors.provider.voe import extract_voe_source_from_html  # type: ignore

    default_user_agent = getattr(aniworld_config, "DEFAULT_USER_AGENT", "Mozilla/5.0")
    global_session = getattr(aniworld_config, "GLOBAL_SESSION")
    provider_headers = getattr(aniworld_config, "PROVIDER_HEADERS_D", {})
    headers = provider_headers.get("VOE", {"User-Agent": default_user_agent})
    visited: set[str] = set()

    for start_url in initial_urls:
        next_url = (start_url or "").strip()
        while next_url and next_url not in visited:
            visited.add(next_url)
            try:
                response = global_session.get(next_url, headers=headers, timeout=10)
                response.raise_for_status()
            except Exception as err:
                logger.warning("VOE fallback failed to fetch {}: {}", next_url, err)
                break

            html = response.text
            direct_url = extract_voe_source_from_html(html)
            if direct_url:
                logger.success("VOE fallback resolved direct URL via {}", next_url)
                return direct_url

            candidate = choose_redirect_candidate(html, str(response.url))
            logger.debug(
                "VOE fallback redirect step: current={}, next={}",
                response.url,
                candidate,
            )
            if not candidate:
                break
            next_url = candidate

    return None


def is_transient_error(err: Exception) -> bool:
    """
    Detect transient VOE fetch failures that should be retried.
    """
    message = str(err).lower()
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS)
