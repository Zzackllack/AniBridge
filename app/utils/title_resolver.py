from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List, Optional, Set, Tuple

import requests.exceptions
from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.logger import config as configure_logger
from app.utils.http_client import get as http_get  # type: ignore

from app.config import (
    CATALOG_SITES_LIST,
    CATALOG_SITE_CONFIGS,
    MEGAKINO_BASE_URL,
    STO_BASE_URL,
)
from app.providers import get_provider
from app.providers.base import CatalogProvider

configure_logger()

# Site-specific regex patterns for slug extraction
HREF_PATTERNS: Dict[str, re.Pattern[str]] = {
    "aniworld.to": re.compile(r"/anime/stream/([^/?#]+)"),
    "s.to": re.compile(r"/serie/([^/?#]+)"),
    "megakino": re.compile(r"/(?:serials|films)/\d+-([^./?#]+)"),
}

# Legacy pattern for backward compatibility
HREF_RE = HREF_PATTERNS["aniworld.to"]

_PROVIDER_CACHE: Dict[str, CatalogProvider | None] = {
    "megakino": get_provider("megakino"),
}

# suppress repetitive logging from _extract_slug by emitting each message only once
_extracted_any: bool = False
_no_slug_warned: bool = False


def _extract_slug(href: object, site: str = "aniworld.to") -> Optional[str]:
    """
    Extract the slug from an anchor href for a given site.

    Parameters:
        href (str): The href string to search for a slug.
        site (str): Site identifier selecting the site-specific extraction pattern (e.g., "aniworld.to", "s.to", "megakino").

    Returns:
        slug (str) or None: The captured slug if the href matches the site's URL pattern, None otherwise.

    Notes:
        Megakino URLs commonly use paths like /serials/<id>-<slug>.html or /films/<id>-<slug>.html.
    """
    global _extracted_any, _no_slug_warned
    pattern = HREF_PATTERNS.get(site, HREF_PATTERNS["aniworld.to"])
    href_text = str(href) if href is not None else ""
    m = pattern.search(href_text)

    if m:
        if not _extracted_any:
            logger.debug(
                "Slug extraction: first successful match found; further matches will not be logged."
            )
            _extracted_any = True
        return m.group(1)
    else:
        if not _no_slug_warned:
            logger.warning(
                "Slug extraction: encountered hrefs that do not match pattern; further misses will be suppressed."
            )
            _no_slug_warned = True
        return None


def build_index_from_html(html_text: str, site: str = "aniworld.to") -> Dict[str, str]:
    """
    Builds a mapping from series slug to display title by parsing the provided HTML for the specified site.

    Parses anchor tags and, using site-specific slug extraction rules, associates each extracted slug with the anchor's trimmed text if non-empty.

    Parameters:
        html_text (str): Raw HTML content to parse.
        site (str): Site identifier used to select slug extraction rules (e.g., "aniworld.to").

    Returns:
        Dict[str, str]: A dictionary mapping each discovered slug to its display title.
    """
    logger.info(f"Building index from HTML text for site: {site}.")
    soup = BeautifulSoup(html_text, "html.parser")
    result: Dict[str, str] = {}
    for a in soup.find_all("a"):
        href = a.get("href") or ""  # type: ignore
        slug = _extract_slug(str(href or ""), site)
        if not slug:
            logger.debug(f"Skipping anchor with no valid slug: {href}")
            continue

        title = (a.get_text() or "").strip()
        if title:
            result[slug] = title
            logger.debug(f"Added entry: slug={slug}, title={title}")
        else:
            logger.warning(f"Anchor with slug '{slug}' has empty title.")
    logger.success(f"Built index with {len(result)} entries for site: {site}.")
    return result


# -------- Live-Fetch + Cache (Multi-Site Support) --------

# Per-site caches
_cached_indices: Dict[str, Dict[str, str] | None] = {}  # site -> (slug -> title)
_cached_alts: Dict[str, Dict[str, List[str]] | None] = {}  # site -> (slug -> [titles])
_cached_at: Dict[str, float | None] = {}  # site -> timestamp


