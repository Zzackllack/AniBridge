from __future__ import annotations

import re

from app.config import MEGAKINO_BASE_URL, MEGAKINO_TITLES_REFRESH_HOURS
from app.providers.base import CatalogProvider, ProviderMatch
from app.providers.megakino import client as megakino_client


_MEGAKINO_SLUG_PATTERN = re.compile(r"/(?:serials|films)/\d+-([^./?#]+)")


class MegakinoProvider(CatalogProvider):
    def load_or_refresh_index(self) -> dict[str, str]:
        entries = megakino_client.get_default_client().load_index()
        index = {slug: megakino_client.slug_to_title(slug) for slug in entries}
        self._cached_index = index
        self._cached_alts = {}
        self._cached_at = self._cached_at or 0.0
        return index

    def load_or_refresh_alternatives(self) -> dict[str, list[str]]:
        self._cached_alts = {}
        return self._cached_alts

    def resolve_title(self, slug: str | None) -> str | None:
        if not slug:
            return None
        entries = megakino_client.get_default_client().load_index()
        if slug not in entries:
            return None
        return megakino_client.slug_to_title(slug)

    def search_slug(self, query: str) -> ProviderMatch | None:
        if not query:
            return None
        results = megakino_client.get_default_client().search(query, limit=1)
        if results:
            top = results[0]
            return ProviderMatch(slug=top.slug, score=top.score)
        return None


_MEGAKINO_PROVIDER = MegakinoProvider(
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
    return _MEGAKINO_PROVIDER
