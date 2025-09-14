from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple
import xml.etree.ElementTree as ET

from fastapi import HTTPException
from loguru import logger

from app.config import (
    INDEXER_API_KEY,
    INDEXER_NAME,
    TORZNAB_CAT_ANIME,
    TORZNAB_FAKE_LEECHERS,
    TORZNAB_FAKE_SEEDERS,
)


SUPPORTED_PARAMS = "q,season,ep"


def _require_apikey(apikey: Optional[str]) -> None:
    if INDEXER_API_KEY:
        if not apikey or apikey != INDEXER_API_KEY:
            logger.warning(f"API key missing or invalid: received '{apikey}'")
            raise HTTPException(status_code=401, detail="invalid apikey")
    else:
        logger.debug("No API key required for this instance.")


def _rss_root() -> Tuple[ET.Element, ET.Element]:
    """Create the RSS root and channel elements (rss, channel)."""
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
    """Map free-text query -> slug using main and alternative titles."""
    logger.debug(f"Resolving slug from query: '{q}'")
    from app.utils.title_resolver import (
        load_or_refresh_alternatives,
        load_or_refresh_index,
    )

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
    # Helps differentiate magnets vs .torrent files for some consumers
    enc.set("type", "application/x-bittorrent;x-scheme-handler/magnet")
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
    _add_torznab_attr(item, "peers", str(peers))
    _add_torznab_attr(item, "leechers", str(leechers))
