from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.http_client import get as http_get
from app.utils.release_dates import parse_release_at_from_html

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
    """
    Extract provider redirect URLs and language metadata from an S.to v2 episode HTML page.

    Parameters:
        html_text (str): Raw HTML of the episode page.
        base_url (str): Base S.to URL used to resolve relative provider/play URLs.

    Returns:
        providers (Dict[str, Dict[int, str]]): Mapping from provider name to a mapping of language ID to resolved redirect URL.
        language_ids (List[int]): Ordered list of language IDs found on the page.
        language_names (List[str]): List of human-readable language names corresponding to `language_ids`.
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


def parse_release_at_from_sto_html(html_text: str) -> Optional[datetime]:
    """
    Extract the UTC release timestamp from S.to v2 episode HTML, if present.

    Parameters:
        html_text (str): Raw HTML of the episode page.

    Returns:
        datetime | None: UTC datetime of the episode's release, or None if no timestamp is found.
    """
    return parse_release_at_from_html(html_text)


def enrich_episode_from_v2_html(
    *,
    episode: "Episode",
    html_text: str,
    base_url: str,
) -> None:
    """
    Enrich an Episode object with provider, language, and release metadata extracted from S.to v2 HTML.

    If no providers are found, logs a warning (including the episode link when available) and returns without modifying the episode.

    Parameters:
        episode (Episode): Episode instance to enrich; this function mutates the object.
        html_text (str): HTML content of the S.to v2 episode page.
        base_url (str): Base S.to URL used to resolve provider redirect URLs and other relative links.

    Side effects:
        - Sets episode.provider to a mapping of providers to language -> redirect URL.
        - Sets episode.provider_name to the list of provider names.
        - Sets episode.language to the ordered list of language IDs when available.
        - Sets episode.language_name to the list of human-readable language names when available.
        - If a release timestamp is found, sets episode._anibridge_release_at to that datetime.
        - Always sets episode._anibridge_sto_v2_html to the raw provided HTML.
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

    release_at = parse_release_at_from_sto_html(html_text)
    if release_at is not None:
        setattr(episode, "_anibridge_release_at", release_at)
    setattr(episode, "_anibridge_sto_v2_html", html_text)


def enrich_episode_from_v2_url(*, episode: "Episode", base_url: str) -> None:
    """
    Enriches an Episode with provider, language, and release information by fetching and parsing its S.to v2 page.

    If the episode has no link, the function returns without modifying the episode. On successful fetch and parse, the function updates the episode's provider-related attributes (e.g., `provider`, `provider_name`, `language`, `language_name`) and may set `_anibridge_release_at` (datetime or None) and `_anibridge_sto_v2_html` (raw HTML string).

    Parameters:
        episode (Episode): Episode instance to enrich; must have a `link` attribute to perform fetching.
        base_url (str): Base S.to URL used to resolve provider redirect URLs.
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
