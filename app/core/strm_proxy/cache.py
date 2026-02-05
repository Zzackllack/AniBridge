from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from typing import Optional

from loguru import logger

from app.config import STRM_PROXY_CACHE_TTL_SECONDS
from app.db import utcnow
from .types import StrmIdentity


@dataclass
class StrmCacheEntry:
    url: str
    provider_used: Optional[str]
    resolved_at: datetime


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
        age = utcnow() - entry.resolved_at
        return age <= timedelta(seconds=self._ttl_seconds)

    def get(self, identity: StrmIdentity) -> Optional[StrmCacheEntry]:
        """
        Retrieve a cached entry for the given identity if fresh.
        """
        logger.trace("Memory cache lookup for {}", identity.cache_key())
        key = identity.cache_key()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                logger.trace("Memory cache miss for {}", key)
                return None
            if not self._is_fresh(entry):
                logger.debug("STRM cache expired for {}", key)
                self._data.pop(key, None)
                return None
            logger.trace("Memory cache hit for {}", key)
            return entry

    def set(self, identity: StrmIdentity, entry: StrmCacheEntry) -> None:
        """
        Store a cache entry for the given identity.
        """
        logger.trace("Memory cache set for {}", identity.cache_key())
        key = identity.cache_key()
        with self._lock:
            self._data[key] = entry

    def invalidate(self, identity: StrmIdentity) -> None:
        """
        Remove any cached entry for the given identity.
        """
        logger.trace("Memory cache invalidate for {}", identity.cache_key())
        key = identity.cache_key()
        with self._lock:
            self._data.pop(key, None)


MEMORY_CACHE = StrmMemoryCache(STRM_PROXY_CACHE_TTL_SECONDS)
