from __future__ import annotations

import threading
import time
from urllib.parse import urlencode

from loguru import logger

from app.config import ANIBRIDGE_TEST_MODE
from app.providers.aniworld.specials import SpecialIds
from app.utils.http_client import get as http_get

from .helpers import coerce_non_negative_int, coerce_positive_int

SKYHOOK_SEARCH_URL = "https://skyhook.sonarr.tv/v1/tvdb/search/en/"
SKYHOOK_SHOW_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"
TVSEARCH_ID_CACHE_TTL_SECONDS = 300.0
TVSEARCH_ID_CACHE_MAX_ENTRIES = 512

_cache_lock = threading.Lock()
_term_to_tvdb_cache: dict[str, tuple[float, int]] = {}
_tvdb_to_title_cache: dict[int, tuple[float, str]] = {}


def _cache_get_term_tvdb(term: str) -> int | None:
    """Return a fresh cached tvdb id for a SkyHook search term."""
    now = time.time()
    with _cache_lock:
        entry = _term_to_tvdb_cache.get(term)
        if not entry:
            return None
        cached_at, cached_tvdb = entry
        if now - cached_at > TVSEARCH_ID_CACHE_TTL_SECONDS:
            _term_to_tvdb_cache.pop(term, None)
            return None
        return cached_tvdb


def _cache_set_term_tvdb(term: str, tvdb_id: int) -> None:
    """Store a SkyHook term->tvdb mapping with TTL semantics."""
    with _cache_lock:
        _term_to_tvdb_cache[term] = (time.time(), tvdb_id)
        if len(_term_to_tvdb_cache) > TVSEARCH_ID_CACHE_MAX_ENTRIES:
            oldest = min(_term_to_tvdb_cache.items(), key=lambda item: item[1][0])[0]
            _term_to_tvdb_cache.pop(oldest, None)


def _cache_get_tvdb_title(tvdb_id: int) -> str | None:
    """Return a fresh cached title for a tvdb id."""
    now = time.time()
    with _cache_lock:
        entry = _tvdb_to_title_cache.get(tvdb_id)
        if not entry:
            return None
        cached_at, cached_title = entry
        if now - cached_at > TVSEARCH_ID_CACHE_TTL_SECONDS:
            _tvdb_to_title_cache.pop(tvdb_id, None)
            return None
        return cached_title


def _cache_set_tvdb_title(tvdb_id: int, title: str) -> None:
    """Store a SkyHook tvdb->title mapping with TTL semantics."""
    with _cache_lock:
        _tvdb_to_title_cache[tvdb_id] = (time.time(), title)
        if len(_tvdb_to_title_cache) > TVSEARCH_ID_CACHE_MAX_ENTRIES:
            oldest = min(_tvdb_to_title_cache.items(), key=lambda item: item[1][0])[0]
            _tvdb_to_title_cache.pop(oldest, None)


def resolve_tvsearch_query_from_ids(
    *,
    tvdbid: int | None,
    tmdbid: int | None,
    imdbid: str | None,
) -> str | None:
    """Resolve a canonical show title from Torznab ids via SkyHook."""
    tvdb_id = coerce_positive_int(tvdbid)
    if tvdb_id is None:
        lookup_terms: list[str] = []
        tmdb = coerce_positive_int(tmdbid)
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
                response = http_get(f"{SKYHOOK_SEARCH_URL}?{query}", timeout=8.0)
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
                candidate = coerce_positive_int(item.get("tvdbId"))
                if candidate is None:
                    continue
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
        response = http_get(SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id), timeout=8.0)
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


def resolve_tvdb_id_for_tvsearch(
    *,
    q_str: str,
    tvdbid: int | None,
    tmdbid: int | None,
    imdbid: str | None,
) -> int | None:
    """Resolve a tvdb id for tvsearch using explicit ids first, then SkyHook."""
    tvdb_id = coerce_positive_int(tvdbid)
    if tvdb_id is not None:
        return tvdb_id
    if ANIBRIDGE_TEST_MODE:
        return None

    lookup_terms: list[str] = []
    tmdb = coerce_positive_int(tmdbid)
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
                f"{SKYHOOK_SEARCH_URL}?{query_params}",
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
            candidate = coerce_positive_int(item.get("tvdbId"))
            if candidate is None:
                continue
            _cache_set_term_tvdb(term, candidate)
            return candidate
    return None


def metadata_episode_numbers_for_season(
    *,
    q_str: str,
    season_i: int,
    ids: SpecialIds,
) -> list[int]:
    """Resolve season episode numbers from SkyHook metadata."""
    tvdb_id = resolve_tvdb_id_for_tvsearch(
        q_str=q_str,
        tvdbid=ids.tvdbid,
        tmdbid=ids.tmdbid,
        imdbid=ids.imdbid,
    )
    if tvdb_id is None:
        return []

    try:
        response = http_get(SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id), timeout=8.0)
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

    episode_numbers: list[int] = []
    for item in raw_episodes:
        if not isinstance(item, dict):
            continue
        item_season = coerce_non_negative_int(item.get("seasonNumber"))
        item_episode = coerce_positive_int(item.get("episodeNumber"))
        if item_season != season_i or item_episode is None:
            continue
        episode_numbers.append(item_episode)
    return sorted(set(episode_numbers))
