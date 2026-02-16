from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import xml.etree.ElementTree as ET
import threading
import time
from urllib.parse import urlencode

from fastapi import Depends, Query, Request, Response
from fastapi.responses import Response as FastAPIResponse
from loguru import logger
from sqlmodel import Session

from app.config import (
    ANIBRIDGE_TEST_MODE,
    CATALOG_SITE_CONFIGS,
    SPECIALS_METADATA_ENABLED,
    STRM_FILES_MODE,
    TORZNAB_CAT_ANIME,
    TORZNAB_CAT_MOVIE,
    TORZNAB_RETURN_TEST_RESULT,
    TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES,
    TORZNAB_SEASON_SEARCH_MAX_EPISODES,
    TORZNAB_TEST_EPISODE,
    TORZNAB_TEST_LANGUAGE,
    TORZNAB_TEST_SEASON,
    TORZNAB_TEST_SLUG,
    TORZNAB_TEST_TITLE,
)
from app.db import get_session
from app.providers.aniworld.specials import (
    SpecialIds,
    resolve_special_mapping_from_episode_request,
    resolve_special_mapping_from_query,
)
from app.utils.magnet import _site_prefix
from app.utils.movie_year import get_movie_year
from app.utils.http_client import get as http_get

from . import router
from .utils import _build_item, _caps_xml, _require_apikey, _rss_root

_SKYHOOK_SEARCH_URL = "https://skyhook.sonarr.tv/v1/tvdb/search/en/"
_SKYHOOK_SHOW_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"
_TVSEARCH_ID_CACHE_TTL_SECONDS = 300.0
_TVSEARCH_ID_CACHE_MAX_ENTRIES = 512
_TVSEARCH_SKYHOOK_CACHE_LOCK = threading.Lock()
_TVSEARCH_TERM_TO_TVDB_CACHE: dict[str, tuple[float, int]] = {}
_TVSEARCH_TVDB_TO_TITLE_CACHE: dict[int, tuple[float, str]] = {}


def _default_languages_for_site(site: str) -> List[str]:
    """
    Get the default language preference ordering for a catalogue site.

    Parameters:
        site (str): Catalogue site key to look up in CATALOG_SITE_CONFIGS.

    Returns:
        List[str]: Language names in preference order. If the site has no valid mapping, returns the configured aniworld.to defaults (fallbacking to ["German Dub", "German Sub", "English Sub"] if that configuration is absent).
    """
    cfg = CATALOG_SITE_CONFIGS.get(site)
    if cfg:
        languages = cfg.get("default_languages")
        if isinstance(languages, list) and languages:
            # return a shallow copy to avoid accidental mutation of config state
            return list(languages)
    fallback = CATALOG_SITE_CONFIGS.get("aniworld.to", {}).get(
        "default_languages", ["German Dub", "German Sub", "English Sub"]
    )
    return list(fallback)


def _coerce_positive_int(value: object) -> Optional[int]:
    """
    Coerce an arbitrary value into a positive integer.

    Parameters:
        value (object): Value to convert to an integer.

    Returns:
        The parsed positive integer if conversion succeeds and is greater than zero, `None` otherwise.
    """
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_non_negative_int(value: object) -> Optional[int]:
    """Coerce an arbitrary value into a non-negative integer."""
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _cache_get_term_tvdb(term: str) -> Optional[int]:
    """Return cached tvdb id for a SkyHook search term when entry is fresh."""
    now = time.time()
    with _TVSEARCH_SKYHOOK_CACHE_LOCK:
        entry = _TVSEARCH_TERM_TO_TVDB_CACHE.get(term)
        if not entry:
            return None
        cached_at, cached_tvdb = entry
        if now - cached_at > _TVSEARCH_ID_CACHE_TTL_SECONDS:
            _TVSEARCH_TERM_TO_TVDB_CACHE.pop(term, None)
            return None
        return cached_tvdb


def _cache_set_term_tvdb(term: str, tvdb_id: int) -> None:
    """Cache tvdb id for a SkyHook search term with TTL."""
    with _TVSEARCH_SKYHOOK_CACHE_LOCK:
        _TVSEARCH_TERM_TO_TVDB_CACHE[term] = (time.time(), tvdb_id)
        if len(_TVSEARCH_TERM_TO_TVDB_CACHE) > _TVSEARCH_ID_CACHE_MAX_ENTRIES:
            oldest = min(
                _TVSEARCH_TERM_TO_TVDB_CACHE.items(), key=lambda item: item[1][0]
            )[0]
            _TVSEARCH_TERM_TO_TVDB_CACHE.pop(oldest, None)


def _cache_get_tvdb_title(tvdb_id: int) -> Optional[str]:
    """Return cached SkyHook show title for tvdb id when entry is fresh."""
    now = time.time()
    with _TVSEARCH_SKYHOOK_CACHE_LOCK:
        entry = _TVSEARCH_TVDB_TO_TITLE_CACHE.get(tvdb_id)
        if not entry:
            return None
        cached_at, cached_title = entry
        if now - cached_at > _TVSEARCH_ID_CACHE_TTL_SECONDS:
            _TVSEARCH_TVDB_TO_TITLE_CACHE.pop(tvdb_id, None)
            return None
        return cached_title


def _cache_set_tvdb_title(tvdb_id: int, title: str) -> None:
    """Cache SkyHook show title for tvdb id with TTL."""
    with _TVSEARCH_SKYHOOK_CACHE_LOCK:
        _TVSEARCH_TVDB_TO_TITLE_CACHE[tvdb_id] = (time.time(), title)
        if len(_TVSEARCH_TVDB_TO_TITLE_CACHE) > _TVSEARCH_ID_CACHE_MAX_ENTRIES:
            oldest = min(
                _TVSEARCH_TVDB_TO_TITLE_CACHE.items(), key=lambda item: item[1][0]
            )[0]
            _TVSEARCH_TVDB_TO_TITLE_CACHE.pop(oldest, None)


