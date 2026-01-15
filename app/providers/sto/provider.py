from __future__ import annotations

import re

from app.providers.base import CatalogProvider


_STO_SLUG_PATTERN = re.compile(r"/serie/stream/([^/?#]+)")


def _build_provider() -> CatalogProvider:
    from app.config import (
        RELEASE_GROUP_STO,
        STO_ALPHABET_HTML,
        STO_ALPHABET_URL,
        STO_BASE_URL,
        STO_TITLES_REFRESH_HOURS,
    )

    return CatalogProvider(
        key="s.to",
        slug_pattern=_STO_SLUG_PATTERN,
        base_url=STO_BASE_URL,
        alphabet_url=STO_ALPHABET_URL,
        alphabet_html=STO_ALPHABET_HTML,
        titles_refresh_hours=STO_TITLES_REFRESH_HOURS,
        default_languages=["German Dub", "English Dub", "German Sub"],
        release_group=RELEASE_GROUP_STO,
    )


def get_provider() -> CatalogProvider:
    return _build_provider()
