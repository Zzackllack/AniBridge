from __future__ import annotations

import re
from functools import lru_cache

from app.providers.base import CatalogProvider

_ANIWORLD_SLUG_PATTERN = re.compile(r"/anime/stream/([^/?#]+)")


def _build_provider() -> CatalogProvider:
    """Build the AniWorld CatalogProvider with configured index sources.

    Returns:
        A configured CatalogProvider instance for AniWorld.
    """
    from app.config import (
        ANIWORLD_ALPHABET_HTML,
        ANIWORLD_ALPHABET_URL,
        ANIWORLD_BASE_URL,
        ANIWORLD_TITLES_REFRESH_HOURS,
        RELEASE_GROUP_ANIWORLD,
    )

    return CatalogProvider(
        key="aniworld.to",
        slug_pattern=_ANIWORLD_SLUG_PATTERN,
        base_url=ANIWORLD_BASE_URL,
        alphabet_url=ANIWORLD_ALPHABET_URL,
        alphabet_html=ANIWORLD_ALPHABET_HTML,
        titles_refresh_hours=ANIWORLD_TITLES_REFRESH_HOURS,
        default_languages=["German Dub", "German Sub", "English Sub"],
        release_group=RELEASE_GROUP_ANIWORLD,
    )


@lru_cache(maxsize=1)
def get_provider() -> CatalogProvider:
    """Return the cached AniWorld provider instance.

    Returns:
        The singleton CatalogProvider instance for AniWorld.
    """
    return _build_provider()
