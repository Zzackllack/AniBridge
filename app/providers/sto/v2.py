from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup  # type: ignore
from loguru import logger

from app.utils.http_client import get as http_get

_LANG_ID_TO_NAME = {
    1: "German Dub",
    2: "English Dub",
    3: "German Sub",
}

_LANG_LABEL_TO_ID = {
    "deutsch": 1,
    "german": 1,
    "englisch": 2,
    "english": 2,
}


@dataclass(frozen=True)
class StoProviderEntry:
    provider: str
    language_id: int
    redirect_url: str
    language_label: str | None = None


def build_episode_url(base_url: str, slug: str, season: int, episode: int) -> str:
    base = base_url.rstrip("/")
    return f"{base}/serie/{slug}/staffel-{season}/episode-{episode}"


def fetch_episode_html(url: str) -> str:
    logger.debug("Fetching S.to episode HTML: {}", url)
    resp = http_get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_language_id(raw_id: str | None, label: str | None) -> Optional[int]:
    if raw_id and str(raw_id).isdigit():
        return int(raw_id)
    if label:
        key = str(label).strip().lower()
        return _LANG_LABEL_TO_ID.get(key)
    return None


def parse_episode_providers(
    html_text: str, base_url: str
) -> Tuple[Dict[str, Dict[int, str]], List[int], List[str]]:
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

        redirect_url = play_url
        if redirect_url.startswith("/"):
            redirect_url = f"{base_url.rstrip('/')}{redirect_url}"

        providers.setdefault(provider, {})[lang_id] = redirect_url
        if lang_id not in languages:
            languages.append(lang_id)

    language_names = [
        _LANG_ID_TO_NAME.get(lang_id, f"Unknown({lang_id})") for lang_id in languages
    ]
    return providers, languages, language_names


def enrich_episode_from_v2_html(
    *,
    episode,
    html_text: str,
    base_url: str,
) -> None:
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


def enrich_episode_from_v2_url(*, episode, base_url: str) -> None:
    link = getattr(episode, "link", None)
    if not link:
        return
    html_text = fetch_episode_html(link)
    enrich_episode_from_v2_html(episode=episode, html_text=html_text, base_url=base_url)
