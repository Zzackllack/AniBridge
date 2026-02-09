from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import re
import threading
import time
import unicodedata
from urllib.parse import urlencode

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.config import (
    ANIWORLD_BASE_URL,
    SPECIALS_MATCH_CONFIDENCE_THRESHOLD,
    SPECIALS_METADATA_CACHE_TTL_MINUTES,
    SPECIALS_METADATA_ENABLED,
    SPECIALS_METADATA_TIMEOUT_SECONDS,
)
from app.utils.http_client import get as http_get

_FILM_PATH_RE = re.compile(r"/filme/film-(\d+)")
_PART_NUMBER_RE = re.compile(r"\b(?:part|teil)\s*(\d+)\b", re.IGNORECASE)

_DEFAULT_TIMEOUT_SECONDS = max(1.0, float(SPECIALS_METADATA_TIMEOUT_SECONDS))
_CACHE_TTL_SECONDS = max(0, int(SPECIALS_METADATA_CACHE_TTL_MINUTES)) * 60

_CACHE_LOCK = threading.Lock()
_SKYHOOK_SEARCH_CACHE: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
_SKYHOOK_SHOW_CACHE: Dict[int, tuple[float, Dict[str, Any]]] = {}
_ANIWORLD_SPECIALS_CACHE: Dict[str, tuple[float, List["AniworldSpecialEntry"]]] = {}

_SKYHOOK_SEARCH_URL = "https://skyhook.sonarr.tv/v1/tvdb/search/en/"
_SKYHOOK_SHOW_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"


@dataclass(frozen=True)
class SpecialIds:
    tvdbid: Optional[int] = None
    tmdbid: Optional[int] = None
    imdbid: Optional[str] = None
    rid: Optional[int] = None
    tvmazeid: Optional[int] = None


@dataclass(frozen=True)
class AniworldSpecialEntry:
    film_index: int
    episode_id: Optional[int]
    episode_season_id: Optional[int]
    href: str
    title_de: str
    title_alt: str
    tags: tuple[str, ...]

    @property
    def combined_title(self) -> str:
        return " ".join(p for p in [self.title_de, self.title_alt] if p).strip()


@dataclass(frozen=True)
class SkyHookEpisode:
    season_number: int
    episode_number: int
    title: str


@dataclass(frozen=True)
class SpecialEpisodeMapping:
    source_season: int
    source_episode: int
    alias_season: int
    alias_episode: int
    metadata_title: str
    metadata_tvdb_id: int


def _as_int(raw: object) -> Optional[int]:
    try:
        if raw is None:
            return None
        value = str(raw).strip()
        if not value:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("’", "'").replace("`", "'")
    normalized = normalized.replace("[", " ").replace("]", " ")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized)
    return normalized.lower().strip()


