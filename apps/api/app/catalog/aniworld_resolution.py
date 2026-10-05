"""User-local provider resolution through bounded host parsing.

This is not the worker parser: host offers and expiring media URLs never leave
this local attempt. Host capabilities and live host evidence remain separate gates.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from catalog_core.identity import path as validate_path

from app.core.downloader.errors import ProviderResolutionError
from app.hosts import catalog_sources

from .resolution_transport import Budget, ResolutionError

LANGUAGES = {"de-dub": "1", "en-sub": "2", "de-sub": "3"}


@dataclass(frozen=True)
class Media:
    host: str
    url: str = field(repr=False)


def offers(
    html: str, origin: str, language: str, provider="aniworld.to"
) -> dict[str, str]:
    if provider == "megakino":
        from .megakino_resolution import offers as movie_offers

        return movie_offers(html, origin, language)
    if provider == "s.to":
        # Keep the provider's explicit label semantics. AniWorld numeric keys
        # describe a different language set and cannot be reused here.
        label = {"de-dub": "Deutsch", "en-dub": "Englisch"}.get(language)
        if label is None:
            raise ResolutionError("unavailable")
        soup = BeautifulSoup(html, "html.parser")
        found = {}
        for row in soup.select("button[data-play-url][data-provider-name]"):
            if row.get("data-language-label") != label:
                continue
            name, target = row.get("data-provider-name"), row.get("data-play-url")
            if name and target and name not in found:
                found[name] = urljoin(origin, target)
        return found
    code = LANGUAGES.get(language)
    if code is None:
        raise ResolutionError("unavailable")
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for row in soup.select("li[data-lang-key][data-link-target]"):
        if row.get("data-lang-key") != code:
            continue
        label = row.find("h4")
        anchor = row.find("a", href=True)
        if label is not None and anchor is not None:
            name = label.get_text(" ", strip=True)
            if name and name not in found:
                found[name] = urljoin(origin, anchor["href"])
    return found


def resolve(
    payload: dict,
    origin: str,
    hosts: tuple[str, ...],
    budget: Budget,
    *,
    source_parser=None,
    redirect_parser=None,
) -> Media:
    if payload["provider"] not in ("aniworld.to", "s.to", "megakino"):
        raise ResolutionError("extraction_error")
    path = validate_path(payload["path"])
    if payload["provider"] == "megakino" and (
        payload.get("kind") != "movie"
        or re.fullmatch(r"/films/[1-9][0-9]*-[^/]+\.html", path) is None
    ):
        raise ResolutionError("extraction_error")
    get = budget.get_megakino if payload["provider"] == "megakino" else budget.get
    page = get(origin.rstrip("/") + path, origin=origin)
    available = offers(page.text, origin, payload["language"], payload["provider"])
    choices = [
        host
        for host in hosts
        if host in available and host in catalog_sources.SUPPORTED
    ][:3]
    if not choices:
        raise ResolutionError("unavailable")
    if source_parser is None or redirect_parser is None:
        # Reuse the installed parser's pure decoding function, never its network
        # helper (which has browser/curl fallbacks outside this attempt budget).
        from app.utils.aniworld_compat import prepare_aniworld_home

        prepare_aniworld_home()
        from aniworld.extractors.provider.voe import extract_voe_source_from_html

        from app.core.downloader.extractors.voe import choose_redirect_candidate

        source_parser = extract_voe_source_from_html
        redirect_parser = choose_redirect_candidate
    last = "extraction_error"
    for host in choices:
        url, visited = available[host], set()
        try:
            while url and url not in visited:
                visited.add(url)
                page = budget.get(url)
                visited.add(page.url)
                source = (
                    source_parser(page.text)
                    if host == "VOE"
                    else catalog_sources.html_source(host, page.text)
                )
                if not source and host == "Filemoon":
                    api_url = catalog_sources.filemoon_api(page.url)
                    if api_url is not None:
                        try:
                            observed = budget.get(api_url, origin=page.url)
                            source = catalog_sources.filemoon_source(observed.text)
                        except ResolutionError as exc:
                            # A legacy HTML player may have no API. Challenges
                            # still stop the attempt; no unbudgeted fallback.
                            if exc.code != "unavailable":
                                raise
                budget.remaining()
                if source:
                    budget.validate_url(source, stage="resolved media")
                    return Media(host, source)
                url = redirect_parser(page.text, page.url) if host == "VOE" else None
        except ResolutionError as exc:
            if exc.code == "challenge":
                raise
            last = exc.code
        except ValueError, TypeError, ProviderResolutionError:
            last = "extraction_error"
    raise ResolutionError(last)
