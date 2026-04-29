from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import urlencode
import threading
import time

from loguru import logger

from app.db import normalize_catalog_text
from app.utils.http_client import get as http_get

SKYHOOK_SEARCH_URL = "https://skyhook.sonarr.tv/v1/tvdb/search/en/"
SKYHOOK_SHOW_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"
SKYHOOK_TIMEOUT_SECONDS = 4.0
SKYHOOK_CACHE_TTL_SECONDS = 3600.0

_cache_lock = threading.Lock()
_search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_show_cache: dict[int, tuple[float, dict[str, Any]]] = {}


@dataclass(slots=True)
class TvCanonicalMatch:
    tvdb_id: int
    title: str
    confidence: str
    source: str
    rationale: str
    payload: dict[str, Any]


def _cache_get_search(term: str) -> list[dict[str, Any]] | None:
    now = time.time()
    with _cache_lock:
        entry = _search_cache.get(term)
        if entry is None:
            return None
        cached_at, payload = entry
        if now - cached_at > SKYHOOK_CACHE_TTL_SECONDS:
            _search_cache.pop(term, None)
            return None
        return [dict(item) for item in payload]


def _cache_set_search(term: str, payload: list[dict[str, Any]]) -> None:
    with _cache_lock:
        _search_cache[term] = (time.time(), [dict(item) for item in payload])


def _cache_get_show(tvdb_id: int) -> dict[str, Any] | None:
    now = time.time()
    with _cache_lock:
        entry = _show_cache.get(tvdb_id)
        if entry is None:
            return None
        cached_at, payload = entry
        if now - cached_at > SKYHOOK_CACHE_TTL_SECONDS:
            _show_cache.pop(tvdb_id, None)
            return None
        return dict(payload)


def _cache_set_show(tvdb_id: int, payload: dict[str, Any]) -> None:
    with _cache_lock:
        _show_cache[tvdb_id] = (time.time(), dict(payload))


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
        payload = _cache_get_search(term)
        if payload is None:
            try:
                query = urlencode({"term": term})
                response = http_get(
                    f"{SKYHOOK_SEARCH_URL}?{query}",
                    timeout=SKYHOOK_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                raw_payload = response.json()
            except Exception as exc:
                logger.debug("SkyHook search failed for '{}': {}", term, exc)
                continue
            if not isinstance(raw_payload, list):
                continue
            payload = [item for item in raw_payload if isinstance(item, dict)]
            _cache_set_search(term, payload)
        try:
            for item in payload:
                copied = dict(item)
                copied["_ab_source"] = source
                copied["_ab_term"] = term
                candidates.append(copied)
        except Exception:
            continue

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
    payload = _cache_get_show(tvdb_id)
    if payload is None:
        try:
            response = http_get(
                SKYHOOK_SHOW_URL.format(tvdb_id=tvdb_id),
                timeout=SKYHOOK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            raw_payload = response.json()
        except Exception as exc:
            logger.debug("SkyHook show fetch failed for tvdb {}: {}", tvdb_id, exc)
            return None
        if not isinstance(raw_payload, dict):
            return None
        payload = raw_payload
        _cache_set_show(tvdb_id, payload)

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
