from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple
import re
import xml.etree.ElementTree as ET
import threading

from fastapi import HTTPException
from loguru import logger

from app.config import (
    CATALOG_SITES_LIST,
    INDEXER_API_KEY,
    INDEXER_NAME,
    TORZNAB_CAT_ANIME,
    TORZNAB_CAT_MOVIE,
    TORZNAB_FAKE_LEECHERS,
    TORZNAB_FAKE_SEEDERS,
)

SUPPORTED_PARAMS = "q,season,ep"
SUPPORTED_MOVIE_PARAMS = "q"
SUPPORTED_SEARCH_PARAMS = "q"


def _require_apikey(apikey: Optional[str]) -> None:
    """
    Validate the provided API key against the configured INDEXER_API_KEY and raise on mismatch.

    If an INDEXER_API_KEY is configured, this function checks that `apikey` is present and equals that value; if not, it logs a warning and raises an HTTPException with status 401 and detail "invalid apikey". If no INDEXER_API_KEY is configured, the function performs no validation.

    Parameters:
        apikey (Optional[str]): The API key supplied by the caller; may be None.

    Raises:
        HTTPException: Raised with status code 401 and detail "invalid apikey" when a configured API key is missing or does not match.
    """
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
    """
    Builds the Torznab "caps" (capabilities) XML document describing server info, limits, available search types, and categories.

    The returned XML contains a top-level <caps> element with:
    - a <server> child (version and supportedSites),
    - a <limits> child (max and default result counts),
    - a <searching> child with <search>, <tv-search>, and <movie-search> elements (each with available and supportedParams),
    - a <categories> child containing "TV/Anime" and "Movies" category entries.

    Returns:
        str: The serialized XML document as a UTF-8 string.
    """
    logger.debug("Generating caps XML.")
    caps = ET.Element("caps")

    server = ET.SubElement(caps, "server")
    server.set("version", "1.0")
    server.set("supportedSites", ",".join(CATALOG_SITES_LIST))

    limits = ET.SubElement(caps, "limits")
    limits.set("max", "100")
    limits.set("default", "50")

    searching = ET.SubElement(caps, "searching")
    # I am not sure if adding those is the cause of why Prowlarr search now works - but ig it does..
    search = ET.SubElement(searching, "search")
    search.set("available", "yes")
    search.set("supportedParams", SUPPORTED_SEARCH_PARAMS)
    tvsearch = ET.SubElement(searching, "tv-search")
    tvsearch.set("available", "yes")
    tvsearch.set("supportedParams", SUPPORTED_PARAMS)
    moviesearch = ET.SubElement(searching, "movie-search")
    moviesearch.set("available", "yes")
    moviesearch.set("supportedParams", SUPPORTED_MOVIE_PARAMS)

    cats = ET.SubElement(caps, "categories")
    cat = ET.SubElement(cats, "category")
    cat.set("id", str(TORZNAB_CAT_ANIME))
    cat.set("name", "TV/Anime")
    movie_cat = ET.SubElement(cats, "category")
    movie_cat.set("id", str(TORZNAB_CAT_MOVIE))
    movie_cat.set("name", "Movies")

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


def _derive_newznab_language_attrs(
    language: Optional[str], title: str
) -> Tuple[Optional[str], Optional[str]]:
    """Derive Newznab language/subs attributes from language labels or title tags."""
    normalized = (language or "").strip().lower()
    audio: Optional[str] = None
    subs: Optional[str] = None

    if normalized:
        if "german" in normalized or "deutsch" in normalized:
            audio = "German"
        elif "english" in normalized or "englisch" in normalized:
            audio = "English"
        if "sub" in normalized and audio:
            subs = audio

    if not audio:
        upper = title.upper()
        if "GER.SUB" in upper or "GER-SUB" in upper or "GER_SUB" in upper:
            return ("German", "German")
        if "ENG.SUB" in upper or "ENG-SUB" in upper or "ENG_SUB" in upper:
            return ("English", "English")
        if re.search(r"(?:^|[.\-_ ])GER(?:[.\-_ ]|$)", upper):
            return ("German", None)
        if re.search(r"(?:^|[.\-_ ])ENG(?:[.\-_ ]|$)", upper):
            return ("English", None)

    return (audio, subs)


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
    length_bytes: int | None = None,
    language: Optional[str] = None,
) -> None:
    """
    Append a complete Torznab-compatible RSS <item> to the provided channel element.

    Creates an <item> with title, GUID (not a permalink), optional pubDate, category, and an <enclosure> for the given magnet URL. The enclosure length is set to the provided `length_bytes` when given; otherwise an estimated size is used. Adds Torznab attribute elements for `magneturl`, `size`, and `infohash` (when the BTIH can be extracted), and adds configured seeders, peers, and leechers attributes.

    Parameters:
        channel (xml.etree.ElementTree.Element): The RSS <channel> element to append the new <item> to.
        title (str): The display title for the item.
        magnet (str): The magnet URI to use as the enclosure URL.
        pubdate (Optional[datetime.datetime]): Publication date; when provided a RFC-822 formatted <pubDate> element is added.
        cat_id (int): Numeric category identifier to place in the <category> element.
        guid_str (str): Opaque GUID string to include inside the <guid> element (marked as not a permalink).
        length_bytes (Optional[int]): If provided, used as the enclosure length in bytes; otherwise a heuristic estimate is used.
    """
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
    est_size = (
        int(length_bytes)
        if length_bytes is not None
        else _estimate_size_from_title_bytes(title)
    )
    enc.set("length", str(est_size))

    # torznab attrs
    _add_torznab_attr(item, "magneturl", magnet)
    _add_torznab_attr(item, "size", str(est_size))
    btih = _parse_btih_from_magnet(magnet)
    if btih:
        _add_torznab_attr(item, "infohash", btih)

    audio_lang, subs_lang = _derive_newznab_language_attrs(language, title)
    if audio_lang:
        _add_torznab_attr(item, "language", audio_lang)
    if subs_lang:
        _add_torznab_attr(item, "subs", subs_lang)

    # Fake Seed-/Leech-Werte (per ENV konfigurierbar)
    seeders = max(0, int(TORZNAB_FAKE_SEEDERS))
    leechers = max(0, int(TORZNAB_FAKE_LEECHERS))
    peers = seeders + leechers

    _add_torznab_attr(item, "seeders", str(seeders))
    _add_torznab_attr(item, "peers", str(peers))
    _add_torznab_attr(item, "leechers", str(leechers))
