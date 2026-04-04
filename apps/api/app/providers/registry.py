"""
Deprecated provider registry module.

This module originally implemented a standalone, thread-safe registry for
:class:`CatalogProvider` instances. The current provider initialization flow
in ``app.providers`` does not use this registry at all, which made the
previous implementation dead code and a potential source of confusion.

The functions defined here are retained as stubs for backwards compatibility
only. They deliberately raise :class:`RuntimeError` when called so that any
accidental usage fails loudly and directs maintainers to the supported
provider management API.
"""

from __future__ import annotations

from typing import Iterable, List

from .base import CatalogProvider


def _deprecated_registry_error(function_name: str) -> RuntimeError:
    """
    Create a standardized error for calls into this deprecated module.

    Parameters:
        function_name: Name of the registry function that was called.

    Returns:
        RuntimeError indicating that the legacy registry is not supported.
    """
    message = (
        f"app.providers.registry.{function_name}() is deprecated and the "
        "legacy provider registry is no longer used. Please use the "
        "public provider access functions exposed by the 'app.providers' "
        "package instead."
    )
    return RuntimeError(message)


def register_provider(provider: CatalogProvider) -> None:
    """
    Deprecated stub for registering a provider in the legacy registry.

    This function previously stored the given provider instance in an
    internal, thread-safe registry that is now unused. It now raises
    :class:`RuntimeError` unconditionally to make any accidental use
    explicit.

    Parameters:
        provider: Provider instance that would have been registered.

    Raises:
        RuntimeError: Always raised to indicate the registry is deprecated.
    """
    _ = provider
    raise _deprecated_registry_error("register_provider")


def get_provider(key: str) -> CatalogProvider | None:
    """
    Deprecated stub for retrieving a provider from the legacy registry.

    The active provider lookup logic is implemented in the
    ``app.providers`` package, not in this module.

    Parameters:
        key: Provider key that would have been used to perform the lookup.

    Returns:
        This function never returns; it always raises :class:`RuntimeError`.

    Raises:
        RuntimeError: Always raised to indicate the registry is deprecated.
    """
    _ = key
    raise _deprecated_registry_error("get_provider")


def list_providers() -> List[CatalogProvider]:
    """
    Deprecated stub for listing providers from the legacy registry.

    The authoritative list of providers is managed by the
    ``app.providers`` package.

    Returns:
        This function never returns; it always raises :class:`RuntimeError`.

    Raises:
        RuntimeError: Always raised to indicate the registry is deprecated.
    """
    _ = CatalogProvider
    raise _deprecated_registry_error("list_providers")


def ensure_providers(
    keys: Iterable[str],
    providers: Iterable[CatalogProvider],
) -> None:
    """
    Deprecated stub for conditionally registering providers.

    The original implementation registered providers in the local registry
    if their keys matched the provided key set. Since the legacy registry is
    no longer used, this function now raises :class:`RuntimeError` to
    prevent silent divergence from the supported provider workflow.

    Parameters:
        keys: Iterable of provider keys that would have been used for matching.
        providers: Iterable of provider instances that would have been considered
            for registration.

    Raises:
        RuntimeError: Always raised to indicate the registry is deprecated.
    """
    _ = (keys, providers)
    raise _deprecated_registry_error("ensure_providers")
