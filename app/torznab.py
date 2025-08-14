from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Tuple
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import Response as FastAPIResponse
from loguru import logger
from sqlmodel import Session

from app.config import INDEXER_API_KEY, INDEXER_NAME, TORZNAB_CAT_ANIME
from app.magnet import build_magnet
from app.models import (
    get_session,
    get_availability,
    list_available_languages_cached,
    upsert_availability,
)
from app.naming import build_release_name
from app.probe_quality import probe_episode_quality
from app.title_resolver import load_or_refresh_index, resolve_series_title


router = APIRouter(prefix="/torznab")


SUPPORTED_PARAMS = "q,season,ep"


def _require_apikey(apikey: Optional[str]) -> None:
    if INDEXER_API_KEY:
        if not apikey or apikey != INDEXER_API_KEY:
            raise HTTPException(status_code=401, detail="invalid apikey")


def _rss_root() -> Tuple[ET.Element, ET.Element]:
    """
    returns (rss, channel)
    """
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:torznab", "http://torznab.com/schemas/2015/feed")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = INDEXER_NAME
    ET.SubElement(channel, "description").text = "AniBridge Torznab feed"
    ET.SubElement(channel, "link").text = "https://localhost/"
    return rss, channel


def _caps_xml() -> str:
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
    # einfache Normalisierung für fuzzy-match
    return "".join(ch.lower() if ch.isalnum() else " " for ch in s).split()


def _slug_from_query(q: str) -> Optional[str]:
    """
    mappe Freitext q -> slug (über Title-Index)
    """
    index = load_or_refresh_index()  # slug -> display title
    q_tokens = set(_normalize_tokens(q))
    best_slug: Optional[str] = None
    best_score = 0
    for slug, title in index.items():
        t_tokens = set(_normalize_tokens(title))
        inter = len(q_tokens & t_tokens)
        if inter > best_score:
            best_slug = slug
            best_score = inter
    return best_slug


def _build_item(
    *,
    channel: ET.Element,
    title: str,
    magnet: str,
    pubdate: Optional[datetime],
    cat_id: int,
    guid_str: str,
) -> None:
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = title
    guid_el = ET.SubElement(item, "guid")
    guid_el.set("isPermaLink", "false")
    guid_el.text = guid_str
    if pubdate:
        ET.SubElement(item, "pubDate").text = pubdate.strftime("%a, %d %b %Y %H:%M:%S %z")
    ET.SubElement(item, "category").text = str(cat_id)
    enc = ET.SubElement(item, "enclosure")
    enc.set("url", magnet)
    enc.set("type", "application/x-bittorrent")
    tor_attr = ET.SubElement(item, "{http://torznab.com/schemas/2015/feed}attr")
    tor_attr.set("name", "magneturl")
    tor_attr.set("value", magnet)


@router.get("/api", response_class=FastAPIResponse)
def torznab_api(
    request: Request,
    t: str = Query(..., description="caps|tvsearch"),
    apikey: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    season: Optional[int] = Query(default=None),
    ep: Optional[int] = Query(default=None),
    cat: Optional[str] = Query(default=None),  # wird (derzeit) ignoriert
    offset: int = Query(default=0),
    limit: int = Query(default=50),
    session: Session = Depends(get_session),
) -> Response:
    _require_apikey(apikey)

    if t == "caps":
        xml = _caps_xml()
        return Response(content=xml, media_type="application/xml; charset=utf-8")

    if t != "tvsearch":
        raise HTTPException(status_code=400, detail="unknown t")

    # tvsearch: laut Spec brauchen wir (q + season + ep) (wir unterstützen keine tvdbid/rid/…)
    if not q or season is None or ep is None:
        # Leeres, aber valides RSS zurückgeben
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    # ab hier garantiert non-None:
    season_i = int(season)
    ep_i = int(ep)
    q_str = str(q)

    slug = _slug_from_query(q_str)
    if not slug:
        rss, _channel = _rss_root()
        xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    display_title = resolve_series_title(slug) or q_str

    # Sprachen-Kandidaten aus Cache (frisch) oder Default-Set
    cached_langs = list_available_languages_cached(session, slug=slug, season=season_i, episode=ep_i)
    candidate_langs: List[str] = cached_langs if cached_langs else ["German Dub", "German Sub", "English Sub"]

    rss, channel = _rss_root()
    count = 0
    now = datetime.now(timezone.utc)

    for lang in candidate_langs:
        # Cache-Eintrag je Sprache prüfen
        rec = get_availability(session, slug=slug, season=season_i, episode=ep_i, language=lang)
        need_probe = True
        height: Optional[int] = None
        vcodec: Optional[str] = None
        prov_used: Optional[str] = None

        if rec and rec.is_fresh:
            if rec.available:
                height = rec.height
                vcodec = rec.vcodec
                prov_used = rec.provider
                need_probe = False
            else:
                # Sprachlich nicht verfügbar -> nichts ausspielen
                continue

        if need_probe:
            available, h, vc, prov, _info = probe_episode_quality(
                slug=slug, season=season_i, episode=ep_i, language=lang
            )
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
            if not available:
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

        magnet = build_magnet(
            title=release_title,
            slug=slug,
            season=season_i,
            episode=ep_i,
            language=lang,
            provider=prov_used,
        )
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
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")