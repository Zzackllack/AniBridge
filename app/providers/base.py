from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import re

import requests.exceptions
from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.http_client import get as http_get


@dataclass
class ProviderMatch:
    """Represents a catalog search result with a matched slug and score.

    Attributes:
        slug: The catalog entry slug (e.g., 'one-piece' or 'attack-on-titan').
        score: The match score indicating query relevance (higher is better).
    """

    slug: str
    score: int


@dataclass
class CatalogProvider:
    """Base class for standardized catalog site provider implementations.

    CatalogProvider provides a generic interface for catalog sites (e.g.,
    AniWorld, s.to, Megakino) with slug parsing, index loading, alternative
    title handling, and query matching. Subclasses can override methods to
    implement site-specific behavior while conforming to a common API.

    Attributes:
        key: Unique identifier for the provider (e.g., 'aniworld.to', 's.to').
        slug_pattern: Compiled regex pattern for extracting slugs from URLs.
        base_url: The provider's base URL for catalog browsing.
        alphabet_url: URL for fetching the alphabetical title index.
        alphabet_html: Optional local HTML file path for the title index.
        titles_refresh_hours: How often to refresh the cached index (0 = never).
        default_languages: Default language preferences for this catalog.
        release_group: Release group label used for torrent/magnet metadata.
        allow_insecure_tls: Whether to allow insecure TLS connections.
        _cached_index: Internal cache mapping slugs to primary titles.
        _cached_alts: Internal cache mapping slugs to alternative titles.
        _cached_at: Timestamp (Unix epoch) of the last successful index load.
    """

    key: str
    slug_pattern: re.Pattern[str]
    base_url: str
    alphabet_url: str
    alphabet_html: Optional[Path]
    titles_refresh_hours: float
    default_languages: List[str]
    release_group: str
    allow_insecure_tls: bool = False
    _cached_index: Dict[str, str] | None = field(default=None, init=False)
    _cached_alts: Dict[str, List[str]] | None = field(default=None, init=False)
    _cached_at: float | None = field(default=None, init=False)

    def slug_from_href(self, href: object) -> Optional[str]:
        """Extract the slug from an href attribute using the provider's slug pattern.

        Parameters:
            href: The href value to parse (typically from an HTML anchor tag).

        Returns:
            The extracted slug if the pattern matches, otherwise None.
        """
        match = self.slug_pattern.search(str(href or ""))
        if match:
            return match.group(1)
        return None

    def parse_index_and_alts(
        self, html_text: str
    ) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """Parse HTML to extract the catalog index and alternative titles.

        This method scans all anchor tags in the provided HTML, extracts slugs
        using the provider's slug pattern, and builds a mapping of slugs to
        primary titles and alternative title lists. The data-alternative-title
        attribute is parsed as a comma-separated list of alternative titles.

        Parameters:
            html_text: The raw HTML content to parse.

        Returns:
            A tuple of (index_dict, alts_dict) where:
            - index_dict maps slug to primary title
            - alts_dict maps slug to a list of alternative titles (including primary)
        """
        soup = BeautifulSoup(html_text, "html.parser")
        idx: Dict[str, str] = {}
        alts: Dict[str, List[str]] = {}

        for anchor in soup.find_all("a"):
            href = anchor.get("href") or ""  # type: ignore
            slug = self.slug_from_href(href)
            if not slug:
                continue

            title = (anchor.get_text() or "").strip()
            # Extract data-alternative-title attribute safely, consistent with title_resolver.py
            alt_attr = anchor.get("data-alternative-title")  # type: ignore
            alt_raw = ""
            if alt_attr is not None:
                # Convert to string before stripping to avoid errors if the
                # attribute value is not already a string.
                alt_raw = str(alt_attr).strip()
            alt_list: List[str] = []
            if alt_raw:
                for piece in alt_raw.split(","):
                    entry = piece.strip().strip("'\"")
                    if entry:
                        alt_list.append(entry)
            if title and title not in alt_list:
                alt_list.insert(0, title)
            if title:
                idx[slug] = title
            if alt_list:
                alts[slug] = alt_list
        return idx, alts

    def _has_index_sources(self) -> bool:
        """Check if the provider has configured index sources.

        Returns:
            True if either alphabet_url or alphabet_html is configured.
        """
        return bool(self.alphabet_url or self.alphabet_html)

    def _should_refresh(self, now: float) -> bool:
        """Determine if the cached index should be refreshed.

        Parameters:
            now: Current Unix timestamp (from time.time()).

        Returns:
            True if the index cache is stale and should be refreshed, False otherwise.
        """
        if not self._has_index_sources():
            return False
        if self._cached_index is None:
            return True
        if isinstance(self._cached_index, dict) and not self._cached_index:
            return True
        if self.titles_refresh_hours <= 0:
            return False
        if self._cached_at is None:
            return True
        age = now - self._cached_at
        return age > self.titles_refresh_hours * 3600.0

    def _fetch_index_from_url(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """Fetch the catalog index from the configured alphabet URL.

        This method downloads the alphabet page from the provider's alphabet_url
        and parses it to extract the index and alternative titles. If TLS
        verification fails and allow_insecure_tls is enabled, it retries with
        verification disabled.

        Returns:
            A tuple of (index_dict, alts_dict) as returned by parse_index_and_alts.

        Raises:
            requests.exceptions.SSLError: If TLS verification fails and
                allow_insecure_tls is False.
            requests.exceptions.HTTPError: If the HTTP request fails.
        """
        url = (self.alphabet_url or "").strip()
        if not url:
            return {}, {}
        logger.info("Fetching index from URL: {} for site: {}", url, self.key)
        try:
            resp = http_get(url, timeout=20)
            resp.raise_for_status()
            return self.parse_index_and_alts(resp.text)
        except requests.exceptions.SSLError as exc:
            if not self.allow_insecure_tls:
                logger.error(
                    "TLS verification failed for {} index: {}",
                    self.key,
                    exc,
                )
                raise
            logger.warning(
                "TLS verification failed for {} index; retrying with verify=False: {}",
                self.key,
                exc,
            )
            resp = http_get(url, timeout=20, verify=False)
            resp.raise_for_status()
            return self.parse_index_and_alts(resp.text)

    def _load_index_from_file(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """Load the catalog index from a local HTML file.

        This method reads the alphabet page from the provider's configured
        alphabet_html file path and parses it to extract the index.

        Returns:
            A tuple of (index_dict, alts_dict) as returned by parse_index_and_alts.
        """
        if not self.alphabet_html:
            return {}, {}
        path = self.alphabet_html
        logger.info("Loading index from file: {} for site: {}", path, self.key)
        if not path.exists():
            logger.warning("Configured HTML file does not exist: {}", path)
            return {}, {}
        html_text = path.read_text(encoding="utf-8", errors="replace")
        return self.parse_index_and_alts(html_text)

    def load_or_refresh_index(self) -> Dict[str, str]:
        """Load or refresh the catalog index, returning cached data if fresh.

        This method returns the cached index if it exists and is not stale.
        Otherwise, it fetches the index from the alphabet URL (with fallback
        to the local HTML file if the URL fetch fails). If no index sources
        are configured, it operates in search-only mode with an empty index.

        Returns:
            A dictionary mapping slugs to primary titles.
        """
        now = time.time()
        if not self._has_index_sources():
            logger.info(
                "No alphabet sources configured for {}; using search-only mode.",
                self.key,
            )
            self._cached_index = {}
            self._cached_alts = {}
            self._cached_at = now
            return {}

        if not self._should_refresh(now):
            return self._cached_index or {}

        index: Dict[str, str] = {}
        alts: Dict[str, List[str]] = {}
        try:
            index, alts = self._fetch_index_from_url()
        except Exception as exc:
            logger.error("Error fetching index from live URL for {}: {}", self.key, exc)

        if index:
            self._cached_index = index
            self._cached_alts = alts
            self._cached_at = now
            return index

        try:
            index, alts = self._load_index_from_file()
        except Exception as exc:
            logger.error(
                "Error loading index from local file for {}: {}", self.key, exc
            )

        if index:
            self._cached_index = index
            self._cached_alts = alts
            self._cached_at = now
            return index

        self._cached_index = self._cached_index or {}
        self._cached_alts = self._cached_alts or {}
        self._cached_at = self._cached_at or now
        return self._cached_index

    def load_or_refresh_alternatives(self) -> Dict[str, List[str]]:
        """Load or refresh the alternative titles mapping.

        This method ensures the index is loaded and returns the cached
        alternative titles. If the index needs refreshing, it triggers
        load_or_refresh_index first.

        Returns:
            A dictionary mapping slugs to lists of alternative titles.
        """
        now = time.time()
        if self._has_index_sources() and self._should_refresh(now):
            self.load_or_refresh_index()
        return self._cached_alts or {}

    def resolve_title(self, slug: Optional[str]) -> Optional[str]:
        """Resolve a slug to its primary title.

        Parameters:
            slug: The catalog entry slug to resolve.

        Returns:
            The primary title for the given slug, or None if not found.
        """
        if not slug:
            return None
        index = self.load_or_refresh_index()
        return index.get(slug)

    def _normalize_tokens(self, text: str) -> List[str]:
        """Normalize text into a list of lowercase alphanumeric tokens.

        This method removes punctuation, converts to lowercase, and filters
        out numeric-only tokens to produce a normalized token list for matching.

        Parameters:
            text: The text to normalize.

        Returns:
            A list of normalized tokens.
        """
        raw = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
        return [tok for tok in raw.split() if tok and not tok.isdigit()]

    def _score_tokens(self, query_tokens: List[str], title_tokens: List[str]) -> int:
        """Calculate the match score between query and title tokens.

        The score is the count of tokens that appear in both sets.

        Parameters:
            query_tokens: Normalized tokens from the search query.
            title_tokens: Normalized tokens from a candidate title.

        Returns:
            The number of matching tokens (0 if no match).
        """
        if not query_tokens or not title_tokens:
            return 0
        return len(set(query_tokens) & set(title_tokens))

    def match_query(self, query: str) -> Optional[ProviderMatch]:
        """Find the best matching catalog entry for a query string.

        This method tokenizes the query, scores all catalog entries against it,
        and returns the slug with the highest score. Both primary titles and
        alternative titles are considered during matching.

        Parameters:
            query: The search query string.

        Returns:
            A ProviderMatch with the best slug and score, or None if no match.
        """
        if not query:
            return None
        query_tokens = self._normalize_tokens(query)
        if not query_tokens:
            return None
        index = self.load_or_refresh_index()
        if not index:
            return None
        alts = self.load_or_refresh_alternatives()
        best_slug: Optional[str] = None
        best_score = 0
        for slug, main_title in index.items():
            titles = [main_title]
            alt_list = alts.get(slug)
            if alt_list:
                titles.extend(alt_list)
            local_best = 0
            for candidate in titles:
                score = self._score_tokens(
                    query_tokens, self._normalize_tokens(candidate)
                )
                if score > local_best:
                    local_best = score
            if local_best > best_score:
                best_score = local_best
                best_slug = slug
        if best_slug and best_score > 0:
            return ProviderMatch(slug=best_slug, score=best_score)
        return None

    def search_slug(self, query: str) -> Optional[ProviderMatch]:
        """Search for a catalog entry matching the query.

        This is an alias for match_query, provided for API consistency.

        Parameters:
            query: The search query string.

        Returns:
            A ProviderMatch with the best slug and score, or None if no match.
        """
        return self.match_query(query)
