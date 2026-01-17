from __future__ import annotations

import re

from app.providers.base import CatalogProvider


_STO_SLUG_PATTERN = re.compile(r"/serie/stream/([^/?#]+)")


def _build_provider() -> CatalogProvider:
    """Build the s.to CatalogProvider with configured index sources.

    _build_provider assembles a CatalogProvider for key "s.to" using the
    configured base URL, alphabet URL or HTML snapshot, title refresh cadence,
    default languages, and release group. Imports are local to avoid circular
    imports and unnecessary startup work when the provider is not used.
    """
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
