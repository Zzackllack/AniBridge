from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional, Tuple

from loguru import logger

from app.utils.logger import config as configure_logger

configure_logger()

from aniworld.common.common import get_season_episode_count  # type: ignore


@lru_cache(maxsize=64)
def _season_counts(slug: str) -> Dict[int, int]:
    logger.debug("Fetching season episode counts for slug='{}'", slug)
    try:
        counts = get_season_episode_count(slug)
    except Exception as exc:  # pragma: no cover - safety net around external lib
        logger.error(
            "Failed to load season episode counts for slug='{}': {}", slug, exc
        )
        counts = {}
    if not counts:
        logger.warning("Season episode counts empty for slug='{}'", slug)
    else:
        logger.debug("Season counts for slug='{}': {}", slug, counts)
    return counts or {}


def resolve_absolute_episode(
    slug: str, absolute_number: int
) -> Optional[Tuple[int, int]]:
    """
    Map an absolute episode index to (season, episode) for AniWorld.

    Returns None if the mapping cannot be determined.
    """
    if absolute_number <= 0:
        logger.warning(
            "Absolute number must be positive (slug='{}', absolute={})",
            slug,
            absolute_number,
        )
        return None

    counts = _season_counts(slug)
    if not counts:
        logger.warning(
            "No season episode counts available for slug='{}' (absolute={})",
            slug,
            absolute_number,
        )
        return None

    running_total = 0
    for season in sorted(counts):
        season_total = counts.get(season) or 0
        if season_total <= 0:
            logger.debug(
                "Skipping season {} for slug='{}' due to non-positive total ({})",
                season,
                slug,
                season_total,
            )
            continue
        next_total = running_total + season_total
        if absolute_number <= next_total:
            episode = absolute_number - running_total
            logger.debug(
                "Resolved absolute={} for slug='{}' -> season={} episode={}",
                absolute_number,
                slug,
                season,
                episode,
            )
            return (season, episode)
        running_total = next_total

    logger.warning(
        "Absolute number {} exceeds available episodes for slug='{}' (total={})",
        absolute_number,
        slug,
        running_total,
    )
    return None


def clear_absolute_cache(slug: Optional[str] = None) -> None:
    """
    Helper for tests to clear cached season counts.
    """
    if slug is None:
        _season_counts.cache_clear()
        return

    cache = _season_counts.cache_info()
    if cache.currsize == 0:
        return
    # Python functools LRU cache doesn't expose per-key invalidation, so clear all.
    _season_counts.cache_clear()
