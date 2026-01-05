from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple
import time
import xml.etree.ElementTree as ET

from loguru import logger

from app.utils.http_client import get as http_get


@dataclass(frozen=True)
class MegakinoIndexEntry:
    """Represents a single megakino sitemap entry."""

    slug: str
    url: str
    kind: str
    lastmod: Optional[datetime]


@dataclass
class MegakinoIndex:
    """In-memory megakino sitemap index."""

    entries: Dict[str, MegakinoIndexEntry]
    fetched_at: float


def _strip_namespace(tag: str) -> str:
    """
    Remove an XML namespace prefix from an element tag, if present.
    
    Parameters:
        tag (str): XML element tag, possibly in the form "{namespace}localname".
    
    Returns:
        str: The local tag name with any leading "{...}" namespace removed.
    """
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_lastmod(text: Optional[str]) -> Optional[datetime]:
    """
    Parse a sitemap `lastmod` text value into a datetime.
    
    Accepts None or empty strings and returns None. Recognizes and parses these formats:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SSZ or with numeric timezone offset (`%Y-%m-%dT%H:%M:%S%z`)
    - YYYY-MM-DDTHH:MM:SS (no timezone)
    
    Parameters:
        text (Optional[str]): The raw `lastmod` text from a sitemap.
    
    Returns:
        Optional[datetime]: A datetime parsed from `text` if a supported format matches, `None` otherwise.
    """
    if not text:
        return None
    raw = text.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _iter_sitemap_urls(root: ET.Element) -> Iterable[Tuple[str, Optional[str]]]:
    """
    Iterate URL entries in a sitemap XML root.
    
    Yields tuples of (loc, lastmod) where `loc` is the trimmed URL string from each `<loc>` element and `lastmod` is the trimmed text from the `<lastmod>` element or an empty string if absent.
    """
    for url_node in root.findall(".//{*}url"):
        loc_node = url_node.find("{*}loc")
        if loc_node is None or not (loc_node.text or "").strip():
            continue
        lastmod_node = url_node.find("{*}lastmod")
        yield (loc_node.text.strip(), (lastmod_node.text or "").strip())


def _extract_slug(url: str) -> Optional[Tuple[str, str]]:
    """
    Extract the resource slug and kind from a Megakino content URL.
    
    Parses the URL path for "/films/" or "/serials/" and returns the slug extracted from the path tail together with the content kind.
    
    Returns:
        Tuple[str, str]: `(slug, kind)` where `kind` is `"film"` or `"serial"`, or `None` if the URL does not contain a recognized path or a valid slug.
    """
    lowered = url.lower()
    if "/films/" in lowered:
        kind = "film"
    elif "/serials/" in lowered:
        kind = "serial"
    else:
        return None

    try:
        tail = (
            lowered.split("/films/", 1)[1]
            if kind == "film"
            else lowered.split("/serials/", 1)[1]
        )
    except IndexError:
        return None

    if not tail:
        return None
    tail = tail.split("?", 1)[0]
    tail = tail.split("#", 1)[0]
    if ".html" in tail:
        tail = tail.split(".html", 1)[0]
    if "-" not in tail:
        return None
    _, slug = tail.split("-", 1)
    slug = slug.strip("/ ")
    if not slug:
        return None
    return slug, kind


