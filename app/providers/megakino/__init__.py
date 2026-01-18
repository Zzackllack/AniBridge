"""Megakino provider implementation."""

from .client import MegakinoClient, MegakinoSearchResult
from .sitemap import MegakinoIndexEntry
from .provider import get_provider

__all__ = [
    "MegakinoClient",
    "MegakinoIndexEntry",
    "MegakinoSearchResult",
    "get_provider",
]