def _has_index_sources(site_cfg: Optional[dict]) -> bool:
    """
    Determine whether a site configuration provides alphabet index sources.

    Parameters:
        site_cfg (Optional[dict]): Site configuration mapping; may be None.

    Returns:
        `True` if `site_cfg` is None or contains a non-empty `alphabet_url` or `alphabet_html` entry, `False` otherwise.
    """
    if not site_cfg:
        return True
    return bool(site_cfg.get("alphabet_url") or site_cfg.get("alphabet_html"))


def _get_site_cfg(site: str) -> Optional[dict]:
    """
    Retrieve the configuration dictionary for a given site identifier, returning a Megakino default config when requested and no catalog entry exists.

    Parameters:
        site (str): Site identifier (e.g., "aniworld.to", "s.to", "megakino").

    Returns:
        dict or None: The site configuration from CATALOG_SITE_CONFIGS if present.
            For the special case "megakino" and no catalog entry, returns a default config with keys:
                - "base_url": MEGAKINO_BASE_URL
                - "alphabet_html": None
                - "alphabet_url": None
                - "titles_refresh_hours": 0.0
            Returns None if no configuration is found.
    """
    site_cfg = CATALOG_SITE_CONFIGS.get(site)
    if site_cfg:
        return site_cfg
    if site == "megakino":
        return {
            "base_url": MEGAKINO_BASE_URL,
            "alphabet_html": None,
            "alphabet_url": None,
            "titles_refresh_hours": 0.0,
        }
    return None


def _should_refresh(
    site: str, now: float, refresh_hours: float, *, has_index_sources: bool = True
) -> bool:
    """
    Determine whether the cached index for the given site needs refreshing.

    Checks if the site's in-memory index is missing, the cached timestamp is missing, or the elapsed time since the last refresh exceeds refresh_hours. A refresh is disabled when refresh_hours <= 0.

    Parameters:
        site (str): Site identifier whose cache is evaluated.
        now (float): Current UNIX timestamp in seconds.
        refresh_hours (float): Time-to-live in hours for the cache; <= 0 disables automatic refresh.

    Returns:
        bool: `True` if the cache should be refreshed, `False` otherwise.
    """
    logger.debug(
        f"Checking if cache should refresh for site={site}. now={now}, _cached_at={_cached_at.get(site)}, refresh_hours={refresh_hours}"
    )
    if not has_index_sources:
        logger.info(f"Search-only site detected for {site}; skipping refresh.")
        return False
    cached_index = _cached_indices.get(site)
    if isinstance(cached_index, dict) and not cached_index:
        logger.info(f"Cached index empty for {site}. Refresh needed.")
        return True
    if site not in _cached_indices or _cached_indices[site] is None:
        logger.info(f"No cached index found for {site}. Refresh needed.")
        return True
    if refresh_hours <= 0:
        logger.info(f"Refresh hours <= 0 for {site}. No refresh needed.")
        return False
    # Safely obtain the cached timestamp and handle None explicitly to satisfy static type checkers
    ts = _cached_at.get(site)
    if ts is None:
        logger.info(f"No cached timestamp found for {site}. Refresh needed.")
        return True
    expired = (now - ts) > refresh_hours * 3600.0
    if expired:
        logger.info(f"Cache expired for {site}. Refresh needed.")
    else:
        logger.debug(f"Cache still valid for {site}. No refresh needed.")
    return expired


