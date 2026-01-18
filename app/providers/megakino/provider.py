from __future__ import annotations

import re
import time

from app.providers.base import CatalogProvider, ProviderMatch
from app.providers.megakino import client as megakino_client

_MEGAKINO_SLUG_PATTERN = re.compile(r"/(?:serials|films)/\d+-([^./?#]+)")


class MegakinoProvider(CatalogProvider):
    """Catalog provider for Megakino titles and search."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cached_index: dict[str, str] | None = None
        self._cached_alts: dict[str, list[str]] | None = None
        self._cached_at: float | None = None

    def _is_cache_stale(self) -> bool:
        if self._cached_at is None:
            return True
        if self.titles_refresh_hours <= 0:
            return False
        age = time.time() - self._cached_at
        return age >= self.titles_refresh_hours * 3600.0

    def load_or_refresh_index(self) -> dict[str, str]:
        """Load the Megakino index and refresh cached entries."""
        if self._cached_index is not None and not self._is_cache_stale():
            return self._cached_index
        entries = megakino_client.get_default_client().load_index()
        index = {slug: megakino_client.slug_to_title(slug) for slug in entries}
        self._cached_index = index
        self._cached_alts = {}
        self._cached_at = time.time()
        return index

    def load_or_refresh_alternatives(self) -> dict[str, list[str]]:
        self._cached_alts = {}
        return self._cached_alts

    def resolve_title(self, slug: str | None) -> str | None:
        if not slug:
            return None
        entries = self._cached_index
        if entries is None or not entries or self._is_cache_stale():
            entries = self.load_or_refresh_index()
        if slug not in entries:
            return None
        return entries.get(slug)

    def search_slug(self, query: str) -> ProviderMatch | None:
        if not query:
            return None
        results = megakino_client.get_default_client().search(query, limit=1)
        if results:
            top = results[0]
            return ProviderMatch(slug=top.slug, score=top.score)
        return None


def _build_provider() -> CatalogProvider:
    from app.config import MEGAKINO_BASE_URL, MEGAKINO_TITLES_REFRESH_HOURS

    return MegakinoProvider(
        key="megakino",
        slug_pattern=_MEGAKINO_SLUG_PATTERN,
        base_url=MEGAKINO_BASE_URL,
        alphabet_url="",
        alphabet_html=None,
        titles_refresh_hours=MEGAKINO_TITLES_REFRESH_HOURS,
        default_languages=["Deutsch", "German Dub"],
        release_group="megakino",
    )


def get_provider() -> CatalogProvider:
    return _build_provider()
