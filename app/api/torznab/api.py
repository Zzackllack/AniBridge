from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import xml.etree.ElementTree as ET

from fastapi import Depends, Query, Request, Response
from fastapi.responses import Response as FastAPIResponse
from loguru import logger
from sqlmodel import Session

from app.config import (
    ANIBRIDGE_FALLBACK_ALL_EPISODES,
    TORZNAB_CAT_ANIME,
    TORZNAB_RETURN_TEST_RESULT,
    TORZNAB_TEST_EPISODE,
    TORZNAB_TEST_LANGUAGE,
    TORZNAB_TEST_SEASON,
    TORZNAB_TEST_SLUG,
    TORZNAB_TEST_TITLE,
)
from app.db import get_session
from app.utils import absolute_numbering as absmap

from . import router
from .utils import _build_item, _caps_xml, _require_apikey, _rss_root


@router.get("/api", response_class=FastAPIResponse)
def torznab_api(
    request: Request,
    t: str = Query(..., description="caps|tvsearch|search"),
    apikey: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    season: Optional[int] = Query(default=None),
    ep: Optional[int] = Query(default=None),
    cat: Optional[str] = Query(default=None),
    offset: int = Query(default=0),
    limit: int = Query(default=50),
    sonarr_absolute: Optional[bool] = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
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

        if not q_str and TORZNAB_RETURN_TEST_RESULT:
            logger.debug("Returning synthetic test result for empty query.")
            # synthetic test result
            release_title = TORZNAB_TEST_TITLE
            magnet = tn.build_magnet(
                title=release_title,
                slug=TORZNAB_TEST_SLUG,
                season=TORZNAB_TEST_SEASON,
                episode=TORZNAB_TEST_EPISODE,
                language=TORZNAB_TEST_LANGUAGE,
                provider=None,
            )
            guid = f"aw:{TORZNAB_TEST_SLUG}:s{TORZNAB_TEST_SEASON}e{TORZNAB_TEST_EPISODE}:{TORZNAB_TEST_LANGUAGE}"
            now = datetime.now(timezone.utc)

            _build_item(
                channel=channel,
                title=release_title,
                magnet=magnet,
                pubdate=now,
                cat_id=TORZNAB_CAT_ANIME,
                guid_str=guid,
            )
        elif q_str:
            absolute_candidate = absmap.detect_absolute_number(
                query=q_str,
                season=None,
                episode=None,
                absolute_hint=sonarr_absolute,
            )

            slug = tn._slug_from_query(q_str)
            if slug:
                display_title = tn.resolve_series_title(slug) or q_str
                fetch_catalog = lambda: absmap.fetch_episode_catalog(slug)
                targets: List[dict]
                fallback_used = False

                if absolute_candidate is not None:
                    mappings, fallback_used = absmap.resolve_absolute_targets(
                        session,
                        series_slug=slug,
                        absolute_number=absolute_candidate,
                        fetch_catalog=fetch_catalog,
                        fallback_enabled=ANIBRIDGE_FALLBACK_ALL_EPISODES,
                    )
                    if not mappings:
                        rss_xml = ET.tostring(
                            rss, encoding="utf-8", xml_declaration=True
                        ).decode("utf-8")
                        return Response(
                            content=rss_xml,
                            media_type="application/rss+xml; charset=utf-8",
                        )
                    targets = [
                        {
                            "season": mapping.season_number,
                            "episode": mapping.episode_number,
                            "absolute": mapping.absolute_number,
                        }
                        for mapping in mappings
                    ]
                else:
                    targets = [{"season": 1, "episode": 1, "absolute": None}]

                now = datetime.now(timezone.utc)
                for target in targets:
                    season_i = target["season"]
                    ep_i = target["episode"]
                    absolute_val = target["absolute"]

                    cached_langs = tn.list_available_languages_cached(
                        session, slug=slug, season=season_i, episode=ep_i
                    )
                    candidate_langs: List[str] = (
                        cached_langs
                        if cached_langs
                        else ["German Dub", "German Sub", "English Sub"]
                    )

                    for lang in candidate_langs:
                        try:
                            available, h, vc, prov, _info = tn.probe_episode_quality(
                                slug=slug, season=season_i, episode=ep_i, language=lang
                            )
                        except Exception as e:
                            logger.error(
                                "Error probing preview quality for slug={}, S{}E{}, lang={}: {}".format(
                                    slug, season_i, ep_i, lang, e
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
                            )
                        except Exception as e:
                            logger.error(
                                "Error upserting preview availability for slug={}, S{}E{}, lang={}: {}".format(
                                    slug, season_i, ep_i, lang, e
                                )
                            )
                        if not available:
                            continue
                        release_title = tn.build_release_name(
                            series_title=display_title,
                            season=season_i,
                            episode=ep_i,
                            absolute_number=absolute_val,
                            height=h,
                            vcodec=vc,
                            language=lang,
                        )
                        try:
                            magnet = tn.build_magnet(
                                title=release_title,
                                slug=slug,
                                season=season_i,
                                episode=ep_i,
                                language=lang,
                                provider=prov,
                                absolute_number=absolute_val,
                            )
                        except Exception as e:
                            logger.error(
                                f"Error building magnet for release '{release_title}': {e}"
                            )
                            continue

                        guid = f"aw:{slug}:s{season_i}e{ep_i}:{lang}"
                        try:
                            _build_item(
                                channel=channel,
                                title=release_title,
                                magnet=magnet,
                                pubdate=now,
                                cat_id=TORZNAB_CAT_ANIME,
                                guid_str=guid,
                            )
                            item = channel[-1]
                            if absolute_val is not None:
                                tn._add_torznab_attr(
                                    item, "absoluteNumber", str(absolute_val)
                                )
                            if fallback_used and absolute_candidate is not None:
                                tn._add_torznab_attr(item, "anibridgeFallback", "true")
                        except Exception as e:
                            logger.error(
                                f"Error building RSS item for release '{release_title}': {e}"
                            )
                            continue
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    # --- TVSEARCH ---
    if t != "tvsearch":
        # Maintain previous behavior: unknown t -> 400
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="invalid t")

    # require at least q, and either both season+ep or only season (we'll default ep=1)
    import app.api.torznab as tn

    absolute_candidate = absmap.detect_absolute_number(
        query=q,
        season=season,
        episode=ep,
        absolute_hint=sonarr_absolute,
    )

    if absolute_candidate is None and (q is None or season is None):
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to missing parameters.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
    if season is not None and ep is None:
        logger.debug("tvsearch: ep missing; defaulting ep=1 for preview")
        ep = 1

    if q is None:
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to missing query string.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    q_str = str(q)
    season_i = int(season) if season is not None else None
    ep_i = int(ep) if ep is not None else None

    logger.debug(
        f"Searching for slug for query '{q_str}' (season={season_i}, ep={ep_i})"
    )
    slug = tn._slug_from_query(q_str)
    if not slug:
        logger.warning(f"No slug found for query '{q_str}'. Returning empty RSS feed.")
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    display_title = tn.resolve_series_title(slug) or q_str
    logger.debug(f"Resolved display title: '{display_title}' for slug '{slug}'")

    fetch_catalog = lambda: absmap.fetch_episode_catalog(slug)
    targets: List[dict]
    fallback_used = False

    if absolute_candidate is not None:
        mappings, fallback_used = absmap.resolve_absolute_targets(
            session,
            series_slug=slug,
            absolute_number=absolute_candidate,
            fetch_catalog=fetch_catalog,
            fallback_enabled=ANIBRIDGE_FALLBACK_ALL_EPISODES,
        )
        if not mappings:
            rss, _channel = _rss_root()
            xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode(
                "utf-8"
            )
            logger.debug("Absolute request resolved to no episodes.")
            return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
        targets = [
            {
                "season": mapping.season_number,
                "episode": mapping.episode_number,
                "absolute": mapping.absolute_number,
                "title": mapping.episode_title,
            }
            for mapping in mappings
        ]
    else:
        if season_i is None or ep_i is None:
            rss, _channel = _rss_root()
            xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode(
                "utf-8"
            )
            logger.debug("Standard request missing season/episode information.")
            return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
        targets = [
            {
                "season": season_i,
                "episode": ep_i,
                "absolute": None,
                "title": None,
            }
        ]

    rss, channel = _rss_root()
    now = datetime.now(timezone.utc)
    count = 0
    max_items = max(1, int(limit))

    for target in targets:
        if count >= max_items:
            break
        season_val = target["season"]
        episode_val = target["episode"]
        absolute_val = target["absolute"]
        if season_val is None or episode_val is None:
            continue

        cached_langs = tn.list_available_languages_cached(
            session, slug=slug, season=season_val, episode=episode_val
        )
        candidate_langs: List[str] = (
            cached_langs
            if cached_langs
            else ["German Dub", "German Sub", "English Sub"]
        )
        logger.debug(
            "Candidate languages for slug '{}' S{}E{}: {}".format(
                slug, season_val, episode_val, candidate_langs
            )
        )

        for lang in candidate_langs:
            if count >= max_items:
                break
            logger.debug(f"Checking availability for language '{lang}'")
            try:
                rec = tn.get_availability(
                    session,
                    slug=slug,
                    season=season_val,
                    episode=episode_val,
                    language=lang,
                )
            except Exception as e:
                logger.error(
                    "Error reading availability cache for slug={}, S{}E{}, lang={}: {}".format(
                        slug, season_val, episode_val, lang, e
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
                    "Using cached availability for {} S{}E{} {}: h={}, vcodec={}, prov={}".format(
                        slug, season_val, episode_val, lang, height, vcodec, prov_used
                    )
                )
            else:
                try:
                    available, height, vcodec, prov_used, _info = tn.probe_episode_quality(
                        slug=slug,
                        season=season_val,
                        episode=episode_val,
                        language=lang,
                    )
                except Exception as e:
                    logger.error(
                        f"Error probing quality for slug={slug}, S{season_val}E{episode_val}, lang={lang}: {e}"
                    )
                    available = False

                try:
                    tn.upsert_availability(
                        session,
                        slug=slug,
                        season=season_val,
                        episode=episode_val,
                        language=lang,
                        available=available,
                        height=height,
                        vcodec=vcodec,
                        provider=prov_used,
                        extra=None,
                    )
                except Exception as e:
                    logger.error(
                        f"Error upserting availability for slug={slug}, S{season_val}E{episode_val}, lang={lang}: {e}"
                    )

            if not available:
                logger.debug(
                    f"Language '{lang}' currently not available for {slug} S{season_val}E{episode_val}. Skipping."
                )
                continue

            release_title = tn.build_release_name(
                series_title=display_title,
                season=season_val,
                episode=episode_val,
                absolute_number=absolute_val,
                height=height,
                vcodec=vcodec,
                language=lang,
            )
            logger.debug(f"Built release title: '{release_title}'")

            try:
            magnet = tn.build_magnet(
                title=release_title,
                slug=slug,
                season=season_val,
                episode=episode_val,
                language=lang,
                provider=prov_used,
                absolute_number=absolute_val,
            )
            except Exception as e:
                logger.error(f"Error building magnet for release '{release_title}': {e}")
                continue

            guid = f"aw:{slug}:s{season_val}e{episode_val}:{lang}"

            try:
                _build_item(
                    channel=channel,
                    title=release_title,
                    magnet=magnet,
                    pubdate=now,
                    cat_id=TORZNAB_CAT_ANIME,
                    guid_str=guid,
                )
                item = channel[-1]
                if absolute_val is not None:
                    tn._add_torznab_attr(item, "absoluteNumber", str(absolute_val))
                if fallback_used and absolute_candidate is not None:
                    tn._add_torznab_attr(item, "anibridgeFallback", "true")
            except Exception as e:
                logger.error(f"Error building RSS item for release '{release_title}': {e}")
                continue

            count += 1
            logger.debug(f"Added item for language '{lang}'. Total count: {count}")

    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
    logger.info(f"Returning RSS feed with {count} items.")
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
