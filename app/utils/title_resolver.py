from __future__ import annotations
import sys
import os
from loguru import logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

from typing import Dict, Optional, Tuple, List, Set
from pathlib import Path
from functools import lru_cache
from time import time

import re
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore

from app.config import (
    ANIWORLD_ALPHABET_HTML,
    ANIWORLD_ALPHABET_URL,
    ANIWORLD_TITLES_REFRESH_HOURS,
)

HREF_RE = re.compile(r"/anime/stream/([^/?#]+)")


def _extract_slug(href: str) -> Optional[str]:
    logger.debug(f"Extracting slug from href: {href}")
    m = HREF_RE.search(href or "")
    if m:
        logger.debug(f"Extracted slug: {m.group(1)}")
    else:
        logger.warning(f"No slug found in href: {href}")
    return m.group(1) if m else None


def build_index_from_html(html_text: str) -> Dict[str, str]:
    logger.info("Building index from HTML text.")
    soup = BeautifulSoup(html_text, "html.parser")
    result: Dict[str, str] = {}
    for a in soup.find_all("a"):
        href = a.get("href") or ""  # type: ignore
        slug = _extract_slug(href)  # type: ignore
        if not slug:
            logger.debug(f"Skipping anchor with no valid slug: {href}")
            continue
        title = (a.get_text() or "").strip()
        if title:
            result[slug] = title
            logger.debug(f"Added entry: slug={slug}, title={title}")
        else:
            logger.warning(f"Anchor with slug '{slug}' has empty title.")
    logger.success(f"Built index with {len(result)} entries.")
    return result


# -------- Live-Fetch + Cache --------

_cached_index: Dict[str, str] | None = None
_cached_alts: Dict[str, List[str]] | None = (
    None  # slug -> alternative titles (incl. main)
)
_cached_at: float | None = None


def _should_refresh(now: float) -> bool:
    logger.debug(
        f"Checking if cache should refresh. now={now}, _cached_at={_cached_at}, refresh_hours={ANIWORLD_TITLES_REFRESH_HOURS}"
    )
    if _cached_index is None:
        logger.info("No cached index found. Refresh needed.")
        return True
    if ANIWORLD_TITLES_REFRESH_HOURS <= 0:
        logger.info("Refresh hours <= 0. No refresh needed.")
        return False
    if _cached_at is None:
        logger.info("No cached timestamp found. Refresh needed.")
        return True
    expired = (now - _cached_at) > ANIWORLD_TITLES_REFRESH_HOURS * 3600.0
    if expired:
        logger.info("Cache expired. Refresh needed.")
    else:
        logger.debug("Cache still valid. No refresh needed.")
    return expired


def _parse_index_and_alts(
    html_text: str,
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Parse HTML to produce:
    - slug -> display title
    - slug -> list of alternative titles (including the display title)
    """
    soup = BeautifulSoup(html_text, "html.parser")
    idx: Dict[str, str] = {}
    alts: Dict[str, List[str]] = {}
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        slug = _extract_slug(href)  # type: ignore
        if not slug:
            continue
        title = (a.get_text() or "").strip()
        alt_raw = (a.get("data-alternative-title") or "").strip()
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


def _fetch_index_from_url() -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    logger.info(f"Fetching index from URL: {ANIWORLD_ALPHABET_URL}")
    try:
        resp = requests.get(ANIWORLD_ALPHABET_URL, timeout=20)
        resp.raise_for_status()
        logger.success("Successfully fetched index from URL.")
        return _parse_index_and_alts(resp.text)
    except Exception as e:
        logger.error(f"Failed to fetch index from URL: {e}")
        raise


def _load_index_from_file(path: Path) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Load the index strictly from the provided file path.
    Intentionally avoids implicit fallbacks so tests can point to a
    minimal, deterministic HTML sample via ANIWORLD_ALPHABET_HTML.
    """
    logger.info(f"Loading index from file: {path}")
    if not path.exists():
        logger.warning(f"Configured HTML file does not exist: {path}")
        return {}, {}
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        logger.success(f"Successfully read file: {path}")
        return _parse_index_and_alts(html_text)
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        raise


def load_or_refresh_index() -> Dict[str, str]:
    """
    Bevorzugt Live-URL (falls konfiguriert), sonst lokale Datei.
    Nutzt In-Memory-Cache mit TTL und Fallback-Strategie.
    """
    global _cached_index, _cached_at, _cached_alts
    now = time()

    logger.debug("Starting load_or_refresh_index.")

    # Refresh-Bedingung prüfen
    if not _should_refresh(now):
        logger.info("Returning cached index.")
        return _cached_index or {}

    # 1) Versuche Live-URL (falls gesetzt/nicht leer)
    index: Dict[str, str] = {}
    alts: Dict[str, List[str]] = {}
    url = (ANIWORLD_ALPHABET_URL or "").strip()
    if url:
        try:
            logger.info("Attempting to fetch index from live URL.")
            index, alts = _fetch_index_from_url()
            if index:
                logger.success("Index fetched from live URL. Updating cache.")
                _cached_index = index
                _cached_alts = alts
                _cached_at = now
                return index
            else:
                logger.warning("Fetched index from live URL is empty.")
        except Exception as e:
            logger.error(f"Error fetching index from live URL: {e}")
            # Fallback auf Datei

    # 2) Fallback: Lokale Datei
    try:
        logger.info("Attempting to load index from local file.")
        index, alts = _load_index_from_file(ANIWORLD_ALPHABET_HTML)
        if index:
            logger.success("Index loaded from local file. Updating cache.")
            _cached_index = index
            _cached_alts = alts
            _cached_at = now
            return index
        else:
            logger.warning("Index loaded from local file is empty.")
    except Exception as e:
        logger.error(f"Error loading index from local file: {e}")

    # 3) Nichts gefunden
    logger.warning(
        "No index found from live URL or local file. Returning cached index (may be empty)."
    )
    _cached_index = _cached_index or {}
    _cached_alts = _cached_alts or {}
    _cached_at = _cached_at or now
    return _cached_index


def resolve_series_title(slug: Optional[str]) -> Optional[str]:
    logger.debug(f"Resolving series title for slug: {slug}")
    if not slug:
        logger.warning("No slug provided to resolve_series_title.")
        return None
    index = load_or_refresh_index()
    title = index.get(slug)
    if title:
        logger.info(f"Resolved title for slug '{slug}': {title}")
    else:
        logger.warning(f"No title found for slug: {slug}")
    return title


def load_or_refresh_alternatives() -> Dict[str, List[str]]:
    """
    Ensure alternative titles are cached and return them. Will also populate
    the main index cache if needed.
    """
    global _cached_alts
    now = time()
    if _should_refresh(now):
        # Trigger a refresh through the main loader
        load_or_refresh_index()
    return _cached_alts or {}


def _normalize_tokens(s: str) -> Set[str]:
    return set("".join(ch.lower() if ch.isalnum() else " " for ch in s).split())


def slug_from_query(q: str) -> Optional[str]:
    """
    Resolve a slug by matching the query against both the main display titles
    and any alternative titles parsed from the AniWorld index HTML.
    """
    index = load_or_refresh_index()  # slug -> display title
    alts = load_or_refresh_alternatives()  # slug -> [titles]
    if not q:
        return None
    q_tokens = _normalize_tokens(q)
    best_slug: Optional[str] = None
    best_score = 0

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

    return best_slug
