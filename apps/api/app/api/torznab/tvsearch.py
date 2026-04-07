from __future__ import annotations

from datetime import datetime
import xml.etree.ElementTree as ET

from loguru import logger
from sqlmodel import Session

from app.config import TORZNAB_CAT_ANIME
from app.providers.aniworld.specials import SpecialIds
from app.utils.magnet import _site_prefix

from .helpers import default_languages_for_site, ordered_unique
from .utils import _build_item


def discover_episode_languages_for_fast_season_mode(
    *,
    slug: str,
    season_i: int,
    episode_i: int,
    site_found: str,
) -> list[str]:
    """Discover available languages from provider page metadata."""
    try:
        from app.core.downloader import build_episode
        from app.core.downloader.language import normalize_language
    except Exception as exc:  # pragma: no cover
        logger.debug(
            "Fast season-search language discovery unavailable (slug={} S{}E{}): {}",
            slug,
            season_i,
            episode_i,
            exc,
        )
        return []

    try:
        episode = build_episode(
            slug=slug,
            season=season_i,
            episode=episode_i,
            site=site_found,
        )
    except Exception as exc:
        logger.debug(
            (
                "Fast season-search language discovery failed for slug={} "
                "S{}E{} on {}: {}"
            ),
            slug,
            season_i,
            episode_i,
            site_found,
            exc,
        )
        return []

    raw_values: list[object] = []
    for attr in ("language_name", "languages", "available_languages", "language"):
        value = getattr(episode, attr, None)
        if value is None:
            continue
        if isinstance(value, str):
            raw_values.append(value)
            continue
        try:
            raw_values.extend(list(value))
        except Exception:
            raw_values.append(value)

    discovered: list[str] = []
    for value in raw_values:
        if value is None or isinstance(value, int):
            continue
        text = str(value).strip()
        if not text or text.isdigit():
            continue
        discovered.append(normalize_language(text))

    discovered = ordered_unique(discovered)
    if not discovered:
        return []

    site_defaults = default_languages_for_site(site_found)
    prioritized = [lang for lang in site_defaults if lang in discovered]
    prioritized.extend([lang for lang in discovered if lang not in prioritized])
    logger.debug(
        "Fast season-search discovered languages for slug={} S{}E{} on {}: {}",
        slug,
        season_i,
        episode_i,
        site_found,
        prioritized,
    )
    return prioritized


def probe_episode_available_for_discovery(
    *,
    tn_module,
    session: Session,
    slug: str,
    season_i: int,
    episode_i: int,
    site_found: str,
) -> bool:
    """Determine whether an episode is available in any candidate language."""
    cached_langs = tn_module.list_available_languages_cached(
        session,
        slug=slug,
        season=season_i,
        episode=episode_i,
        site=site_found,
    )
    candidate_langs = cached_langs or default_languages_for_site(site_found)
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
        except ValueError, RuntimeError:
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
        except ValueError, RuntimeError:
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
        except ValueError, RuntimeError:
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
    metadata_episode_numbers_for_season,
    probe_episode_available_for_discovery_fn,
    max_episodes: int,
    max_consecutive_misses: int,
    allow_fallback_probe: bool = True,
) -> list[int]:
    """Resolve season episode numbers via metadata, cache, and probing."""
    metadata_episodes = metadata_episode_numbers_for_season(
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
        discovery_sources: list[str] = []
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

    if not allow_fallback_probe:
        logger.info(
            (
                "tvsearch season discovery source=fallback-probe skipped "
                "slug={} season={} reason=fast-mode"
            ),
            slug,
            season_i,
        )
        return []

    discovered: list[int] = []
    consecutive_misses = 0
    termination = "max episodes"
    for episode_i in range(1, max_episodes + 1):
        if probe_episode_available_for_discovery_fn(
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
        if consecutive_misses >= max_consecutive_misses:
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
        max_episodes,
        max_consecutive_misses,
    )
    return discovered


def try_mapped_special_probe(
    *,
    tn_module,
    session: Session,
    slug: str,
    lang: str,
    site_found: str,
    special_map,
) -> tuple[bool, int | None, str | None, str | None, int, int, int, int]:
    """Probe a mapped special target episode, reusing cache when available."""
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
    except ValueError, RuntimeError:
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
    except (ValueError, RuntimeError) as exc:
        logger.error(
            "Error probing mapped special quality for slug={}, S{}E{}, lang={}, site={}: {}",
            slug,
            source_season,
            source_episode,
            lang,
            site_found,
            exc,
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
    max_items: int | None,
    discover_episode_languages_for_fast_season_mode_fn,
    try_mapped_special_probe_fn,
    resolve_special_mapping_from_episode_request_fn,
    specials_metadata_enabled: bool,
    strm_files_mode: str,
    allow_live_probe: bool = True,
    fast_episode_languages: list[str] | None = None,
) -> tuple[int, bool]:
    """Emit RSS items for a requested tvsearch season/episode pair."""
    cached_langs = tn_module.list_available_languages_cached(
        session,
        slug=slug,
        season=request_season,
        episode=request_episode,
        site=site_found,
    )
    discovered_fast_languages = fast_episode_languages
    if not allow_live_probe and not cached_langs and not discovered_fast_languages:
        discovered_fast_languages = discover_episode_languages_for_fast_season_mode_fn(
            slug=slug,
            season_i=request_season,
            episode_i=request_episode,
            site_found=site_found,
        )
    default_langs = default_languages_for_site(site_found)
    if discovered_fast_languages:
        candidate_langs = ordered_unique(discovered_fast_languages + cached_langs)
    else:
        candidate_langs = cached_langs or default_langs
    logger.debug(
        "Candidate languages for slug='{}' season={} episode={} site='{}': {}",
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
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Error reading availability cache for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                source_season,
                source_episode,
                lang,
                site_found,
                exc,
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
            if not allow_live_probe:
                if rec and rec.available:
                    available = True
                    height = rec.height
                    vcodec = rec.vcodec
                    prov_used = rec.provider
                elif discovered_fast_languages and lang in discovered_fast_languages:
                    available = True
                else:
                    available = False
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
                except (ValueError, RuntimeError) as exc:
                    logger.error(
                        "Error probing quality for slug={}, S{}E{}, lang={}, site={}: {}",
                        slug,
                        source_season,
                        source_episode,
                        lang,
                        site_found,
                        exc,
                    )
                    available = False

                if (
                    not available
                    and specials_metadata_enabled
                    and site_found == "aniworld.to"
                ):
                    if not special_map_attempted:
                        special_map_attempted = True
                        special_map = resolve_special_mapping_from_episode_request_fn(
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
                        ) = try_mapped_special_probe_fn(
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
                except (ValueError, RuntimeError) as exc:
                    logger.error(
                        "Error upserting availability for slug={}, S{}E{}, lang={}, site={}: {}",
                        slug,
                        source_season,
                        source_episode,
                        lang,
                        site_found,
                        exc,
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
        except Exception as exc:
            logger.error(
                "Error building magnet for release '{}': {}", release_title, exc
            )
            continue

        prefix = _site_prefix(site_found)
        guid_base = f"{prefix}:{slug}:s{source_season}e{source_episode}:{lang}"
        if (alias_season, alias_episode) != (source_season, source_episode):
            guid_base = f"{guid_base}:alias-s{alias_season}e{alias_episode}"

        try:
            if strm_files_mode in ("no", "both"):
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
            if strm_files_mode in ("only", "both"):
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
        except (ValueError, RuntimeError, KeyError) as exc:
            logger.error(
                "Error building RSS item for release '{}': {}", release_title, exc
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