def parse_sitemap_xml(xml_text: str) -> List[MegakinoIndexEntry]:
    """
    Parse a Megakino sitemap XML string into MegakinoIndexEntry items.
    
    Handles both sitemap index documents and regular sitemap URL lists. For a
    sitemapindex, produces entries with kind "sitemap" where the slug is the
    child sitemap URL. For a regular sitemap, extracts film or serial slugs
    from item URLs and produces entries with kind "film" or "serial". Entries
    missing a valid <loc> or with an unrecognized URL pattern are skipped.
    
    Parameters:
        xml_text (str): XML text of the sitemap document.
    
    Returns:
        List[MegakinoIndexEntry]: Parsed index entries. Each entry's `lastmod`
        is parsed into a `datetime` when present, otherwise `None`.
    """
    entries: List[MegakinoIndexEntry] = []
    root = ET.fromstring(xml_text)
    root_tag = _strip_namespace(root.tag)
    if root_tag == "sitemapindex":
        for node in root.findall(".//{*}sitemap"):
            loc_node = node.find("{*}loc")
            if loc_node is None or not (loc_node.text or "").strip():
                continue
            loc = loc_node.text.strip()
            lastmod_node = node.find("{*}lastmod")
            entries.append(
                MegakinoIndexEntry(
                    slug=loc,
                    url=loc,
                    kind="sitemap",
                    lastmod=_parse_lastmod(
                        lastmod_node.text if lastmod_node is not None else None
                    ),
                )
            )
        return entries

    for loc, lastmod_raw in _iter_sitemap_urls(root):
        parsed = _extract_slug(loc)
        if not parsed:
            continue
        slug, kind = parsed
        entries.append(
            MegakinoIndexEntry(
                slug=slug,
                url=loc,
                kind=kind,
                lastmod=_parse_lastmod(lastmod_raw),
            )
        )
    return entries


def _fetch_sitemap(url: str, timeout: float = 20.0) -> str:
    """
    Fetches a sitemap XML document from the given URL.
    
    Parameters:
        url (str): The sitemap URL to fetch.
        timeout (float): Maximum time in seconds to wait for the request (default 20.0).
    
    Returns:
        str: The response body as text.
    
    Raises:
        HTTPError: If the HTTP response status indicates a failure.
    """
    logger.debug("Megakino sitemap fetch: {}", url)
    resp = http_get(url, timeout=timeout)
    resp.raise_for_status()
    logger.debug(
        "Megakino sitemap response: status={} bytes={}",
        resp.status_code,
        len(resp.text or ""),
    )
    return resp.text


def load_sitemap_index(
    sitemap_url: str,
    *,
    timeout: float = 20.0,
) -> Dict[str, MegakinoIndexEntry]:
    """
    Load a Megakino sitemap or sitemap index and return a mapping of slug to entry.
    
    If the provided URL is a sitemap index, each referenced sitemap will be fetched and merged; entries from later sitemaps overwrite earlier ones. If no usable entries are found, an empty mapping is returned. Failures fetching individual child sitemaps are ignored and do not stop processing.
    
    Parameters:
        sitemap_url (str): URL of the sitemap or sitemap index to load.
        timeout (float): HTTP request timeout in seconds (default 20.0).
    
    Returns:
        Dict[str, MegakinoIndexEntry]: Mapping from slug to MegakinoIndexEntry; empty if nothing usable was parsed.
    """
    xml_text = _fetch_sitemap(sitemap_url, timeout=timeout)
    top_level = parse_sitemap_xml(xml_text)
    if not top_level:
        logger.warning("Megakino sitemap returned no usable entries.")
        return {}

    # If we got sitemap index entries, fetch each sitemap URL and merge results.
    if all(entry.kind == "sitemap" for entry in top_level):
        merged: Dict[str, MegakinoIndexEntry] = {}
        for entry in top_level:
            try:
                xml_child = _fetch_sitemap(entry.url, timeout=timeout)
                for item in parse_sitemap_xml(xml_child):
                    merged[item.slug] = item
            except Exception as exc:
                logger.warning("Megakino child sitemap fetch failed: {}", exc)
        logger.info("Megakino sitemap index loaded: {} entries", len(merged))
        return merged

    merged = {entry.slug: entry for entry in top_level}
    logger.info("Megakino sitemap loaded: {} entries", len(merged))
    return merged


def needs_refresh(index: Optional[MegakinoIndex], refresh_hours: float) -> bool:
    """
    Determine whether a Megakino sitemap index should be refreshed based on a time-to-live value.
    
    Parameters:
        index (Optional[MegakinoIndex]): Previously fetched index or `None` if no index is available.
        refresh_hours (float): Time-to-live in hours. A value less than or equal to 0 disables refreshing.
    
    Returns:
        `true` if the index needs refresh, `false` otherwise.
    """
    if refresh_hours <= 0:
        return False
    if index is None:
        return True
    age = time.time() - index.fetched_at
    return age > refresh_hours * 3600.0