"""Resolve a frozen Filmo source through a bounded first-party CSRF session."""

import json
from urllib.parse import quote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from catalog_core import identity
from catalog_core.providers import filmo as filmo_parser

from app.core.downloader.provider_policy import looks_like_verification_page
from app.hosts import detect_host

from .resolution_transport import Budget, ResolutionError


def _filmo_offer_token(body: bytes, metadata: dict, anchor: str) -> str:
    """Pair the selected normalized offer with its ephemeral detail-page token."""
    try:
        from catalog_core.release_metadata import same_selection

        parsed = filmo_parser.parse(body, "detail", metadata["path"])
        expected = {key: value for key, value in metadata.items() if key != "path"}
        current = next(
            (offer for offer in parsed.offers if offer["variant_anchor"] == anchor),
            None,
        )
        if current is None or not same_selection(current, expected):
            raise ResolutionError("stale_selection")
        soup = BeautifulSoup(body, "html.parser")
        tokens = []
        for row in soup.select(".provider-row"):
            language_node = row.select_one(".provider-row__lang")
            language = (
                language_node.get_text(" ", strip=True) if language_node else "unknown"
            )
            for chip in row.select("[data-provider-chip]"):
                token = chip.get("data-p")
                try:
                    candidate = filmo_parser.offer_metadata(
                        chip.get("data-movie-link-id") or "",
                        chip.get("aria-label") or "unknown",
                        language,
                        [
                            node.get_text(" ", strip=True)
                            for node in chip.select(".provider-chip__metadata-tag")
                        ],
                    )
                except ValueError, TypeError:
                    continue
                if (
                    same_selection(candidate, expected)
                    and isinstance(token, str)
                    and 1 <= len(token.encode()) <= 4096
                ):
                    tokens.append(token)
        if not tokens:
            raise ResolutionError("stale_selection")
        return tokens[0]
    except ResolutionError:
        raise
    except StopIteration:
        raise ResolutionError("stale_selection") from None
    except ValueError, KeyError, IndexError, TypeError:
        raise ResolutionError("extraction_error") from None


def _filmo_embed(
    payload: dict, origin: str, budget: Budget, *, anchor: str, metadata: dict
) -> tuple[str, str]:
    """Mint and resolve one exact Filmo offer while keeping its session local."""
    path = identity.path(payload["path"])
    require_path = filmo_parser.MOVIE.fullmatch(path)
    if payload.get("kind") != "movie" or require_path is None:
        raise ResolutionError("extraction_error")
    expected_host = metadata.get("host")
    if expected_host not in {"VOE", "Byse"} or len(anchor) > 256:
        raise ResolutionError("extraction_error")
    origin_url = urlsplit(origin)
    if (
        origin_url.scheme != "https"
        or not origin_url.hostname
        or origin_url.username
        or origin_url.password
        or origin_url.query
        or origin_url.fragment
        or origin_url.path not in {"", "/"}
    ):
        raise ResolutionError("extraction_error")
    root = origin.rstrip("/")
    cookies = httpx.Cookies()

    for attempt in range(2):  # one fresh detail/CSRF recovery after HTTP 419
        detail = budget.filmo_exchange(
            "GET",
            root + path,
            origin=origin,
            cookies=cookies,
            headers={"Accept": "text/html"},
        )
        if detail.status in (403, 429):
            raise ResolutionError(
                "challenge" if detail.status == 403 else "transport_failure"
            )
        if detail.status != 200:
            raise ResolutionError(
                "unavailable" if detail.status in (404, 410) else "transport_failure"
            )
        if looks_like_verification_page(
            detail.body[:8192].decode("utf-8", errors="replace")
        ):
            raise ResolutionError("challenge")
        page = BeautifulSoup(detail.body, "html.parser")
        csrf_node = page.select_one('meta[name="csrf-token"]')
        csrf = csrf_node.get("content") if csrf_node else None
        if not isinstance(csrf, str) or not 1 <= len(csrf.encode()) <= 4096:
            raise ResolutionError("extraction_error")
        token = _filmo_offer_token(detail.body, {**metadata, "path": path}, anchor)
        minted = budget.filmo_exchange(
            "POST",
            root + "/n",
            origin=origin,
            cookies=cookies,
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-TOKEN": csrf,
                "Referer": root + path,
            },
            json_body={"p": token},
            max_body=65536,
        )
        if minted.status == 419 and attempt == 0:
            continue
        if minted.status in (401, 403, 419):
            raise ResolutionError("challenge")
        if minted.status != 200:
            raise ResolutionError("transport_failure")
        try:
            wrapper_token = json.loads(minted.body).get("x")
        except ValueError, AttributeError:
            raise ResolutionError("extraction_error") from None
        if (
            not isinstance(wrapper_token, str)
            or not 1 <= len(wrapper_token.encode()) <= 4096
        ):
            raise ResolutionError("extraction_error")
        wrapper_path = "/n/" + quote(wrapper_token, safe="")
        wrapper = budget.filmo_exchange(
            "GET",
            root + wrapper_path,
            origin=origin,
            cookies=cookies,
            headers={"Accept": "text/html", "Referer": root + path},
            max_body=512 * 1024,
        )
        if wrapper.status in (401, 403):
            raise ResolutionError("challenge")
        if wrapper.status in (404, 410):
            raise ResolutionError("unavailable")
        if wrapper.status in (301, 302, 303, 307, 308):
            location = wrapper.headers.get("location")
            target = urljoin(wrapper.url, location or "")
            if not location:
                raise ResolutionError("extraction_error")
            parsed = urlsplit(target)
            host = detect_host(target)
            if (
                parsed.scheme != "https"
                or parsed.username
                or parsed.password
                or not host
            ):
                raise ResolutionError("extraction_error")
            if host.name != expected_host:
                raise ResolutionError("unavailable")
            return host.name, target
        if wrapper.status != 200:
            raise ResolutionError("transport_failure")
        if looks_like_verification_page(
            wrapper.body[:8192].decode("utf-8", errors="replace")
        ):
            raise ResolutionError("challenge")
        page = BeautifulSoup(wrapper.body, "html.parser")
        for node in page.select("a[href], iframe[src]"):
            target = urljoin(wrapper.url, node.get("href") or node.get("src") or "")
            parsed = urlsplit(target)
            host = detect_host(target)
            if (
                parsed.scheme == "https"
                and not parsed.username
                and not parsed.password
                and host is not None
                and host.name == expected_host
            ):
                return host.name, target
        raise ResolutionError("unavailable")
    raise ResolutionError("challenge")
