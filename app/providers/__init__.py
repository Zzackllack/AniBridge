"""Provider implementations."""

from app.config import CATALOG_SITES_LIST

from .aniworld import get_provider as get_aniworld_provider
from .sto import get_provider as get_sto_provider
from .megakino import get_provider as get_megakino_provider

_PROVIDER_FACTORIES = {
    "aniworld.to": get_aniworld_provider,
    "s.to": get_sto_provider,
    "megakino": get_megakino_provider,
}


def get_provider(key: str):
    factory = _PROVIDER_FACTORIES.get(key)
    return factory() if factory else None


def list_providers():
    return [
        _PROVIDER_FACTORIES[site]()
        for site in CATALOG_SITES_LIST
        if site in _PROVIDER_FACTORIES
    ]


__all__ = ["get_provider", "list_providers"]
