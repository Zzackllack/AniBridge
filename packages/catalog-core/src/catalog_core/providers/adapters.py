"""Explicit provider dispatch. Public identity paths remain provider-native."""

from catalog_core.json_codec import require


def adapter(provider: str):
    from importlib import import_module

    modules = {"aniworld.to": "aniworld", "s.to": "sto", "megakino": "megakino"}
    require(provider in modules, "provider adapter unavailable")
    return import_module("." + modules[provider], __package__)


def listing_path(provider: str) -> str:
    adapter(provider)
    return {
        "aniworld.to": "/animes-alphabet",
        "s.to": "/serien?by=alpha",
        "megakino": "/sitemap.xml",
    }[provider]
