from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.catalog.metadata import resolve_tv_canonical_match
from app.config import CATALOG_SITE_CONFIGS
from app.db import normalize_catalog_text
from app.providers import get_provider
from app.providers.megakino.client import (
    get_default_client as get_default_megakino_client,
)
from app.utils.domain_resolver import get_megakino_base_url
from app.utils.http_client import get as http_get


@dataclass(slots=True)
class EpisodeLanguageRecord:
    language: str
    host_hints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EpisodeRecord:
    season: int
    episode: int
    relative_path: str
    title_primary: Optional[str]
    title_secondary: Optional[str]
    media_type_hint: str
    languages: list[EpisodeLanguageRecord] = field(default_factory=list)


@dataclass(slots=True)
class CanonicalPayload:
    series: Optional[dict[str, Any]] = None
    episodes: list[dict[str, Any]] = field(default_factory=list)
    series_mappings: list[dict[str, Any]] = field(default_factory=list)
    episode_mappings: list[dict[str, Any]] = field(default_factory=list)
    movie_mappings: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class TitleRecord:
    provider: str
    slug: str
    title: str
    aliases: list[str]
    media_type_hint: str
    relative_path: str
    episodes: list[EpisodeRecord] = field(default_factory=list)
    canonical: CanonicalPayload = field(default_factory=CanonicalPayload)


def _relative_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _normalize_provider_data(raw: Any, *, site: str) -> list[EpisodeLanguageRecord]:
    if not isinstance(raw, dict):
        return []
    languages: list[EpisodeLanguageRecord] = []
    for key, provider_map in raw.items():
        if site == "aniworld.to":
            audio = getattr(key[0], "value", str(key[0])) if isinstance(key, tuple) else ""
            subtitles = (
                getattr(key[1], "value", str(key[1])) if isinstance(key, tuple) and len(key) > 1 else ""
            )
            if audio == "German" and subtitles == "None":
                language = "German Dub"
            elif audio == "Japanese" and subtitles == "German":
                language = "German Sub"
            elif audio == "Japanese" and subtitles == "English":
                language = "English Sub"
            else:
                language = f"{audio} {subtitles}".strip()
        else:
            lang_id = int(key) if isinstance(key, int) or str(key).isdigit() else None
            if lang_id == 1:
                language = "German Dub"
            elif lang_id == 2:
                language = "English Dub"
            elif lang_id == 3:
                language = "German Sub"
            else:
                language = str(key)
        host_hints = sorted(str(name) for name in (provider_map or {}).keys())
        languages.append(EpisodeLanguageRecord(language=language, host_hints=host_hints))
    languages.sort(key=lambda entry: entry.language)
    return languages


def _score_episode_title(left: str, right: str) -> float:
    a = normalize_catalog_text(left)
    b = normalize_catalog_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _build_tv_canonical_payload(
    *,
    provider: str,
    slug: str,
    title: str,
    aliases: list[str],
    imdb_id: Optional[str],
    mal_id: Optional[int],
    episodes: list[EpisodeRecord],
) -> CanonicalPayload:
    match = resolve_tv_canonical_match(
        title=title,
        aliases=aliases,
        imdb_id=imdb_id,
        tmdb_id=None,
    )
    if match is None:
        return CanonicalPayload()

    payload = match.payload
    raw_episodes = payload.get("episodes")
    if not isinstance(raw_episodes, list):
        raw_episodes = []
    canonical_episodes: list[dict[str, Any]] = []
    for item in raw_episodes:
        if not isinstance(item, dict):
            continue
        season_number = item.get("seasonNumber")
        episode_number = item.get("episodeNumber")
        episode_title = str(item.get("title") or "").strip()
        if not isinstance(season_number, int) or not isinstance(episode_number, int) or not episode_title:
            continue
        canonical_episodes.append(
            {
                "season": season_number,
                "episode": episode_number,
                "title": episode_title,
            }
        )

    series_payload = {
        "tvdb_id": match.tvdb_id,
        "title": match.title,
        "tmdb_id": payload.get("tmdbId") if isinstance(payload.get("tmdbId"), int) else None,
        "imdb_id": imdb_id or str(payload.get("imdbId") or "").strip() or None,
        "tvmaze_id": payload.get("tvMazeId") if isinstance(payload.get("tvMazeId"), int) else None,
        "anilist_id": None,
        "mal_id": mal_id,
        "aliases": aliases,
    }
    series_mappings = [
        {
            "tvdb_id": match.tvdb_id,
            "confidence": match.confidence,
            "source": match.source,
            "rationale": match.rationale,
        }
    ]

    by_number = {
        (item["season"], item["episode"]): item for item in canonical_episodes
    }
    by_season: dict[int, list[dict[str, Any]]] = {}
    for item in canonical_episodes:
        by_season.setdefault(int(item["season"]), []).append(item)

    episode_mappings: list[dict[str, Any]] = []
    for provider_episode in episodes:
        direct = by_number.get((provider_episode.season, provider_episode.episode))
        if direct is not None:
            episode_mappings.append(
                {
                    "provider_season": provider_episode.season,
                    "provider_episode": provider_episode.episode,
                    "tvdb_id": match.tvdb_id,
                    "canonical_season": direct["season"],
                    "canonical_episode": direct["episode"],
                    "confidence": "confirmed",
                    "source": "direct_numbering",
                    "rationale": "season+episode match",
                }
            )
            continue

        candidate_pool = by_season.get(provider_episode.season, canonical_episodes)
        scored: list[tuple[float, dict[str, Any]]] = []
        search_titles = [
            value
            for value in [provider_episode.title_primary, provider_episode.title_secondary]
            if value
        ]
        for candidate in candidate_pool:
            score = max(
                (_score_episode_title(search_title, candidate["title"]) for search_title in search_titles),
                default=0.0,
            )
            if score >= 0.65:
                scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            continue
        top_score = scored[0][0]
        plausible = [
            candidate
            for score, candidate in scored
            if score >= top_score - 0.05
        ]
        confidence = "high_confidence" if top_score >= 0.85 else "low_confidence"
        for candidate in plausible:
            episode_mappings.append(
                {
                    "provider_season": provider_episode.season,
                    "provider_episode": provider_episode.episode,
                    "tvdb_id": match.tvdb_id,
                    "canonical_season": int(candidate["season"]),
                    "canonical_episode": int(candidate["episode"]),
                    "confidence": confidence,
                    "source": "title_match",
                    "rationale": f"title score={top_score:.2f}",
                }
            )

    return CanonicalPayload(
        series=series_payload,
        episodes=canonical_episodes,
        series_mappings=series_mappings,
        episode_mappings=episode_mappings,
    )


