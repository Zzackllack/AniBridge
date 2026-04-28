from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import urlencode

from loguru import logger

from app.db import normalize_catalog_text
from app.utils.http_client import get as http_get

SKYHOOK_SEARCH_URL = "https://skyhook.sonarr.tv/v1/tvdb/search/en/"
SKYHOOK_SHOW_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"


@dataclass(slots=True)
class TvCanonicalMatch:
    tvdb_id: int
    title: str
    confidence: str
    source: str
    rationale: str
    payload: dict[str, Any]


def _score_title(query: str, candidate: str) -> float:
    left = normalize_catalog_text(query)
    right = normalize_catalog_text(candidate)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _candidate_terms(
    *,
    title: str,
    aliases: list[str],
    imdb_id: Optional[str],
    tmdb_id: Optional[int],
) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    if imdb_id:
        terms.append((f"imdb:{imdb_id}", "explicit_imdb"))
    if tmdb_id:
        terms.append((f"tmdb:{tmdb_id}", "explicit_tmdb"))
    if title:
        terms.append((title, "title"))
    for alias in aliases:
        alias_clean = (alias or "").strip()
        if alias_clean and alias_clean != title:
            terms.append((alias_clean, "alias"))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for term, source in terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append((term, source))
    return deduped


def resolve_tv_canonical_match(
    *,
    title: str,
    aliases: list[str],
    imdb_id: Optional[str],
    tmdb_id: Optional[int],
) -> Optional[TvCanonicalMatch]:
    candidates: list[dict[str, Any]] = []
    for term, source in _candidate_terms(
        title=title,
        aliases=aliases,
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
    ):
        try:
            query = urlencode({"term": term})
            response = http_get(f"{SKYHOOK_SEARCH_URL}?{query}", timeout=8.0)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.debug("SkyHook search failed for '{}': {}", term, exc)
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if isinstance(item, dict):
                item["_ab_source"] = source
                item["_ab_term"] = term
                candidates.append(item)

    best_match: Optional[tuple[float, dict[str, Any]]] = None
    for item in candidates:
        candidate_title = str(item.get("title") or "").strip()
        candidate_tvdb = item.get("tvdbId")
        if not candidate_title or not isinstance(candidate_tvdb, int):
            continue
        scores = [_score_title(title, candidate_title)]
        scores.extend(_score_title(alias, candidate_title) for alias in aliases)
        score = max(scores or [0.0])
        if item.get("_ab_source") in {"explicit_imdb", "explicit_tmdb"}:
            score = max(score, 0.99)
        current = (score, item)
        if best_match is None or current[0] > best_match[0]:
            best_match = current

    if best_match is None or best_match[0] < 0.45:
        return None

    score, item = best_match
    tvdb_id = int(item["tvdbId"])
    try:
        response = http_get(SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id), timeout=8.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.debug("SkyHook show fetch failed for tvdb {}: {}", tvdb_id, exc)
        return None
    if not isinstance(payload, dict):
        return None

    if score >= 0.99:
        confidence = "confirmed"
    elif score >= 0.85:
        confidence = "high_confidence"
    else:
        confidence = "low_confidence"

    return TvCanonicalMatch(
        tvdb_id=tvdb_id,
        title=str(payload.get("title") or item.get("title") or title).strip(),
        confidence=confidence,
        source=str(item.get("_ab_source") or "title"),
        rationale=f"score={score:.2f} term={item.get('_ab_term')}",
        payload=payload,
    )
