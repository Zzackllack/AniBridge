from __future__ import annotations

from importlib import import_module
from typing import Optional

from loguru import logger

from app.utils.aniworld_compat import prepare_aniworld_home


def _get_registry_extractor(function_name: str):
    try:
        extractors_module = import_module("aniworld.extractors")
    except ImportError:
        return None

    provider_functions = getattr(extractors_module, "provider_functions", {})
    extractor = provider_functions.get(function_name)
    if callable(extractor):
        return extractor
    return None


def resolve_via_aniworld(
    *,
    module_name: str,
    function_name: str,
    url: str,
    host_name: str,
) -> Optional[str]:
    """Call an upstream aniworld extractor through a thin local host wrapper."""
    prepare_aniworld_home()

    extractor = _get_registry_extractor(function_name)
    if extractor is not None:
        return extractor(url)

    try:
        module = import_module(f"aniworld.extractors.provider.{module_name}")
        extractor = getattr(module, function_name)
    except (ImportError, AttributeError) as exc:
        logger.debug(
            "{} host module import failed for {}: {}; trying provider_functions fallback",
            host_name,
            url,
            exc,
        )
        extractor = _get_registry_extractor(function_name)
        if extractor is None:
            return None

    return extractor(url)
