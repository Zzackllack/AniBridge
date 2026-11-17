"""Worker facade for Filmo's shared bounded metadata parser."""

from catalog_core.providers.filmo import MOVIE, PAGINATION, parse

from .aniworld import Link, Page

__all__ = ["MOVIE", "PAGINATION", "Link", "Page", "parse"]
