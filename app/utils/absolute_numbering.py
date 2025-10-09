from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

from loguru import logger
from sqlmodel import Session

from app.db import (
    EpisodeNumberMapping,
    get_episode_mapping_by_absolute,
    get_episode_mapping_by_season_episode,
    list_episode_mappings_for_series,
    upsert_episode_mapping,
)

ABSOLUTE_IDENTIFIER_RE = re.compile(r"^\d+$")


def is_absolute_identifier(identifier: str | None) -> bool:
    if identifier is None:
        return False
    return bool(ABSOLUTE_IDENTIFIER_RE.fullmatch(identifier.strip()))


def parse_absolute_identifier(identifier: str | None) -> Optional[int]:
    if not identifier:
        return None
    token = identifier.strip()
    if not ABSOLUTE_IDENTIFIER_RE.fullmatch(token):
        return None
    value = int(token)
    if value <= 0:
        return None
    return value


def _parse_from_query(query: str | None) -> Optional[int]:
    if not query:
        return None
    tokens = re.findall(r"\d+", query)
    if not tokens:
        return None
    # Prefer the last group of digits – Sonarr appends the absolute index
    return parse_absolute_identifier(tokens[-1])


def detect_absolute_number(
    *,
    query: str | None,
    season: Optional[int],
    episode: Optional[int],
    absolute_hint: Optional[bool],
) -> Optional[int]:
    """Return the absolute episode number if the request should be handled in absolute mode."""
    if absolute_hint:
        if episode is not None:
            return episode if episode > 0 else None
        return _parse_from_query(query)

    if season == 0 and episode is not None:
        return episode if episode > 0 else None

    if episode is None:
        return _parse_from_query(query)

    # When Sonarr supplies both season and episode we default to standard numbering.
    return None


@dataclass
class EpisodeCatalogEntry:
    absolute: int
    season: int
    episode: int
    title: Optional[str] = None
    is_special: bool = False


def _entry_from_raw(raw: object) -> Optional[EpisodeCatalogEntry]:
    try:
        if isinstance(raw, EpisodeCatalogEntry):
            return raw
        if isinstance(raw, dict):
            absolute = int(raw.get("absolute"))
            season = int(raw.get("season"))
            episode = int(raw.get("episode"))
            title = raw.get("title")
            is_special = bool(raw.get("is_special", False))
            return EpisodeCatalogEntry(
                absolute=absolute,
                season=season,
                episode=episode,
                title=title,
                is_special=is_special or season <= 0,
            )

        # Support AniWorld Episode objects dynamically
        absolute = getattr(raw, "absolute", None) or getattr(
            raw, "absolute_number", None
        )
        season = getattr(raw, "season", None)
        episode = getattr(raw, "episode", None) or getattr(raw, "number", None)
        title = getattr(raw, "title", None)
        if absolute is None or season is None or episode is None:
            return None
        absolute_i = int(absolute)
        season_i = int(season)
        episode_i = int(episode)
        return EpisodeCatalogEntry(
            absolute=absolute_i,
            season=season_i,
            episode=episode_i,
            title=str(title) if title is not None else None,
            is_special=season_i <= 0,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Skipping malformed catalog entry {}: {}", raw, exc)
        return None


def _store_catalog_entries(
    session: Session,
    series_slug: str,
    entries: Sequence[EpisodeCatalogEntry],
) -> List[EpisodeNumberMapping]:
    stored: List[EpisodeNumberMapping] = []
    for entry in entries:
        if entry.absolute <= 0 or entry.season <= 0 or entry.episode <= 0:
            continue
        try:
            mapping = upsert_episode_mapping(
                session,
                series_slug=series_slug,
                absolute_number=entry.absolute,
                season_number=entry.season,
                episode_number=entry.episode,
                episode_title=entry.title,
            )
            stored.append(mapping)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to upsert mapping for slug={} abs={} S{}E{}: {}",
                series_slug,
                entry.absolute,
                entry.season,
                entry.episode,
                exc,
            )
    return stored


