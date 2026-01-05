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
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_lastmod(text: Optional[str]) -> Optional[datetime]:
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
    """Yield (loc, lastmod) tuples from a sitemap XML root."""
    for url_node in root.findall(".//{*}url"):
        loc_node = url_node.find("{*}loc")
        if loc_node is None or not (loc_node.text or "").strip():
            continue
        lastmod_node = url_node.find("{*}lastmod")
        yield (loc_node.text.strip(), (lastmod_node.text or "").strip())


def _extract_slug(url: str) -> Optional[Tuple[str, str]]:
    """
    Extract slug and kind from a megakino URL.

    Returns:
        Tuple[str, str]: (slug, kind) where kind is "film" or "serial".
    """
    lowered = url.lower()
    if "/films/" in lowered:
        kind = "film"
    elif "/serials/" in lowered:
        kind = "serial"
    else:
        return None

    try:
        tail = lowered.split("/films/", 1)[1] if kind == "film" else lowered.split("/serials/", 1)[1]
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
    """Parse a megakino sitemap XML string into index entries."""
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
                    lastmod=_parse_lastmod(lastmod_node.text if lastmod_node is not None else None),
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
    """Load a sitemap (or sitemap index) into a slug -> entry mapping."""
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
    """Check if the sitemap index needs refreshing based on TTL."""
    if refresh_hours <= 0:
        return False
    if index is None:
        return True
    age = time.time() - index.fetched_at
    return age > refresh_hours * 3600.0
