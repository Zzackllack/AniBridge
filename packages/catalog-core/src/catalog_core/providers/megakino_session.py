"""Exact HTTP cookie bootstrap, without executing provider JavaScript.

Cookies see the logical verified HTTPS URL, never the connection's pinned IP.
They live for one bounded attempt and cannot travel to a video host.
"""

import asyncio
import re
from urllib.parse import urlsplit

import httpx

from catalog_core.json_codec import require

TOKEN_PATH = "/index.php"
TOKEN_QUERY = {"yg": "token"}
STUB = re.compile(
    rb'\s*<!doctype html><meta charset="utf-8">\s*<script>\s*'
    rb'fetch\("/index\.php\?yg=token",\{credentials:"include"\}\)\s*'
    rb'\.then\(function\(\)\{ location\.replace\("([^"\\]*)"\) \}\)\s*'
    rb"\.catch\(function\(\)\{ location\.reload\(\) \}\);\s*</script>\s*",
    re.IGNORECASE,
)


def bootstrap(body: bytes, path: str) -> bool:
    """Recognise only the observed tiny stub and exact original return path."""
    if len(body) > 1024:
        return False
    match = STUB.fullmatch(body)
    return bool(match and match[1] == path.encode("utf-8"))


def extract_cookies(jar: httpx.Cookies, response, logical: httpx.Request) -> None:
    values = response.headers.get_list("set-cookie")
    require(
        len(values) <= 16 and sum(len(v.encode()) for v in values) <= 8192,
        "cookie headers overflow",
    )
    jar.extract_cookies(
        httpx.Response(response.status_code, headers=response.headers, request=logical)
    )
    hostname = logical.url.host
    for cookie in list(jar.jar):
        # A provider does not need cookies for a parent domain or another origin.
        if cookie.domain.lstrip(".") != hostname:
            jar.jar.clear(cookie.domain, cookie.path, cookie.name)
    require(len(jar.jar) <= 32, "cookie jar overflow")


async def fetch(
    origin: str,
    path: str,
    *,
    body_bytes=8388608,
    deadline=30,
    before_request=None,
    query=None,
):
    from .transport import Fetch, _fetch

    require(
        urlsplit(origin).scheme == "https" and not query,
        "Megakino bootstrap requires HTTPS without query",
    )
    jar = httpx.Cookies()
    try:
        async with asyncio.timeout(deadline):
            result = await _fetch(
                origin,
                path,
                body_bytes=body_bytes,
                deadline=deadline,
                before_request=before_request,
                _cookies=jar,
            )
            if result.outcome != "ok" or not bootstrap(result.body, path):
                return result
            left = body_bytes - len(result.body)
            token = await _fetch(
                origin,
                TOKEN_PATH,
                query=TOKEN_QUERY,
                _token=True,
                _cookies=jar,
                body_bytes=min(4096, left),
                deadline=deadline,
                before_request=before_request,
            )
            if token.outcome != "ok":
                return token
            left -= len(token.body)
            result = await _fetch(
                origin,
                path,
                _cookies=jar,
                body_bytes=left,
                deadline=deadline,
                before_request=before_request,
            )
            if result.outcome == "ok" and bootstrap(result.body, path):
                return Fetch("challenge_or_block")
            return result
    except TimeoutError:
        return Fetch("transport_failure")
    except ValueError:
        return Fetch("unexpected_structure")
