"""Explicit provider dispatch. Public identity paths remain provider-native."""

from catalog_core.json_codec import require

from . import aniworld, megakino, sto


def adapter(provider: str):
    adapters = {"aniworld.to": aniworld, "s.to": sto, "megakino": megakino}
    require(provider in adapters, "provider adapter unavailable")
    return adapters[provider]


def listing_path(provider: str) -> str:
    adapter(provider)
    return {
        "aniworld.to": "/animes-alphabet",
        "s.to": "/serien?by=alpha",
        "megakino": "/sitemap.xml",
    }[provider]
