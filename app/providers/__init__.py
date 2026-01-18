"""Provider implementations."""

from typing import Optional

from app.config import CATALOG_SITES_LIST

from .aniworld import get_provider as get_aniworld_provider
from .sto import get_provider as get_sto_provider
from .megakino import get_provider as get_megakino_provider
from .base import CatalogProvider

_PROVIDER_FACTORIES = {
    "aniworld.to": get_aniworld_provider,
    "s.to": get_sto_provider,
    "megakino": get_megakino_provider,
}


def get_provider(key: str) -> Optional[CatalogProvider]:
    """Return the provider instance for a given key, if available.

    Parameters:
        key (str): Provider key mapped in _PROVIDER_FACTORIES.

    Returns:
        CatalogProvider | None: Provider instance or None when missing.
    """
    factory = _PROVIDER_FACTORIES.get(key)
    return factory() if factory else None


def list_providers() -> list[CatalogProvider]:
    """Return provider instances for sites enabled in CATALOG_SITES_LIST.

    Returns:
        list[CatalogProvider]: Instantiated providers for active sites.
    """
    return [
        _PROVIDER_FACTORIES[site]()
        for site in CATALOG_SITES_LIST
        if site in _PROVIDER_FACTORIES
    ]


__all__ = ["get_provider", "list_providers"]
