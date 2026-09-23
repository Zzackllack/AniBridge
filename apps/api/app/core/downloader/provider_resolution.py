from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

from loguru import logger

from app.config import PROVIDER_ORDER
from .errors import (
    DownloadError,
    LanguageUnavailableError,
    ProviderResolutionError,
    ProviderUnavailableError,
)
from .language import normalize_language

if TYPE_CHECKING:
    from .episode import EpisodeSource


def _try_get_direct(
    ep: EpisodeSource, provider_name: str, language: str
) -> Optional[str]:
    """
    Attempt to obtain a direct download URL from a specific provider for a given language.

    Parameters:
        ep (Episode): Episode to query for a direct link.
        provider_name (str): Provider identifier to query.
        language (str): Desired language (will be normalized before the request).

    Returns:
        Optional[str]: Direct download URL if found, `None` otherwise.

    Raises:
        LanguageUnavailableError: If the provider reports the requested language is not offered; the exception contains the list of available languages.
    """
    language = normalize_language(language)
    logger.info("Trying provider '{}' for language '{}'", provider_name, language)
    try:
        url = ep.get_direct_link(provider_name, language)  # Lib-API
        if url:
            logger.success("Found direct URL from video host '{}'.", provider_name)
            return url
        logger.warning("Provider '{}' returned no URL.", provider_name)
    except LanguageUnavailableError:
        raise
    except ProviderUnavailableError as exc:
        logger.info("Video host '{}' is unavailable: {}", provider_name, exc)
    except ProviderResolutionError:
        raise
    except Exception as exc:
        logger.warning(
            "Unexpected exception from video host '{}': {}",
            provider_name,
            type(exc).__name__,
        )
    return None


def _auto_fill_languages(ep: EpisodeSource) -> Optional[object]:
    """
    Retrieve or populate the episode's available languages.

    If the episode already exposes language information via `language_name`, `languages`, or
    `available_languages`, that value is returned. Otherwise, attempts the episode's
    auto-fill methods in order: `auto_fill_details`, `_auto_fill_basic_details`,
    `auto_fill_basic_details` to populate language data, ignoring errors from those calls,
    and then returns whatever language information is available afterwards.

    Parameters:
        ep (Episode): The episode object to inspect or auto-fill.

    Returns:
        The episode's language value (e.g., a string, list, or other representation) if present,
        or `None` when no language information could be determined.
    """
    _langs = (
        getattr(ep, "language_name", None)
        or getattr(ep, "languages", None)
        or getattr(ep, "available_languages", None)
    )
    if _langs:
        return _langs
    for auto_name in (
        "auto_fill_details",
        "_auto_fill_basic_details",
        "auto_fill_basic_details",
    ):
        auto_fn = getattr(ep, auto_name, None)
        if callable(auto_fn):
            try:
                auto_fn()
                break
            except Exception as err:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to auto-fill episode details using {}(): {}",
                    auto_name,
                    err,
                )
    return (
        getattr(ep, "language_name", None)
        or getattr(ep, "languages", None)
        or getattr(ep, "available_languages", None)
    )


def _validate_language_available(ep: EpisodeSource, language: str) -> None:
    """
    Ensure the requested language is listed among the episode's available languages.

    If the episode exposes no language information, the check is skipped. If the episode provides one or more available languages and the requested language is not among them, a LanguageUnavailableError is raised containing the requested language and the available languages.

    Parameters:
        ep (Episode): Episode whose available languages will be checked.
        language (str): Language to validate (code or name as used by episode/providers).

    Raises:
        LanguageUnavailableError: If the episode reports available languages and the requested language is not present; includes the requested language and the list of available languages.
    """
    langs = _auto_fill_languages(ep)
    if langs is None:
        return
    if isinstance(langs, str):
        lang_iter = [langs]
    else:
        try:
            lang_iter = list(langs)
        except Exception:
            lang_iter = None
    if lang_iter is not None and language not in lang_iter:
        logger.error(
            "Requested language '{}' not available. Available: {}", language, lang_iter
        )
        raise LanguageUnavailableError(language, lang_iter)


def get_direct_url_with_fallback(
    ep: EpisodeSource,
    *,
    preferred: Optional[str],
    language: str,
) -> Tuple[str, str]:
    """
    Resolve a direct download URL for an episode, trying a preferred video host first and falling back to the configured host order.

    Parameters:
        ep (Episode): Episode object to resolve the direct link for.
        preferred (Optional[str]): Video host name to try first; ignored if empty or None.
        language (str): Desired language label; will be normalized before use.

    Returns:
        tuple: (direct_url, host_name) where `direct_url` is the resolved URL and `host_name` is the video host that supplied it.

    Raises:
        LanguageUnavailableError: If the requested language is not offered by the episode or a host indicates the language is unavailable.
        DownloadError: If no host yields a direct URL after all fallbacks.
    """
    language = normalize_language(language)
    logger.info(
        "Getting direct URL with fallback. Preferred: {}, Language: {}",
        preferred,
        language,
    )

    _validate_language_available(ep, language)

    tried: List[str] = []
    last_resolution_error: ProviderResolutionError | None = None

    if preferred:
        pref = preferred.strip()
        if pref:
            tried.append(pref)
            url = None
            try:
                url = _try_get_direct(ep, pref, language)
            except LanguageUnavailableError:
                raise
            except ProviderResolutionError as exc:
                last_resolution_error = exc
            if url:
                logger.success("Using preferred provider '{}'", pref)
                return url, pref

    for provider in PROVIDER_ORDER:
        if provider in tried:
            continue
        tried.append(provider)
        try:
            url = _try_get_direct(ep, provider, language)
        except LanguageUnavailableError:
            raise
        except ProviderResolutionError as exc:
            last_resolution_error = exc
            continue
        if url:
            logger.success("Using fallback provider '{}'", provider)
            return url, provider

    logger.error(
        "No direct link found. Tried providers: {}", ", ".join(tried) or "none"
    )
    if last_resolution_error is not None:
        raise last_resolution_error
    raise DownloadError(
        f"No direct link found. Tried providers: {', '.join(tried) or 'none'}"
    )