def _resolve_tvsearch_query_from_ids(
    *,
    tvdbid: Optional[int],
    tmdbid: Optional[int],
    imdbid: Optional[str],
) -> Optional[str]:
    """
    Resolve a canonical TV series title from provided Torznab identifiers.

    If a positive `tvdbid` is supplied, the function looks up the show title for that ID.
    If not, it attempts to resolve a `tvdbid` by querying SkyHook using `tmdbid` and/or `imdbid`,
    then looks up the show title for the resolved `tvdbid`.

    Returns:
        title (str): The resolved show title when found.
        None: If no title could be resolved.
    """
    tvdb_id = _coerce_positive_int(tvdbid)
    if tvdb_id is None:
        lookup_terms: List[str] = []
        tmdb = _coerce_positive_int(tmdbid)
        imdb = (imdbid or "").strip()
        if tmdb is not None:
            lookup_terms.append(f"tmdb:{tmdb}")
        if imdb:
            lookup_terms.append(f"imdb:{imdb}")

        for term in lookup_terms:
            cached_tvdb = _cache_get_term_tvdb(term)
            if cached_tvdb is not None:
                tvdb_id = cached_tvdb
                break
            try:
                query = urlencode({"term": term})
                response = http_get(
                    f"{_SKYHOOK_SEARCH_URL}?{query}",
                    timeout=8.0,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.debug("SkyHook ID search failed for '{}': {}", term, exc)
                continue
            if not isinstance(payload, list):
                continue
            for item in payload:
                if not isinstance(item, dict):
                    continue
                candidate = _coerce_positive_int(item.get("tvdbId"))
                if candidate is not None:
                    tvdb_id = candidate
                    _cache_set_term_tvdb(term, candidate)
                    break
            if tvdb_id is not None:
                break

    if tvdb_id is None:
        return None

    cached_title = _cache_get_tvdb_title(tvdb_id)
    if cached_title is not None:
        return cached_title

    try:
        response = http_get(_SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id), timeout=8.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.debug("SkyHook show lookup failed for tvdb {}: {}", tvdb_id, exc)
        return None

    if not isinstance(payload, dict):
        return None
    title = str(payload.get("title") or "").strip()
    if title:
        _cache_set_tvdb_title(tvdb_id, title)
    return title or None


def _resolve_tvdb_id_for_tvsearch(
    *,
    q_str: str,
    tvdbid: Optional[int],
    tmdbid: Optional[int],
    imdbid: Optional[str],
) -> Optional[int]:
    """
    Resolve a tvdb id for tvsearch using explicit ids first, then SkyHook lookup terms.
    """
    tvdb_id = _coerce_positive_int(tvdbid)
    if tvdb_id is not None:
        return tvdb_id
    if ANIBRIDGE_TEST_MODE:
        return None

    lookup_terms: List[str] = []
    tmdb = _coerce_positive_int(tmdbid)
    imdb = (imdbid or "").strip()
    query = (q_str or "").strip()
    if tmdb is not None:
        lookup_terms.append(f"tmdb:{tmdb}")
    if imdb:
        lookup_terms.append(f"imdb:{imdb}")
    if query:
        lookup_terms.append(query)

    for term in lookup_terms:
        cached_tvdb = _cache_get_term_tvdb(term)
        if cached_tvdb is not None:
            return cached_tvdb
        try:
            query_params = urlencode({"term": term})
            response = http_get(
                f"{_SKYHOOK_SEARCH_URL}?{query_params}",
                timeout=8.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.debug("SkyHook ID search failed for '{}': {}", term, exc)
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            candidate = _coerce_positive_int(item.get("tvdbId"))
            if candidate is None:
                continue
            _cache_set_term_tvdb(term, candidate)
            return candidate
    return None


def _metadata_episode_numbers_for_season(
    *,
    q_str: str,
    season_i: int,
    ids: SpecialIds,
) -> List[int]:
    """
    Resolve episode numbers for one season from SkyHook metadata.
    """
    tvdb_id = _resolve_tvdb_id_for_tvsearch(
        q_str=q_str,
        tvdbid=ids.tvdbid,
        tmdbid=ids.tmdbid,
        imdbid=ids.imdbid,
    )
    if tvdb_id is None:
        return []

    try:
        response = http_get(_SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id), timeout=8.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.debug("SkyHook show lookup failed for tvdb {}: {}", tvdb_id, exc)
        return []

    if not isinstance(payload, dict):
        return []
    raw_episodes = payload.get("episodes")
    if not isinstance(raw_episodes, list):
        return []

    episode_numbers: List[int] = []
    for item in raw_episodes:
        if not isinstance(item, dict):
            continue
        item_season = _coerce_non_negative_int(item.get("seasonNumber"))
        item_episode = _coerce_positive_int(item.get("episodeNumber"))
        if item_season != season_i or item_episode is None:
            continue
        episode_numbers.append(item_episode)
    return sorted(set(episode_numbers))


def _probe_episode_available_for_discovery(
    *,
    tn_module,
    session: Session,
    slug: str,
    season_i: int,
    episode_i: int,
    site_found: str,
) -> bool:
    """
    Probe whether an episode is available in at least one candidate language.
    """
    cached_langs = tn_module.list_available_languages_cached(
        session,
        slug=slug,
        season=season_i,
        episode=episode_i,
        site=site_found,
    )
    default_langs = _default_languages_for_site(site_found)
    candidate_langs: List[str] = cached_langs if cached_langs else default_langs
    for lang in candidate_langs:
        try:
            rec = tn_module.get_availability(
                session,
                slug=slug,
                season=season_i,
                episode=episode_i,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError):
            rec = None

        if rec and rec.available and rec.is_fresh:
            return True

        try:
            available, height, vcodec, prov_used, _info = (
                tn_module.probe_episode_quality(
                    slug=slug,
                    season=season_i,
                    episode=episode_i,
                    language=lang,
                    site=site_found,
                )
            )
        except (ValueError, RuntimeError):
            available = False
            height = None
            vcodec = None
            prov_used = None

        try:
            tn_module.upsert_availability(
                session,
                slug=slug,
                season=season_i,
                episode=episode_i,
                language=lang,
                available=available,
                height=height,
                vcodec=vcodec,
                provider=prov_used,
                extra=None,
                site=site_found,
            )
        except (ValueError, RuntimeError):
            pass
        if available:
            return True
    return False


def resolve_season_episode_numbers(
    *,
    tn_module,
    session: Session,
    slug: str,
    season_i: int,
    site_found: str,
    q_str: str,
    ids: SpecialIds,
) -> List[int]:
    """
    Resolve episode numbers for tvsearch season mode via metadata, cache, and fallback probing.
    """
    metadata_episodes = _metadata_episode_numbers_for_season(
        q_str=q_str,
        season_i=season_i,
        ids=ids,
    )
    if metadata_episodes:
        logger.debug(
            "tvsearch season discovery source=metadata slug={} season={} episodes={}",
            slug,
            season_i,
            metadata_episodes,
        )

    cached_episodes = tn_module.list_cached_episode_numbers_for_season(
        session,
        slug=slug,
        season=season_i,
        site=site_found,
    )
    if cached_episodes:
        logger.debug(
            "tvsearch season discovery source=cache slug={} season={} episodes={}",
            slug,
            season_i,
            cached_episodes,
        )

    merged = sorted(set(metadata_episodes + cached_episodes))
    if merged:
        discovery_sources: List[str] = []
        if metadata_episodes:
            discovery_sources.append("metadata")
        if cached_episodes:
            discovery_sources.append("cache")
        logger.info(
            "tvsearch season discovery slug={} season={} episodes={} sources={}",
            slug,
            season_i,
            len(merged),
            "+".join(discovery_sources),
        )
        return merged

    discovered: List[int] = []
    consecutive_misses = 0
    termination = "max episodes"
    for episode_i in range(1, TORZNAB_SEASON_SEARCH_MAX_EPISODES + 1):
        if _probe_episode_available_for_discovery(
            tn_module=tn_module,
            session=session,
            slug=slug,
            season_i=season_i,
            episode_i=episode_i,
            site_found=site_found,
        ):
            discovered.append(episode_i)
            consecutive_misses = 0
            continue
        consecutive_misses += 1
        if consecutive_misses >= TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES:
            termination = "consecutive misses"
            break

    logger.info(
        (
            "tvsearch season discovery source=fallback-probe slug={} season={} "
            "episodes={} termination={} max_episodes={} max_consecutive_misses={}"
        ),
        slug,
        season_i,
        len(discovered),
        termination,
        TORZNAB_SEASON_SEARCH_MAX_EPISODES,
        TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES,
    )
    return discovered


def _try_mapped_special_probe(
    *,
    tn_module,
    session: Session,
    slug: str,
    lang: str,
    site_found: str,
    special_map,
) -> tuple[bool, Optional[int], Optional[str], Optional[str], int, int, int, int]:
    """
    Probe availability and quality for an AniWorld special that maps to a different source episode, using cached availability when possible.

    Parameters:
        tn_module: Provider module exposing `get_availability` and `probe_episode_quality` used to fetch cached availability or probe live quality.
        session (Session): Database/session object used by `get_availability`.
        slug (str): Show identifier used for probing.
        lang (str): Language to probe (e.g., "German Dub").
        site_found (str): Catalogue site name where the source episode is hosted.
        special_map: Mapping object containing `source_season`, `source_episode`, `alias_season`, and `alias_episode` that describe the source coordinates and their alias.

    Returns:
        tuple: (
            available (bool): `True` if the source episode is available, `False` otherwise,
            height (Optional[int]): video height in pixels if known, otherwise `None`,
            vcodec (Optional[str]): video codec identifier if known, otherwise `None`,
            provider (Optional[str]): provider name that supplied the quality info if known, otherwise `None`,
            source_season (int): season number of the mapped source episode,
            source_episode (int): episode number of the mapped source episode,
            alias_season (int): alias season number requested,
            alias_episode (int): alias episode number requested
        )
    """
    source_season = special_map.source_season
    source_episode = special_map.source_episode
    alias_season = special_map.alias_season
    alias_episode = special_map.alias_episode

    try:
        rec_mapped = tn_module.get_availability(
            session,
            slug=slug,
            season=source_season,
            episode=source_episode,
            language=lang,
            site=site_found,
        )
    except (ValueError, RuntimeError):
        rec_mapped = None
    if rec_mapped and rec_mapped.available and rec_mapped.is_fresh:
        return (
            True,
            rec_mapped.height,
            rec_mapped.vcodec,
            rec_mapped.provider,
            source_season,
            source_episode,
            alias_season,
            alias_episode,
        )

    try:
        available, height, vcodec, prov_used, _info = tn_module.probe_episode_quality(
            slug=slug,
            season=source_season,
            episode=source_episode,
            language=lang,
            site=site_found,
        )
    except (ValueError, RuntimeError) as e:
        logger.error(
            "Error probing mapped special quality for slug={}, S{}E{}, lang={}, site={}: {}",
            slug,
            source_season,
            source_episode,
            lang,
            site_found,
            e,
        )
        available = False
        height = None
        vcodec = None
        prov_used = None

    return (
        available,
        height,
        vcodec,
        prov_used,
        source_season,
        source_episode,
        alias_season,
        alias_episode,
    )


def emit_tvsearch_episode_items(
    *,
    tn_module,
    session: Session,
    channel: ET.Element,
    slug: str,
    site_found: str,
    display_title: str,
    q_str: str,
    request_season: int,
    request_episode: int,
    ids: SpecialIds,
    now: datetime,
    strm_suffix: str,
    max_items: Optional[int],
) -> tuple[int, bool]:
    """
    Emit tvsearch RSS items for one requested season/episode pair.

    Returns:
        tuple[int, bool]:
            - Number of emitted RSS items.
            - Whether emission stopped because the provided `max_items` was reached.
    """
    cached_langs = tn_module.list_available_languages_cached(
        session,
        slug=slug,
        season=request_season,
        episode=request_episode,
        site=site_found,
    )
    default_langs = _default_languages_for_site(site_found)
    candidate_langs: List[str] = cached_langs if cached_langs else default_langs
    logger.debug(
        ("Candidate languages for slug='{}' season={} episode={} site='{}': {}"),
        slug,
        request_season,
        request_episode,
        site_found,
        candidate_langs,
    )

    count = 0
    special_map_attempted = False
    special_map = None

    for lang in candidate_langs:
        if max_items is not None and count >= max_items:
            return count, True

        logger.debug("Checking availability for language '{}'", lang)
        source_season = request_season
        source_episode = request_episode
        alias_season = request_season
        alias_episode = request_episode
        if special_map is not None:
            source_season = special_map.source_season
            source_episode = special_map.source_episode
            alias_season = special_map.alias_season
            alias_episode = special_map.alias_episode

        try:
            rec = tn_module.get_availability(
                session,
                slug=slug,
                season=source_season,
                episode=source_episode,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Error reading availability cache for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                source_season,
                source_episode,
                lang,
                site_found,
                e,
            )
            rec = None

        available = False
        height = None
        vcodec = None
        prov_used = None

        if rec and rec.available and rec.is_fresh:
            available = True
            height = rec.height
            vcodec = rec.vcodec
            prov_used = rec.provider
            logger.debug(
                (
                    "Using cached availability for {} S{}E{} {} on {}: "
                    "h={}, vcodec={}, prov={}"
                ),
                slug,
                source_season,
                source_episode,
                lang,
                site_found,
                height,
                vcodec,
                prov_used,
            )
        else:
            try:
                available, height, vcodec, prov_used, _info = (
                    tn_module.probe_episode_quality(
                        slug=slug,
                        season=source_season,
                        episode=source_episode,
                        language=lang,
                        site=site_found,
                    )
                )
            except (ValueError, RuntimeError) as e:
                logger.error(
                    "Error probing quality for slug={}, S{}E{}, lang={}, site={}: {}",
                    slug,
                    source_season,
                    source_episode,
                    lang,
                    site_found,
                    e,
                )
                available = False

            if (
                not available
                and SPECIALS_METADATA_ENABLED
                and site_found == "aniworld.to"
            ):
                if not special_map_attempted:
                    special_map_attempted = True
                    special_map = resolve_special_mapping_from_episode_request(
                        slug=slug,
                        request_season=request_season,
                        request_episode=request_episode,
                        query=q_str,
                        series_title=display_title,
                        ids=ids,
                    )
                    if special_map is not None:
                        logger.info(
                            (
                                "Special mapping (tvsearch) resolved: slug={} "
                                "requested=S{}E{} target=S{}E{}"
                            ),
                            slug,
                            request_season,
                            request_episode,
                            special_map.source_season,
                            special_map.source_episode,
                        )
                if special_map is not None:
                    (
                        available,
                        height,
                        vcodec,
                        prov_used,
                        source_season,
                        source_episode,
                        alias_season,
                        alias_episode,
                    ) = _try_mapped_special_probe(
                        tn_module=tn_module,
                        session=session,
                        slug=slug,
                        lang=lang,
                        site_found=site_found,
                        special_map=special_map,
                    )

            try:
                tn_module.upsert_availability(
                    session,
                    slug=slug,
                    season=source_season,
                    episode=source_episode,
                    language=lang,
                    available=available,
                    height=height,
                    vcodec=vcodec,
                    provider=prov_used,
                    extra=(
                        {
                            "special_alias_season": alias_season,
                            "special_alias_episode": alias_episode,
                        }
                        if special_map is not None
                        else None
                    ),
                    site=site_found,
                )
            except (ValueError, RuntimeError) as e:
                logger.error(
                    "Error upserting availability for slug={}, S{}E{}, lang={}, site={}: {}",
                    slug,
                    source_season,
                    source_episode,
                    lang,
                    site_found,
                    e,
                )

        if not available:
            logger.debug(
                "Language '{}' currently not available for {} S{}E{} on {}. Skipping.",
                lang,
                slug,
                source_season,
                source_episode,
                site_found,
            )
            continue

        release_title = tn_module.build_release_name(
            series_title=display_title,
            season=alias_season,
            episode=alias_episode,
            height=height,
            vcodec=vcodec,
            language=lang,
            site=site_found,
        )
        logger.debug("Built release title: '{}'", release_title)

        try:
            magnet = tn_module.build_magnet(
                title=release_title,
                slug=slug,
                season=source_season,
                episode=source_episode,
                language=lang,
                provider=prov_used,
                site=site_found,
            )
        except Exception as e:
            logger.error("Error building magnet for release '{}': {}", release_title, e)
            continue

        prefix = _site_prefix(site_found)
        guid_base = f"{prefix}:{slug}:s{source_season}e{source_episode}:{lang}"
        if (alias_season, alias_episode) != (source_season, source_episode):
            guid_base = f"{guid_base}:alias-s{alias_season}e{alias_episode}"

        try:
            if STRM_FILES_MODE in ("no", "both"):
                if max_items is not None and count >= max_items:
                    return count, True
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=TORZNAB_CAT_ANIME,
                    guid_str=guid_base,
                    language=lang,
                )
                count += 1
            if STRM_FILES_MODE in ("only", "both"):
                if max_items is not None and count >= max_items:
                    return count, True
                magnet_strm = tn_module.build_magnet(
                    title=release_title + strm_suffix,
                    slug=slug,
                    season=source_season,
                    episode=source_episode,
                    language=lang,
                    provider=prov_used,
                    site=site_found,
                    mode="strm",
                )
                _build_item(
                    channel=channel,
                    title=release_title + strm_suffix,
                    magnet=magnet_strm,
                    pubdate=now,
                    cat_id=TORZNAB_CAT_ANIME,
                    guid_str=f"{guid_base}:strm",
                    language=lang,
                )
                count += 1
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(
                "Error building RSS item for release '{}': {}", release_title, e
            )
            continue

        logger.debug(
            "Added tvsearch item(s) for S{}E{} lang='{}'. Episode item count now {}.",
            request_season,
            request_episode,
            lang,
            count,
        )

    return count, False


def _handle_preview_search(
    session: Session,
    q_str: str,
    channel: ET.Element,
    cat_id: int,
    *,
    site: Optional[str] = None,
    limit: Optional[int] = None,
    strm_suffix: str = " [STRM]",
) -> int:
    """
    Populate the RSS channel with preview (S01E01) search results for the given query.

    Resolves the query to a series slug (optionally constrained by site), determines candidate languages, probes and upserts preview availability per language, constructs magnet (and optional STRM) links according to STRM_FILES_MODE, and adds corresponding RSS items to the provided channel.

    Parameters:
        site (Optional[str]): Optional site identifier to constrain slug resolution and source-specific behavior.
        limit (Optional[int]): Maximum number of items to add; None means no explicit limit.
        strm_suffix (str): Suffix appended to release titles for STRM entries (default: " [STRM]").

    Returns:
        int: Number of items added to the channel.
    """
    import app.api.torznab as tn

    q_str = (q_str or "").strip()
    if not q_str:
        return 0
    if ANIBRIDGE_TEST_MODE:
        logger.debug("Test mode enabled; skipping preview probe for '{}'", q_str)
        return 0

    movie_year = get_movie_year(q_str)
    result = (
        tn._slug_from_query(q_str, site=site) if site else tn._slug_from_query(q_str)
    )
    if not result:
        if site:
            logger.debug("No slug found for query '{}' using site '{}'", q_str, site)
        return 0

    site_found, slug = result
    display_title = tn.resolve_series_title(slug, site_found) or q_str
    if movie_year:
        display_title = f"{display_title} {movie_year}"
    season_i, ep_i = 1, 1

    cached_langs = tn.list_available_languages_cached(
        session, slug=slug, season=season_i, episode=ep_i, site=site_found
    )
    default_langs = _default_languages_for_site(site_found)
    candidate_langs: List[str] = cached_langs if cached_langs else default_langs
    now = datetime.now(timezone.utc)
    count = 0

    for lang in candidate_langs:
        try:
            available, h, vc, prov, _info = tn.probe_episode_quality(
                slug=slug,
                season=season_i,
                episode=ep_i,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Error probing preview quality for slug={}, S{}E{}, lang={}, site={}: {}".format(
                    slug, season_i, ep_i, lang, site_found, e
                )
            )
            continue
        try:
            tn.upsert_availability(
                session,
                slug=slug,
                season=season_i,
                episode=ep_i,
                language=lang,
                available=available,
                height=h,
                vcodec=vc,
                provider=prov,
                extra=None,
                site=site_found,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Error upserting preview availability for slug={}, S{}E{}, lang={}, site={}: {}".format(
                    slug, season_i, ep_i, lang, site_found, e
                )
            )
        if not available:
            continue

        # Preview results omit SxxEyy in the release title, but we keep S01E01
        # placeholders in the magnet metadata for backward compatibility.
        release_title = tn.build_release_name(
            series_title=display_title,
            season=None,
            episode=None,
            height=h,
            vcodec=vc,
            language=lang,
            site=site_found,
        )
        try:
            magnet = tn.build_magnet(
                title=release_title,
                slug=slug,
                season=season_i,
                episode=ep_i,
                language=lang,
                provider=prov,
                site=site_found,
            )
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(f"Error building magnet for release '{release_title}': {e}")
            continue

        prefix = _site_prefix(site_found)
        guid_base = f"{prefix}:{slug}:s{season_i}e{ep_i}:{lang}"
        try:
            if STRM_FILES_MODE in ("no", "both"):
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=guid_base,
                    language=lang,
                )
            if STRM_FILES_MODE in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=slug,
                    season=season_i,
                    episode=ep_i,
                    language=lang,
                    provider=prov,
                    site=site_found,
                    mode="strm",
                )
                _build_item(
                    channel=channel,
                    title=release_title + strm_suffix,
                    magnet=magnet_strm,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=f"{guid_base}:strm",
                    language=lang,
                )
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(f"Error building RSS item for release '{release_title}': {e}")
            continue

        count += 1
        if limit is not None and count >= max(1, int(limit)):
            break

    return count


