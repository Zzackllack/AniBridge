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
    slug: str
    score: int


@dataclass
class CatalogProvider:
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
        match = self.slug_pattern.search(str(href or ""))
        if match:
            return match.group(1)
        return None

    def parse_index_and_alts(
        self, html_text: str
    ) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        soup = BeautifulSoup(html_text, "html.parser")
        idx: Dict[str, str] = {}
        alts: Dict[str, List[str]] = {}

        for anchor in soup.find_all("a"):
            href = anchor.get("href") or ""  # type: ignore
            slug = self.slug_from_href(href)
            if not slug:
                continue

            title = (anchor.get_text() or "").strip()
            alt_raw = (anchor.get("data-alternative-title") or "").strip()  # type: ignore
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
        return bool(self.alphabet_url or self.alphabet_html)

    def _should_refresh(self, now: float) -> bool:
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
        if not self.alphabet_html:
            return {}, {}
        path = self.alphabet_html
        logger.info("Loading index from file: {} for site: {}", path, self.key)
        if not path.exists():
            logger.warning("Configured HTML file does not exist: {}", path)
            return {}, {}
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        return self.parse_index_and_alts(html_text)

    def load_or_refresh_index(self) -> Dict[str, str]:
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
        now = time.time()
        if self._has_index_sources() and self._should_refresh(now):
            self.load_or_refresh_index()
        return self._cached_alts or {}

    def resolve_title(self, slug: Optional[str]) -> Optional[str]:
        if not slug:
            return None
        index = self.load_or_refresh_index()
        return index.get(slug)

    def _normalize_tokens(self, text: str) -> List[str]:
        raw = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
        return [tok for tok in raw.split() if tok and not tok.isdigit()]

    def _score_tokens(self, query_tokens: List[str], title_tokens: List[str]) -> int:
        if not query_tokens or not title_tokens:
            return 0
        return len(set(query_tokens) & set(title_tokens))

    def match_query(self, query: str) -> Optional[ProviderMatch]:
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
        return self.match_query(query)
