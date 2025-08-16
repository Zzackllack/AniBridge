from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Tuple
import xml.etree.ElementTree as ET
import os
import sys

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import Response as FastAPIResponse
from loguru import logger
from sqlmodel import Session

from app.config import (
    INDEXER_API_KEY,
    INDEXER_NAME,
    TORZNAB_CAT_ANIME,
    TORZNAB_FAKE_SEEDERS,
    TORZNAB_FAKE_LEECHERS,
    TORZNAB_RETURN_TEST_RESULT,
    TORZNAB_TEST_TITLE,
    TORZNAB_TEST_SLUG,
    TORZNAB_TEST_SEASON,
    TORZNAB_TEST_EPISODE,
    TORZNAB_TEST_LANGUAGE,
)
from app.magnet import build_magnet
from app.models import (
    get_session,
    get_availability,
    list_available_languages_cached,
    upsert_availability,
)
from app.naming import build_release_name
from app.probe_quality import probe_episode_quality
from app.title_resolver import (
    load_or_refresh_index,
    resolve_series_title,
    load_or_refresh_alternatives,
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

router = APIRouter(prefix="/torznab")

SUPPORTED_PARAMS = "q,season,ep"


def _require_apikey(apikey: Optional[str]) -> None:
    if INDEXER_API_KEY:
        if not apikey or apikey != INDEXER_API_KEY:
            logger.warning(f"API key missing or invalid: received '{apikey}'")
            raise HTTPException(status_code=401, detail="invalid apikey")
    else:
        logger.debug("No API key required for this instance.")


def _rss_root() -> Tuple[ET.Element, ET.Element]:
    """
    returns (rss, channel)
    """
    logger.debug("Building RSS root and channel elements.")
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:torznab", "http://torznab.com/schemas/2015/feed")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = INDEXER_NAME
    ET.SubElement(channel, "description").text = "AniBridge Torznab feed"
    ET.SubElement(channel, "link").text = "https://localhost/"
    return rss, channel


def _caps_xml() -> str:
    logger.debug("Generating caps XML.")
    caps = ET.Element("caps")

    server = ET.SubElement(caps, "server")
    server.set("version", "1.0")

    limits = ET.SubElement(caps, "limits")
    limits.set("max", "100")
    limits.set("default", "50")

    searching = ET.SubElement(caps, "searching")
    tvsearch = ET.SubElement(searching, "tv-search")
    tvsearch.set("available", "yes")
    tvsearch.set("supportedParams", SUPPORTED_PARAMS)

    cats = ET.SubElement(caps, "categories")
    cat = ET.SubElement(cats, "category")
    cat.set("id", str(TORZNAB_CAT_ANIME))
    cat.set("name", "TV/Anime")

    return ET.tostring(caps, encoding="utf-8", xml_declaration=True).decode("utf-8")


def _normalize_tokens(s: str) -> List[str]:
    logger.debug(f"Normalizing tokens for string: '{s}'")
    return "".join(ch.lower() if ch.isalnum() else " " for ch in s).split()


def _slug_from_query(q: str) -> Optional[str]:
    """
    Map free-text query -> slug using main and alternative titles.
    """
    logger.debug(f"Resolving slug from query: '{q}'")
    # Use only the currently loaded index as the candidate set so
    # monkeypatching in tests and controlled contexts behaves deterministically.
    index = load_or_refresh_index()  # slug -> display title
    alts = load_or_refresh_alternatives()  # slug -> [titles]
    q_tokens = set(_normalize_tokens(q))
    best_slug: Optional[str] = None
    best_score = 0

    for s, title in index.items():
        candidates: List[str] = [title]
        if s in alts and alts[s]:
            candidates.extend(alts[s])
        local_best = 0
        for cand in candidates:
            t_tokens = set(_normalize_tokens(cand))
            inter = len(q_tokens & t_tokens)
            if inter > local_best:
                local_best = inter
        if local_best > best_score:
            best_score = local_best
            best_slug = s

    if not best_slug:
        logger.warning(f"No slug match found for query: '{q}'")
    else:
        logger.debug(
            f"Best slug match for '{q}' is '{best_slug}' with score {best_score}"
        )
    return best_slug


def _add_torznab_attr(item: ET.Element, name: str, value: str) -> None:
    attr = ET.SubElement(item, "{http://torznab.com/schemas/2015/feed}attr")
    attr.set("name", name)
    attr.set("value", value)


def _estimate_size_from_title_bytes(title: str) -> int:
    t = title.lower()
    # crude heuristics based on common quality tags
    if "2160p" in t or "4k" in t:
        return 8 * 1024 * 1024 * 1024  # 8 GB
    if "1080p" in t:
        return 1_500 * 1024 * 1024  # ~1.5 GB
    if "720p" in t:
        return 700 * 1024 * 1024  # ~700 MB
    if "480p" in t:
        return 350 * 1024 * 1024  # ~350 MB
    return 500 * 1024 * 1024  # default ~500 MB


def _parse_btih_from_magnet(magnet: str) -> Optional[str]:
    # magnet:?xt=urn:btih:<hash> or with parameters
    try:
        from urllib.parse import parse_qs, urlparse

        q = urlparse(magnet)
        params = parse_qs(q.query)
        xt_vals = params.get("xt") or []
        for xt in xt_vals:
            if xt.lower().startswith("urn:btih:"):
                return xt.split(":")[-1]
    except Exception:
        pass
    # fallback: simple search
    if "btih:" in magnet:
        return magnet.split("btih:")[-1].split("&")[0]
    return None


def _build_item(
    *,
    channel: ET.Element,
    title: str,
    magnet: str,
    pubdate: Optional[datetime],
    cat_id: int,
    guid_str: str,
) -> None:
    logger.debug(
        f"Building RSS item: title='{title}', guid='{guid_str}', magnet='{magnet}'"
    )
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = title
    guid_el = ET.SubElement(item, "guid")
    guid_el.set("isPermaLink", "false")
    guid_el.text = guid_str
    if pubdate:
        ET.SubElement(item, "pubDate").text = pubdate.strftime(
            "%a, %d %b %Y %H:%M:%S %z"
        )
    ET.SubElement(item, "category").text = str(cat_id)
    # enclosure + size
    enc = ET.SubElement(item, "enclosure")
    enc.set("url", magnet)
    enc.set("type", "application/x-bittorrent")
    est_size = _estimate_size_from_title_bytes(title)
    enc.set("length", str(est_size))

    # torznab attrs
    _add_torznab_attr(item, "magneturl", magnet)
    _add_torznab_attr(item, "size", str(est_size))
    btih = _parse_btih_from_magnet(magnet)
    if btih:
        _add_torznab_attr(item, "infohash", btih)

    # Fake Seed-/Leech-Werte (per ENV konfigurierbar)
    seeders = max(0, int(TORZNAB_FAKE_SEEDERS))
    leechers = max(0, int(TORZNAB_FAKE_LEECHERS))
    peers = seeders + leechers

    _add_torznab_attr(item, "seeders", str(seeders))
    _add_torznab_attr(
        item, "peers", str(peers)
    )  # viele Indexer setzen peers=seed+leech
    _add_torznab_attr(
        item, "leechers", str(leechers)
    )  # einige Apps schauen explizit hierauf

    # Optional sinnvoll:
    # - downloadvolumefactor 0 => zählt nicht gegen Ratio bei Seedbox-Trackern,
    #   hier aber optional, da wir kein echtes Torrent-Netz haben.
    # _add_torznab_attr(item, "downloadvolumefactor", "0")
    # _add_torznab_attr(item, "uploadvolumefactor", "1")


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
    session: Session = Depends(get_session),
) -> Response:
    logger.info(
        f"Torznab request: t={t}, q={q}, season={season}, ep={ep}, cat={cat}, offset={offset}, limit={limit}, apikey={'<set>' if apikey else '<none>'}"
    )
    _require_apikey(apikey)

    # --- CAPS ---
    if t == "caps":
        logger.debug("Handling 'caps' request.")
        xml = _caps_xml()
        logger.debug("Returning caps XML response.")
        return Response(content=xml, media_type="application/xml; charset=utf-8")

    # --- SEARCH (generic) ---
    # Prowlarr nutzt das für den Connectivity-Check: t=search&extended=1
    # Zusätzlich: Wenn q gesetzt ist, liefern wir eine Vorschau (S01E01) für das Matching
    # der Serie zurück, damit man in Prowlarr manuell Ergebnisse sieht.
    if t == "search":
        logger.debug("Handling 'search' request.")
        rss, channel = _rss_root()
        q_str = (q or "").strip()
        logger.debug(f"Search query string: '{q_str}'")

        if not q_str and TORZNAB_RETURN_TEST_RESULT:
            logger.debug("Returning synthetic test result for empty query.")
            # synthetisches Test-Ergebnis zurückgeben
            release_title = TORZNAB_TEST_TITLE
            magnet = build_magnet(
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
            # Preview-Suche: S01E01 für die angefragte Serie
            slug = _slug_from_query(q_str)
            if slug:
                display_title = resolve_series_title(slug) or q_str
                season_i, ep_i = 1, 1
                cached_langs = list_available_languages_cached(
                    session, slug=slug, season=season_i, episode=ep_i
                )
                candidate_langs: List[str] = (
                    cached_langs
                    if cached_langs
                    else ["German Dub", "German Sub", "English Sub"]
                )
                now = datetime.now(timezone.utc)
                count = 0
                for lang in candidate_langs:
                    try:
                        available, h, vc, prov, _info = probe_episode_quality(
                            slug=slug, season=season_i, episode=ep_i, language=lang
                        )
                    except Exception as e:
                        logger.error(
                            f"Error probing preview quality for slug={slug}, S{season_i}E{ep_i}, lang={lang}: {e}"
                        )
                        continue
                    try:
                        upsert_availability(
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
                            f"Error upserting preview availability for slug={slug}, S{season_i}E{ep_i}, lang={lang}: {e}"
                        )
                    if not available:
                        continue
                    release_title = build_release_name(
                        series_title=display_title,
                        season=season_i,
                        episode=ep_i,
                        height=h,
                        vcodec=vc,
                        language=lang,
                    )
                    try:
                        magnet = build_magnet(
                            title=release_title,
                            slug=slug,
                            season=season_i,
                            episode=ep_i,
                            language=lang,
                            provider=prov,
                        )
                    except Exception as e:
                        logger.error(
                            f"Error building preview magnet for '{release_title}': {e}"
                        )
                        continue
                    guid = f"aw:{slug}:s{season_i}e{ep_i}:{lang}"
                    _build_item(
                        channel=channel,
                        title=release_title,
                        magnet=magnet,
                        pubdate=now,
                        cat_id=TORZNAB_CAT_ANIME,
                        guid_str=guid,
                    )
                    count += 1
                    if count >= max(1, int(limit)):
                        break

        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning RSS feed for 'search' request.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    # --- TVSEARCH ---
    if t != "tvsearch":
        logger.error(f"Unknown 't' parameter value: '{t}'")
        raise HTTPException(status_code=400, detail="unknown t")

    # tvsearch benötigt q + season + ep; wenn ep fehlt, defaulten wir auf 1,
    # um manuelle Suchen in Prowlarr (nur Staffel gewählt) zu unterstützen.
    if not q:
        logger.warning(
            f"Missing required tvsearch parameters: q={q}, season={season}, ep={ep}"
        )
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to missing parameters.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    if season is None and ep is None:
        logger.warning(
            f"Missing required tvsearch parameters: q={q}, season={season}, ep={ep}"
        )
        # Leeres, aber valides RSS zurückgeben
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        logger.debug("Returning empty RSS feed due to missing parameters.")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")
    if season is not None and ep is None:
        logger.debug("tvsearch: ep missing; defaulting ep=1 for preview")
        ep = 1

    # ab hier garantiert non-None:
    season_i = int(season)
    ep_i = int(ep)
    q_str = str(q)

    logger.debug(
        f"Searching for slug for query '{q_str}' (season={season_i}, ep={ep_i})"
    )
    slug = _slug_from_query(q_str)
    if not slug:
        logger.warning(f"No slug found for query '{q_str}'. Returning empty RSS feed.")
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    display_title = resolve_series_title(slug) or q_str
    logger.debug(f"Resolved display title: '{display_title}' for slug '{slug}'")

    # Sprachen-Kandidaten aus Cache (frisch) oder Default-Set
    cached_langs = list_available_languages_cached(
        session, slug=slug, season=season_i, episode=ep_i
    )
    candidate_langs: List[str] = (
        cached_langs if cached_langs else ["German Dub", "German Sub", "English Sub"]
    )
    logger.debug(
        f"Candidate languages for slug '{slug}', season {season_i}, episode {ep_i}: {candidate_langs}"
    )

    rss, channel = _rss_root()
    count = 0
    now = datetime.now(timezone.utc)

    for lang in candidate_langs:
        logger.debug(f"Checking availability for language '{lang}'")
        # Cache-Eintrag je Sprache prüfen
        try:
            rec = get_availability(
                session, slug=slug, season=season_i, episode=ep_i, language=lang
            )
        except Exception as e:
            logger.error(
                f"Error fetching availability for slug={slug}, season={season_i}, episode={ep_i}, language={lang}: {e}"
            )
            continue

        need_probe = True
        height: Optional[int] = None
        vcodec: Optional[str] = None
        prov_used: Optional[str] = None

        if rec and rec.is_fresh:
            logger.debug(
                f"Found fresh cache record for language '{lang}': available={rec.available}"
            )
            if rec.available:
                height = rec.height
                vcodec = rec.vcodec
                prov_used = rec.provider
                need_probe = False
            else:
                logger.info(
                    f"Language '{lang}' not available for slug={slug}, season={season_i}, episode={ep_i}"
                )
                continue

        if need_probe:
            logger.debug(
                f"Probing episode quality for slug={slug}, season={season_i}, episode={ep_i}, language={lang}"
            )
            try:
                available, h, vc, prov, _info = probe_episode_quality(
                    slug=slug, season=season_i, episode=ep_i, language=lang
                )
            except Exception as e:
                logger.error(
                    f"Error probing episode quality for slug={slug}, season={season_i}, episode={ep_i}, language={lang}: {e}"
                )
                continue
            try:
                upsert_availability(
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
                    f"Error upserting availability for slug={slug}, season={season_i}, episode={ep_i}, language={lang}: {e}"
                )
            if not available:
                logger.info(
                    f"Language '{lang}' not available after probe for slug={slug}, season={season_i}, episode={ep_i}"
                )
                continue
            height, vcodec, prov_used = h, vc, prov

        # Titel bauen (Unknown wenn height None)
        release_title = build_release_name(
            series_title=display_title,
            season=season_i,
            episode=ep_i,
            height=height,
            vcodec=vcodec,
            language=lang,
        )
        logger.debug(f"Built release title: '{release_title}'")

        try:
            magnet = build_magnet(
                title=release_title,
                slug=slug,
                season=season_i,
                episode=ep_i,
                language=lang,
                provider=prov_used,
            )
        except Exception as e:
            logger.error(f"Error building magnet for release '{release_title}': {e}")
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
