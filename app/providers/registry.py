from __future__ import annotations

from typing import Dict, Iterable, List

from .base import CatalogProvider


_PROVIDER_REGISTRY: Dict[str, CatalogProvider] = {}


def register_provider(provider: CatalogProvider) -> None:
    _PROVIDER_REGISTRY[provider.key] = provider


def get_provider(key: str) -> CatalogProvider | None:
    return _PROVIDER_REGISTRY.get(key)


def list_providers() -> List[CatalogProvider]:
    return list(_PROVIDER_REGISTRY.values())


def ensure_providers(keys: Iterable[str], providers: Iterable[CatalogProvider]) -> None:
    for provider in providers:
        if provider.key in keys:
            register_provider(provider)
