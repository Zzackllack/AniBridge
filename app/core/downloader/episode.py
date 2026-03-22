from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Optional, TYPE_CHECKING
from urllib.parse import urlparse

from loguru import logger

from app.config import (
    CATALOG_SITE_CONFIGS,
    PROVIDER_REDIRECT_RETRIES,
    PROVIDER_REDIRECT_TIMEOUT_SECONDS,
)
from app.core.downloader.extractors import voe as voe_extractor
from app.utils.aniworld_compat import prepare_aniworld_home

if TYPE_CHECKING:
    from aniworld.models import Episode


def _resolve_provider_redirect_url(redirect_url: str, provider_name: str) -> str:
    """
    Resolve a redirect URL to its final provider embed URL, retrying on transient failures.

    Parameters:
        redirect_url (str): The catalogue redirect URL or token to follow.
        provider_name (str): Human-readable provider identifier used in log messages.

    Returns:
        str: The final resolved URL after following redirects.

    Raises:
        ValueError: If all retry attempts fail; the exception message contains the last underlying error.
    """
    prepare_aniworld_home()
    from aniworld.config import GLOBAL_SESSION  # type: ignore

    attempts = PROVIDER_REDIRECT_RETRIES + 1
    last_error: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        try:
            response = GLOBAL_SESSION.get(
                redirect_url,
                timeout=PROVIDER_REDIRECT_TIMEOUT_SECONDS,
            )
            return str(response.url)
        except Exception as err:
            last_error = err
            logger.warning(
                "Provider redirect resolution failed for '{}' (attempt {}/{}): {}",
                provider_name,
                attempt,
                attempts,
                err,
            )

    raise ValueError(str(last_error))


def _get_direct_link_with_retries(
    *,
    provider_name: str,
    redirect_url: str,
    extractor: Any,
    site: str,
) -> str:
    """
    Resolve a provider's final direct media URL, retrying transient VOE failures.

    Attempts provider direct-link extraction up to PROVIDER_REDIRECT_RETRIES + 1 times. For provider "voe" on site "s.to" it uses the VOE extractor's direct resolve path and will retry on errors that VOE marks as transient, applying a small backoff between attempts; for other providers it resolves the provider redirect URL and calls the supplied extractor. If VOE extraction fails to produce a direct URL, a VOE fallback resolver is attempted before failing.

    Returns:
        The resolved direct media URL as a string.

    Raises:
        ValueError: If resolution fails after retries or if the extractor returns no direct URL.
        Exception: Any exception raised by the extractor (propagated after retry logic).
    """
    attempts = PROVIDER_REDIRECT_RETRIES + 1
    last_error: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        direct_url = None
        extractor_error: Optional[Exception] = None

        if provider_name.lower() == "voe" and site == "s.to":
            try:
                return voe_extractor.resolve_direct_link_from_redirect(
                    redirect_url=redirect_url,
                    site=site,
                )
            except ValueError as exc:
                extractor_error = exc
                logger.warning("VOE extractor failed for {}: {}", redirect_url, exc)
                last_error = extractor_error
                if attempt < attempts and voe_extractor.is_transient_error(
                    extractor_error
                ):
                    logger.warning(
                        "Retrying VOE direct extraction after transient failure (attempt {}/{}).",
                        attempt + 1,
                        attempts,
                    )
                    time.sleep(min(1.0 * attempt, 2.0))
                    continue

        provider_url = _resolve_provider_redirect_url(redirect_url, provider_name)

        try:
            direct_url = extractor(provider_url)
        except ValueError as exc:
            if extractor_error is None:
                extractor_error = exc
            if provider_name.lower() != "voe":
                raise
            logger.warning("VOE extractor failed for {}: {}", provider_url, exc)

        if not direct_url and provider_name.lower() == "voe":
            direct_url = voe_extractor.resolve_direct_link_fallback(
                initial_urls=[provider_url, redirect_url]
            )
            if direct_url:
                return direct_url

        if direct_url:
            return direct_url

        if extractor_error is None:
            raise ValueError(
                f"Extractor for provider '{provider_name}' returned no direct URL."
            )

        last_error = extractor_error
        if provider_name.lower() != "voe":
            raise extractor_error
        if attempt >= attempts or not voe_extractor.is_transient_error(extractor_error):
            raise extractor_error

        logger.warning(
            "Retrying VOE direct extraction after transient failure (attempt {}/{}).",
            attempt + 1,
            attempts,
        )
        time.sleep(min(1.0 * attempt, 2.0))

    if last_error is not None:
        raise last_error
    raise ValueError(f"Failed to resolve provider '{provider_name}' direct URL.")