def _parse_index_and_alts(
    html_text: str, site: str = "aniworld.to"
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Parse HTML and extract slug-to-title mappings and per-slug alternative titles for a given site.

    The function finds anchor tags whose href matches the site-specific slug pattern, uses the anchor text as the display title, and reads comma-separated alternative titles from the `data-alternative-title` attribute (trimmed of surrounding quotes and whitespace).

    Parameters:
        html_text (str): Raw HTML to parse.
        site (str): Site identifier used to select the href-to-slug extraction pattern (defaults to "aniworld.to").

    Returns:
        Tuple[Dict[str, str], Dict[str, List[str]]]: A tuple where the first element is a mapping from slug to display title, and the second element maps slug to a list of alternative titles. When a display title is present it will be included as the first element of its alternatives list.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    idx: Dict[str, str] = {}
    alts: Dict[str, List[str]] = {}

    for a in soup.find_all("a"):
        href = a.get("href") or ""  # type: ignore
        slug = _extract_slug(str(href or ""), site)
        if not slug:
            continue

        title = (a.get_text() or "").strip()
        alt_value = a.get("data-alternative-title")
        alt_raw = str(alt_value).strip() if alt_value is not None else ""
        # Split by comma and normalize pieces
        alt_list: List[str] = []
        if alt_raw:
            for piece in alt_raw.split(","):
                p = piece.strip().strip("'\"")
                if p:
                    alt_list.append(p)
        # Always include the main display title as an alternative as well
        if title and title not in alt_list:
            alt_list.insert(0, title)
        if title:
            idx[slug] = title
        if alt_list:
            alts[slug] = alt_list
    return idx, alts


def _fetch_index_from_url(
    url: str, site: str = "aniworld.to"
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Fetch an index HTML from a URL and parse it into slug-to-title and slug-to-alternatives mappings for the given site.

    Parameters:
        url (str): HTTP(S) URL to fetch the index HTML from.
        site (str): Site identifier used for site-specific parsing rules.

    Returns:
        Tuple[Dict[str, str], Dict[str, List[str]]]:
            - index: mapping of slug -> display title.
            - alternatives: mapping of slug -> list of alternative titles (main title appears first when present).

    Raises:
        requests.exceptions.RequestException: On network, TLS, or HTTP errors while fetching the URL.
    """
    logger.info(f"Fetching index from URL: {url} for site: {site}")
    try:
        resp = http_get(url, timeout=20)
        resp.raise_for_status()
        logger.success(f"Successfully fetched index from URL for site: {site}.")
        return _parse_index_and_alts(resp.text, site)
    except requests.exceptions.SSLError as e:
        logger.warning(
            f"TLS verification failed for {site} index; retrying with verify=False: {e}"
        )
        resp = http_get(url, timeout=20, verify=False)
        resp.raise_for_status()
        logger.success(
            f"Successfully fetched index from URL for site {site} with verify=False."
        )
        return _parse_index_and_alts(resp.text, site)
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch index from URL for {site}: {e}")
        raise


def _load_index_from_file(
    path: Path, site: str = "aniworld.to"
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Load a slug-to-title index and alternative titles from a local HTML file for the given site.

    Parameters:
        path (Path): Path to the local HTML file to parse.
        site (str): Site identifier used for slug extraction and parsing rules.

    Returns:
        Tuple[Dict[str, str], Dict[str, List[str]]]: A tuple (index, alternatives) where
            - index maps slug -> display title
            - alternatives maps slug -> list of alternative titles (first element is the main title when present)

    Behavior:
        - If the file does not exist, returns ({}, {}).
        - If reading or parsing fails, the exception is logged and re-raised.
    """
    logger.info(f"Loading index from file: {path} for site: {site}")
    if not path.exists():
        logger.warning(f"Configured HTML file does not exist: {path}")
        return {}, {}
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        logger.success(f"Successfully read file: {path} for site: {site}")
        return _parse_index_and_alts(html_text, site)
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"Failed to read file {path} for {site}: {e}")
        raise


def load_or_refresh_index(site: str = "aniworld.to") -> Dict[str, str]:
    """
    Obtain the slug-to-display-title index for a site, refreshing the per-site cache when appropriate.

    Prefers fetching a live HTML index (when configured) and falls back to a local HTML file; successful refreshes update the in-memory per-site index, alternative titles, and timestamp used for TTL checks.

    Returns:
        slug_to_title (Dict[str, str]): Mapping of slug -> display title for the requested site (empty if no index is available).
    """
    global _cached_indices, _cached_at, _cached_alts
    now = time.time()

    logger.debug(f"Starting load_or_refresh_index for site: {site}.")

    if site == "megakino":
        provider = _PROVIDER_CACHE.get("megakino")
        if provider:
            try:
                index = provider.load_or_refresh_index()
                _cached_indices[site] = index
                _cached_alts[site] = provider.load_or_refresh_alternatives()
                _cached_at[site] = now
                logger.info(f"Megakino sitemap index loaded: {len(index)} entries")
                return index
            except Exception as exc:
                logger.error(f"Megakino index refresh failed: {exc}")
                return _cached_indices.get(site) or {}

    site_cfg = _get_site_cfg(site)
    if not site_cfg:
        logger.warning(
            f"Unknown site '{site}' requested. Falling back to aniworld.to configuration."
        )
        site_cfg = CATALOG_SITE_CONFIGS.get("aniworld.to", {})

    url = str(site_cfg.get("alphabet_url", "") or "")
    html_file_value = site_cfg.get("alphabet_html")
    if isinstance(html_file_value, Path):
        html_file = html_file_value
    elif html_file_value:
        html_file = Path(html_file_value)
    else:
        html_file = None
    refresh_hours = float(site_cfg.get("titles_refresh_hours", 24.0))
    has_index_sources = _has_index_sources(site_cfg)

    if not has_index_sources:
        logger.info(
            f"No alphabet sources configured for {site}; running in search-only mode."
        )
        _cached_indices[site] = {}
        _cached_alts[site] = {}
        _cached_at[site] = now
        return {}

    # Check refresh condition
    if not _should_refresh(
        site, now, refresh_hours, has_index_sources=has_index_sources
    ):
        logger.info(f"Returning cached index for {site}.")
        return _cached_indices.get(site) or {}

    # 1) Try live URL (if set/not empty)
    index: Dict[str, str] = {}
    alts: Dict[str, List[str]] = {}
    url_stripped = url.strip()
    if url_stripped:
        try:
            logger.info(f"Attempting to fetch index from live URL for {site}.")
            index, alts = _fetch_index_from_url(url_stripped, site)
            if index:
                logger.success(
                    f"Index fetched from live URL for {site}. Updating cache."
                )
                _cached_indices[site] = index
                _cached_alts[site] = alts
                _cached_at[site] = now
                return index
            else:
                logger.warning(f"Fetched index from live URL is empty for {site}.")
        except Exception as e:
            logger.error(f"Error fetching index from live URL for {site}: {e}")
            # Fallback to file

    # 2) Fallback: Local file
    if html_file:
        try:
            logger.info(f"Attempting to load index from local file for {site}.")
            index, alts = _load_index_from_file(html_file, site)
            if index:
                logger.success(
                    f"Index loaded from local file for {site}. Updating cache."
                )
                _cached_indices[site] = index
                _cached_alts[site] = alts
                _cached_at[site] = now
                return index
            else:
                logger.warning(f"Index loaded from local file is empty for {site}.")
        except Exception as e:
            logger.error(f"Error loading index from local file for {site}: {e}")
    else:
        logger.warning(
            f"No local alphabet HTML configured for {site}; skipping file fallback."
        )

    # 3) Nothing found
    logger.warning(
        f"No index found from live URL or local file for {site}. Returning cached index (may be empty)."
    )
    if site not in _cached_indices:
        _cached_indices[site] = {}
    if site not in _cached_alts:
        _cached_alts[site] = {}
    if site not in _cached_at:
        _cached_at[site] = now
    return _cached_indices[site] or {}


def resolve_series_title(
    slug: Optional[str], site: str = "aniworld.to"
) -> Optional[str]:
    """
    Resolve the display title for a series slug on the given site.

    Parameters:
        slug (Optional[str]): The series slug (path identifier) to look up. If not provided or empty, the function returns `None`.
        site (str): Site identifier used to select which index to consult (e.g., "aniworld.to").

    Returns:
        Optional[str]: The resolved display title for the slug if found, `None` otherwise.
    """
    logger.debug(f"Resolving series title for slug: {slug}, site: {site}")
    if not slug:
        logger.warning("No slug provided to resolve_series_title.")
        return None
    index = load_or_refresh_index(site)
    title = index.get(slug)
    if title:
        logger.info(f"Resolved title for slug '{slug}' on {site}: {title}")
    else:
        logger.warning(f"No title found for slug: {slug} on {site}")
    return title


def load_or_refresh_alternatives(site: str = "aniworld.to") -> Dict[str, List[str]]:
    """
    Return a mapping of slugs to alternative display titles for the given site, refreshing the cached data if the site's TTL has expired.

    Each mapping value is a list of alternative titles where the primary/display title is the first element. If no alternatives are available, an empty dict is returned.
    Returns:
        Dict[str, List[str]]: Mapping from slug to list of alternative titles (primary title first).
    """
    global _cached_alts
    now = time.time()
    site_cfg = _get_site_cfg(site) or CATALOG_SITE_CONFIGS.get("aniworld.to", {})
    refresh_hours = float(site_cfg.get("titles_refresh_hours", 24.0))
    has_index_sources = _has_index_sources(site_cfg)
    if _should_refresh(site, now, refresh_hours, has_index_sources=has_index_sources):
        # Trigger a refresh through the main loader
        load_or_refresh_index(site)
    return _cached_alts.get(site) or {}


def _normalize_tokens(s: str) -> Set[str]:
    """
    Extract unique lowercase tokens by splitting the input on non-alphanumeric characters.

    Parameters:
        s (str): Input text to tokenize; non-alphanumeric characters are treated as separators.

    Returns:
        Set[str]: Unique lowercase tokens extracted from the input.
    """
    return set("".join(ch.lower() if ch.isalnum() else " " for ch in s).split())


def _normalize_alnum(s: str) -> str:
    """Lowercase and filter to alphanumeric characters."""
    return "".join(ch.lower() for ch in s if ch.isalnum())


def _build_sto_search_terms(query: str) -> List[str]:
    """Build ordered S.to search variants from a raw query.

    Returns the raw query, a compact alphanumeric-only variant, and a dashed
    variant when the compact form is numeric with length >= 3. Empty values are
    filtered and the list is de-duplicated while preserving order.
    """
    raw = (query or "").strip()
    if not raw:
        return []
    terms = [raw]
    compact = _normalize_alnum(raw)
    if compact and compact != raw:
        terms.append(compact)
    if compact.isdigit() and len(compact) >= 3:
        dashed = "-".join(compact)
        if dashed not in terms:
            terms.append(dashed)
    return list(dict.fromkeys(t for t in terms if t))


def _search_sto_slug(query: str) -> Optional[str]:
    """Resolve an S.to slug using the public suggest API.

    Queries /api/search/suggest for each term variant and scores results by
    token overlap with a large boost for exact normalized matches. Returns the
    best matching slug or None when no result can be found.
    """
    terms = _build_sto_search_terms(query)
    if not terms:
        return None
    base_url = STO_BASE_URL.rstrip("/")
    best_slug: Optional[str] = None
    best_score = -1
    q_tokens = _normalize_tokens(query)
    q_norm = _normalize_alnum(query)

    for term in terms:
        try:
            request_url = f"{base_url}/api/search/suggest?term={quote(term)}"
            resp = http_get(request_url, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.debug("S.to suggest lookup failed for term '{}': {}", term, exc)
            continue
        except (json.JSONDecodeError, ValueError) as exc:
            logger.debug("S.to suggest lookup failed for term '{}': {}", term, exc)
            continue

        shows = payload.get("shows") if isinstance(payload, dict) else None
        if not isinstance(shows, list):
            continue

        for entry in shows:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            entry_url = str(entry.get("url") or "").strip()
            slug = _extract_slug(entry_url, "s.to")
            if not slug or not name:
                continue

            t_tokens = _normalize_tokens(name)
            score = len(q_tokens & t_tokens)
            t_norm = _normalize_alnum(name)
            if q_norm and t_norm and q_norm == t_norm:
                score += 100
            if score > best_score:
                best_score = score
                best_slug = slug

    return best_slug


def slug_from_query(q: str, site: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Find the best-matching site and slug for a free-text query by comparing token overlap with titles and alternative titles.

    Parameters:
        q (str): Free-text query used to match against series titles.
        site (Optional[str]): If provided, restricts the search to this site; otherwise searches all configured sites.

    Returns:
        Optional[Tuple[str, str]]: `(site, slug)` of the best match, `None` if the query is empty or no match is found.
    """
    if not q:
        return None

    def _search_sites(sites: List[str]) -> Optional[Tuple[str, str]]:
        q_tokens = _normalize_tokens(q)
        best_slug: Optional[str] = None
        best_site: Optional[str] = None
        best_score = 0

        for search_site in sites:
            index = load_or_refresh_index(search_site)  # slug -> display title
            if not index and _has_index_sources(_get_site_cfg(search_site)):
                continue
            if not index:
                direct = _slug_from_search_only_query(q, search_site)
                if direct:
                    return (search_site, direct)
                continue
            alts = load_or_refresh_alternatives(search_site)  # slug -> [titles]

            for slug, main_title in index.items():
                # Start with main title tokens
                titles_for_slug: List[str] = [main_title]
                alt_list = alts.get(slug)
                if alt_list:
                    titles_for_slug.extend(alt_list)

                # Evaluate best overlap score across all candidate titles
                local_best = 0
                for candidate in titles_for_slug:
                    t_tokens = _normalize_tokens(candidate)
                    inter = len(q_tokens & t_tokens)
                    if inter > local_best:
                        local_best = inter

                if local_best > best_score:
                    best_score = local_best
                    best_slug = slug
                    best_site = search_site

        if best_slug and best_site:
            return (best_site, best_slug)
        for search_site in sites:
            if search_site == "s.to":
                api_slug = _search_sto_slug(q)
                if api_slug:
                    return (search_site, api_slug)
        return None

    if site:
        return _search_sites([site])

    primary_sites = [s for s in CATALOG_SITES_LIST if s != "megakino"]
    result = _search_sites(primary_sites)
    if result:
        return result

    if "megakino" in CATALOG_SITES_LIST or "megakino" in _PROVIDER_CACHE:
        raw = (q or "").strip()
        direct_slug = _extract_slug(raw, "megakino")
        if direct_slug:
            return ("megakino", direct_slug)
        lowered = raw.lower()
        if _MEGAKINO_SLUG_RE.match(lowered):
            return ("megakino", lowered)

    fallback_sites = [s for s in CATALOG_SITES_LIST if s == "megakino"]
    if fallback_sites:
        return _search_sites(fallback_sites)
    return None


_MEGAKINO_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _slug_from_search_only_query(q: str, site: str) -> Optional[str]:
    """
    Derive a normalized slug from a free-text query for sites that lack an alphabet index.

    For sites like Megakino, this will validate the query as a slug format or attempt a site search to resolve a slug; for other search-only sites it returns the cleaned candidate slug.

    Parameters:
        q (str): Free-text query or URL that may contain a slug.
        site (str): Site identifier (e.g., "megakino") used to select site-specific validation.

    Returns:
        str or None: The resolved slug in lowercase if one can be determined, otherwise `None`.
    """
    raw = (q or "").strip()
    if not raw:
        return None
    candidate = _extract_slug(raw, site) or raw
    candidate = candidate.strip().lower()
    if site == "megakino":
        logger.debug("Megakino search-only query: '{}'", raw)
        provider = _PROVIDER_CACHE.get("megakino")
        if provider:
            try:
                match = provider.search_slug(raw)
            except Exception as exc:
                logger.debug("Megakino provider search failed: {}", exc)
                match = None
            if match and match.slug:
                logger.debug("Megakino provider search returned slug: '{}'", match.slug)
                return match.slug
        if _MEGAKINO_SLUG_RE.match(candidate):
            logger.debug("Megakino query treated as slug: '{}'", candidate)
            return candidate
        searched = _search_megakino_slug(raw)
        if searched:
            logger.debug("Megakino search returned slug: '{}'", searched)
        else:
            logger.debug("Megakino search returned no slug for '{}'", raw)
        return searched
    return candidate if candidate else None


def _search_megakino_slug(query: str) -> Optional[str]:
    """
    Find the first Megakino slug that matches a free-text search query.

    Parameters:
        query (str): Free-text search phrase to send to the Megakino search API.

    Returns:
        str or None: The first matching slug if a result is found, `None` otherwise.
    """
    provider = _PROVIDER_CACHE.get("megakino")
    if not provider:
        return None
    try:
        match = provider.search_slug(query)
    except Exception as exc:
        logger.debug("Megakino provider search failed: {}", exc)
        return None
    return match.slug if match else None
