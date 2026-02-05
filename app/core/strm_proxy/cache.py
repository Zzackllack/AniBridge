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
    Get the current UTC time as a timezone-aware datetime.
    
    Returns:
        datetime: Current UTC datetime with timezone set to UTC.
    """
    return datetime.now(timezone.utc)


class StrmMemoryCache:
    """
    Simple in-memory cache for resolved STRM URLs with TTL support.
    """

    def __init__(self, ttl_seconds: int):
        """
        Create a thread-safe in-memory cache for resolved STRM URLs using the specified TTL.
        
        Parameters:
            ttl_seconds (int): Time-to-live for cache entries in seconds. If less than or equal to zero, cached entries are treated as never expiring.
        """
        self._ttl_seconds = ttl_seconds
        self._data: dict[tuple[str, str, int, int, str, str], StrmCacheEntry] = {}
        self._lock = threading.Lock()

    def _is_fresh(self, entry: StrmCacheEntry) -> bool:
        """
        Check whether a cache entry is still within the configured time-to-live (TTL).
        
        This compares the entry's resolved_at timestamp to the current UTC time; if the cache's TTL is less than or equal to zero, entries are considered always fresh.
        
        Returns:
            True if the entry's age is less than or equal to the TTL or if TTL <= 0, False otherwise.
        """
        if self._ttl_seconds <= 0:
            return True
        age = _utcnow() - entry.resolved_at
        return age <= timedelta(seconds=self._ttl_seconds)

    def get(self, identity: StrmIdentity) -> Optional[StrmCacheEntry]:
        """
        Retrieve the cached StrmCacheEntry for the given identity if a fresh entry exists.
        
        Parameters:
            identity (StrmIdentity): Identity whose cache key is used to look up the entry.
        
        Returns:
            StrmCacheEntry | None: `StrmCacheEntry` if a fresh entry exists for the identity, `None` otherwise.
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
        Store the provided StrmCacheEntry in the in-memory cache under the key derived from `identity`.
        
        Parameters:
            identity (StrmIdentity): Identity whose cache key will be used to index the entry.
            entry (StrmCacheEntry): Cache entry to store.
        """
        logger.trace("Memory cache set for {}", identity.cache_key())
        key = identity.cache_key()
        with self._lock:
            self._data[key] = entry

    def invalidate(self, identity: StrmIdentity) -> None:
        """
        Invalidate the cache entry associated with the given STRM identity.
        
        Parameters:
            identity (StrmIdentity): The identity whose cached entry will be removed if present.
        """
        logger.trace("Memory cache invalidate for {}", identity.cache_key())
        key = identity.cache_key()
        with self._lock:
            self._data.pop(key, None)


MEMORY_CACHE = StrmMemoryCache(STRM_PROXY_CACHE_TTL_SECONDS)