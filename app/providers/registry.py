from __future__ import annotations

"""Thread-safe registry for catalog providers."""

import threading
from typing import Dict, Iterable, List

from .base import CatalogProvider


_PROVIDER_REGISTRY: Dict[str, CatalogProvider] = {}
_PROVIDER_REGISTRY_LOCK = threading.Lock()


def register_provider(provider: CatalogProvider) -> None:
    """Register a CatalogProvider in the global registry.

    Parameters:
        provider (CatalogProvider): Provider instance to register.
    """
    with _PROVIDER_REGISTRY_LOCK:
        _PROVIDER_REGISTRY[provider.key] = provider


def get_provider(key: str) -> CatalogProvider | None:
    """Return the provider registered for the given key, if any.

    Parameters:
        key (str): Provider key to look up.
    """
    with _PROVIDER_REGISTRY_LOCK:
        return _PROVIDER_REGISTRY.get(key)


def list_providers() -> List[CatalogProvider]:
    """Return a list of all registered providers."""
    with _PROVIDER_REGISTRY_LOCK:
        return list(_PROVIDER_REGISTRY.values())


def ensure_providers(keys: Iterable[str], providers: Iterable[CatalogProvider]) -> None:
    """Register providers whose keys match the requested key list.

    Parameters:
        keys (Iterable[str]): Provider keys to include.
        providers (Iterable[CatalogProvider]): Providers to consider for registration.
    """
    keys_set = set(keys)
    for provider in providers:
        if provider.key in keys_set:
            register_provider(provider)