def _site_base_url(site: str) -> str:
    """
    Resolve the configured base URL for a catalogue site.

    Parameters:
        site: Catalogue site identifier such as `aniworld.to` or `s.to`.

    Returns:
        The configured base URL without a trailing slash, or a synthesized
        `https://<site>` fallback when no site config exists.
    """
    site_cfg = CATALOG_SITE_CONFIGS.get(site) or {}
    base_url = site_cfg.get("base_url")
    if isinstance(base_url, str) and base_url:
        return base_url.rstrip("/")
    return f"https://{site.rstrip('/')}"


def _build_episode_link(site: str, slug: str, season: int, episode: int) -> str:
    """
    Build a canonical episode URL from site-specific coordinates.

    Parameters:
        site: Catalogue site identifier. `s.to` uses the Serienstream URL
            layout; AniWorld uses `staffel-N/episode-N` or `filme/film-N`.
        slug: Series slug.
        season: Season number. Season `0` is treated as AniWorld film/special
            content.
        episode: Episode or film index within the selected season.

    Returns:
        The fully qualified episode page URL.
    """
    if site == "s.to":
        from app.providers.sto.v2 import build_episode_url

        return build_episode_url(_site_base_url(site), slug, season, episode)

    base_url = _site_base_url(site)
    if season == 0:
        return f"{base_url}/anime/stream/{slug}/filme/film-{episode}"
    return f"{base_url}/anime/stream/{slug}/staffel-{season}/episode-{episode}"


def _extract_slug_from_link(link: str, site: str) -> str:
    """
    Extract a series slug from an episode URL.

    Parameters:
        link: Fully qualified episode URL.
        site: Catalogue site identifier used to choose path semantics.

    Returns:
        The parsed series slug.

    Raises:
        ValueError: If the URL does not match the expected site-specific
            structure.
    """
    parts = [part for part in urlparse(link).path.split("/") if part]
    if site == "s.to":
        if "serie" in parts:
            idx = parts.index("serie")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    if "stream" in parts:
        idx = parts.index("stream")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    raise ValueError(f"Could not extract slug from episode link: {link}")


def _extract_season_episode_from_link(link: str, site: str) -> tuple[int, int]:
    """
    Extract season and episode coordinates from an episode URL.

    Parameters:
        link: Fully qualified episode URL.
        site: Catalogue site identifier. AniWorld `filme/film-N` links are
            mapped to `(0, N)`.

    Returns:
        A tuple of `(season, episode)`.

    Raises:
        ValueError: If season/episode markers cannot be parsed from the URL.
    """
    parts = [part for part in urlparse(link).path.split("/") if part]
    if site == "aniworld.to" and "filme" in parts:
        film_part = parts[-1]
        if film_part.startswith("film-"):
            return 0, int(film_part.removeprefix("film-"))
    season_part = next((part for part in parts if part.startswith("staffel-")), None)
    episode_part = next((part for part in parts if part.startswith("episode-")), None)
    if not season_part or not episode_part:
        raise ValueError(f"Could not extract season/episode from episode link: {link}")
    return int(season_part.removeprefix("staffel-")), int(
        episode_part.removeprefix("episode-")
    )


