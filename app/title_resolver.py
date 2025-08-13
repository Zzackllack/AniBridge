from __future__ import annotations
import sys
import os
from loguru import logger
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

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
    m = HREF_RE.search(href or "")
    return m.group(1) if m else None


def build_index_from_html(html_text: str) -> Dict[str, str]:
    logger.info("Building index from HTML text.")
    soup = BeautifulSoup(html_text, "html.parser")
    result: Dict[str, str] = {}
    for a in soup.find_all("a"):
        href = a.get("href") or "" # type: ignore
        slug = _extract_slug(href) # type: ignore
        if not slug:
            continue
        title = (a.get_text() or "").strip()
        if title:
            result[slug] = title
    logger.success(f"Built index with {len(result)} entries.")
    return result

# -------- Live-Fetch + Cache --------

_cached_index: Dict[str, str] | None = None
_cached_at: float | None = None

def _should_refresh(now: float) -> bool:
    if _cached_index is None:
        return True
    if ANIWORLD_TITLES_REFRESH_HOURS <= 0:
        return False
    if _cached_at is None:
        return True
    return (now - _cached_at) > ANIWORLD_TITLES_REFRESH_HOURS * 3600.0

def _fetch_index_from_url() -> Dict[str, str]:
    resp = requests.get(ANIWORLD_ALPHABET_URL, timeout=20)
    resp.raise_for_status()
    return build_index_from_html(resp.text)

def _load_index_from_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    return build_index_from_html(html_text)

def load_or_refresh_index() -> Dict[str, str]:
    """
    Bevorzugt Live-URL (falls konfiguriert), sonst lokale Datei.
    Nutzt In-Memory-Cache mit TTL und Fallback-Strategie.
    """
    global _cached_index, _cached_at
    now = time()

    # Refresh-Bedingung prüfen
    if not _should_refresh(now):
        return _cached_index or {}

    # 1) Versuche Live-URL (falls gesetzt/nicht leer)
    index: Dict[str, str] = {}
    url = (ANIWORLD_ALPHABET_URL or "").strip()
    if url:
        try:
            index = _fetch_index_from_url()
            if index:
                _cached_index = index
                _cached_at = now
                return index
        except Exception:
            # Fallback auf Datei
            pass

    # 2) Fallback: Lokale Datei
    try:
        index = _load_index_from_file(ANIWORLD_ALPHABET_HTML)
        if index:
            _cached_index = index
            _cached_at = now
            return index
    except Exception:
        pass

    # 3) Nichts gefunden
    _cached_index = _cached_index or {}
    _cached_at = _cached_at or now
    return _cached_index

def resolve_series_title(slug: Optional[str]) -> Optional[str]:
    if not slug:
        return None
    index = load_or_refresh_index()
    return index.get(slug)