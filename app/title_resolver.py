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

from typing import Dict, Optional, Tuple
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


def _fetch_index_from_url() -> Dict[str, str]:
    logger.info(f"Fetching index from URL: {ANIWORLD_ALPHABET_URL}")
    try:
        resp = requests.get(ANIWORLD_ALPHABET_URL, timeout=20)
        resp.raise_for_status()
        logger.success("Successfully fetched index from URL.")
        return build_index_from_html(resp.text)
    except Exception as e:
        logger.error(f"Failed to fetch index from URL: {e}")
        raise


def _load_index_from_file(path: Path) -> Dict[str, str]:
    logger.info(f"Loading index from file: {path}")
    if not path.exists():
        logger.warning(f"File does not exist: {path}")
        return {}
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        logger.success(f"Successfully read file: {path}")
        return build_index_from_html(html_text)
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        raise


def load_or_refresh_index() -> Dict[str, str]:
    """
    Bevorzugt Live-URL (falls konfiguriert), sonst lokale Datei.
    Nutzt In-Memory-Cache mit TTL und Fallback-Strategie.
    """
    global _cached_index, _cached_at
    now = time()

    logger.debug("Starting load_or_refresh_index.")

    # Refresh-Bedingung prüfen
    if not _should_refresh(now):
        logger.info("Returning cached index.")
        return _cached_index or {}

    # 1) Versuche Live-URL (falls gesetzt/nicht leer)
    index: Dict[str, str] = {}
    url = (ANIWORLD_ALPHABET_URL or "").strip()
    if url:
        try:
            logger.info("Attempting to fetch index from live URL.")
            index = _fetch_index_from_url()
            if index:
                logger.success("Index fetched from live URL. Updating cache.")
                _cached_index = index
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
        index = _load_index_from_file(ANIWORLD_ALPHABET_HTML)
        if index:
            logger.success("Index loaded from local file. Updating cache.")
            _cached_index = index
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