@dataclass(slots=True)
class EpisodeCompat:
    """Compatibility shim for aniworld>=4 site-specific episode classes."""

    _backend: Any
    link: str
    slug: str
    season: int
    episode: int
    site: str

    @property
    def language_name(self) -> list[str]:
        return self.available_languages

    @property
    def languages(self) -> list[str]:
        return self.available_languages

    @property
    def available_languages(self) -> list[str]:
        provider_data = getattr(self._backend, "provider_data", None)
        raw = getattr(provider_data, "_data", provider_data)
        if not isinstance(raw, dict):
            return []

        labels: list[str] = []
        seen: set[str] = set()

        if self.site == "aniworld.to":
            prepare_aniworld_home()
            from aniworld.config import INVERSE_LANG_KEY_MAP, LANG_LABELS  # type: ignore

            for key in raw.keys():
                try:
                    label = LANG_LABELS[INVERSE_LANG_KEY_MAP[key]]
                except KeyError:
                    logger.debug(
                        "Skipping unknown aniworld language tuple in compatibility layer: {}",
                        key,
                    )
                    continue
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
            return labels

        for key in raw.keys():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            audio = getattr(key[0], "value", None)
            subtitles = getattr(key[1], "value", None)
            if audio == "German" and subtitles == "None":
                label = "German Dub"
            elif audio == "English" and subtitles == "None":
                label = "English Dub"
            else:
                continue
            if label not in seen:
                seen.add(label)
                labels.append(label)
        return labels

    def _normalize_language_for_backend(self, language: str) -> Any:
        if self.site == "s.to":
            normalize = getattr(self._backend, "_normalize_language", None)
            if callable(normalize):
                return normalize(language)
            return language

        prepare_aniworld_home()
        from aniworld.config import INVERSE_LANG_LABELS, LANG_KEY_MAP  # type: ignore

        key = INVERSE_LANG_LABELS.get(language)
        if key is None:
            raise ValueError(
                f"Invalid language: {language}. Valid options for {self.site}: {self.available_languages}"
            )
        return LANG_KEY_MAP[key]

    def _get_provider_redirect_url(self, language: Any, provider_name: str) -> str:
        provider_data = getattr(self._backend, "provider_data", None)
        raw = getattr(provider_data, "_data", provider_data)
        if not isinstance(raw, dict):
            raise ValueError("Episode backend has no provider data")

        provider_dict = raw.get(language)
        if provider_dict is None and isinstance(language, tuple) and len(language) == 2:
            for key, candidate in raw.items():
                if not (isinstance(key, tuple) and len(key) == 2):
                    continue
                try:
                    if getattr(key[0], "value", key[0]) == getattr(
                        language[0], "value", language[0]
                    ) and getattr(key[1], "value", key[1]) == getattr(
                        language[1], "value", language[1]
                    ):
                        provider_dict = candidate
                        break
                except Exception:
                    continue

        if not isinstance(provider_dict, dict):
            raise ValueError("No provider data found for requested backend language")

        redirect_url = provider_dict.get(provider_name)
        if not redirect_url:
            raise ValueError(
                f"Provider '{provider_name}' not found for requested backend language"
            )

        return redirect_url

    def get_direct_link(self, provider_name: str, language: str) -> str:
        """
        Resolve and return the provider's final direct media URL for the given language.

        Parameters:
            provider_name (str): Provider identifier as used in the backend provider data.
            language (str): Human-facing language label to select provider data (e.g., "German Dub").

        Returns:
            str: The resolved direct media URL for the requested provider and language.

        Raises:
            ValueError: If the provider is not available for the language/site, no redirect URL is present,
                        the provider extractor is not implemented, or direct-link resolution fails.
        """
        backend_language = self._normalize_language_for_backend(language)
        redirect_url: Optional[str] = None
        try:
            redirect_url = self._get_provider_redirect_url(
                backend_language, provider_name
            )
        except Exception as exc:
            available = self.available_languages
            msg = str(exc)
            if "Provider '" in msg and "not found" in msg:
                raise ValueError(
                    f"Provider '{provider_name}' not found for language '{language}' on site '{self.site}'."
                ) from exc
            if available:
                raise ValueError(
                    f"No provider found for language '{language}' on site '{self.site}'. Available languages: {available}"
                ) from exc
            raise

        if not redirect_url:
            raise ValueError(
                f"Provider '{provider_name}' did not return a redirect URL for {self.link}"
            )

        prepare_aniworld_home()
        from aniworld.extractors import provider_functions  # type: ignore
        from niquests import RequestException, Timeout  # type: ignore

        extractor = provider_functions.get(
            f"get_direct_link_from_{provider_name.lower()}"
        )
        if extractor is None:
            raise ValueError(
                f"The provider '{provider_name}' is not implemented in aniworld>=4."
            )

        try:
            return _get_direct_link_with_retries(
                provider_name=provider_name,
                redirect_url=redirect_url,
                extractor=extractor,
                site=self.site,
            )
        except (Timeout, RequestException, ValueError) as exc:
            raise ValueError(
                f"Failed to resolve provider '{provider_name}' at {redirect_url}: {exc}"
            ) from exc


