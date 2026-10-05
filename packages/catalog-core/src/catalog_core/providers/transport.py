"""Cancellable provider HTTP with DNS pinning, verified TLS and no ambient proxy."""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin, urlsplit

import httpx

from catalog_core.json_codec import require


@dataclass(frozen=True)
class Fetch:
    outcome: str
    body: bytes = b""
    retry_after: int | None = None


def challenge(body: bytes) -> bool:
    lower = body.lower()
    return any(
        a in lower and b in lower
        for a, b in (
            (b"cf-turnstile", b"captcha-form"),
            (b"cf-turnstile", b"verify you are human"),
            (b"challenge-platform", b"cf-turnstile-response"),
            (b"stream wird vorbereitet", b"captcha"),
        )
    )


async def _fetch(
    origin: str,
    path: str,
    *,
    body_bytes: int = 8388608,
    deadline: int = 30,
    before_request=None,
    query: dict[str, str] | None = None,
    bearer: str | None = None,
    _cookies=None,
    _token: bool = False,
) -> Fetch:
    """Return typed outcomes; every redirect consumes a caller's rate budget."""
    from catalog_core.identity import path as validate_path

    base = urlsplit(origin)
    url = origin.rstrip("/") + validate_path(path)
    expected_query = urlencode(query or {})
    require(
        bearer is None or origin == "https://api.themoviedb.org", "credential origin"
    )
    if expected_query:
        require(
            _token
            and path == "/index.php"
            and query == {"yg": "token"}
            or origin in ("https://skyhook.sonarr.tv", "https://api.themoviedb.org")
            or path == "/serien"
            and query.get("by") == "alpha"
            and set(query) <= {"by", "page"}
            and (
                "page" not in query
                or query["page"].isdecimal()
                and 0 < int(query["page"]) <= 9999
            ),
            "query only permitted for canonical adapter",
        )
        url += "?" + expected_query
    try:
        async with asyncio.timeout(deadline):
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(10, connect=5, pool=1),
            ) as client:
                for hop in range(3):
                    target = urlsplit(url)
                    require(
                        (target.scheme, target.netloc) == (base.scheme, base.netloc),
                        "cross-origin redirect",
                    )
                    require(
                        target.query == expected_query
                        and (not _token or target.path == "/index.php")
                        and not target.fragment
                        and not target.username,
                        "invalid provider URL",
                    )
                    addresses = await asyncio.get_running_loop().getaddrinfo(
                        target.hostname, target.port or 443, type=socket.SOCK_STREAM
                    )
                    require(
                        bool(addresses)
                        and all(
                            ipaddress.ip_address(a[4][0]).is_global for a in addresses
                        ),
                        "unsafe DNS",
                    )
                    if before_request:
                        await before_request()
                    logical = httpx.Request("GET", url)
                    if _cookies is not None:
                        _cookies.set_cookie_header(logical)
                        require(
                            len(logical.headers.get("cookie", "").encode()) <= 8192,
                            "cookie header overflow",
                        )
                    client.cookies.clear()
                    pinned = httpx.URL(url).copy_with(host=addresses[0][4][0])
                    async with client.stream(
                        "GET",
                        pinned,
                        headers={
                            "Host": target.netloc,
                            "Accept-Encoding": "identity",
                            **(
                                {"Cookie": logical.headers["cookie"]}
                                if "cookie" in logical.headers
                                else {}
                            ),
                            **({"Authorization": "Bearer " + bearer} if bearer else {}),
                        },
                        extensions={"sni_hostname": target.hostname},
                    ) as response:
                        if _cookies is not None:
                            from .megakino_session import extract_cookies

                            extract_cookies(_cookies, response, logical)
                        if _token and response.status_code == 204:
                            return Fetch("ok")
                        if response.status_code in {301, 302, 303, 307, 308}:
                            require(
                                hop < 2 and "location" in response.headers,
                                "redirect limit",
                            )
                            url = urljoin(url, response.headers["location"])
                            continue
                        if response.status_code in {403, 401}:
                            return Fetch("challenge_or_block")
                        if response.status_code == 429:
                            value = response.headers.get("retry-after", "3600")
                            seconds = int(value) if value.isdecimal() else 3600
                            return Fetch(
                                "rate_limited",
                                retry_after=max(3600, min(86400, seconds)),
                            )
                        if response.status_code in {404, 410}:
                            return Fetch("not_found")
                        if response.status_code != 200:
                            return Fetch("transport_failure")
                        # Refuse HTTP compression rather than let a decoder allocate an
                        # unbounded expansion before we can enforce the body cap.
                        require(
                            response.headers.get("content-encoding", "identity")
                            == "identity",
                            "unexpected content encoding",
                        )
                        data = bytearray()
                        async for chunk in response.aiter_raw(65536):
                            require(
                                len(data) + len(chunk) <= body_bytes, "body overflow"
                            )
                            data.extend(chunk)
                        body = bytes(data)
                        return Fetch(
                            "challenge_or_block" if challenge(body) else "ok", body
                        )
    except httpx.HTTPError, TimeoutError, OSError:
        return Fetch("transport_failure")
    except ValueError:
        return Fetch("unexpected_structure")
    return Fetch("unexpected_structure")


async def fetch(
    origin: str,
    path: str,
    *,
    body_bytes: int = 8388608,
    deadline: int = 30,
    before_request=None,
    query: dict[str, str] | None = None,
    bearer: str | None = None,
) -> Fetch:
    """Ordinary fetch has no cookie session or provider token-query capability."""
    return await _fetch(
        origin,
        path,
        body_bytes=body_bytes,
        deadline=deadline,
        before_request=before_request,
        query=query,
        bearer=bearer,
    )
