from __future__ import annotations
import sys
import os
from loguru import logger
from app.utils.logger import config as configure_logger

configure_logger()

from typing import Dict, Optional, Tuple, List, Set
from pathlib import Path
from functools import lru_cache
from time import time

import re
from app.utils.http_client import get as http_get  # type: ignore
from bs4 import BeautifulSoup  # type: ignore

from app.config import (
    CATALOG_SITES_LIST,
    ANIWORLD_ALPHABET_HTML,
    ANIWORLD_ALPHABET_URL,
    ANIWORLD_TITLES_REFRESH_HOURS,
    STO_ALPHABET_HTML,
    STO_ALPHABET_URL,
    STO_TITLES_REFRESH_HOURS,
)

# Site-specific regex patterns for slug extraction
HREF_PATTERNS = {
    "aniworld.to": re.compile(r"/anime/stream/([^/?#]+)"),
    "s.to": re.compile(r"/serie/stream/([^/?#]+)"),
}

# Legacy pattern for backward compatibility
HREF_RE = HREF_PATTERNS["aniworld.to"]


def _extract_slug(href: str, site: str = "aniworld.to") -> Optional[str]:
    logger.debug(f"Extracting slug from href: {href} for site: {site}")
    pattern = HREF_PATTERNS.get(site, HREF_PATTERNS["aniworld.to"])
    m = pattern.search(href or "")
    if m:
        logger.debug(f"Extracted slug: {m.group(1)}")
    else:
        logger.warning(f"No slug found in href: {href}")
    return m.group(1) if m else None


def build_index_from_html(html_text: str, site: str = "aniworld.to") -> Dict[str, str]:
    logger.info(f"Building index from HTML text for site: {site}.")
    soup = BeautifulSoup(html_text, "html.parser")
    result: Dict[str, str] = {}
    for a in soup.find_all("a"):
        href = a.get("href") or ""  # type: ignore
        slug = _extract_slug(href, site)  # type: ignore
        if not slug:
            logger.debug(f"Skipping anchor with no valid slug: {href}")
            continue
        title = (a.get_text() or "").strip()
        if title:
            result[slug] = title
            logger.debug(f"Added entry: slug={slug}, title={title}")
        else:
            logger.warning(f"Anchor with slug '{slug}' has empty title.")
    logger.success(f"Built index with {len(result)} entries for site: {site}.")
    return result


# -------- Live-Fetch + Cache (Multi-Site Support) --------

# Per-site caches
_cached_indices: Dict[str, Dict[str, str] | None] = {}  # site -> (slug -> title)
_cached_alts: Dict[str, Dict[str, List[str]] | None] = {}  # site -> (slug -> [titles])
_cached_at: Dict[str, float | None] = {}  # site -> timestamp


def _should_refresh(site: str, now: float, refresh_hours: float) -> bool:
    logger.debug(
        f"Checking if cache should refresh for site={site}. now={now}, _cached_at={_cached_at.get(site)}, refresh_hours={refresh_hours}"
    )
    if site not in _cached_indices or _cached_indices[site] is None:
        logger.info(f"No cached index found for {site}. Refresh needed.")
        return True
    if refresh_hours <= 0:
        logger.info(f"Refresh hours <= 0 for {site}. No refresh needed.")
        return False
    if site not in _cached_at or _cached_at[site] is None:
        logger.info(f"No cached timestamp found for {site}. Refresh needed.")
        return True
    expired = (now - _cached_at[site]) > refresh_hours * 3600.0
    if expired:
        logger.info(f"Cache expired for {site}. Refresh needed.")
    else:
        logger.debug(f"Cache still valid for {site}. No refresh needed.")
    return expired


