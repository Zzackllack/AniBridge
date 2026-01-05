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
    """
    Extract the last 4-digit year (1900–2099) found as a whole word in the query.

    Returns:
        The year as an int if a valid 4-digit year is found, otherwise None.
    """
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
    """
    Normalize text into a set of lowercase alphanumeric word tokens, excluding tokens that consist only of digits.

    Parameters:
        text (str): Input string to tokenize and normalize.

    Returns:
        set[str]: Unique tokens composed of lowercase letters and digits extracted from the input, with punctuation replaced by spaces and purely numeric tokens removed.
    """
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = {tok for tok in cleaned.split() if tok and not tok.isdigit()}
    return tokens


def parse_imdb_suggestions(payload: dict, query: str) -> Optional[ImdbSuggestion]:
    """
    Select the best-matching IMDb suggestion from a suggestion payload for a given query.

    Parameters:
        payload (dict): IMDb suggestion JSON object expected to contain a "d" key with a list of suggestion entries.
        query (str): The user search query to match against suggestion titles.

    Returns:
        ImdbSuggestion or None: An ImdbSuggestion with the chosen title and optional year when a best match is found, `None` if the payload is malformed or no suitable suggestion exists.
    """
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
    """
    Derive a movie release year by querying IMDb's public suggestion endpoint for the given query.

    Returns:
        int: The matched year if found, `None` otherwise.
    """
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
    """
    Resolve a movie year from a user query by extracting an explicit year or falling back to an IMDb suggestion lookup.

    Returns:
        movie_year (Optional[int]): The movie year as an integer if found, `None` otherwise.
    """
    year = extract_year_from_query(query)
    if year:
        return year
    return lookup_year_from_imdb(query)
