from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.http_client import get as http_get
from app.utils.domain_resolver import get_megakino_base_url
from app.config import MEGAKINO_SITEMAP_URL, MEGAKINO_TITLES_REFRESH_HOURS
from .sitemap import MegakinoIndex, MegakinoIndexEntry, load_sitemap_index, needs_refresh


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
        self._sitemap_url = sitemap_url
        self._refresh_hours = refresh_hours
        self._index: Optional[MegakinoIndex] = None

    def load_index(self) -> Dict[str, MegakinoIndexEntry]:
        """Load or refresh the sitemap index."""
        if needs_refresh(self._index, self._refresh_hours):
            logger.info("Refreshing megakino sitemap index.")
            entries = load_sitemap_index(self._sitemap_url)
            self._index = MegakinoIndex(entries=entries, fetched_at=time_now())
        if not self._index:
            return {}
        return self._index.entries

    def search(self, query: str, limit: int = 5) -> List[MegakinoSearchResult]:
        """Search sitemap index for best matching slugs."""
        entries = self.load_index()
        q_tokens = _normalize_tokens(query)
        if not q_tokens:
            logger.debug("Megakino search skipped: empty token set for '{}'", query)
            return []
        logger.debug(
            "Megakino search tokens: {} (entries={})", q_tokens, len(entries)
        )
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
        logger.debug(
            "Megakino search results: {}", [r.slug for r in results[:limit]]
        )
        return results[: max(1, limit)]

    def resolve_url(self, slug: str) -> Optional[str]:
        """Resolve a slug to its canonical megakino URL."""
        entries = self.load_index()
        entry = entries.get(slug)
        if entry:
            return entry.url
        return None

    def resolve_direct_url(self, slug: str, preferred_provider: Optional[str] = None) -> Tuple[str, str]:
        """Resolve a direct media URL from a megakino slug."""
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
            direct = _megakino_get_direct_link(url)
            if direct:
                logger.debug("Megakino direct link resolved via '{}'", url)
                return direct, "MEGAKINO"
            if url:
                logger.debug("Megakino fallback to iframe URL '{}'", url)
                return _normalize_url(url), "EMBED"

        raise ValueError("No direct megakino provider URL resolved")


def time_now() -> float:
    """Return current time as epoch float."""
    import time

    return time.time()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = get_megakino_base_url().rstrip("/")
    normalized = f"{base}/{url.lstrip('/') }".rstrip("/")
    logger.debug("Megakino normalized URL '{}' -> '{}'", url, normalized)
    return normalized


def slug_to_title(slug: str) -> str:
    """Convert a slug into a readable title."""
    parts = slug.replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts)


def _normalize_tokens(text: str) -> List[str]:
    raw = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = [tok for tok in raw.split() if tok and not tok.isdigit()]
    return tokens


def _score_tokens(query_tokens: List[str], title_tokens: List[str]) -> int:
    if not query_tokens or not title_tokens:
        return 0
    intersection = set(query_tokens) & set(title_tokens)
    return len(intersection)


def _extract_provider_links(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("data-src") or iframe.get("src")
        if src:
            links.append(src)
    return links


def _megakino_get_direct_link(link: str) -> Optional[str]:
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
    return (
        f"https://watch.gxplayer.xyz/m3u8/{uid}/{md5}/master.txt?s=1&id={video_id}&cache=1"
    )


_DEFAULT_CLIENT: Optional[MegakinoClient] = None


def get_default_client() -> MegakinoClient:
    """Return a shared megakino client instance configured from env."""
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = MegakinoClient(
            sitemap_url=MEGAKINO_SITEMAP_URL,
            refresh_hours=MEGAKINO_TITLES_REFRESH_HOURS,
        )
    return _DEFAULT_CLIENT


def reset_default_client() -> None:
    """Reset the shared megakino client so it reloads updated configuration."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = None