def build_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    site: str = "aniworld.to",
) -> Episode | EpisodeCompat:
    """
    Construct an episode object from a URL or from slug/season/episode coordinates.

    When the legacy `aniworld.models.Episode` class is importable, returns an instance of that legacy Episode (optionally enriched for s.to). When the legacy API is not available (aniworld>=4), returns an EpisodeCompat that wraps a site-specific backend episode object.

    Returns:
        An instance of the legacy `Episode` when available, otherwise an `EpisodeCompat` wrapping the new site-specific episode backend.

    Raises:
        ValueError: If neither `link` nor the (`slug`, `season`, `episode`) triple is provided; if required coordinates are missing when constructing a resolved link; or if the specified `site` is not supported.
    """
    logger.info(
        "Building episode: link={}, slug={}, season={}, episode={}, site={}",
        link,
        slug,
        season,
        episode,
        site,
    )
    if not link and not (slug and season is not None and episode is not None):
        logger.error(
            "Invalid episode parameters: must provide either link or (slug, season, episode)."
        )
        raise ValueError("Provide either link OR (slug, season, episode).")

    site_cfg = CATALOG_SITE_CONFIGS.get(site) or {}
    base_url = site_cfg.get("base_url")
    site_domain = site
    if isinstance(base_url, str) and base_url:
        parsed = urlparse(base_url)
        site_domain = parsed.netloc or base_url.strip().strip("/")

    prepare_aniworld_home()
    try:
        from aniworld.models import Episode as LegacyEpisode  # type: ignore
    except ImportError:
        LegacyEpisode = None

    if LegacyEpisode is not None:
        ep: Optional[Episode] = None
        if link:
            ep = LegacyEpisode(link=link, site=site_domain)
        else:
            missing = [
                name
                for name, value in (
                    ("slug", slug),
                    ("season", season),
                    ("episode", episode),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    "slug, season and episode must be provided; missing: "
                    + ", ".join(missing)
                )
            if site == "s.to" and isinstance(base_url, str) and base_url:
                from app.providers.sto.v2 import build_episode_url

                link = build_episode_url(base_url, slug, season, episode)
                ep = LegacyEpisode(
                    link=link,
                    slug=slug,
                    season=season,
                    episode=episode,
                    site=site_domain,
                )
            else:
                ep = LegacyEpisode(
                    slug=slug, season=season, episode=episode, site=site_domain
                )

        if getattr(ep, "link", None) is None:
            auto_basic = getattr(ep, "_auto_fill_basic_details", None)
            if callable(auto_basic):
                if getattr(ep, "_basic_details_filled", False):
                    setattr(ep, "_basic_details_filled", False)
                try:
                    auto_basic()
                except Exception as err:  # pragma: no cover - defensive
                    logger.warning(
                        "Failed to populate legacy episode basics (slug={}, season={}, episode={}): {}",
                        getattr(ep, "slug", slug),
                        getattr(ep, "season", season),
                        getattr(ep, "episode", episode),
                        err,
                    )

        if site == "s.to":
            try:
                from app.providers.sto.v2 import enrich_episode_from_v2_url

                if isinstance(base_url, str) and base_url:
                    enrich_episode_from_v2_url(episode=ep, base_url=base_url)
            except Exception as err:  # noqa: BLE001
                logger.warning("Failed to enrich S.to v2 episode: {}", err)

        return ep

    resolved_link = link
    if resolved_link is None:
        missing = [
            name
            for name, value in (
                ("slug", slug),
                ("season", season),
                ("episode", episode),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                "resolved_link requires slug, season and episode; missing: "
                + ", ".join(missing)
            )
        resolved_link = _build_episode_link(site, slug, season, episode)
    if slug is None:
        slug = _extract_slug_from_link(resolved_link, site)
    if season is None or episode is None:
        season, episode = _extract_season_episode_from_link(resolved_link, site)

    if site == "aniworld.to":
        from aniworld.models import AniworldEpisode  # type: ignore

        backend = AniworldEpisode(url=resolved_link)
    elif site == "s.to":
        from aniworld.models import SerienstreamEpisode  # type: ignore

        backend = SerienstreamEpisode(url=resolved_link)
    else:
        raise ValueError(f"Unsupported aniworld-backed site: {site}")

    return EpisodeCompat(
        _backend=backend,
        link=resolved_link,
        slug=slug,
        season=season,
        episode=episode,
        site=site,
    )
