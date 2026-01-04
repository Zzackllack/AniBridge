from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import xml.etree.ElementTree as ET

from fastapi import Depends, Query, Request, Response
from fastapi.responses import Response as FastAPIResponse
from loguru import logger
from sqlmodel import Session

from app.config import (
    CATALOG_SITE_CONFIGS,
    STRM_FILES_MODE,
    TORZNAB_CAT_ANIME,
    TORZNAB_CAT_MOVIE,
    TORZNAB_RETURN_TEST_RESULT,
    TORZNAB_TEST_EPISODE,
    TORZNAB_TEST_LANGUAGE,
    TORZNAB_TEST_SEASON,
    TORZNAB_TEST_SLUG,
    TORZNAB_TEST_TITLE,
)
from app.db import get_session
from app.utils.magnet import _site_prefix

from . import router
from .utils import _build_item, _caps_xml, _require_apikey, _rss_root


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


@router.get("/api", response_class=FastAPIResponse)
def torznab_api(
    request: Request,
    t: str = Query(..., description="caps|tvsearch|search|movie"),
    apikey: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    season: Optional[int] = Query(default=None),
    ep: Optional[int] = Query(default=None),
    cat: Optional[str] = Query(default=None),
    offset: int = Query(default=0),
    limit: int = Query(default=50),
    session: Session = Depends(get_session),
) -> Response:
    """
    Handle Torznab API requests and produce the appropriate XML or RSS response.

    Parameters:
        request (Request): Incoming FastAPI request.
        t (str): Mode selector: "caps", "search", or "tvsearch".
        apikey (Optional[str]): API key required for access; validated by the endpoint.
        q (Optional[str]): Query string identifying a series or search terms.
        season (Optional[int]): Season number for TV searches; required for "tvsearch".
        ep (Optional[int]): Episode number for TV searches; defaults to 1 when omitted for preview searches.
        cat (Optional[str]): Optional category filter passed through the request.
        offset (int): Result offset for paging.
        limit (int): Maximum number of RSS items to include.
        session (Session): Database session (injected; omitted from consumer-facing docs).

    Returns:
        Response: FastAPI Response containing XML:
            - application/xml; charset=utf-8 for "caps"
            - application/rss+xml; charset=utf-8 for "search" and "tvsearch"
            - Raises HTTP 400 for an unknown `t` value.
            - Returns an empty RSS feed when required parameters are missing or when slug resolution yields no result.
    """
    logger.info(
        "Torznab request: t={}, q={}, season={}, ep={}, cat={}, offset={}, limit={}, apikey={}".format(
            t, q, season, ep, cat, offset, limit, "<set>" if apikey else "<none>"
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
        if cat:
            cat_list = [c.strip() for c in str(cat).split(",") if c.strip()]
            if str(TORZNAB_CAT_MOVIE) in cat_list:
                cat_id = TORZNAB_CAT_MOVIE

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
                )
        elif q_str:
            # Preview search: S01E01 for requested series
            result = tn._slug_from_query(q_str)
            if result:
                site_found, slug = result
                display_title = tn.resolve_series_title(slug, site_found) or q_str
                season_i, ep_i = 1, 1
                cached_langs = tn.list_available_languages_cached(
                    session, slug=slug, season=season_i, episode=ep_i, site=site_found
                )

                default_langs = _default_languages_for_site(site_found)
                candidate_langs: List[str] = (
                    cached_langs if cached_langs else default_langs
                )
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
                    release_title = tn.build_release_name(
                        series_title=display_title,
                        season=season_i,
                        episode=ep_i,
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
                    except Exception as e:
                        logger.error(
                            f"Error building magnet for release '{release_title}': {e}"
                        )
                        continue

                    # Use site-appropriate prefix for GUID
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
                            )
                    except Exception as e:
                        logger.error(
                            f"Error building RSS item for release '{release_title}': {e}"
                        )
                        continue
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
                )
        elif q_str:
            result = tn._slug_from_query(q_str)
            if result:
                site_found, slug = result
                display_title = tn.resolve_series_title(slug, site_found) or q_str
                season_i, ep_i = 1, 1
                cached_langs = tn.list_available_languages_cached(
                    session, slug=slug, season=season_i, episode=ep_i, site=site_found
                )
                default_langs = _default_languages_for_site(site_found)
                candidate_langs: List[str] = (
                    cached_langs if cached_langs else default_langs
                )
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
                            "Error probing movie quality for slug={}, S{}E{}, lang={}, site={}: {}".format(
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
                            "Error upserting movie availability for slug={}, S{}E{}, lang={}, site={}: {}".format(
                                slug, season_i, ep_i, lang, site_found, e
                            )
                        )
                    if not available:
                        continue
                    release_title = tn.build_release_name(
                        series_title=display_title,
                        season=season_i,
                        episode=ep_i,
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
                    except Exception as e:
                        logger.error(
                            f"Error building magnet for release '{release_title}': {e}"
                        )
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
                                cat_id=TORZNAB_CAT_MOVIE,
                                guid_str=guid_base,
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
                                cat_id=TORZNAB_CAT_MOVIE,
                                guid_str=f"{guid_base}:strm",
                            )
                    except Exception as e:
                        logger.error(
                            f"Error building RSS item for release '{release_title}': {e}"
                        )
                        continue
                    count += 1
                    if count >= max(1, int(limit)):
                        break
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    # --- TVSEARCH ---
    if t != "tvsearch":
        # Maintain previous behavior: unknown t -> 400
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="invalid t")

    # require at least q, and either both season+ep or only season (we'll default ep=1)
    import app.api.torznab as tn

    if q is None or season is None:
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to missing parameters.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
    if season is not None and ep is None:
        logger.debug("tvsearch: ep missing; defaulting ep=1 for preview")
        ep = 1

    # from here on, non-None
    assert season is not None and ep is not None and q is not None
    season_i = int(season)
    ep_i = int(ep)
    q_str = str(q)

    logger.debug(
        f"Searching for slug for query '{q_str}' (season={season_i}, ep={ep_i})"
    )
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

    # language candidates from cache or defaults
    cached_langs = tn.list_available_languages_cached(
        session, slug=slug, season=season_i, episode=ep_i, site=site_found
    )

    default_langs = _default_languages_for_site(site_found)
    candidate_langs: List[str] = cached_langs if cached_langs else default_langs
    logger.debug(
        f"Candidate languages for slug '{slug}', season {season_i}, episode {ep_i}, site '{site_found}': {candidate_langs}"
    )

    rss, channel = _rss_root()
    count = 0
    now = datetime.now(timezone.utc)
    strm_suffix = " [STRM]"

    for lang in candidate_langs:
        logger.debug(f"Checking availability for language '{lang}'")
        # check cache per language
        try:
            rec = tn.get_availability(
                session,
                slug=slug,
                season=season_i,
                episode=ep_i,
                language=lang,
                site=site_found,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Error reading availability cache for slug={}, S{}E{}, lang={}, site={}: {}".format(
                    slug, season_i, ep_i, lang, site_found, e
                )
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
                f"Using cached availability for {slug} S{season_i}E{ep_i} {lang} on {site_found}: h={height}, vcodec={vcodec}, prov={prov_used}"
            )
        else:
            try:
                available, height, vcodec, prov_used, _info = tn.probe_episode_quality(
                    slug=slug,
                    season=season_i,
                    episode=ep_i,
                    language=lang,
                    site=site_found,
                )
            except (ValueError, RuntimeError) as e:
                logger.error(
                    f"Error probing quality for slug={slug}, S{season_i}E{ep_i}, lang={lang}, site={site_found}: {e}"
                )
                available = False

            try:
                tn.upsert_availability(
                    session,
                    slug=slug,
                    season=season_i,
                    episode=ep_i,
                    language=lang,
                    available=available,
                    height=height,
                    vcodec=vcodec,
                    provider=prov_used,
                    extra=None,
                    site=site_found,
                )
            except (ValueError, RuntimeError) as e:
                logger.error(
                    f"Error upserting availability for slug={slug}, S{season_i}E{ep_i}, lang={lang}, site={site_found}: {e}"
                )

        if not available:
            logger.debug(
                f"Language '{lang}' currently not available for {slug} S{season_i}E{ep_i} on {site_found}. Skipping."
            )
            continue

        # build release name
        release_title = tn.build_release_name(
            series_title=display_title,
            season=season_i,
            episode=ep_i,
            height=height,
            vcodec=vcodec,
            language=lang,
            site=site_found,
        )
        logger.debug(f"Built release title: '{release_title}'")

        try:
            magnet = tn.build_magnet(
                title=release_title,
                slug=slug,
                season=season_i,
                episode=ep_i,
                language=lang,
                provider=prov_used,
                site=site_found,
            )
        except Exception as e:
            logger.error(f"Error building magnet for release '{release_title}': {e}")
            continue

        # Use site-appropriate prefix for GUID
        prefix = _site_prefix(site_found)
        guid_base = f"{prefix}:{slug}:s{season_i}e{ep_i}:{lang}"

        try:
            if STRM_FILES_MODE in ("no", "both"):
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=TORZNAB_CAT_ANIME,
                    guid_str=guid_base,
                )
            if STRM_FILES_MODE in ("only", "both"):
                magnet_strm = tn.build_magnet(
                    title=release_title + strm_suffix,
                    slug=slug,
                    season=season_i,
                    episode=ep_i,
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
                )
        except Exception as e:
            logger.error(f"Error building RSS item for release '{release_title}': {e}")
            continue

        count += 1
        logger.debug(f"Added item for language '{lang}'. Total count: {count}")
        if count >= max(1, int(limit)):
            logger.info(f"Reached limit ({limit}). Stopping item generation.")
            break

    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
    logger.info(f"Returning RSS feed with {count} items.")
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