def _parse_index_and_alts(
    html_text: str, site: str = "aniworld.to"
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Parse HTML to produce:
    - slug -> display title
    - slug -> list of alternative titles (including the display title)
    """
    soup = BeautifulSoup(html_text, "html.parser")
    idx: Dict[str, str] = {}
    alts: Dict[str, List[str]] = {}
    pattern = HREF_PATTERNS.get(site, HREF_PATTERNS["aniworld.to"])
    
    for a in soup.find_all("a"):
        href = a.get("href") or ""  # type: ignore
        m = pattern.search(href)
        if not m:
            continue
        slug = m.group(1)
        
        title = (a.get_text() or "").strip()
        alt_raw = (a.get("data-alternative-title") or "").strip()  # type: ignore
        # Split by comma and normalize pieces
        alt_list: List[str] = []
        if alt_raw:
            for piece in alt_raw.split(","):
                p = piece.strip().strip("'\"")
                if p:
                    alt_list.append(p)
        # Always include the main display title as an alternative as well
        if title and title not in alt_list:
            alt_list.insert(0, title)
        if title:
            idx[slug] = title
        if alt_list:
            alts[slug] = alt_list
    return idx, alts


def _fetch_index_from_url(
    url: str, site: str = "aniworld.to"
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    logger.info(f"Fetching index from URL: {url} for site: {site}")
    try:
        resp = http_get(url, timeout=20)
        resp.raise_for_status()
        logger.success(f"Successfully fetched index from URL for site: {site}.")
        return _parse_index_and_alts(resp.text, site)
    except Exception as e:
        logger.error(f"Failed to fetch index from URL for {site}: {e}")
        raise


def _load_index_from_file(
    path: Path, site: str = "aniworld.to"
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Load the index strictly from the provided file path.
    Intentionally avoids implicit fallbacks so tests can point to a
    minimal, deterministic HTML sample via ANIWORLD_ALPHABET_HTML.
    """
    logger.info(f"Loading index from file: {path} for site: {site}")
    if not path.exists():
        logger.warning(f"Configured HTML file does not exist: {path}")
        return {}, {}
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        logger.success(f"Successfully read file: {path} for site: {site}")
        return _parse_index_and_alts(html_text, site)
    except Exception as e:
        logger.error(f"Failed to read file {path} for {site}: {e}")
        raise


def load_or_refresh_index(site: str = "aniworld.to") -> Dict[str, str]:
    """
    Load or refresh the title index for a specific site.
    Prefers live URL (if configured), otherwise falls back to local file.
    Uses in-memory cache with TTL and fallback strategy.
    """
    global _cached_indices, _cached_at, _cached_alts
    now = time()

    logger.debug(f"Starting load_or_refresh_index for site: {site}.")

    # Site configuration
    if site == "aniworld.to":
        url = ANIWORLD_ALPHABET_URL
        html_file = ANIWORLD_ALPHABET_HTML
        refresh_hours = ANIWORLD_TITLES_REFRESH_HOURS
    elif site == "s.to":
        url = STO_ALPHABET_URL
        html_file = STO_ALPHABET_HTML
        refresh_hours = STO_TITLES_REFRESH_HOURS
    else:
        logger.warning(f"Unknown site: {site}. Defaulting to aniworld.to configuration.")
        url = ANIWORLD_ALPHABET_URL
        html_file = ANIWORLD_ALPHABET_HTML
        refresh_hours = ANIWORLD_TITLES_REFRESH_HOURS

    # Check refresh condition
    if not _should_refresh(site, now, refresh_hours):
        logger.info(f"Returning cached index for {site}.")
        return _cached_indices.get(site) or {}

    # 1) Try live URL (if set/not empty)
    index: Dict[str, str] = {}
    alts: Dict[str, List[str]] = {}
    url_stripped = (url or "").strip()
    if url_stripped:
        try:
            logger.info(f"Attempting to fetch index from live URL for {site}.")
            index, alts = _fetch_index_from_url(url_stripped, site)
            if index:
                logger.success(f"Index fetched from live URL for {site}. Updating cache.")
                _cached_indices[site] = index
                _cached_alts[site] = alts
                _cached_at[site] = now
                return index
            else:
                logger.warning(f"Fetched index from live URL is empty for {site}.")
        except Exception as e:
            logger.error(f"Error fetching index from live URL for {site}: {e}")
            # Fallback to file

    # 2) Fallback: Local file
    try:
        logger.info(f"Attempting to load index from local file for {site}.")
        index, alts = _load_index_from_file(html_file, site)
        if index:
            logger.success(f"Index loaded from local file for {site}. Updating cache.")
            _cached_indices[site] = index
            _cached_alts[site] = alts
            _cached_at[site] = now
            return index
        else:
            logger.warning(f"Index loaded from local file is empty for {site}.")
    except Exception as e:
        logger.error(f"Error loading index from local file for {site}: {e}")

    # 3) Nothing found
    logger.warning(
        f"No index found from live URL or local file for {site}. Returning cached index (may be empty)."
    )
    if site not in _cached_indices:
        _cached_indices[site] = {}
    if site not in _cached_alts:
        _cached_alts[site] = {}
    if site not in _cached_at:
        _cached_at[site] = now
    return _cached_indices[site] or {}


def resolve_series_title(slug: Optional[str], site: str = "aniworld.to") -> Optional[str]:
    logger.debug(f"Resolving series title for slug: {slug}, site: {site}")
    if not slug:
        logger.warning("No slug provided to resolve_series_title.")
        return None
    index = load_or_refresh_index(site)
    title = index.get(slug)
    if title:
        logger.info(f"Resolved title for slug '{slug}' on {site}: {title}")
    else:
        logger.warning(f"No title found for slug: {slug} on {site}")
    return title


def load_or_refresh_alternatives(site: str = "aniworld.to") -> Dict[str, List[str]]:
    """
    Ensure alternative titles are cached and return them. Will also populate
    the main index cache if needed.
    """
    global _cached_alts
    now = time()
    refresh_hours = (
        ANIWORLD_TITLES_REFRESH_HOURS if site == "aniworld.to" else STO_TITLES_REFRESH_HOURS
    )
    if _should_refresh(site, now, refresh_hours):
        # Trigger a refresh through the main loader
        load_or_refresh_index(site)
    return _cached_alts.get(site) or {}


def _normalize_tokens(s: str) -> Set[str]:
    return set("".join(ch.lower() if ch.isalnum() else " " for ch in s).split())


def slug_from_query(q: str, site: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Resolve a slug by matching the query against both the main display titles
    and any alternative titles parsed from the index HTML.
    
    Returns a tuple of (site, slug) if found, or None if no match.
    If site is provided, only searches that site. Otherwise searches all enabled sites.
    """
    if not q:
        return None
    
    q_tokens = _normalize_tokens(q)
    best_slug: Optional[str] = None
    best_site: Optional[str] = None
    best_score = 0
    
    # Determine which sites to search
    sites_to_search = [site] if site else CATALOG_SITES_LIST
    
    for search_site in sites_to_search:
        index = load_or_refresh_index(search_site)  # slug -> display title
        alts = load_or_refresh_alternatives(search_site)  # slug -> [titles]
        
        for slug, main_title in index.items():
            # Start with main title tokens
            titles_for_slug: List[str] = [main_title]
            if slug in alts and alts[slug]:
                titles_for_slug.extend(alts[slug])

            # Evaluate best overlap score across all candidate titles
            local_best = 0
            for candidate in titles_for_slug:
                t_tokens = _normalize_tokens(candidate)
                inter = len(q_tokens & t_tokens)
                if inter > local_best:
                    local_best = inter

            if local_best > best_score:
                best_score = local_best
                best_slug = slug
                best_site = search_site

    if best_slug and best_site:
        return (best_site, best_slug)
    return None
