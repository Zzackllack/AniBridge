from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.config import (
    PROVIDER_CHALLENGE_BACKOFF_SECONDS,
    PROVIDER_REDIRECT_TIMEOUT_SECONDS,
)
from app.core.downloader.errors import (
    ProviderVerificationRequiredError,
    UnsupportedProviderResponseError,
)
from app.core.downloader.provider_policy import (
    describe_url,
    fetch_verified_response,
)

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


def fetch_episode_html(url: str, *, base_url: str | None = None) -> str:
    """Fetch raw episode HTML using the shared HTTP client.

    Parameters:
        url: Episode page URL to fetch.

    Returns:
        HTML response body as a string.
    """
    allowed_origin = describe_url(base_url or url)
    logger.debug("Fetching S.to episode metadata from {}", allowed_origin)
    try:
        resp = fetch_verified_response(
            url,
            stage="Serienstream episode metadata",
            timeout_seconds=PROVIDER_REDIRECT_TIMEOUT_SECONDS,
            allowed_origin=allowed_origin,
        )
    except ProviderVerificationRequiredError as exc:
        raise ProviderVerificationRequiredError(
            "Serienstream episode metadata requires interactive verification; "
            "browser solving is not enabled.",
            stage=exc.stage,
            status_code=exc.status_code,
            host=exc.host,
            retry_after_seconds=PROVIDER_CHALLENGE_BACKOFF_SECONDS,
        ) from exc
    return resp.text


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


def parse_episode_provider_data(
    html_text: str, base_url: str
) -> dict[str, dict[str, str]]:
    """Return language-to-host redirect data for the local episode facade."""
    providers, _language_ids, _language_names = parse_episode_providers(
        html_text, base_url
    )
    configured_host = urlparse(base_url).netloc.lower()
    result: dict[str, dict[str, str]] = {}

    for provider_name, language_urls in providers.items():
        for language_id, redirect_url in language_urls.items():
            redirect_host = urlparse(redirect_url).netloc.lower()
            if redirect_host != configured_host:
                raise UnsupportedProviderResponseError(
                    "Serienstream episode metadata returned a redirect outside "
                    "the configured catalogue origin.",
                    stage="Serienstream episode metadata",
                    host=redirect_host or None,
                )
            language_name = _LANG_ID_TO_NAME.get(language_id)
            if language_name:
                result.setdefault(language_name, {})[provider_name] = redirect_url

    if not result:
        raise UnsupportedProviderResponseError(
            "Serienstream episode metadata contained no recognized provider buttons.",
            stage="Serienstream episode metadata",
            host=configured_host or None,
        )
    return result


def fetch_episode_provider_data(
    *, url: str, base_url: str
) -> dict[str, dict[str, str]]:
    """Fetch and parse Serienstream metadata on the configured verified origin."""
    html_text = fetch_episode_html(url, base_url=base_url)
    return parse_episode_provider_data(html_text, base_url)
