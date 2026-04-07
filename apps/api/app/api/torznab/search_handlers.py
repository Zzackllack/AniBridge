from __future__ import annotations

from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from loguru import logger
from sqlmodel import Session

from app.providers.aniworld.specials import SpecialIds
from app.utils.magnet import _site_prefix
from app.utils.movie_year import get_movie_year

from .helpers import default_languages_for_site
from .utils import _build_item


def handle_preview_search(
    session: Session,
    q_str: str,
    channel: ET.Element,
    cat_id: int,
    *,
    site: str | None = None,
    limit: int | None = None,
    strm_suffix: str = " [STRM]",
    anibridge_test_mode: bool,
    strm_files_mode: str,
) -> int:
    """Populate preview search results using the first episode as a probe target."""
    import app.api.torznab as tn

    q_str = (q_str or "").strip()
    if not q_str or anibridge_test_mode:
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

    season_i = 1
    episode_i = 1
    cached_langs = tn.list_available_languages_cached(
        session,
        slug=slug,
        season=season_i,
        episode=episode_i,
        site=site_found,
    )
    candidate_langs = cached_langs or default_languages_for_site(site_found)
    now = datetime.now(timezone.utc)
    count = 0

    for lang in candidate_langs:
        try:
            available, height, vcodec, provider, _info = tn.probe_episode_quality(
                slug=slug,
                season=season_i,
                episode=episode_i,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Error probing preview quality for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                season_i,
                episode_i,
                lang,
                site_found,
                exc,
            )
            continue

        try:
            tn.upsert_availability(
                session,
                slug=slug,
                season=season_i,
                episode=episode_i,
                language=lang,
                available=available,
                height=height,
                vcodec=vcodec,
                provider=provider,
                extra=None,
                site=site_found,
            )
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Error upserting preview availability for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                season_i,
                episode_i,
                lang,
                site_found,
                exc,
            )
        if not available:
            continue

        release_title = tn.build_release_name(
            series_title=display_title,
            season=None,
            episode=None,
            height=height,
            vcodec=vcodec,
            language=lang,
            site=site_found,
        )
        try:
            magnet = tn.build_magnet(
                title=release_title,
                slug=slug,
                season=season_i,
                episode=episode_i,
                language=lang,
                provider=provider,
                site=site_found,
            )
        except (ValueError, RuntimeError, KeyError) as exc:
            logger.error(
                "Error building magnet for release '{}': {}", release_title, exc
            )
            continue

        prefix = _site_prefix(site_found)
        guid_base = f"{prefix}:{slug}:s{season_i}e{episode_i}:{lang}"
        try:
            if strm_files_mode in ("no", "both"):
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=guid_base,
                    language=lang,
                )
            if strm_files_mode in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=slug,
                    season=season_i,
                    episode=episode_i,
                    language=lang,
                    provider=provider,
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
        except (ValueError, RuntimeError, KeyError) as exc:
            logger.error(
                "Error building RSS item for release '{}': {}", release_title, exc
            )
            continue

        count += 1
        if limit is not None and count >= max(1, int(limit)):
            break

    return count


def handle_special_search(
    session: Session,
    q_str: str,
    channel: ET.Element,
    cat_id: int,
    *,
    ids: SpecialIds,
    limit: int | None = None,
    strm_suffix: str = " [STRM]",
    anibridge_test_mode: bool,
    specials_metadata_enabled: bool,
    strm_files_mode: str,
    resolve_special_mapping_from_query_fn,
) -> int:
    """Generate title-only search results for special episode aliases."""
    import app.api.torznab as tn

    q_str = (q_str or "").strip()
    if not q_str or anibridge_test_mode or not specials_metadata_enabled:
        return 0

    result = tn._slug_from_query(q_str)
    if not result:
        return 0

    site_found, slug = result
    if site_found != "aniworld.to":
        return 0

    display_title = tn.resolve_series_title(slug, site_found) or q_str
    mapping = resolve_special_mapping_from_query_fn(
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
    candidate_langs = cached_langs or default_languages_for_site(site_found)
    now = datetime.now(timezone.utc)
    count = 0

    for lang in candidate_langs:
        try:
            available, height, vcodec, provider, _info = tn.probe_episode_quality(
                slug=slug,
                season=target_season,
                episode=target_episode,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Error probing mapped special quality for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                target_season,
                target_episode,
                lang,
                site_found,
                exc,
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
                height=height,
                vcodec=vcodec,
                provider=provider,
                extra={
                    "special_alias_season": alias_season,
                    "special_alias_episode": alias_episode,
                },
                site=site_found,
            )
        except (ValueError, RuntimeError) as exc:
            logger.error(
                "Error upserting mapped special availability for slug={}, S{}E{}, lang={}, site={}: {}",
                slug,
                target_season,
                target_episode,
                lang,
                site_found,
                exc,
            )
        if not available:
            continue

        release_title = tn.build_release_name(
            series_title=display_title,
            season=alias_season,
            episode=alias_episode,
            height=height,
            vcodec=vcodec,
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
                provider=provider,
                site=site_found,
            )
        except (ValueError, RuntimeError, KeyError) as exc:
            logger.error(
                "Error building magnet for mapped special '{}': {}",
                release_title,
                exc,
            )
            continue

        prefix = _site_prefix(site_found)
        guid_base = (
            f"{prefix}:{slug}:s{target_season}e{target_episode}:{lang}"
            f":alias-s{alias_season}e{alias_episode}"
        )
        try:
            if strm_files_mode in ("no", "both"):
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=guid_base,
                    language=lang,
                )
            if strm_files_mode in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=slug,
                    season=target_season,
                    episode=target_episode,
                    language=lang,
                    provider=provider,
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
        except (ValueError, RuntimeError, KeyError) as exc:
            logger.error(
                "Error building RSS item for mapped special '{}': {}",
                release_title,
                exc,
            )
            continue

        count += 1
        if limit is not None and count >= max(1, int(limit)):
            break

    return count
