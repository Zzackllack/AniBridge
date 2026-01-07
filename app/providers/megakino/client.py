from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.http_client import get as http_get
from app.utils.domain_resolver import get_megakino_base_url
from app.config import MEGAKINO_TITLES_REFRESH_HOURS
from .sitemap import (
    MegakinoIndex,
    MegakinoIndexEntry,
    load_sitemap_index,
    needs_refresh,
)


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
        self, slug: str, preferred_provider: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Resolve a direct media URL and its provider name for a given Megakino slug.

        Parameters:
            slug (str): Megakino page slug to resolve.
            preferred_provider (Optional[str]): Optional provider identifier to prefer when multiple providers are available.

        Returns:
            tuple: (`url`, `provider_name`) where `url` is the direct media URL (or an iframe URL fallback) and `provider_name` is the inferred provider label (for example, `"EMBED"`).

        Raises:
            ValueError: If the slug does not map to a Megakino page, if no provider iframes are found, or if no provider yields a resolvable URL.
        """
        page_url = self.resolve_url(slug)
        if not page_url:
            raise ValueError(f"Megakino page not found for slug '{slug}'")
        logger.debug("Megakino page URL resolved: {}", page_url)
        resp = http_get(page_url, timeout=20)
        resp.raise_for_status()
        providers = _extract_provider_links(resp.text)
        if not providers:
            raise ValueError("No provider iframes found on megakino page")
        logger.debug("Megakino providers extracted: {}", providers)

        preferred = (preferred_provider or "").lower()
        ordered = providers
        if preferred:
            ordered = sorted(
                providers,
                key=lambda url: 0 if preferred in url.lower() else 1,
            )

        for url in ordered:
            direct = _extract_provider_direct(url)
            if direct:
                logger.debug("Megakino direct link resolved via '{}'", url)
                return direct, _provider_name_from_url(url)
            logger.debug("Megakino extractor did not return direct URL for '{}'", url)

        # Fallback to first iframe URL for yt-dlp to try if supported.
        if providers:
            fallback = _normalize_url(providers[0])
            logger.debug("Megakino fallback to iframe URL '{}'", fallback)
            return fallback, "EMBED"

        raise ValueError("No direct megakino provider URL resolved")


def resolve_direct_url(
    slug: str, preferred_provider: Optional[str] = None
) -> Tuple[str, str]:
    """
    Resolve a slug to a direct media URL using the default shared MegakinoClient.

    Parameters:
        slug (str): Megakino slug identifying the media page.
        preferred_provider (Optional[str]): Optional provider name to prefer when multiple providers are available.

    Returns:
        Tuple[str, str]: A tuple containing the resolved direct media URL and the provider label used (e.g., `"EMBED"` when falling back to an embed URL).
    """
    client = get_default_client()
    return client.resolve_direct_url(slug, preferred_provider=preferred_provider)


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
    for iframe in soup.find_all("iframe"):
        src = iframe.get("data-src") or iframe.get("src")
        if src:
            links.append(src)
    return links


def _megakino_get_direct_link(link: str) -> Optional[str]:
    """
    Probe a Megakino provider page and construct a gxplayer direct media URL when the page exposes the required identifiers.

    Parameters:
        link (str): URL of the provider page to fetch and inspect.

    Returns:
        str: Constructed gxplayer m3u8 URL when `uid`, `md5`, and `id` are present in the page, `None` otherwise.
    """
    logger.debug("Megakino direct link probe: {}", link)
    try:
        resp = http_get(link, timeout=20)
    except Exception as exc:
        logger.warning("Megakino provider fetch failed: {}", exc)
        return None
    uid_match = re.search(r'"uid":"(.*?)"', resp.text)
    md5_match = re.search(r'"md5":"(.*?)"', resp.text)
    id_match = re.search(r'"id":"(.*?)"', resp.text)
    if not all([uid_match, md5_match, id_match]):
        return None
    uid = uid_match.group(1)
    md5 = md5_match.group(1)
    video_id = id_match.group(1)
    return f"https://watch.gxplayer.xyz/m3u8/{uid}/{md5}/master.txt?s=1&id={video_id}&cache=1"


def _provider_name_from_url(url: str) -> str:
    """
    Infer the canonical provider name from a provider or embed URL.

    Parameters:
        url (str): The provider or iframe URL to inspect.

    Returns:
        provider_name (str): One of the known provider identifiers (e.g., "VOE", "Doodstream", "Filemoon", "Streamtape", "Vidmoly", "SpeedFiles", "LoadX", "Luluvdo", "Vidoza"); returns "EMBED" if no known provider is detected.
    """
    host = urlparse(url).netloc.lower()
    if "voe" in host:
        return "VOE"
    if "dood" in host or "d0000d" in host:
        return "Doodstream"
    if "filemoon" in host:
        return "Filemoon"
    if "streamtape" in host or "streamta.pe" in host:
        return "Streamtape"
    if "vidmoly" in host:
        return "Vidmoly"
    if "speedfiles" in host:
        return "SpeedFiles"
    if "loadx" in host:
        return "LoadX"
    if "luluvdo" in host:
        return "Luluvdo"
    if "vidoza" in host:
        return "Vidoza"
    return "EMBED"


def _extract_provider_direct(url: str) -> Optional[str]:
    """
    Determine and return a direct media URL for a provider iframe URL by selecting and invoking a provider-specific extractor.

    The function inspects the host part of `url` to choose a provider extractor (e.g., Voe, Doodstream, Filemoon, Streamtape, Vidmoly, Speedfiles, Loadx, Luluvdo, Vidoza). If a matching extractor is available it is imported and called; if the host contains "gxplayer" a legacy GXPlayer extraction is attempted. Any extraction error is caught and results in `None`.

    Parameters:
        url (str): The provider iframe URL to resolve.

    Returns:
        str | None: The direct media URL produced by the provider extractor, or `None` if no extractor matches or extraction fails.
    """
    host = urlparse(url).netloc.lower()
    try:
        if "voe" in host:
            from aniworld.extractors.provider.voe import (  # type: ignore
                get_direct_link_from_voe,
            )

            return get_direct_link_from_voe(url)
        if "dood" in host or "d0000d" in host:
            from aniworld.extractors.provider.doodstream import (  # type: ignore
                get_direct_link_from_doodstream,
            )

            return get_direct_link_from_doodstream(url)
        if "filemoon" in host:
            from aniworld.extractors.provider.filemoon import (  # type: ignore
                get_direct_link_from_filemoon,
            )

            return get_direct_link_from_filemoon(url)
        if "streamtape" in host or "streamta.pe" in host:
            from aniworld.extractors.provider.streamtape import (  # type: ignore
                get_direct_link_from_streamtape,
            )

            return get_direct_link_from_streamtape(url)
        if "vidmoly" in host:
            from aniworld.extractors.provider.vidmoly import (  # type: ignore
                get_direct_link_from_vidmoly,
            )

            return get_direct_link_from_vidmoly(url)
        if "speedfiles" in host:
            from aniworld.extractors.provider.speedfiles import (  # type: ignore
                get_direct_link_from_speedfiles,
            )

            return get_direct_link_from_speedfiles(url)
        if "loadx" in host:
            from aniworld.extractors.provider.loadx import (  # type: ignore
                get_direct_link_from_loadx,
            )

            return get_direct_link_from_loadx(url)
        if "luluvdo" in host:
            from aniworld.extractors.provider.luluvdo import (  # type: ignore
                get_direct_link_from_luluvdo,
            )

            return get_direct_link_from_luluvdo(url)
        if "vidoza" in host:
            from aniworld.extractors.provider.vidoza import (  # type: ignore
                get_direct_link_from_vidoza,
            )

            return get_direct_link_from_vidoza(url)
    except Exception as exc:
        logger.warning("Megakino provider extraction failed for {}: {}", url, exc)
        return None
    # Try the legacy gxplayer extractor for direct links if present.
    if "gxplayer" in host:
        direct = _megakino_get_direct_link(url)
        return direct
    return None


_DEFAULT_CLIENT: Optional[MegakinoClient] = None


def get_default_client() -> MegakinoClient:
    """Return a shared megakino client instance configured from env."""
    global _DEFAULT_CLIENT
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
