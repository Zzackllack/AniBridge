from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import threading
from typing import Optional

from loguru import logger

from app.config import STRM_PROXY_CACHE_TTL_SECONDS
from .types import StrmIdentity


@dataclass
class StrmCacheEntry:
    url: str
    provider_used: Optional[str]
    resolved_at: datetime


def _utcnow() -> datetime:
    """
    Return current UTC time as timezone-aware datetime.
    """
    return datetime.now(timezone.utc)


class StrmMemoryCache:
    """
    Simple in-memory cache for resolved STRM URLs with TTL support.
    """

    def __init__(self, ttl_seconds: int):
        self._ttl_seconds = ttl_seconds
        self._data: dict[tuple[str, str, int, int, str, str], StrmCacheEntry] = {}
        self._lock = threading.Lock()

    def _is_fresh(self, entry: StrmCacheEntry) -> bool:
        """
        Determine whether a cache entry is still within TTL.
        """
        if self._ttl_seconds <= 0:
            return True
        age = _utcnow() - entry.resolved_at
        return age <= timedelta(seconds=self._ttl_seconds)

    def get(self, identity: StrmIdentity) -> Optional[StrmCacheEntry]:
        """
        Retrieve a cached entry for the given identity if fresh.
        """
        key = identity.cache_key()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            if not self._is_fresh(entry):
                logger.debug("STRM cache expired for {}", key)
                self._data.pop(key, None)
                return None
            return entry

    def set(self, identity: StrmIdentity, entry: StrmCacheEntry) -> None:
        """
        Store a cache entry for the given identity.
        """
        key = identity.cache_key()
        with self._lock:
            self._data[key] = entry

    def invalidate(self, identity: StrmIdentity) -> None:
        """
        Remove any cached entry for the given identity.
        """
        key = identity.cache_key()
        with self._lock:
            self._data.pop(key, None)


MEMORY_CACHE = StrmMemoryCache(STRM_PROXY_CACHE_TTL_SECONDS)