def fetch_episode_catalog(slug: str) -> List[dict]:
    """Fetch the AniWorld catalogue for a given slug.

    Returns a list of dictionaries with absolute, season, episode, title, and is_special keys.
    """
    try:
        from aniworld.models import Anime  # type: ignore
    except Exception as exc:  # pragma: no cover - runtime environment only
        logger.warning(
            "AniWorld library unavailable while fetching catalog for slug '{}': {}",
            slug,
            exc,
        )
        return []

    try:
        anime = Anime(slug=slug)
    except Exception as exc:
        logger.error("Failed to initialise AniWorld series '{}': {}", slug, exc)
        return []

    episodes: Iterable[object] = []
    try:
        episodes = getattr(anime, "episodes", None)
        if callable(episodes):
            episodes = episodes()
        if episodes is None:
            episodes = []
    except Exception as exc:
        logger.error("AniWorld episodes lookup failed for '{}': {}", slug, exc)
        return []

    catalog: List[dict] = []
    for raw in episodes:
        entry = _entry_from_raw(raw)
        if not entry:
            continue
        catalog.append(
            {
                "absolute": entry.absolute,
                "season": entry.season,
                "episode": entry.episode,
                "title": entry.title,
                "is_special": entry.is_special,
            }
        )
    return catalog


def ensure_catalog_mappings(
    session: Session,
    *,
    series_slug: str,
    fetch_catalog: Callable[[], Iterable[object]],
) -> List[EpisodeNumberMapping]:
    raw_entries = list(fetch_catalog() or [])
    entries = [
        entry
        for entry in (_entry_from_raw(raw) for raw in raw_entries)
        if entry and not entry.is_special
    ]
    if not entries:
        return []

    _store_catalog_entries(session, series_slug, entries)
    mappings = list_episode_mappings_for_series(session, series_slug=series_slug)
    return [m for m in mappings if m.season_number > 0]


def resolve_absolute_episode(
    session: Session,
    *,
    series_slug: str,
    absolute_number: int,
    fetch_catalog: Callable[[], Iterable[object]],
) -> Optional[EpisodeNumberMapping]:
    mapping = get_episode_mapping_by_absolute(
        session, series_slug=series_slug, absolute_number=absolute_number
    )
    if mapping and mapping.season_number > 0:
        return mapping

    ensure_catalog_mappings(
        session, series_slug=series_slug, fetch_catalog=fetch_catalog
    )

    mapping = get_episode_mapping_by_absolute(
        session, series_slug=series_slug, absolute_number=absolute_number
    )
    if mapping and mapping.season_number > 0:
        return mapping
    return None


def resolve_absolute_targets(
    session: Session,
    *,
    series_slug: str,
    absolute_number: int,
    fetch_catalog: Callable[[], Iterable[object]],
    fallback_enabled: bool,
) -> tuple[List[EpisodeNumberMapping], bool]:
    mapping = resolve_absolute_episode(
        session,
        series_slug=series_slug,
        absolute_number=absolute_number,
        fetch_catalog=fetch_catalog,
    )
    if mapping:
        return [mapping], False

    logger.error(
        "cannot map episode: slug={} absolute={} has no season/episode mapping",
        series_slug,
        absolute_number,
    )
    if not fallback_enabled:
        return [], False

    mappings = ensure_catalog_mappings(
        session, series_slug=series_slug, fetch_catalog=fetch_catalog
    )
    if not mappings:
        return [], True

    logger.warning(
        "using fallback catalogue for slug={} ({} episodes)",
        series_slug,
        len(mappings),
    )
    return mappings, True


def find_by_season_episode(
    session: Session,
    *,
    series_slug: str,
    season_number: int,
    episode_number: int,
) -> Optional[EpisodeNumberMapping]:
    return get_episode_mapping_by_season_episode(
        session,
        series_slug=series_slug,
        season_number=season_number,
        episode_number=episode_number,
    )
