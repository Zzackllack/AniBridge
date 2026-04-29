from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from difflib import SequenceMatcher
from threading import Lock
from time import time
from typing import Any, Generic, Optional, TypeVar
from urllib.parse import urlencode

from loguru import logger

from app.config import (
    CANONICAL_CACHE_MEMORY_MAX_SEARCH,
    CANONICAL_CACHE_MEMORY_MAX_SHOW,
    CANONICAL_CACHE_TTL_SECONDS,
)
from app.db import normalize_catalog_text
from app.utils.http_client import get as http_get

SKYHOOK_SEARCH_URL = "https://skyhook.sonarr.tv/v1/tvdb/search/en/"
SKYHOOK_SHOW_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"
SKYHOOK_TIMEOUT_SECONDS = 4.0

TKey = TypeVar("TKey")
TValue = TypeVar("TValue")


class TtlLruCache(Generic[TKey, TValue]):
    def __init__(self, *, max_entries: int, ttl_seconds: int) -> None:
        self._max_entries = max(1, int(max_entries))
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._entries: OrderedDict[TKey, tuple[float, TValue]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: TKey) -> TValue | None:
        now = time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return payload

    def set(self, key: TKey, value: TValue) -> None:
        expires_at = time() + self._ttl_seconds
        with self._lock:
            self._entries[key] = (expires_at, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def size(self) -> int:
        with self._lock:
            return len(self._entries)


@dataclass(slots=True)
class TvCanonicalMatch:
    tvdb_id: int
    title: str
    confidence: str
    source: str
    rationale: str
    payload: dict[str, Any]


_search_cache: TtlLruCache[str, list[dict[str, Any]]] = TtlLruCache(
    max_entries=CANONICAL_CACHE_MEMORY_MAX_SEARCH,
    ttl_seconds=CANONICAL_CACHE_TTL_SECONDS,
)
_show_cache: TtlLruCache[int, dict[str, Any]] = TtlLruCache(
    max_entries=CANONICAL_CACHE_MEMORY_MAX_SHOW,
    ttl_seconds=CANONICAL_CACHE_TTL_SECONDS,
)


def canonical_cache_stats() -> dict[str, int]:
    return {
        "search_entries": _search_cache.size(),
        "show_entries": _show_cache.size(),
    }


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
        payload = _search_cache.get(term)
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
            _search_cache.set(term, [dict(item) for item in payload])
        for item in payload:
            copied = dict(item)
            copied["_ab_source"] = source
            copied["_ab_term"] = term
            candidates.append(copied)

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
    payload = _show_cache.get(tvdb_id)
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
        payload = dict(raw_payload)
        _show_cache.set(tvdb_id, dict(payload))

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
