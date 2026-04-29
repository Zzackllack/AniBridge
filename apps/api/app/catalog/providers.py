from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.catalog.metadata import resolve_tv_canonical_match
from app.config import CATALOG_SITE_CONFIGS
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


@dataclass(slots=True)
class CatalogCrawlObserver:
    on_index_loaded: Callable[[int], None] | None = None
    on_title_started: Callable[[str], None] | None = None
    on_title_crawled: Callable[[str], None] | None = None
    on_title_failed: Callable[[str, str], None] | None = None


@dataclass(slots=True)
class CatalogStreamSummary:
    discovered_titles: int = 0
    crawled_titles: int = 0
    failed_titles: int = 0


def _relative_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _run_with_timeout(
    timeout_seconds: float, func: Callable[..., Any], *args, **kwargs
):
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=max(0.001, timeout_seconds))
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"title crawl exceeded {int(timeout_seconds)}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _normalize_provider_data(raw: Any, *, site: str) -> list[EpisodeLanguageRecord]:
    if not isinstance(raw, dict):
        return []
    languages: list[EpisodeLanguageRecord] = []
    for key, provider_map in raw.items():
        if site == "aniworld.to":
            audio = (
                getattr(key[0], "value", str(key[0])) if isinstance(key, tuple) else ""
            )
            subtitles = (
                getattr(key[1], "value", str(key[1]))
                if isinstance(key, tuple) and len(key) > 1
                else ""
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
        languages.append(
            EpisodeLanguageRecord(language=language, host_hints=host_hints)
        )
    languages.sort(key=lambda entry: entry.language)
    return languages


def _dedupe_languages(
    languages: list[EpisodeLanguageRecord],
) -> list[EpisodeLanguageRecord]:
    deduped: dict[str, set[str]] = {}
    for item in languages:
        bucket = deduped.setdefault(item.language, set())
        bucket.update(item.host_hints)
    return [
        EpisodeLanguageRecord(language=language, host_hints=sorted(host_hints))
        for language, host_hints in sorted(deduped.items())
    ]


def _aniworld_languages_from_flags(
    host_hints: list[str], row: BeautifulSoup
) -> list[EpisodeLanguageRecord]:
    languages: list[EpisodeLanguageRecord] = []
    for image in row.select("td.editFunctions img.flag"):
        src = str(image.get("src") or "").lower()
        title = str(image.get("title") or "").lower()
        alt = str(image.get("alt") or "").lower()
        text = " ".join([src, title, alt])
        if "japanese-german" in text or "deutsch" in text and "untertitel" in text:
            languages.append(
                EpisodeLanguageRecord(
                    language="German Sub",
                    host_hints=host_hints,
                )
            )
        elif "japanese-english" in text or "englisch" in text:
            languages.append(
                EpisodeLanguageRecord(
                    language="English Sub",
                    host_hints=host_hints,
                )
            )
        elif (
            "german.svg" in src
            or "deutsche sprache" in text
            or "deutsch/german" in text
        ):
            languages.append(
                EpisodeLanguageRecord(
                    language="German Dub",
                    host_hints=host_hints,
                )
            )
    return _dedupe_languages(languages)


def _host_hints_from_row(row: BeautifulSoup) -> list[str]:
    names: list[str] = []
    for icon in row.select("i.icon"):
        classes = [cls for cls in icon.get("class", []) if cls != "icon"]
        if classes:
            names.append(str(classes[-1]))
            continue
        title = str(icon.get("title") or "").strip()
        if title:
            names.append(title.replace("Hoster ", "").strip())
    return sorted(dict.fromkeys(name for name in names if name))


def _parse_aniworld_season_rows(season) -> list[EpisodeRecord]:
    soup = BeautifulSoup(season._html, "html.parser")
    episodes: list[EpisodeRecord] = []
    for row in soup.select('tr[itemtype="http://schema.org/Episode"]'):
        link = row.select_one('a[itemprop="url"]')
        if link is None:
            continue
        href = str(link.get("href") or "").strip()
        if not href:
            continue
        relative_path = _relative_path(href)
        episode_number = 0
        number_meta = row.select_one('meta[itemprop="episodeNumber"]')
        if number_meta is not None:
            content = str(number_meta.get("content") or "").strip()
            if content.isdigit():
                episode_number = int(content)
        if episode_number <= 0:
            match = re.search(r"(?:episode|film)-(\d+)", href)
            if match:
                episode_number = int(match.group(1))
        if episode_number <= 0:
            continue
        title_primary = None
        title_secondary = None
        title_cell = row.select_one("td.seasonEpisodeTitle")
        if title_cell is not None:
            strong = title_cell.select_one("strong")
            span = title_cell.select_one("span")
            title_primary = (
                strong.get_text(" ", strip=True) if strong is not None else None
            )
            title_secondary = (
                span.get_text(" ", strip=True) if span is not None else None
            )
        host_hints = _host_hints_from_row(row)
        languages = _aniworld_languages_from_flags(host_hints, row)
        episodes.append(
            EpisodeRecord(
                season=int(getattr(season, "season_number", 0) or 0),
                episode=episode_number,
                relative_path=relative_path,
                title_primary=title_primary,
                title_secondary=title_secondary,
                media_type_hint="movie"
                if getattr(season, "are_movies", False)
                else "episode",
                languages=languages,
            )
        )
    return episodes


def _parse_sto_season_rows(season) -> list[EpisodeRecord]:
    html = season._html
    season_number = int(getattr(season, "season_number", 0) or 0)
    pattern = re.compile(
        r'href="(?P<href>(?:https?://(?:serienstream|s)\.to)?/serie/[^"\s]+/staffel-'
        + str(season_number)
        + r"/episode-(?P<episode>\d+))/?\""
    )
    episodes: list[EpisodeRecord] = []
    seen: set[tuple[int, str]] = set()
    for match in pattern.finditer(html):
        episode_number = int(match.group("episode"))
        href = match.group("href")
        relative_path = _relative_path(href)
        key = (episode_number, relative_path)
        if key in seen:
            continue
        seen.add(key)
        episodes.append(
            EpisodeRecord(
                season=season_number,
                episode=episode_number,
                relative_path=relative_path,
                title_primary=None,
                title_secondary=None,
                media_type_hint="episode",
                languages=[],
            )
        )
    return episodes


def _score_episode_title(left: str, right: str) -> float:
    from app.db import normalize_catalog_text

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
        if (
            not isinstance(season_number, int)
            or not isinstance(episode_number, int)
            or not episode_title
        ):
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
        "tmdb_id": payload.get("tmdbId")
        if isinstance(payload.get("tmdbId"), int)
        else None,
        "imdb_id": imdb_id or str(payload.get("imdbId") or "").strip() or None,
        "tvmaze_id": payload.get("tvMazeId")
        if isinstance(payload.get("tvMazeId"), int)
        else None,
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

    by_number = {(item["season"], item["episode"]): item for item in canonical_episodes}
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
            for value in [
                provider_episode.title_primary,
                provider_episode.title_secondary,
            ]
            if value
        ]
        for candidate in candidate_pool:
            score = max(
                (
                    _score_episode_title(search_title, candidate["title"])
                    for search_title in search_titles
                ),
                default=0.0,
            )
            if score >= 0.65:
                scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            continue
        top_score = scored[0][0]
        plausible = [
            candidate for score, candidate in scored if score >= top_score - 0.05
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


def _fallback_title_record(
    *,
    provider_key: str,
    slug: str,
    title: str,
    aliases: list[str],
) -> TitleRecord:
    media_type_hint = "movie" if provider_key == "megakino" else "series"
    if provider_key == "aniworld.to":
        relative_path = f"/anime/stream/{slug}"
    elif provider_key == "s.to":
        relative_path = f"/serie/{slug}"
    else:
        relative_path = f"/{slug}"
    return TitleRecord(
        provider=provider_key,
        slug=slug,
        title=title,
        aliases=aliases,
        media_type_hint=media_type_hint,
        relative_path=relative_path,
        episodes=[],
        canonical=CanonicalPayload(),
    )


def load_provider_title_index(
    provider_key: str,
    *,
    observer: CatalogCrawlObserver | None = None,
) -> list[TitleRecord]:
    provider = get_provider(provider_key)
    if provider is None:
        return []

    if provider_key == "megakino":
        client = get_default_megakino_client()
        entries = client.load_index()
        if observer is not None and observer.on_index_loaded is not None:
            observer.on_index_loaded(len(entries))
        rows = [
            TitleRecord(
                provider=provider_key,
                slug=entry.slug,
                title=entry.slug.replace("-", " ").title(),
                aliases=[],
                media_type_hint="movie" if entry.kind == "film" else "series",
                relative_path=_relative_path(entry.url),
                episodes=[],
                canonical=CanonicalPayload(),
            )
            for entry in entries.values()
        ]
        rows.sort(key=lambda item: item.slug)
        return rows

    logger.info("Provider catalog {}: loading title index", provider_key)
    index = provider.load_or_refresh_index()
    alternatives = provider.load_or_refresh_alternatives()
    if observer is not None and observer.on_index_loaded is not None:
        observer.on_index_loaded(len(index))
    rows = []
    for slug, title in index.items():
        aliases = list(dict.fromkeys(alternatives.get(slug, []) or [title]))
        rows.append(
            _fallback_title_record(
                provider_key=provider_key,
                slug=slug,
                title=title,
                aliases=aliases,
            )
        )
    rows.sort(key=lambda item: item.slug)
    return rows


def _crawl_aniworld_like_detail(
    *,
    provider_key: str,
    slug: str,
    title: str,
    aliases: list[str],
) -> TitleRecord:
    base_url = str(CATALOG_SITE_CONFIGS[provider_key]["base_url"]).rstrip("/")
    if provider_key == "aniworld.to":
        from aniworld.models import AniworldSeries

        relative_root = f"/anime/stream/{slug}"
        series = AniworldSeries(f"{base_url}{relative_root}")
    else:
        from aniworld.models import SerienstreamSeries

        relative_root = f"/serie/{slug}"
        series = SerienstreamSeries(f"{base_url}{relative_root}")

    episodes: list[EpisodeRecord] = []
    for season in series.seasons:
        if provider_key == "aniworld.to":
            episodes.extend(_parse_aniworld_season_rows(season))
        else:
            episodes.extend(_parse_sto_season_rows(season))

    return TitleRecord(
        provider=provider_key,
        slug=slug,
        title=series.title or title,
        aliases=aliases,
        media_type_hint="series",
        relative_path=relative_root,
        episodes=episodes,
        canonical=CanonicalPayload(),
    )


def crawl_provider_title_detail(
    *,
    provider_key: str,
    slug: str,
    title: str,
    aliases: list[str],
    timeout_seconds: float,
) -> TitleRecord:
    if provider_key == "megakino":
        return _fallback_title_record(
            provider_key=provider_key,
            slug=slug,
            title=title,
            aliases=aliases,
        )
    return _run_with_timeout(
        timeout_seconds,
        _crawl_aniworld_like_detail,
        provider_key=provider_key,
        slug=slug,
        title=title,
        aliases=aliases,
    )


def resolve_provider_canonical(
    *,
    provider_key: str,
    slug: str,
    title: str,
    aliases: list[str],
    media_type_hint: str,
    episodes: list[EpisodeRecord],
    imdb_id: Optional[str] = None,
    mal_id: Optional[int] = None,
) -> CanonicalPayload:
    if provider_key == "megakino" or media_type_hint == "movie":
        return CanonicalPayload()
    return _build_tv_canonical_payload(
        provider=provider_key,
        slug=slug,
        title=title,
        aliases=aliases,
        imdb_id=imdb_id,
        mal_id=mal_id,
        episodes=episodes,
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


def crawl_provider_catalog(
    provider_key: str,
    *,
    observer: CatalogCrawlObserver | None = None,
) -> list[TitleRecord]:
    rows = load_provider_title_index(provider_key, observer=observer)
    for row in rows:
        if observer is not None and observer.on_title_crawled is not None:
            observer.on_title_crawled(row.slug)
    return rows
