from __future__ import annotations

import re
import time
from functools import lru_cache

from app.providers.base import CatalogProvider, ProviderMatch
from app.providers.megakino import client as megakino_client

_MEGAKINO_SLUG_PATTERN = re.compile(r"/(?:serials|films)/\d+-([^./?#]+)")


class MegakinoProvider(CatalogProvider):
    """Catalog provider for Megakino titles and search."""

    def _is_cache_stale(self) -> bool:
        """Check if the cached index is stale and needs refreshing.

        Returns:
            True if the cache should be refreshed, False otherwise.
        """
        if self._cached_at is None:
            return True
        if self.titles_refresh_hours <= 0:
            return False
        age = time.time() - self._cached_at
        return age >= self.titles_refresh_hours * 3600.0

    def load_or_refresh_index(self) -> dict[str, str]:
        """Load the Megakino index and refresh cached entries.

        This method overrides the base implementation to use Megakino's
        sitemap-based index loading instead of HTML parsing.

        Returns:
            A dictionary mapping slugs to primary titles.
        """
        if self._cached_index is not None and not self._is_cache_stale():
            return self._cached_index
        entries = megakino_client.get_default_client().load_index()
        index = {slug: megakino_client.slug_to_title(slug) for slug in entries}
        self._cached_index = index
        self._cached_alts = {}
        self._cached_at = time.time()
        return index

    def load_or_refresh_alternatives(self) -> dict[str, list[str]]:
        """Load alternative titles for Megakino entries.

        Megakino does not currently support alternative titles, so this
        returns an empty dictionary.

        Returns:
            An empty dictionary.
        """
        self._cached_alts = {}
        return self._cached_alts

    def resolve_title(self, slug: str | None) -> str | None:
        """Resolve a Megakino slug to its primary title.

        Parameters:
            slug: The Megakino entry slug to resolve.

        Returns:
            The primary title for the given slug, or None if not found.
        """
        if not slug:
            return None
        entries = self._cached_index
        if entries is None or not entries or self._is_cache_stale():
            entries = self.load_or_refresh_index()
        if slug not in entries:
            return None
        return entries.get(slug)

    def search_slug(self, query: str) -> ProviderMatch | None:
        """Search for a Megakino entry matching the query.

        This method uses Megakino's native search API instead of the
        base class token-based matching.

        Parameters:
            query: The search query string.

        Returns:
            A ProviderMatch with the best slug and score, or None if no match.
        """
        if not query:
            return None
        results = megakino_client.get_default_client().search(query, limit=1)
        if results:
            top = results[0]
            return ProviderMatch(slug=top.slug, score=top.score)
        return None


def _build_provider() -> CatalogProvider:
    """Build the Megakino CatalogProvider with configured settings.

    Returns:
        A configured MegakinoProvider instance.
    """
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


@lru_cache(maxsize=1)
def get_provider() -> CatalogProvider:
    """Return the cached Megakino provider instance.

    Returns:
        The singleton MegakinoProvider instance.
    """
    return _build_provider()
