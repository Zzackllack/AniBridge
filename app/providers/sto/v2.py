from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.http_client import get as http_get

if TYPE_CHECKING:
    from aniworld.models import Episode

_LANG_ID_TO_NAME = {
    1: "German Dub",
    2: "English Dub",
    3: "German Sub",
}

_LANG_LABEL_TO_ID = {
    # German dubbed audio
    "deutsch": 1,
    "german": 1,
    # English dubbed audio
    "englisch": 2,
    "english": 2,
    # German subtitles
    "deutsch sub": 3,
    "german sub": 3,
    "deutsch untertitel": 3,
    "deutsche untertitel": 3,
    "german subtitle": 3,
}


def build_episode_url(base_url: str, slug: str, season: int, episode: int) -> str:
    """Build an S.to v2 episode URL from components.

    Parameters:
        base_url: Base S.to URL (scheme + host).
        slug: Series slug (e.g., "9-1-1").
        season: Season number.
        episode: Episode number.

    Returns:
        Fully-qualified episode URL for S.to v2.
    """
    base = base_url.rstrip("/")
    return f"{base}/serie/{slug}/staffel-{season}/episode-{episode}"


def fetch_episode_html(url: str) -> str:
    """Fetch raw episode HTML using the shared HTTP client.

    Parameters:
        url: Episode page URL to fetch.

    Returns:
        HTML response body as a string.
    """
    logger.debug("Fetching S.to episode HTML: {}", url)
    resp = http_get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


async def fetch_episode_html_async(url: str) -> str:
    """Asynchronously fetch episode HTML without blocking the event loop."""
    return await asyncio.to_thread(fetch_episode_html, url)


def parse_language_id(raw_id: str | None, label: str | None) -> Optional[int]:
    """Resolve a numeric language id from HTML attributes or label text.

    Parameters:
        raw_id: Raw language id attribute value.
        label: Human-readable language label (e.g., "Deutsch").

    Returns:
        Parsed integer language id, or None if no mapping is available.
    """
    if raw_id and str(raw_id).isdigit():
        return int(raw_id)
    if label:
        key = str(label).strip().lower()
        return _LANG_LABEL_TO_ID.get(key)
    return None


def parse_episode_providers(
    html_text: str, base_url: str
) -> Tuple[Dict[str, Dict[int, str]], List[int], List[str]]:
    """Parse providers and languages from S.to v2 episode HTML.

    Uses BeautifulSoup to locate provider buttons and builds a provider mapping
    (provider -> language id -> redirect URL), the ordered list of language ids
    seen, and the corresponding language names.

    Parameters:
        html_text: Episode page HTML content.
        base_url: Base S.to URL for resolving /r?t= redirects.

    Returns:
        Tuple of (providers, language_ids, language_names).
    """
    soup = BeautifulSoup(html_text, "html.parser")
    providers: Dict[str, Dict[int, str]] = {}
    languages: List[int] = []

    def _attr_text(value: object) -> str:
        return str(value or "").strip()

    buttons = soup.select("button[data-play-url][data-provider-name]")
    for btn in buttons:
        play_url = _attr_text(btn.get("data-play-url"))
        provider = _attr_text(btn.get("data-provider-name"))
        lang_label = _attr_text(btn.get("data-language-label"))
        lang_id = parse_language_id(_attr_text(btn.get("data-language-id")), lang_label)

        if not play_url or not provider or not lang_id:
            continue

        base = f"{base_url.rstrip('/')}/"
        redirect_url = urljoin(base, play_url)

        providers.setdefault(provider, {})[lang_id] = redirect_url
        if lang_id not in languages:
            languages.append(lang_id)

    language_names = [
        _LANG_ID_TO_NAME.get(lang_id, f"Unknown({lang_id})") for lang_id in languages
    ]
    return providers, languages, language_names


def enrich_episode_from_v2_html(
    *,
    episode: "Episode",
    html_text: str,
    base_url: str,
) -> None:
    """Populate an Episode with provider/language data parsed from v2 HTML.

    Parameters:
        episode: Episode instance to enrich.
        html_text: Episode page HTML content.
        base_url: Base S.to URL for resolving redirects.
    """
    providers, languages, language_names = parse_episode_providers(html_text, base_url)
    if not providers:
        logger.warning(
            "No S.to v2 providers parsed for {}", getattr(episode, "link", "<no link>")
        )
        return

    episode.provider = providers
    episode.provider_name = list(providers.keys())
    if languages:
        episode.language = languages
    if language_names:
        episode.language_name = language_names


def enrich_episode_from_v2_url(*, episode: "Episode", base_url: str) -> None:
    """Fetch v2 HTML for the Episode link and populate provider data.

    Uses the shared HTTP client to fetch HTML, then delegates parsing to
    BeautifulSoup-based helpers.

    Parameters:
        episode: Episode instance to enrich (must have a link).
        base_url: Base S.to URL for resolving redirects.
    """
    link = getattr(episode, "link", None)
    if not link:
        return
    try:
        html_text = fetch_episode_html(link)
    except Exception as exc:
        logger.warning("Failed to fetch S.to v2 HTML for {}: {}", link, exc)
        return
    enrich_episode_from_v2_html(episode=episode, html_text=html_text, base_url=base_url)
