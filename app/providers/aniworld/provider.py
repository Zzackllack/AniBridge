from __future__ import annotations

import re

from app.config import (
    ANIWORLD_ALPHABET_HTML,
    ANIWORLD_ALPHABET_URL,
    ANIWORLD_BASE_URL,
    ANIWORLD_TITLES_REFRESH_HOURS,
    RELEASE_GROUP_ANIWORLD,
)
from app.providers.base import CatalogProvider


_ANIWORLD_SLUG_PATTERN = re.compile(r"/anime/stream/([^/?#]+)")


_ANIWORLD_PROVIDER = CatalogProvider(
    key="aniworld.to",
    slug_pattern=_ANIWORLD_SLUG_PATTERN,
    base_url=ANIWORLD_BASE_URL,
    alphabet_url=ANIWORLD_ALPHABET_URL,
    alphabet_html=ANIWORLD_ALPHABET_HTML,
    titles_refresh_hours=ANIWORLD_TITLES_REFRESH_HOURS,
    default_languages=["German Dub", "German Sub", "English Sub"],
    release_group=RELEASE_GROUP_ANIWORLD,
)


def get_provider() -> CatalogProvider:
    return _ANIWORLD_PROVIDER
