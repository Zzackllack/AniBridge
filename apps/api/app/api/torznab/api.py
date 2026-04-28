from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import xml.etree.ElementTree as ET

from fastapi import Depends, Query, Request, Response
from fastapi.responses import Response as FastAPIResponse
from loguru import logger
from sqlmodel import Session

from app.catalog import require_catalog_ready
from app.catalog.exceptions import CatalogNotReadyError
from app.config import (
    ANIBRIDGE_TEST_MODE,
    CATALOG_SITES_LIST,
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
from app.db import (
    find_canonical_series_by_ids_or_title,
    find_provider_episode_mapping,
    find_provider_episode_mappings_for_canonical_episode,
    find_provider_episode_mappings_for_canonical_season,
    get_indexed_episode_languages,
    get_session,
    list_indexed_provider_episodes,
    resolve_indexed_title,
    search_indexed_provider_titles,
)
from app.providers.aniworld.specials import (
    SpecialIds,
    resolve_special_mapping_from_episode_request,
    resolve_special_mapping_from_query,
)
from . import router
from .helpers import (
    coerce_non_negative_int as _coerce_non_negative_int_impl,
    coerce_positive_int as _coerce_positive_int_impl,
    default_languages_for_site as _default_languages_for_site_impl,
    ordered_unique as _ordered_unique_impl,
)
from .search_handlers import (
    handle_preview_search as _handle_preview_search_impl,
    handle_special_search as _handle_special_search_impl,
)
from .skyhook import (
    metadata_episode_numbers_for_season as _metadata_episode_numbers_for_season_impl,
    resolve_tvsearch_query_from_ids as _resolve_tvsearch_query_from_ids_impl,
)
from .tvsearch import (
    discover_episode_languages_for_fast_season_mode as _discover_episode_languages_for_fast_season_mode_impl,
    emit_tvsearch_episode_items as emit_tvsearch_episode_items_impl,
    probe_episode_available_for_discovery as _probe_episode_available_for_discovery_impl,
    resolve_season_episode_numbers as resolve_season_episode_numbers_impl,
    try_mapped_special_probe as _try_mapped_special_probe_impl,
)
from .utils import _build_item, _caps_xml, _require_apikey, _rss_root


def _default_languages_for_site(site: str) -> list[str]:
    """Return configured default languages for a catalogue site."""
    return _default_languages_for_site_impl(site)


def _coerce_positive_int(value: object) -> Optional[int]:
    """Coerce a value into a positive integer."""
    return _coerce_positive_int_impl(value)


def _coerce_non_negative_int(value: object) -> Optional[int]:
    """Coerce a value into a non-negative integer."""
    return _coerce_non_negative_int_impl(value)


def _ordered_unique(values: list[str]) -> list[str]:
    """Return unique non-empty strings while preserving order."""
    return _ordered_unique_impl(values)


def _resolve_tvsearch_query_from_ids(
    *,
    tvdbid: Optional[int],
    tmdbid: Optional[int],
    imdbid: Optional[str],
) -> Optional[str]:
    """Resolve a canonical tvsearch query from identifier hints."""
    return _resolve_tvsearch_query_from_ids_impl(
        tvdbid=tvdbid,
        tmdbid=tmdbid,
        imdbid=imdbid,
    )


def _metadata_episode_numbers_for_season(
    *,
    q_str: str,
    season_i: int,
    ids: SpecialIds,
) -> list[int]:
    """Resolve season episode numbers from SkyHook metadata."""
    return _metadata_episode_numbers_for_season_impl(
        q_str=q_str,
        season_i=season_i,
        ids=ids,
    )


def _discover_episode_languages_for_fast_season_mode(
    *,
    slug: str,
    season_i: int,
    episode_i: int,
    site_found: str,
) -> list[str]:
    """Discover languages from provider metadata for fast season search."""
    return _discover_episode_languages_for_fast_season_mode_impl(
        slug=slug,
        season_i=season_i,
        episode_i=episode_i,
        site_found=site_found,
    )


def _probe_episode_available_for_discovery(
    *,
    tn_module,
    session: Session,
    slug: str,
    season_i: int,
    episode_i: int,
    site_found: str,
) -> bool:
    """Probe whether an episode exists for season discovery."""
    return _probe_episode_available_for_discovery_impl(
        tn_module=tn_module,
        session=session,
        slug=slug,
        season_i=season_i,
        episode_i=episode_i,
        site_found=site_found,
    )


def resolve_season_episode_numbers(
    *,
    tn_module,
    session: Session,
    slug: str,
    season_i: int,
    site_found: str,
    q_str: str,
    ids: SpecialIds,
    allow_fallback_probe: bool = True,
) -> list[int]:
    """Resolve season episode numbers for tvsearch."""
    return resolve_season_episode_numbers_impl(
        tn_module=tn_module,
        session=session,
        slug=slug,
        season_i=season_i,
        site_found=site_found,
        q_str=q_str,
        ids=ids,
        metadata_episode_numbers_for_season=_metadata_episode_numbers_for_season,
        probe_episode_available_for_discovery_fn=(
            _probe_episode_available_for_discovery
        ),
        max_episodes=TORZNAB_SEASON_SEARCH_MAX_EPISODES,
        max_consecutive_misses=TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES,
        allow_fallback_probe=allow_fallback_probe,
    )


def _try_mapped_special_probe(
    *,
    tn_module,
    session: Session,
    slug: str,
    lang: str,
    site_found: str,
    special_map,
) -> tuple[bool, Optional[int], Optional[str], Optional[str], int, int, int, int]:
    """Probe a mapped AniWorld special source episode."""
    return _try_mapped_special_probe_impl(
        tn_module=tn_module,
        session=session,
        slug=slug,
        lang=lang,
        site_found=site_found,
        special_map=special_map,
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
    allow_live_probe: bool = True,
    fast_episode_languages: Optional[list[str]] = None,
) -> tuple[int, bool]:
    """Emit tvsearch RSS items for one requested season/episode pair."""
    return emit_tvsearch_episode_items_impl(
        tn_module=tn_module,
        session=session,
        channel=channel,
        slug=slug,
        site_found=site_found,
        display_title=display_title,
        q_str=q_str,
        request_season=request_season,
        request_episode=request_episode,
        ids=ids,
        now=now,
        strm_suffix=strm_suffix,
        max_items=max_items,
        discover_episode_languages_for_fast_season_mode_fn=(
            _discover_episode_languages_for_fast_season_mode
        ),
        try_mapped_special_probe_fn=_try_mapped_special_probe,
        resolve_special_mapping_from_episode_request_fn=(
            resolve_special_mapping_from_episode_request
        ),
        specials_metadata_enabled=SPECIALS_METADATA_ENABLED,
        strm_files_mode=STRM_FILES_MODE,
        allow_live_probe=allow_live_probe,
        fast_episode_languages=fast_episode_languages,
    )


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
    """Populate preview search results for a generic search query."""
    return _handle_preview_search_impl(
        session,
        q_str,
        channel,
        cat_id,
        site=site,
        limit=limit,
        strm_suffix=strm_suffix,
        anibridge_test_mode=ANIBRIDGE_TEST_MODE,
        strm_files_mode=STRM_FILES_MODE,
    )


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
    """Populate search results for metadata-backed AniWorld specials."""
    return _handle_special_search_impl(
        session,
        q_str,
        channel,
        cat_id,
        ids=ids,
        limit=limit,
        strm_suffix=strm_suffix,
        anibridge_test_mode=ANIBRIDGE_TEST_MODE,
        specials_metadata_enabled=SPECIALS_METADATA_ENABLED,
        strm_files_mode=STRM_FILES_MODE,
        resolve_special_mapping_from_query_fn=resolve_special_mapping_from_query,
    )


def _emit_test_result(
    *,
    tn_module,
    channel: ET.Element,
    cat_id: int,
    strm_suffix: str,
) -> None:
    """Emit the configured synthetic Torznab test result."""
    release_title = TORZNAB_TEST_TITLE
    guid_base = (
        f"aw:{TORZNAB_TEST_SLUG}:"
        f"s{TORZNAB_TEST_SEASON}e{TORZNAB_TEST_EPISODE}:{TORZNAB_TEST_LANGUAGE}"
    )
    now = datetime.now(timezone.utc)

    if STRM_FILES_MODE in ("no", "both"):
        magnet = tn_module.build_magnet(
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
        magnet_strm = tn_module.build_magnet(
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


def _empty_rss_response() -> Response:
    """Return an empty RSS response."""
    rss, _channel = _rss_root()
    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


def _rss_response(rss: ET.Element) -> Response:
    """Serialize an RSS element tree into a FastAPI response."""
    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")


def _indexed_preview_results(
    *,
    tn_module,
    session: Session,
    q_str: str,
    channel: ET.Element,
    cat_id: int,
    providers: list[str],
    limit: int,
    strm_suffix: str,
) -> int:
    rows = search_indexed_provider_titles(
        session,
        query=q_str,
        providers=providers,
        limit=max(1, limit),
    )
    now = datetime.now(timezone.utc)
    count = 0
    for row in rows:
        provider = row.provider
        title = row.title
        episodes = list_indexed_provider_episodes(
            session,
            provider=provider,
            slug=row.slug,
        )
        if episodes:
            target = sorted(episodes, key=lambda item: (item.season, item.episode))[0]
            mapping = find_provider_episode_mapping(
                session,
                provider=provider,
                slug=row.slug,
                provider_season=target.season,
                provider_episode=target.episode,
            )
            languages = get_indexed_episode_languages(
                session,
                provider=provider,
                slug=row.slug,
                season=target.season,
                episode=target.episode,
            )
            language_values = [item.language for item in languages] or _default_languages_for_site(provider)
            season_i = mapping.canonical_season if mapping is not None else target.season
            episode_i = mapping.canonical_episode if mapping is not None else target.episode
            provider_season_i = target.season
            provider_episode_i = target.episode
        else:
            language_values = _default_languages_for_site(provider)
            season_i = 1
            episode_i = 1
            provider_season_i = 1
            provider_episode_i = 1
        for language in language_values:
            release_title = tn_module.build_release_name(
                series_title=title,
                season=None if cat_id == TORZNAB_CAT_MOVIE else season_i,
                episode=None if cat_id == TORZNAB_CAT_MOVIE else episode_i,
                height=None,
                vcodec=None,
                language=language,
                site=provider,
            )
            magnet = tn_module.build_magnet(
                title=release_title,
                slug=row.slug,
                season=provider_season_i,
                episode=provider_episode_i,
                language=language,
                provider=None,
                site=provider,
            )
            _build_item(
                channel=channel,
                title=release_title,
                magnet=magnet,
                pubdate=now,
                cat_id=cat_id,
                guid_str=f"{provider}:{row.slug}:{season_i}:{episode_i}:{language}",
                language=language,
            )
            count += 1
            if count >= max(1, limit):
                return count
            if STRM_FILES_MODE in ("only", "both"):
                magnet_strm = tn_module.build_magnet(
                    title=release_title + strm_suffix,
                    slug=row.slug,
                    season=provider_season_i,
                    episode=provider_episode_i,
                    language=language,
                    provider=None,
                    site=provider,
                    mode="strm",
                )
                _build_item(
                    channel=channel,
                    title=release_title + strm_suffix,
                    magnet=magnet_strm,
                    pubdate=now,
                    cat_id=cat_id,
                    guid_str=f"{provider}:{row.slug}:{season_i}:{episode_i}:{language}:strm",
                    language=language,
                )
                count += 1
            if count >= max(1, limit):
                return count
    return count


def _emit_indexed_mapped_episode(
    *,
    tn_module,
    session: Session,
    channel: ET.Element,
    provider: str,
    slug: str,
    title: str,
    canonical_season: int,
    canonical_episode: int,
    provider_season: int,
    provider_episode: int,
    cat_id: int,
    now: datetime,
    strm_suffix: str,
    max_items: int,
) -> int:
    languages = get_indexed_episode_languages(
        session,
        provider=provider,
        slug=slug,
        season=provider_season,
        episode=provider_episode,
    )
    emitted = 0
    for language_row in languages or []:
        release_title = tn_module.build_release_name(
            series_title=title,
            season=canonical_season,
            episode=canonical_episode,
            height=None,
            vcodec=None,
            language=language_row.language,
            site=provider,
        )
        magnet = tn_module.build_magnet(
            title=release_title,
            slug=slug,
            season=provider_season,
            episode=provider_episode,
            language=language_row.language,
            provider=None,
            site=provider,
        )
        _build_item(
            channel=channel,
            title=release_title,
            magnet=magnet,
            pubdate=now,
            cat_id=cat_id,
            guid_str=f"{provider}:{slug}:S{canonical_season}E{canonical_episode}:{language_row.language}",
            language=language_row.language,
        )
        emitted += 1
        if emitted >= max_items:
            return emitted
        if STRM_FILES_MODE in ("only", "both"):
            magnet_strm = tn_module.build_magnet(
                title=release_title + strm_suffix,
                slug=slug,
                season=provider_season,
                episode=provider_episode,
                language=language_row.language,
                provider=None,
                site=provider,
                mode="strm",
            )
            _build_item(
                channel=channel,
                title=release_title + strm_suffix,
                magnet=magnet_strm,
                pubdate=now,
                cat_id=cat_id,
                guid_str=f"{provider}:{slug}:S{canonical_season}E{canonical_episode}:{language_row.language}:strm",
                language=language_row.language,
            )
            emitted += 1
        if emitted >= max_items:
            return emitted
    return emitted


def _indexed_display_title(
    *,
    session: Session,
    provider: str,
    slug: str,
    fallback_title: str,
) -> str:
    title = resolve_indexed_title(session, provider=provider, slug=slug)
    if title:
        return title
    return fallback_title


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
    """Handle Torznab API requests and return XML or RSS responses."""
    _ = (request, offset)
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

    if t == "caps":
        return Response(
            content=_caps_xml(),
            media_type="application/xml; charset=utf-8",
        )

    if t == "search":
        import app.api.torznab as tn

        try:
            require_catalog_ready()
        except CatalogNotReadyError as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail=str(exc)) from exc

        rss, channel = _rss_root()
        q_str = (q or "").strip()
        strm_suffix = " [STRM]"
        cat_id = TORZNAB_CAT_ANIME
        movie_preferred = False
        if cat:
            cat_list = [value.strip() for value in str(cat).split(",") if value.strip()]
            if str(TORZNAB_CAT_MOVIE) in cat_list:
                cat_id = TORZNAB_CAT_MOVIE
                movie_preferred = True

        if not q_str and TORZNAB_RETURN_TEST_RESULT:
            _emit_test_result(
                tn_module=tn,
                channel=channel,
                cat_id=cat_id,
                strm_suffix=strm_suffix,
            )
            return _rss_response(rss)

        if not q_str:
            return _rss_response(rss)

        if movie_preferred:
            count = _indexed_preview_results(
                tn_module=tn,
                session=session,
                q_str=q_str,
                channel=channel,
                cat_id=TORZNAB_CAT_MOVIE,
                providers=["megakino"],
                limit=limit,
                strm_suffix=strm_suffix,
            )
            if count == 0:
                _indexed_preview_results(
                    tn_module=tn,
                    session=session,
                    q_str=q_str,
                    channel=channel,
                    cat_id=TORZNAB_CAT_ANIME,
                    providers=[site for site in CATALOG_SITES_LIST if site != "megakino"],
                    limit=limit,
                    strm_suffix=strm_suffix,
                )
            return _rss_response(rss)

        _indexed_preview_results(
            tn_module=tn,
            session=session,
            q_str=q_str,
            channel=channel,
            cat_id=cat_id,
            providers=[site for site in CATALOG_SITES_LIST if site != "megakino"],
            limit=limit,
            strm_suffix=strm_suffix,
        )
        return _rss_response(rss)

    if t in ("movie", "movie-search"):
        import app.api.torznab as tn

        try:
            require_catalog_ready()
        except CatalogNotReadyError as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail=str(exc)) from exc

        rss, channel = _rss_root()
        q_str = (q or "").strip()
        strm_suffix = " [STRM]"
        if not q_str and TORZNAB_RETURN_TEST_RESULT:
            _emit_test_result(
                tn_module=tn,
                channel=channel,
                cat_id=TORZNAB_CAT_MOVIE,
                strm_suffix=strm_suffix,
            )
            return _rss_response(rss)
        if q_str:
            _indexed_preview_results(
                tn_module=tn,
                session=session,
                q_str=q_str,
                channel=channel,
                cat_id=TORZNAB_CAT_MOVIE,
                providers=["megakino"],
                limit=limit,
                strm_suffix=strm_suffix,
            )
        return _rss_response(rss)

    if t != "tvsearch":
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="invalid t")

    import app.api.torznab as tn
    try:
        require_catalog_ready()
    except CatalogNotReadyError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if season is None:
        logger.debug("Returning empty RSS feed due to missing season.")
        return _empty_rss_response()

    ep_i = _coerce_positive_int(ep)
    search_mode = "episode-search" if ep_i is not None else "season-search"
    season_i = int(season)
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
    if not q_str:
        logger.debug("Returning empty RSS feed due to unresolved tvsearch query.")
        return _empty_rss_response()

    canonical_series = find_canonical_series_by_ids_or_title(
        session,
        tvdb_id=tvdbid,
        tmdb_id=tmdbid,
        imdb_id=imdbid,
        query=q_str,
    )
    if canonical_series is None:
        logger.warning(
            "No canonical series found for query '{}'. Returning empty RSS feed.",
            q_str,
        )
        return _empty_rss_response()
    rss, channel = _rss_root()
    limit_i = max(1, int(limit))
    now = datetime.now(timezone.utc)
    strm_suffix = " [STRM]"

    if search_mode == "episode-search":
        assert ep_i is not None
        count = 0
        for mapping in find_provider_episode_mappings_for_canonical_episode(
            session,
            tvdb_id=canonical_series.tvdb_id,
            canonical_season=season_i,
            canonical_episode=ep_i,
            providers=CATALOG_SITES_LIST,
        ):
            display_title = _indexed_display_title(
                session=session,
                provider=mapping.provider,
                slug=mapping.slug,
                fallback_title=canonical_series.title,
            )
            remaining = limit_i - count
            if remaining <= 0:
                break
            count += _emit_indexed_mapped_episode(
                tn_module=tn,
                session=session,
                channel=channel,
                provider=mapping.provider,
                slug=mapping.slug,
                title=display_title,
                canonical_season=season_i,
                canonical_episode=ep_i,
                provider_season=mapping.provider_season,
                provider_episode=mapping.provider_episode,
                cat_id=TORZNAB_CAT_ANIME,
                now=now,
                strm_suffix=strm_suffix,
                max_items=remaining,
            )
        return _rss_response(rss)

    count = 0
    season_mappings = sorted(
        find_provider_episode_mappings_for_canonical_season(
            session,
            tvdb_id=canonical_series.tvdb_id,
            canonical_season=season_i,
            providers=CATALOG_SITES_LIST,
        ),
        key=lambda item: (item.canonical_episode, item.provider, item.slug),
    )
    for mapping in season_mappings:
        remaining = limit_i - count
        if remaining <= 0:
            break
        display_title = _indexed_display_title(
            session=session,
            provider=mapping.provider,
            slug=mapping.slug,
            fallback_title=canonical_series.title,
        )
        count += _emit_indexed_mapped_episode(
            tn_module=tn,
            session=session,
            channel=channel,
            provider=mapping.provider,
            slug=mapping.slug,
            title=display_title,
            canonical_season=season_i,
            canonical_episode=mapping.canonical_episode,
            provider_season=mapping.provider_season,
            provider_episode=mapping.provider_episode,
            cat_id=TORZNAB_CAT_ANIME,
            now=now,
            strm_suffix=strm_suffix,
            max_items=remaining,
        )

    logger.info("Returning RSS feed with {} items.", count)
    return _rss_response(rss)
