from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple
import xml.etree.ElementTree as ET
import threading

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


_normalize_tokens_logged = False
_normalize_tokens_log_lock = threading.Lock()


def _normalize_tokens(s: str) -> List[str]:
    """
    Split a string into lowercase alphanumeric tokens.

    Non-alphanumeric characters are treated as token separators; letters are lowercased and digits are preserved.

    Parameters:
        s (str): Input string to tokenize.

    Returns:
        List[str]: A list of lowercase alphanumeric tokens extracted from the input.
    """
    global _normalize_tokens_logged
    if not _normalize_tokens_logged:
        with _normalize_tokens_log_lock:
            if not _normalize_tokens_logged:
                logger.debug("Normalizing tokens for episode/title strings")
                _normalize_tokens_logged = True
    return "".join(ch.lower() if ch.isalnum() else " " for ch in s).split()


def _slug_from_query(q: str, site: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Resolve a free-text query to the best-matching site and canonical slug.

    Parameters:
        q (str): The free-text title or query to resolve.
        site (Optional[str]): Optional site identifier to restrict resolution to a specific site.

    Returns:
        Optional[Tuple[str, str]]: `(site, slug)` with the site identifier and resolved canonical slug when a match is found, `None` otherwise.
    """
    logger.debug(f"Resolving slug from query: '{q}', site filter: {site}")
    from app.utils.title_resolver import slug_from_query  # type: ignore

    # Use the new multi-site slug_from_query
    result = slug_from_query(q, site)
    if result:
        site_found, slug_found = result
        logger.debug(
            f"Best match for '{q}' is slug '{slug_found}' on site '{site_found}'"
        )
        return (site_found, slug_found)
    else:
        logger.warning(f"No slug match found for query: '{q}'")
        return None


def _add_torznab_attr(item: ET.Element, name: str, value: str) -> None:
    """
    Add a torznab `attr` subelement to an RSS item.

    Creates a `torznab:attr` element (namespace http://torznab.com/schemas/2015/feed) as a child of `item` and sets its `name` and `value` attributes.

    Parameters:
        item (xml.etree.ElementTree.Element): The RSS `<item>` element to which the torznab attribute will be added.
        name (str): The `name` attribute to set on the torznab `attr` element.
        value (str): The `value` attribute to set on the torznab `attr` element.
    """
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
