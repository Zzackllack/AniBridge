"""Compatibility shim: re-export models from `app.db`.

Keeping `app.db` as the canonical definition allows pytest to reset
metadata by purging that module name. This module simply forwards imports
for readability under `app.domain` and hosts shared domain-level enums.
"""

from enum import StrEnum

from app.db import *  # noqa: F401,F403


class CatalogueSite(StrEnum):
    """Distinct catalogue identifiers made available across domains."""

    ANIWORLD = "aniworld"
    STO = "sto"


SUPPORTED_CATALOG_SITES: tuple[CatalogueSite, ...] = (
    CatalogueSite.ANIWORLD,
    CatalogueSite.STO,
)