def _tokenize(value: str) -> List[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    return [token for token in normalized.split(" ") if token]


def _part_numbers(value: str) -> set[int]:
    return {int(match) for match in _PART_NUMBER_RE.findall(value or "")}


def _title_score(left: str, right: str) -> float:
    left_n = _normalize_text(left)
    right_n = _normalize_text(right)
    if not left_n or not right_n:
        return 0.0

    left_tokens = set(_tokenize(left_n))
    right_tokens = set(_tokenize(right_n))
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = left_tokens & right_tokens
    overlap = len(intersection) / max(1, len(left_tokens))
    jaccard = len(intersection) / max(1, len(left_tokens | right_tokens))
    containment = 1.0 if (left_n in right_n or right_n in left_n) else 0.0

    score = (0.55 * overlap) + (0.25 * jaccard) + (0.20 * containment)

    left_parts = _part_numbers(left_n)
    right_parts = _part_numbers(right_n)
    if left_parts and right_parts:
        if left_parts == right_parts:
            score += 0.30
        elif left_parts.isdisjoint(right_parts):
            score -= 0.30

    return max(0.0, min(1.0, score))


def parse_filme_entries(html_text: str) -> List[AniworldSpecialEntry]:
    soup = BeautifulSoup(html_text, "html.parser")
    season_zero = soup.find("tbody", id="season0")
    if season_zero is None:
        return []

    entries: List[AniworldSpecialEntry] = []
    for row in season_zero.find_all("tr"):
        link_tag = row.find("a", href=_FILM_PATH_RE)
        if link_tag is None:
            continue

        href = str(link_tag.get("href") or "").strip()
        film_match = _FILM_PATH_RE.search(href)
        if film_match is None:
            continue
        film_index = int(film_match.group(1))

        title_td = row.find("td", class_="seasonEpisodeTitle")
        title_de = ""
        title_alt = ""
        if title_td is not None:
            strong = title_td.find("strong")
            span = title_td.find("span")
            title_de = (strong.get_text(" ", strip=True) if strong else "").strip()
            title_alt = (span.get_text(" ", strip=True) if span else "").strip()

        tag_source = " ".join(part for part in [title_de, title_alt] if part)
        tags = tuple(
            sorted(
                {
                    match.strip()
                    for match in re.findall(r"\[([^\]]+)\]", tag_source)
                    if match.strip()
                }
            )
        )

        entries.append(
            AniworldSpecialEntry(
                film_index=film_index,
                episode_id=_as_int(row.get("data-episode-id")),
                episode_season_id=_as_int(row.get("data-episode-season-id")),
                href=href,
                title_de=title_de,
                title_alt=title_alt,
                tags=tags,
            )
        )

    entries.sort(key=lambda entry: entry.film_index)
    return entries


def _get_cached_entries(slug: str) -> Optional[List[AniworldSpecialEntry]]:
    if _CACHE_TTL_SECONDS <= 0:
        return None
    now = time.time()
    with _CACHE_LOCK:
        record = _ANIWORLD_SPECIALS_CACHE.get(slug)
        if record is None:
            return None
        stored_at, payload = record
        if now - stored_at > _CACHE_TTL_SECONDS:
            _ANIWORLD_SPECIALS_CACHE.pop(slug, None)
            return None
        return payload


def _set_cached_entries(slug: str, entries: List[AniworldSpecialEntry]) -> None:
    if _CACHE_TTL_SECONDS <= 0:
        return
    with _CACHE_LOCK:
        _ANIWORLD_SPECIALS_CACHE[slug] = (time.time(), entries)


def fetch_filme_entries(
    slug: str,
    *,
    base_url: str = ANIWORLD_BASE_URL,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> List[AniworldSpecialEntry]:
    cached = _get_cached_entries(slug)
    if cached is not None:
        return cached

    url = f"{base_url.rstrip('/')}/anime/stream/{slug}/filme"
    response = http_get(url, timeout=timeout_seconds)
    response.raise_for_status()
    entries = parse_filme_entries(response.text)
    _set_cached_entries(slug, entries)
    return entries


def _get_skyhook_cached_search(term: str) -> Optional[List[Dict[str, Any]]]:
    if _CACHE_TTL_SECONDS <= 0:
        return None
    now = time.time()
    with _CACHE_LOCK:
        record = _SKYHOOK_SEARCH_CACHE.get(term)
        if record is None:
            return None
        stored_at, payload = record
        if now - stored_at > _CACHE_TTL_SECONDS:
            _SKYHOOK_SEARCH_CACHE.pop(term, None)
            return None
        return payload


def _set_skyhook_cached_search(term: str, payload: List[Dict[str, Any]]) -> None:
    if _CACHE_TTL_SECONDS <= 0:
        return
    with _CACHE_LOCK:
        _SKYHOOK_SEARCH_CACHE[term] = (time.time(), payload)


def _get_skyhook_cached_show(tvdb_id: int) -> Optional[Dict[str, Any]]:
    if _CACHE_TTL_SECONDS <= 0:
        return None
    now = time.time()
    with _CACHE_LOCK:
        record = _SKYHOOK_SHOW_CACHE.get(tvdb_id)
        if record is None:
            return None
        stored_at, payload = record
        if now - stored_at > _CACHE_TTL_SECONDS:
            _SKYHOOK_SHOW_CACHE.pop(tvdb_id, None)
            return None
        return payload


def _set_skyhook_cached_show(tvdb_id: int, payload: Dict[str, Any]) -> None:
    if _CACHE_TTL_SECONDS <= 0:
        return
    with _CACHE_LOCK:
        _SKYHOOK_SHOW_CACHE[tvdb_id] = (time.time(), payload)


def _skyhook_search(term: str, timeout_seconds: float) -> List[Dict[str, Any]]:
    normalized_term = term.strip().lower()
    if not normalized_term:
        return []
    cached = _get_skyhook_cached_search(normalized_term)
    if cached is not None:
        return cached

    query = urlencode({"term": normalized_term})
    url = f"{_SKYHOOK_SEARCH_URL}?{query}"
    response = http_get(url, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    results: List[Dict[str, Any]] = [item for item in payload if isinstance(item, dict)]
    _set_skyhook_cached_search(normalized_term, results)
    return results


def _skyhook_show(tvdb_id: int, timeout_seconds: float) -> Optional[Dict[str, Any]]:
    cached = _get_skyhook_cached_show(tvdb_id)
    if cached is not None:
        return cached

    url = _SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id)
    response = http_get(url, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    _set_skyhook_cached_show(tvdb_id, payload)
    return payload


def _resolve_tvdb_id(
    *,
    ids: SpecialIds,
    series_title: str,
    query: str,
    timeout_seconds: float,
) -> Optional[int]:
    if ids.tvdbid and ids.tvdbid > 0:
        return ids.tvdbid

    id_terms: List[str] = []
    if ids.tmdbid and ids.tmdbid > 0:
        id_terms.append(f"tmdb:{ids.tmdbid}")
    imdb = (ids.imdbid or "").strip()
    if imdb:
        id_terms.append(f"imdb:{imdb}")
    # rid/tvmazeid are accepted by Torznab clients, but SkyHook lookup uses
    # tvdb/tmdb/imdb prefixes. Keep these as no-op inputs for now.
    for term in id_terms:
        try:
            candidates = _skyhook_search(term, timeout_seconds)
        except Exception as exc:  # pragma: no cover - network resilience
            logger.debug("SkyHook ID lookup failed for {}: {}", term, exc)
            continue
        if not candidates:
            continue
        candidate_id = _as_int(candidates[0].get("tvdbId"))
        if candidate_id and candidate_id > 0:
            return candidate_id

    title_candidates = [series_title, query]
    best_id: Optional[int] = None
    best_score = 0.0
    for candidate_query in title_candidates:
        query_clean = (candidate_query or "").strip()
        if not query_clean:
            continue
        try:
            candidates = _skyhook_search(query_clean, timeout_seconds)
        except Exception as exc:  # pragma: no cover - network resilience
            logger.debug("SkyHook title search failed for {}: {}", query_clean, exc)
            continue
        for show in candidates:
            tvdb_id = _as_int(show.get("tvdbId"))
            title = str(show.get("title") or "")
            if not tvdb_id or not title:
                continue
            score = _title_score(series_title, title)
            if score > best_score:
                best_score = score
                best_id = tvdb_id
    if best_id and best_score >= 0.45:
        return best_id
    return None


def _extract_episodes(show_payload: Dict[str, Any]) -> List[SkyHookEpisode]:
    episodes: List[SkyHookEpisode] = []
    for item in show_payload.get("episodes", []):
        if not isinstance(item, dict):
            continue
        season_number = _as_int(item.get("seasonNumber"))
        episode_number = _as_int(item.get("episodeNumber"))
        title = str(item.get("title") or "").strip()
        if season_number is None or episode_number is None or not title:
            continue
        episodes.append(
            SkyHookEpisode(
                season_number=season_number,
                episode_number=episode_number,
                title=title,
            )
        )
    return episodes


def _pick_episode_by_query(
    query: str,
    episodes: Sequence[SkyHookEpisode],
) -> Optional[SkyHookEpisode]:
    best: Optional[SkyHookEpisode] = None
    best_score = 0.0
    for episode in episodes:
        score = _title_score(query, episode.title)
        if score > best_score:
            best_score = score
            best = episode
    if best is None:
        return None
    threshold = max(0.25, float(SPECIALS_MATCH_CONFIDENCE_THRESHOLD) - 0.10)
    if best_score < threshold:
        return None
    return best


def _pick_entry_for_episode(
    *,
    metadata_episode: SkyHookEpisode,
    entries: Sequence[AniworldSpecialEntry],
) -> Optional[AniworldSpecialEntry]:
    best: Optional[AniworldSpecialEntry] = None
    best_score = 0.0
    for entry in entries:
        candidate_titles = [
            entry.title_de,
            entry.title_alt,
            entry.combined_title,
        ]
        score = max(
            _title_score(metadata_episode.title, title) for title in candidate_titles
        )
        if entry.film_index == metadata_episode.episode_number:
            score += 0.10
        if score > best_score:
            best_score = score
            best = entry
    if best is None:
        return None
    threshold = max(0.25, float(SPECIALS_MATCH_CONFIDENCE_THRESHOLD) - 0.15)
    if best_score < threshold:
        return None
    return best


def _resolve_show_payload(
    *,
    ids: SpecialIds,
    query: str,
    series_title: str,
    timeout_seconds: float,
) -> Optional[Dict[str, Any]]:
    tvdb_id = _resolve_tvdb_id(
        ids=ids,
        series_title=series_title,
        query=query,
        timeout_seconds=timeout_seconds,
    )
    if not tvdb_id:
        return None

    try:
        return _skyhook_show(tvdb_id, timeout_seconds)
    except Exception as exc:  # pragma: no cover - network resilience
        logger.debug("SkyHook show lookup failed for tvdb {}: {}", tvdb_id, exc)
        return None


def resolve_special_mapping_from_query(
    *,
    slug: str,
    query: str,
    series_title: str,
    ids: SpecialIds,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Optional[SpecialEpisodeMapping]:
    if not SPECIALS_METADATA_ENABLED:
        return None
    if not slug or not query:
        return None

    try:
        entries = fetch_filme_entries(slug, timeout_seconds=timeout_seconds)
    except Exception as exc:  # pragma: no cover - network resilience
        logger.debug("AniWorld specials fetch failed for slug {}: {}", slug, exc)
        return None
    if not entries:
        return None

    payload = _resolve_show_payload(
        ids=ids,
        query=query,
        series_title=series_title,
        timeout_seconds=timeout_seconds,
    )
    if not payload:
        return None

    tvdb_id = _as_int(payload.get("tvdbId"))
    if tvdb_id is None:
        return None

    episodes = _extract_episodes(payload)
    specials = [episode for episode in episodes if episode.season_number == 0]
    if not specials:
        return None

    metadata_episode = _pick_episode_by_query(query, specials)
    if metadata_episode is None:
        return None

    matched_entry = _pick_entry_for_episode(
        metadata_episode=metadata_episode,
        entries=entries,
    )
    if matched_entry is None:
        return None

    return SpecialEpisodeMapping(
        source_season=0,
        source_episode=matched_entry.film_index,
        alias_season=metadata_episode.season_number,
        alias_episode=metadata_episode.episode_number,
        metadata_title=metadata_episode.title,
        metadata_tvdb_id=tvdb_id,
    )


def resolve_special_mapping_from_episode_request(
    *,
    slug: str,
    request_season: int,
    request_episode: int,
    query: str,
    series_title: str,
    ids: SpecialIds,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Optional[SpecialEpisodeMapping]:
    if not SPECIALS_METADATA_ENABLED:
        return None
    if not slug:
        return None

    try:
        entries = fetch_filme_entries(slug, timeout_seconds=timeout_seconds)
    except Exception as exc:  # pragma: no cover - network resilience
        logger.debug("AniWorld specials fetch failed for slug {}: {}", slug, exc)
        return None
    if not entries:
        return None

    payload = _resolve_show_payload(
        ids=ids,
        query=query,
        series_title=series_title,
        timeout_seconds=timeout_seconds,
    )
    if not payload:
        return None

    tvdb_id = _as_int(payload.get("tvdbId"))
    if tvdb_id is None:
        return None

    metadata_episode: Optional[SkyHookEpisode] = None
    for episode in _extract_episodes(payload):
        if (
            episode.season_number == request_season
            and episode.episode_number == request_episode
        ):
            metadata_episode = episode
            break

    if metadata_episode is None:
        return None

    matched_entry = _pick_entry_for_episode(
        metadata_episode=metadata_episode,
        entries=entries,
    )
    if matched_entry is None:
        return None

    return SpecialEpisodeMapping(
        source_season=0,
        source_episode=matched_entry.film_index,
        alias_season=request_season,
        alias_episode=request_episode,
        metadata_title=metadata_episode.title,
        metadata_tvdb_id=tvdb_id,
    )
