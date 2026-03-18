from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING
from urllib.parse import urlparse

from loguru import logger

from app.config import CATALOG_SITE_CONFIGS
from app.utils.aniworld_compat import prepare_aniworld_home

if TYPE_CHECKING:
    from aniworld.models import Episode


def _site_base_url(site: str) -> str:
    site_cfg = CATALOG_SITE_CONFIGS.get(site) or {}
    base_url = site_cfg.get("base_url")
    if isinstance(base_url, str) and base_url:
        return base_url.rstrip("/")
    return f"https://{site.rstrip('/')}"


def _build_episode_link(site: str, slug: str, season: int, episode: int) -> str:
    if site == "s.to":
        from app.providers.sto.v2 import build_episode_url

        return build_episode_url(_site_base_url(site), slug, season, episode)

    base_url = _site_base_url(site)
    if season == 0:
        return f"{base_url}/anime/stream/{slug}/filme/film-{episode}"
    return f"{base_url}/anime/stream/{slug}/staffel-{season}/episode-{episode}"


def _extract_slug_from_link(link: str, site: str) -> str:
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
                except Exception:
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

    def get_direct_link(self, provider_name: str, language: str) -> str:
        backend_language = self._normalize_language_for_backend(language)
        try:
            redirect_url = self._backend.provider_link(backend_language, provider_name)
        except Exception as exc:
            available = self.available_languages
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
        from aniworld.config import GLOBAL_SESSION  # type: ignore
        from aniworld.extractors import provider_functions  # type: ignore

        provider_url = GLOBAL_SESSION.get(redirect_url).url
        extractor = provider_functions.get(
            f"get_direct_link_from_{provider_name.lower()}"
        )
        if extractor is None:
            raise ValueError(
                f"The provider '{provider_name}' is not implemented in aniworld>=4."
            )

        direct_url = extractor(provider_url)
        if not direct_url:
            raise ValueError(
                f"Extractor for provider '{provider_name}' returned no direct URL."
            )
        return direct_url


def build_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    site: str = "aniworld.to",
) -> Episode | EpisodeCompat:
    """
    Construct an episode object from either a direct URL or a (slug, season, episode) triple.

    Prefers the legacy `aniworld.models.Episode` API when available. When running
    against aniworld>=4, wraps the new site-specific episode classes in a small
    compatibility shim so the rest of AniBridge can keep using the old contract.
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
            assert slug is not None and season is not None and episode is not None
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
        assert slug is not None and season is not None and episode is not None
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
