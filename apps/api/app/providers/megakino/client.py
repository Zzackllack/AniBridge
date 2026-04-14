from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import threading
import re
import time
import warnings
from urllib.parse import urlparse

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.hosts import detect_host, resolve_host_url
from app.utils.http_client import get as http_get
from app.utils.domain_resolver import get_megakino_base_url
from app.config import MEGAKINO_TITLES_REFRESH_HOURS
from .sitemap import (
    MegakinoIndex,
    MegakinoIndexEntry,
    load_sitemap_index,
    needs_refresh,
)

MEGAKINO_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_MEGAKINO_TOKEN_LOCK = threading.Lock()
_MEGAKINO_TOKEN_AT = 0.0
_MEGAKINO_TOKEN_TTL_SECONDS = 30 * 60
_DEFAULT_CLIENT_LOCK = threading.Lock()


def _is_disabled_provider_url(url: str) -> bool:
    """Return whether a host URL points to a disabled extractor host."""

    return "speedfiles" in urlparse(url).netloc.lower()


@dataclass
class MegakinoSearchResult:
    """Represents a megakino search match."""

    slug: str
    url: str
    title: str
    score: int
    kind: str


class MegakinoClient:
    """Client for resolving megakino slugs and direct links."""

    def __init__(
        self,
        *,
        sitemap_url: str,
        refresh_hours: float,
    ) -> None:
        """
        Initialize the MegakinoClient with the sitemap source and cache refresh interval.

        Parameters:
            sitemap_url (str): URL of the sitemap index used to build and refresh the internal slug-to-entry index.
            refresh_hours (float): Hours to treat the cached sitemap index as fresh before reloading. The index is not loaded during construction; call `load_index()` to populate the cache.
        """
        self._sitemap_url = sitemap_url
        self._refresh_hours = refresh_hours
        self._index: Optional[MegakinoIndex] = None

    def load_index(self) -> Dict[str, MegakinoIndexEntry]:
        """
        Return the sitemap index mapping slugs to their MegakinoIndexEntry, refreshing the cached index when it is stale.

        The client will refresh its cached sitemap index according to its configured refresh interval before returning results.

        Returns:
            Dict[str, MegakinoIndexEntry]: Mapping from slug to index entry. Returns an empty dict if no index is available.
        """
        if needs_refresh(self._index, self._refresh_hours):
            logger.info("Refreshing megakino sitemap index.")
            entries = load_sitemap_index(self._sitemap_url)
            self._index = MegakinoIndex(entries=entries, fetched_at=time_now())
        if not self._index:
            return {}
        return self._index.entries

    def search(self, query: str, limit: int = 5) -> List[MegakinoSearchResult]:
        """
        Search the sitemap index for entries matching the provided query and return the top matches.

        Searches the cached sitemap index for slugs whose derived titles match the query and returns up to `limit` results ordered by relevance. If the query yields no meaningful tokens an empty list is returned.

        Parameters:
            query (str): The user query to match against sitemap slugs.
            limit (int): Maximum number of results to return.

        Returns:
            List[MegakinoSearchResult]: A list of matching search results ordered by descending score; empty if the query produced no tokens or `limit` is 0.
        """
        entries = self.load_index()
        q_tokens = _normalize_tokens(query)
        if not q_tokens:
            logger.debug("Megakino search skipped: empty token set for '{}'", query)
            return []
        logger.debug("Megakino search tokens: {} (entries={})", q_tokens, len(entries))
        results: List[MegakinoSearchResult] = []
        for entry in entries.values():
            title = slug_to_title(entry.slug)
            score = _score_tokens(q_tokens, _normalize_tokens(title))
            if score <= 0:
                continue
            results.append(
                MegakinoSearchResult(
                    slug=entry.slug,
                    url=entry.url,
                    title=title,
                    score=score,
                    kind=entry.kind,
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        logger.debug("Megakino search results: {}", [r.slug for r in results[:limit]])
        if limit <= 0:
            return []
        return results[:limit]

    def resolve_url(self, slug: str) -> Optional[str]:
        """
        Resolve a megakino slug to its canonical page URL.

        Parameters:
            slug (str): Megakino slug identifier to resolve.

        Returns:
            Optional[str]: The canonical URL for the slug, or `None` if the slug is not found.
        """
        entries = self.load_index()
        entry = entries.get(slug)
        if entry:
            return entry.url
        return None

    def resolve_direct_url(
        self,
        slug: str,
        preferred_host: Optional[str] = None,
        *,
        preferred_provider: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Resolve a direct media URL and its host name for a given Megakino slug.

        Parameters:
            slug (str): Megakino page slug to resolve.
            preferred_host (Optional[str]): Optional video-host identifier to prefer when multiple embeds are available.
            preferred_provider (Optional[str]): Deprecated alias for `preferred_host`.

        Returns:
            tuple: (`url`, `host_name`) where `url` is the direct media URL (or an iframe URL fallback) and `host_name` is the inferred video-host label (for example, `"EMBED"`).

        Raises:
            ValueError: If the slug does not map to a Megakino page, if no video-host iframes are found, or if no video host yields a resolvable URL.
        """
        if preferred_host is None and preferred_provider is not None:
            warnings.warn(
                "preferred_provider is deprecated; use preferred_host instead",
                DeprecationWarning,
                stacklevel=2,
            )
            preferred_host = preferred_provider

        page_url = self.resolve_url(slug)
        if not page_url:
            raise ValueError(f"Megakino page not found for slug '{slug}'")
        logger.debug("Megakino page URL resolved: {}", page_url)
        base_url = get_megakino_base_url().rstrip("/")
        _warm_megakino_session(base_url)
        resp = http_get(
            page_url,
            timeout=20,
            headers=_megakino_headers(referer=base_url),
        )
        resp.raise_for_status()
        host_urls = [
            url
            for url in _extract_provider_links(resp.text)
            if not _is_disabled_provider_url(url)
        ]
        if not host_urls:
            raise ValueError("No video host iframes found on megakino page")
        logger.debug("Megakino video hosts extracted: {}", host_urls)

        preferred = (preferred_host or "").lower()
        ordered = host_urls
        if preferred:
            ordered = sorted(
                host_urls,
                key=lambda url: 0 if preferred in url.lower() else 1,
            )

        for url in ordered:
            direct, host_name = resolve_host_url(url)
            if direct:
                logger.debug("Megakino direct link resolved via '{}'", url)
                return direct, host_name
            logger.debug(
                "Megakino host resolver did not return a direct URL for '{}'", url
            )

        # Fallback to first iframe URL for yt-dlp to try if supported.
        if host_urls:
            fallback = _normalize_url(host_urls[0])
            logger.debug("Megakino fallback to iframe URL '{}'", fallback)
            return fallback, "EMBED"

        raise ValueError("No direct megakino host URL resolved")


def resolve_direct_url(
    slug: str,
    preferred_host: Optional[str] = None,
    *,
    preferred_provider: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Resolve a slug to a direct media URL using the default shared MegakinoClient.

    Parameters:
        slug (str): Megakino slug identifying the media page.
        preferred_host (Optional[str]): Optional video-host name to prefer when multiple embeds are available.
        preferred_provider (Optional[str]): Deprecated alias for `preferred_host`.

    Returns:
        Tuple[str, str]: A tuple containing the resolved direct media URL and the host label used (e.g., `"EMBED"` when falling back to an embed URL).
    """
    client = get_default_client()
    return client.resolve_direct_url(
        slug,
        preferred_host=preferred_host,
        preferred_provider=preferred_provider,
    )


def time_now() -> float:
    """
    Get the current time as seconds since the Unix epoch.

    Returns:
        epoch_seconds (float): Seconds since the Unix epoch.
    """
    return time.time()


def _normalize_url(url: str) -> str:
    """
    Normalize a Megakino URL to an absolute URL using the configured Megakino base.

    Parameters:
        url (str): A URL which may be absolute or relative (may be empty).

    Returns:
        str: The absolute URL when `url` is relative or already absolute; an empty string if `url` is empty.
    """
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = get_megakino_base_url().rstrip("/")
    normalized = f"{base}/{url.lstrip('/')}".rstrip("/")
    logger.debug("Megakino normalized URL '{}' -> '{}'", url, normalized)
    return normalized


def slug_to_title(slug: str) -> str:
    """
    Convert a slug into a human-readable title by replacing hyphens with spaces and capitalizing words.

    Returns:
        A title (str) where hyphens are replaced by spaces and each word is capitalized.
    """
    parts = slug.replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts)


def _normalize_tokens(text: str) -> List[str]:
    """
    Normalize input text into lowercase alphanumeric word tokens, excluding tokens that are purely numeric.

    Parameters:
        text (str): Input string to tokenize.

    Returns:
        List[str]: A list of lowercase tokens containing letters or alphanumeric mixes; tokens composed only of digits are omitted.
    """
    raw = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = [tok for tok in raw.split() if tok and not tok.isdigit()]
    return tokens


def _score_tokens(query_tokens: List[str], title_tokens: List[str]) -> int:
    """
    Compute the number of shared tokens between a query and a title.

    Returns:
        int: Number of tokens present in both lists; returns 0 if either input list is empty.
    """
    if not query_tokens or not title_tokens:
        return 0
    intersection = set(query_tokens) & set(title_tokens)
    return len(intersection)


def _extract_provider_links(html: str) -> List[str]:
    """
    Extract iframe provider URLs from the given HTML.

    Parameters:
        html (str): HTML content to parse.

    Returns:
        List[str]: Provider URLs extracted from iframe `data-src` or `src` attributes, in document order.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    seen: set[str] = set()

    def _add_link(url: Optional[str]) -> None:
        if not url:
            return
        if url in seen:
            return
        links.append(url)
        seen.add(url)

    for iframe in soup.find_all("iframe"):
        src = iframe.get("data-src") or iframe.get("src")
        if src:
            _add_link(src)

    if links:
        host_links = [
            link for link in links if _looks_like_provider_url(_normalize_url(link))
        ]
        return host_links or links

    for attr in ("data-src", "data-iframe", "data-embed", "data-player"):
        for tag in soup.find_all(attrs={attr: True}):
            candidate = tag.get(attr)
            if candidate and _looks_like_provider_url(_normalize_url(candidate)):
                _add_link(candidate)

    if links:
        return links

    for match in re.findall(r"https?://[^\s'\"<>]+", html):
        if _looks_like_provider_url(match):
            _add_link(match)

    return links


def _looks_like_provider_url(url: str) -> bool:
    return detect_host(url) is not None or "speedfiles" in urlparse(url).netloc.lower()


def _megakino_headers(*, referer: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "User-Agent": MEGAKINO_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _warm_megakino_session(base_url: str) -> None:
    global _MEGAKINO_TOKEN_AT
    now = time_now()
    if now - _MEGAKINO_TOKEN_AT < _MEGAKINO_TOKEN_TTL_SECONDS:
        return
    token_url = f"{base_url.rstrip('/')}/index.php?yg=token"
    with _MEGAKINO_TOKEN_LOCK:
        now = time_now()
        if now - _MEGAKINO_TOKEN_AT < _MEGAKINO_TOKEN_TTL_SECONDS:
            return
        try:
            http_get(
                token_url,
                timeout=10,
                headers=_megakino_headers(referer=base_url),
            )
            _MEGAKINO_TOKEN_AT = now
            logger.debug("Megakino token request ok")
        except Exception as exc:
            logger.debug("Megakino token request failed: {}", exc)


_DEFAULT_CLIENT: Optional[MegakinoClient] = None


def get_default_client() -> MegakinoClient:
    """
    Get the shared MegakinoClient singleton configured from environment.

    Creates and caches a MegakinoClient on first call using the resolved Megakino base URL (sitemap set to `{base_url}/sitemap.xml`) and configured refresh interval.

    Returns:
        MegakinoClient: the shared client instance.
    """
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        with _DEFAULT_CLIENT_LOCK:
            if _DEFAULT_CLIENT is None:
                base_url = get_megakino_base_url().rstrip("/")
                _DEFAULT_CLIENT = MegakinoClient(
                    sitemap_url=f"{base_url}/sitemap.xml",
                    refresh_hours=MEGAKINO_TITLES_REFRESH_HOURS,
                )
    return _DEFAULT_CLIENT


def reset_default_client() -> None:
    """Reset the shared megakino client so it reloads updated configuration."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = None