def _crawl_aniworld_like_title(
    *,
    provider_key: str,
    slug: str,
    title: str,
    aliases: list[str],
) -> TitleRecord:
    site_cfg = CATALOG_SITE_CONFIGS[provider_key]
    base_url = str(site_cfg["base_url"]).rstrip("/")
    relative_root = (
        f"/anime/stream/{slug}" if provider_key == "aniworld.to" else f"/serie/{slug}"
    )
    url = f"{base_url}{relative_root}"
    if provider_key == "aniworld.to":
        from aniworld.models import AniworldSeries

        series = AniworldSeries(url)
        imdb_id = series.imdb
        mal_id = None
        raw_mal = series.mal_id
        if isinstance(raw_mal, list) and raw_mal:
            try:
                mal_id = int(raw_mal[0])
            except (TypeError, ValueError):
                mal_id = None
    else:
        from aniworld.models import SerienstreamSeries

        series = SerienstreamSeries(url)
        imdb_id = series.imdb
        mal_id = None

    episodes: list[EpisodeRecord] = []
    for season in series.seasons:
        for episode in season.episodes:
            provider_data = getattr(episode.provider_data, "_data", None)
            if provider_data is None:
                provider_data = getattr(episode.provider_data, "data", None)
            episodes.append(
                EpisodeRecord(
                    season=int(getattr(season, "season_number", 0) or 0),
                    episode=int(getattr(episode, "episode_number", 0) or 0),
                    relative_path=_relative_path(episode.url),
                    title_primary=getattr(episode, "title_de", None),
                    title_secondary=getattr(episode, "title_en", None),
                    media_type_hint="movie"
                    if provider_key == "aniworld.to" and getattr(episode, "is_movie", False)
                    else "episode",
                    languages=_normalize_provider_data(provider_data, site=provider_key),
                )
            )

    canonical = _build_tv_canonical_payload(
        provider=provider_key,
        slug=slug,
        title=series.title or title,
        aliases=aliases,
        imdb_id=imdb_id,
        mal_id=mal_id,
        episodes=episodes,
    )
    return TitleRecord(
        provider=provider_key,
        slug=slug,
        title=series.title or title,
        aliases=aliases,
        media_type_hint="series",
        relative_path=relative_root,
        episodes=episodes,
        canonical=canonical,
    )


def _parse_megakino_page_metadata(url: str) -> tuple[str | None, int | None]:
    base_url = get_megakino_base_url().rstrip("/")
    response = http_get(url, timeout=20, headers={"Referer": base_url})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = None
    title_node = soup.find("h1")
    if title_node:
        title = title_node.get_text(" ", strip=True)
    year = None
    for node in soup.find_all(["a", "span", "div"]):
        text = node.get_text(" ", strip=True)
        if text and text.isdigit() and len(text) == 4 and 1900 <= int(text) <= 2100:
            year = int(text)
            break
    return title, year


def crawl_provider_catalog(provider_key: str) -> list[TitleRecord]:
    provider = get_provider(provider_key)
    if provider is None:
        return []

    if provider_key == "megakino":
        client = get_default_megakino_client()
        entries = client.load_index()
        titles: list[TitleRecord] = []
        for entry in entries.values():
            parsed_title = entry.slug.replace("-", " ").title()
            try:
                live_title, _year = _parse_megakino_page_metadata(entry.url)
                if live_title:
                    parsed_title = live_title
            except Exception as exc:
                logger.debug("Megakino metadata fetch failed for {}: {}", entry.url, exc)
            titles.append(
                TitleRecord(
                    provider=provider_key,
                    slug=entry.slug,
                    title=parsed_title,
                    aliases=[],
                    media_type_hint="movie" if entry.kind == "film" else "series",
                    relative_path=_relative_path(entry.url),
                    episodes=[],
                    canonical=CanonicalPayload(),
                )
            )
        return titles

    index = provider.load_or_refresh_index()
    alternatives = provider.load_or_refresh_alternatives()
    workers = int(CATALOG_SITE_CONFIGS[provider_key].get("provider_index_concurrency", 1))
    futures = []
    results: list[TitleRecord] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for slug, title in index.items():
            aliases = list(dict.fromkeys(alternatives.get(slug, []) or [title]))
            futures.append(
                executor.submit(
                    _crawl_aniworld_like_title,
                    provider_key=provider_key,
                    slug=slug,
                    title=title,
                    aliases=aliases,
                )
            )
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item.slug)
    return results
