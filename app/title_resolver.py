# app/title_resolver.py
from __future__ import annotations
from typing import Dict, Optional
from bs4 import BeautifulSoup  # type: ignore
from pathlib import Path
import re
from functools import lru_cache

# Wir lesen die lokal gespeicherte Aniworld-„Alphabet“-Seite.
# Struktur: <div id="seriesContainer"> ... <ul><li><a data-alternative-title="..." href="/anime/stream/<slug>">DisplayTitle</a></li> ...

HREF_RE = re.compile(r"/anime/stream/([^/?#]+)")

def _extract_slug(href: str) -> Optional[str]:
    m = HREF_RE.search(href or "")
    return m.group(1) if m else None

def build_index_from_html(html_text: str) -> Dict[str, str]:
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
    return result

@lru_cache(maxsize=1)
def load_title_index_from_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        return build_index_from_html(html_text)
    except Exception:
        return {}

def resolve_series_title(slug: Optional[str], *, html_file: Optional[Path] = None) -> Optional[str]:
    """
    Liefert den Display-Titel zur aniworld-Slug, falls in der Alphabetliste vorhanden.
    """
    if not slug:
        return None
    index = load_title_index_from_file(html_file) if html_file else load_title_index_from_file.cache_info() and load_title_index_from_file.__wrapped__  # type: ignore
    # Fallback auf globalen Default (via last used file in cache)
    if isinstance(index, dict):
        return index.get(slug)
    return None