def _handle_special_search(
    session: Session,
    q_str: str,
    channel: ET.Element,
    cat_id: int,
    *,
    ids: SpecialIds,
    limit: Optional[int] = None,
    strm_suffix: str = " [STRM]",
) -> int:
    """
    Generate RSS items for title-only searches that map to AniWorld "special" episodes using metadata-backed aliasing.

    When the query resolves to an aniworld.to slug and a special mapping exists, this will add episode-specific RSS items whose displayed release title uses the Sonarr-facing alias season/episode (SxxEyy) while the magnet payload targets the AniWorld source season/episode. For each candidate language it probes availability, upserts availability with alias metadata, and creates magnet and optional STRM items according to STRM_FILES_MODE. Processing stops when the optional limit is reached.

    Parameters:
        session (Session): Database/session object used for cached lookups and upserts.
        q_str (str): Title-only query string to resolve.
        channel (xml.etree.ElementTree.Element): RSS channel element to which items will be appended.
        cat_id (int): Torznab category id to use for generated items.
        ids (SpecialIds): Identifiers (tvdb/tmdb/imdb/rid/tvmaze) used to assist special-mapping resolution.
        limit (Optional[int]): Maximum number of RSS items to add; None means no explicit limit.
        strm_suffix (str): Suffix appended to release titles for STRM-mode items.

    Returns:
        int: Number of RSS items added to the provided channel.
    """
    import app.api.torznab as tn

    q_str = (q_str or "").strip()
    if not q_str:
        return 0
    if ANIBRIDGE_TEST_MODE:
        return 0

    result = tn._slug_from_query(q_str)
    if not result:
        return 0

    site_found, slug = result
    if site_found != "aniworld.to":
        return 0

    display_title = tn.resolve_series_title(slug, site_found) or q_str
    mapping = resolve_special_mapping_from_query(
        slug=slug,
        query=q_str,
        series_title=display_title,
        ids=ids,
    )
    if mapping is None:
        return 0

    target_season = mapping.source_season
    target_episode = mapping.source_episode
    alias_season = mapping.alias_season
    alias_episode = mapping.alias_episode
    logger.info(
        "Special mapping (search) resolved: slug={} target=S{}E{} alias=S{}E{} tvdbid={}",
        slug,
        target_season,
        target_episode,
        alias_season,
        alias_episode,
        mapping.metadata_tvdb_id,
    )

    cached_langs = tn.list_available_languages_cached(
        session,
        slug=slug,
        season=target_season,
        episode=target_episode,
        site=site_found,
    )
    default_langs = _default_languages_for_site(site_found)
    candidate_langs: List[str] = cached_langs if cached_langs else default_langs
    now = datetime.now(timezone.utc)
    count = 0

    for lang in candidate_langs:
        try:
            available, h, vc, prov, _info = tn.probe_episode_quality(
                slug=slug,
                season=target_season,
                episode=target_episode,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Error probing mapped special quality for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                target_season,
                target_episode,
                lang,
                site_found,
                e,
            )
            continue
        try:
            tn.upsert_availability(
                session,
                slug=slug,
                season=target_season,
                episode=target_episode,
                language=lang,
                available=available,
                height=h,
                vcodec=vc,
                provider=prov,
                extra={
                    "special_alias_season": alias_season,
                    "special_alias_episode": alias_episode,
                },
                site=site_found,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Error upserting mapped special availability for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                target_season,
                target_episode,
                lang,
                site_found,
                e,
            )
        if not available:
            continue

        release_title = tn.build_release_name(
            series_title=display_title,
            season=alias_season,
            episode=alias_episode,
            height=h,
            vcodec=vc,
            language=lang,
            site=site_found,
        )
        try:
            magnet = tn.build_magnet(
                title=release_title,
                slug=slug,
                season=target_season,
                episode=target_episode,
                language=lang,
                provider=prov,
                site=site_found,
            )
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(
                f"Error building magnet for mapped special '{release_title}': {e}"
            )
            continue

        prefix = _site_prefix(site_found)
        guid_base = (
            f"{prefix}:{slug}:s{target_season}e{target_episode}:{lang}"
            f":alias-s{alias_season}e{alias_episode}"
        )

        try:
            if STRM_FILES_MODE in ("no", "both"):
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=guid_base,
                    language=lang,
                )
            if STRM_FILES_MODE in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=slug,
                    season=target_season,
                    episode=target_episode,
                    language=lang,
                    provider=prov,
                    site=site_found,
                    mode="strm",
                )
                _build_item(
                    channel=channel,
                    title=release_title + strm_suffix,
                    magnet=magnet_strm,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=f"{guid_base}:strm",
                    language=lang,
                )
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(
                "Error building RSS item for mapped special '{}': {}", release_title, e
            )
            continue

        count += 1
        if limit is not None and count >= max(1, int(limit)):
            break

    return count


