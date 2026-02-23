from __future__ import annotations

from fastapi import APIRouter

from app.utils.logger import config as configure_logger

# Configure logging once
configure_logger()

# Shared router for all Torznab endpoints under this package
router = APIRouter(prefix="/torznab")

# Import submodules to register routes on the shared router
from . import api as _api  # noqa: F401,E402

# Re-export selected helpers for tests and external monkeypatching
from .utils import (  # noqa: E402
    SUPPORTED_PARAMS,
    _caps_xml,
    _require_apikey,
    _rss_root,
    _normalize_tokens,
    _slug_from_query,
    _add_torznab_attr,
    _estimate_size_from_title_bytes,
    _parse_btih_from_magnet,
    _build_item,
)

# Also surface dependencies the tests patch on the torznab module namespace
from app.utils.title_resolver import (  # noqa: E402
    load_or_refresh_index,
    resolve_series_title,
    load_or_refresh_alternatives,
)
from app.utils.naming import build_release_name  # noqa: E402
from app.utils.probe_quality import probe_episode_quality  # noqa: E402
from app.utils.magnet import build_magnet  # noqa: E402
from app.db import (  # noqa: E402
    get_session,
    get_availability,
    list_available_languages_cached,
    list_cached_episode_numbers_for_season,
    upsert_availability,
)

__all__ = [
    "router",
    # helpers
    "SUPPORTED_PARAMS",
    "_caps_xml",
    "_require_apikey",
    "_rss_root",
    "_normalize_tokens",
    "_slug_from_query",
    "_add_torznab_attr",
    "_estimate_size_from_title_bytes",
    "_parse_btih_from_magnet",
    "_build_item",
    # external functions used downstream and by tests
    "load_or_refresh_index",
    "resolve_series_title",
    "load_or_refresh_alternatives",
    "build_release_name",
    "probe_episode_quality",
    "build_magnet",
    "get_session",
    "get_availability",
    "list_available_languages_cached",
    "list_cached_episode_numbers_for_season",
    "upsert_availability",
]
