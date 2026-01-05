from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
import re

from loguru import logger

from app.utils.http_client import get as http_get


_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


@dataclass(frozen=True)
class ImdbSuggestion:
    """Represents a single IMDb suggestion entry."""

    title: str
    year: Optional[int]


def extract_year_from_query(query: str) -> Optional[int]:
    """Extract a 4-digit year from a query string."""
    if not query:
        return None
    matches = _YEAR_RE.findall(query)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def _normalize_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = {tok for tok in cleaned.split() if tok and not tok.isdigit()}
    return tokens


def parse_imdb_suggestions(payload: dict, query: str) -> Optional[ImdbSuggestion]:
    """Parse IMDb suggestion payload and return the best match."""
    items = payload.get("d") or []
    if not isinstance(items, list):
        return None
    q_tokens = _normalize_tokens(query)
    best: Optional[ImdbSuggestion] = None
    best_score = 0
    for item in items:
        title = item.get("l")
        if not title:
            continue
        year = item.get("y")
        try:
            year_val = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_val = None
        t_tokens = _normalize_tokens(title)
        score = len(q_tokens & t_tokens)
        if score > best_score:
            best_score = score
            best = ImdbSuggestion(title=title, year=year_val)
    return best


@lru_cache(maxsize=256)
def lookup_year_from_imdb(query: str) -> Optional[int]:
    """Lookup a movie year from IMDb suggestions without API keys."""
    q_str = (query or "").strip()
    if not q_str:
        return None
    first_letter = q_str[0].lower()
    url = f"https://v2.sg.media-imdb.com/suggestion/{first_letter}/{q_str}.json"
    try:
        resp = http_get(url, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.debug("IMDb suggestion lookup failed: {}", exc)
        return None
    suggestion = parse_imdb_suggestions(payload, q_str)
    if suggestion and suggestion.year:
        logger.debug("IMDb suggestion year for '{}': {}", q_str, suggestion.year)
        return suggestion.year
    return None


def get_movie_year(query: str) -> Optional[int]:
    """Resolve a movie year from the query, using extraction then IMDb fallback."""
    year = extract_year_from_query(query)
    if year:
        return year
    return lookup_year_from_imdb(query)