@router.get("/api", response_class=FastAPIResponse)
def torznab_api(
    request: Request,
    t: str = Query(..., description="caps|tvsearch|search|movie"),
    apikey: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    season: Optional[int] = Query(default=None),
    ep: Optional[int] = Query(default=None),
    tvdbid: Optional[int] = Query(default=None),
    tmdbid: Optional[int] = Query(default=None),
    imdbid: Optional[str] = Query(default=None),
    rid: Optional[int] = Query(default=None),
    tvmazeid: Optional[int] = Query(default=None),
    cat: Optional[str] = Query(default=None),
    offset: int = Query(default=0),
    limit: int = Query(default=50),
    session: Session = Depends(get_session),
) -> Response:
    """
    Handle Torznab API requests and return the corresponding XML or RSS feed.

    Processes four modes selected by `t`: "caps" (returns Torznab capability XML), "search" (generic preview/search across series or movies), "movie" / "movie-search" (movie-focused search and preview), and "tvsearch" (episode/season search). For search modes it builds RSS items per available language and respects STRM_FILES_MODE, category hints, paging via `offset`/`limit`, and cached availability probes.

    Parameters:
        t (str): Mode selector; one of "caps", "search", "tvsearch", "movie", or "movie-search".
        apikey (Optional[str]): API key supplied by the client; validated by the endpoint.
        q (Optional[str]): Query string for slug/title resolution or preview searches.
        season (Optional[int]): Season number for TV searches; required for "tvsearch".
        ep (Optional[int]): Episode number for TV searches; omit for season-search mode.
        cat (Optional[str]): Optional category filter (comma-separated); used to prefer movie handling when movie category is present.
        offset (int): Result offset for paging (unused for caps).
        limit (int): Maximum number of RSS items to include.
        session (Session): Database session (injected; omitted from consumer-facing docs).

    Returns:
        Response: FastAPI Response containing:
            - Torznab capabilities XML for `t == "caps"` (media type application/xml; charset=utf-8).
            - RSS XML for search/tvsearch/movie modes (media type application/rss+xml; charset=utf-8).
            - An empty RSS feed when required parameters are missing or slug resolution fails.
            - HTTP 400 when `t` has an unsupported value.
    """
    logger.info(
        (
            "Torznab request: t={}, q={}, season={}, ep={}, tvdbid={}, tmdbid={}, "
            "imdbid={}, rid={}, tvmazeid={}, cat={}, offset={}, limit={}, apikey={}"
        ).format(
            t,
            q,
            season,
            ep,
            tvdbid,
            tmdbid,
            imdbid,
            rid,
            tvmazeid,
            cat,
            offset,
            limit,
            "<set>" if apikey else "<none>",
        )
    )
    _require_apikey(apikey)

    # --- CAPS ---
    if t == "caps":
        logger.debug("Handling 'caps' request.")
        xml = _caps_xml()
        logger.debug("Returning caps XML response.")
        return Response(content=xml, media_type="application/xml; charset=utf-8")

    # --- SEARCH (generic) ---
    if t == "search":
        import app.api.torznab as tn

        logger.debug("Handling 'search' request.")
        rss, channel = _rss_root()
        q_str = (q or "").strip()
        logger.debug(f"Search query string: '{q_str}'")
        strm_suffix = " [STRM]"
        cat_id = TORZNAB_CAT_ANIME
        movie_preferred = False
        if cat:
            cat_list = [c.strip() for c in str(cat).split(",") if c.strip()]
            if str(TORZNAB_CAT_MOVIE) in cat_list:
                cat_id = TORZNAB_CAT_MOVIE
                movie_preferred = True
        if movie_preferred:
            logger.debug("Movie category detected; preferring megakino resolution.")

        if not q_str and TORZNAB_RETURN_TEST_RESULT:
            logger.debug("Returning synthetic test result for empty query.")
            # synthetic test result
            release_title = TORZNAB_TEST_TITLE
            guid_base = f"aw:{TORZNAB_TEST_SLUG}:s{TORZNAB_TEST_SEASON}e{TORZNAB_TEST_EPISODE}:{TORZNAB_TEST_LANGUAGE}"
            now = datetime.now(timezone.utc)

            if STRM_FILES_MODE in ("no", "both"):
                magnet = tn.build_magnet(
                    title=release_title,
                    slug=TORZNAB_TEST_SLUG,
                    season=TORZNAB_TEST_SEASON,
                    episode=TORZNAB_TEST_EPISODE,
                    language=TORZNAB_TEST_LANGUAGE,
                    provider=None,
                )
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=guid_base,
                    language=TORZNAB_TEST_LANGUAGE,
                )
            if STRM_FILES_MODE in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=TORZNAB_TEST_SLUG,
                    season=TORZNAB_TEST_SEASON,
                    episode=TORZNAB_TEST_EPISODE,
                    language=TORZNAB_TEST_LANGUAGE,
                    provider=None,
                    mode="strm",
                )
                _build_item(
                    channel=channel,
                    title=release_title + strm_suffix,
                    magnet=magnet_strm,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=f"{guid_base}:strm",
                    language=TORZNAB_TEST_LANGUAGE,
                )
        elif q_str:
            if movie_preferred:
                count = _handle_preview_search(
                    session,
                    q_str,
                    channel,
                    TORZNAB_CAT_MOVIE,
                    site="megakino",
                    limit=limit,
                    strm_suffix=strm_suffix,
                )
                if count == 0:
                    # Fallback to anime category when Megakino returns no matches.
                    _handle_preview_search(
                        session,
                        q_str,
                        channel,
                        TORZNAB_CAT_ANIME,
                        limit=limit,
                        strm_suffix=strm_suffix,
                    )
            else:
                special_count = 0
                if SPECIALS_METADATA_ENABLED:
                    special_count = _handle_special_search(
                        session,
                        q_str,
                        channel,
                        cat_id,
                        ids=SpecialIds(
                            tvdbid=tvdbid,
                            tmdbid=tmdbid,
                            imdbid=imdbid,
                            rid=rid,
                            tvmazeid=tvmazeid,
                        ),
                        limit=limit,
                        strm_suffix=strm_suffix,
                    )
                if special_count == 0:
                    _handle_preview_search(
                        session,
                        q_str,
                        channel,
                        cat_id,
                        limit=limit,
                        strm_suffix=strm_suffix,
                    )
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    # --- MOVIE SEARCH ---
    if t in ("movie", "movie-search"):
        import app.api.torznab as tn

        logger.debug("Handling 'movie' request.")
        rss, channel = _rss_root()
        q_str = (q or "").strip()
        strm_suffix = " [STRM]"
        if not q_str and TORZNAB_RETURN_TEST_RESULT:
            logger.debug("Returning synthetic test result for empty movie query.")
            release_title = TORZNAB_TEST_TITLE
            guid_base = f"aw:{TORZNAB_TEST_SLUG}:s{TORZNAB_TEST_SEASON}e{TORZNAB_TEST_EPISODE}:{TORZNAB_TEST_LANGUAGE}"
            now = datetime.now(timezone.utc)

            if STRM_FILES_MODE in ("no", "both"):
                magnet = tn.build_magnet(
                    title=release_title,
                    slug=TORZNAB_TEST_SLUG,
                    season=TORZNAB_TEST_SEASON,
                    episode=TORZNAB_TEST_EPISODE,
                    language=TORZNAB_TEST_LANGUAGE,
                    provider=None,
                )
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=TORZNAB_CAT_MOVIE,
                    guid_str=guid_base,
                    language=TORZNAB_TEST_LANGUAGE,
                )
            if STRM_FILES_MODE in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=TORZNAB_TEST_SLUG,
                    season=TORZNAB_TEST_SEASON,
                    episode=TORZNAB_TEST_EPISODE,
                    language=TORZNAB_TEST_LANGUAGE,
                    provider=None,
                    mode="strm",
                )
                _build_item(
                    channel=channel,
                    title=release_title + strm_suffix,
                    magnet=magnet_strm,
                    pubdate=now,
                    cat_id=TORZNAB_CAT_MOVIE,
                    guid_str=f"{guid_base}:strm",
                    language=TORZNAB_TEST_LANGUAGE,
                )
        elif q_str:
            _handle_preview_search(
                session,
                q_str,
                channel,
                TORZNAB_CAT_MOVIE,
                site="megakino",
                limit=limit,
                strm_suffix=strm_suffix,
            )
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    # --- TVSEARCH ---
    if t != "tvsearch":
        # Maintain previous behavior: unknown t -> 400
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="invalid t")

    # require season and either query text or resolvable identifier hints.
    import app.api.torznab as tn

    if season is None:
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to missing parameters.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    search_mode = "episode-search" if ep is not None else "season-search"
    logger.debug("tvsearch mode={}", search_mode)
    season_i = int(season)
    ep_i = int(ep) if ep is not None else None
    q_str = (q or "").strip()
    if not q_str:
        q_str = (
            _resolve_tvsearch_query_from_ids(
                tvdbid=tvdbid,
                tmdbid=tmdbid,
                imdbid=imdbid,
            )
            or ""
        ).strip()
        if q_str:
            logger.debug(
                "tvsearch: resolved missing q from identifiers to '{}'",
                q_str,
            )
    if not q_str:
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to unresolved query.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    logger.debug("Searching for slug for query '{}' (season={})", q_str, season_i)
    result = tn._slug_from_query(q_str)
    if not result:
        logger.warning(f"No slug found for query '{q_str}'. Returning empty RSS feed.")
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    site_found, slug = result
    display_title = tn.resolve_series_title(slug, site_found) or q_str
    logger.debug(
        f"Resolved display title: '{display_title}' for slug '{slug}' on site '{site_found}'"
    )

    rss, channel = _rss_root()
    count = 0
    limit_i = max(1, int(limit))
    now = datetime.now(timezone.utc)
    strm_suffix = " [STRM]"
    ids = SpecialIds(
        tvdbid=tvdbid,
        tmdbid=tmdbid,
        imdbid=imdbid,
        rid=rid,
        tvmazeid=tvmazeid,
    )
    if search_mode == "episode-search":
        assert ep_i is not None
        emitted, limit_hit = emit_tvsearch_episode_items(
            tn_module=tn,
            session=session,
            channel=channel,
            slug=slug,
            site_found=site_found,
            display_title=display_title,
            q_str=q_str,
            request_season=season_i,
            request_episode=ep_i,
            ids=ids,
            now=now,
            strm_suffix=strm_suffix,
            max_items=limit_i,
        )
        count += emitted
        if limit_hit:
            logger.info(
                "tvsearch episode-search terminated due to limit hit (limit={})",
                limit_i,
            )
    else:
        episode_numbers = resolve_season_episode_numbers(
            tn_module=tn,
            session=session,
            slug=slug,
            season_i=season_i,
            site_found=site_found,
            q_str=q_str,
            ids=ids,
        )
        logger.info(
            "tvsearch season-search discovered {} episodes for slug={} season={}",
            len(episode_numbers),
            slug,
            season_i,
        )
        for episode_i in episode_numbers:
            remaining = limit_i - count
            if remaining <= 0:
                logger.info(
                    "tvsearch season-search termination reason=limit hit limit={}",
                    limit_i,
                )
                break

            emitted, limit_hit = emit_tvsearch_episode_items(
                tn_module=tn,
                session=session,
                channel=channel,
                slug=slug,
                site_found=site_found,
                display_title=display_title,
                q_str=q_str,
                request_season=season_i,
                request_episode=episode_i,
                ids=ids,
                now=now,
                strm_suffix=strm_suffix,
                max_items=remaining,
            )
            count += emitted
            if limit_hit:
                logger.info(
                    (
                        "tvsearch season-search termination reason=limit hit "
                        "limit={} emitted_items={}"
                    ),
                    limit_i,
                    count,
                )
                break

    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
    logger.info(f"Returning RSS feed with {count} items.")
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
