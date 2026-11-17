"""User-local streaming with verified TLS, pinned DNS and finite buffering."""

import asyncio
import ipaddress
import logging
import re
import socket
from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import SplitResult, urljoin, urlsplit

import httpx
from fastapi import HTTPException

ALLOWED_HEADERS = {
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
}
HLS_TYPES = {"application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl"}

_PRIVATE_HTTP = ContextVar("catalog_private_stream_http", default=False)


class PrivateStreamLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX's INFO message includes the complete signed media URL. Suppress
        # it only in this task's transport context, preserving other diagnostics.
        return not _PRIVATE_HTTP.get()


logging.getLogger("httpx").addFilter(PrivateStreamLog())


def target(url: str) -> SplitResult:
    if (
        type(url) is not str
        or not 0 < len(url.encode()) <= 8192
        or any(ord(c) < 32 or ord(c) == 127 for c in url)
    ):
        raise HTTPException(502, "Invalid upstream URL")
    try:
        value = urlsplit(url)
        if (
            value.scheme != "https"
            or not value.hostname
            or value.username
            or value.password
            or value.fragment
        ):
            raise ValueError("URL policy")
        _ = value.port  # urlsplit validates the port lazily.
        return value
    except ValueError:
        raise HTTPException(502, "Invalid upstream URL") from None


async def address(host: str, port: int) -> str:
    try:
        async with asyncio.timeout(5):
            rows = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        if not rows or not all(
            ipaddress.ip_address(row[4][0]).is_global for row in rows
        ):
            raise ValueError("DNS policy")
        return rows[0][4][0]
    except OSError, TimeoutError, ValueError:
        raise HTTPException(502, "Upstream address unavailable") from None


@dataclass(eq=False)
class Opened:
    client: httpx.AsyncClient
    response: httpx.Response
    url: str
    # A HEAD fallback fetched one byte to learn the representation. Without a
    # client Range it must not advertise the probe as the entity length.
    head_length: int | None = None
    head_no_range: bool = False

    async def close(self) -> None:
        try:
            await self.response.aclose()
        finally:
            await self.client.aclose()

    @property
    def status_code(self) -> int:
        return (
            200
            if self.head_no_range and self.response.status_code == 206
            else self.response.status_code
        )

    @property
    def headers(self) -> dict[str, str]:
        values = {
            k: v for k, v in self.response.headers.items() if k in ALLOWED_HEADERS
        }
        if self.head_no_range:
            values.pop("content-range", None)
            if self.head_length is None:
                # Some origins answer the probe without a total. A HEAD reply
                # may omit Content-Length, but must not claim the one-byte probe
                # is the full representation.
                if self.response.status_code == 206:
                    values.pop("content-length", None)
            else:
                values["content-length"] = str(self.head_length)
        return values

    @property
    def playlist(self) -> bool:
        kind = self.response.headers.get("content-type", "").split(";")[0].lower()
        return kind in HLS_TYPES or urlsplit(self.url).path.lower().endswith(
            (".m3u8", ".m3u")
        )

    async def body(self) -> AsyncIterator[bytes]:
        iterator = self.response.aiter_raw(65536).__aiter__()
        while True:
            try:
                # Streaming does not buffer a movie or impose a sample byte cap.
                # An inactive upstream still releases its occupied stream slot.
                async with asyncio.timeout(120):
                    block = await iterator.__anext__()
            except StopAsyncIteration:
                return
            yield block

    async def playlist_body(self) -> bytes:
        body = bytearray()
        async with asyncio.timeout(20):
            async for block in self.body():
                if len(body) + len(block) > 1024**2:
                    raise HTTPException(502, "Upstream playlist exceeds capacity")
                body.extend(block)
        return bytes(body)


async def open_stream(url: str, method: str, range_header: str | None) -> Opened:
    headers = {"Accept-Encoding": "identity"}
    if range_header is not None:
        if not re.fullmatch(
            r"bytes=(?:[0-9]{1,20}-[0-9]{0,20}|-[0-9]{1,20})", range_header
        ):
            raise HTTPException(400, "Invalid byte range")
        headers["Range"] = range_header
    client = httpx.AsyncClient(
        trust_env=False,
        follow_redirects=False,
        timeout=httpx.Timeout(120, connect=5, pool=1),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
    )
    response = None
    head_fallback = False
    private_log = _PRIVATE_HTTP.set(True)
    try:
        async with asyncio.timeout(30):
            for hop in range(3):
                parsed = target(url)
                pinned = await address(parsed.hostname, parsed.port or 443)
                client.cookies.clear()
                request = client.build_request(
                    method,
                    httpx.URL(url).copy_with(host=pinned),
                    headers={**headers, "Host": parsed.netloc},
                    extensions={"sni_hostname": parsed.hostname},
                )
                response = await client.send(request, stream=True)
                if response.status_code in (301, 302, 303, 307, 308):
                    if hop == 2 or "location" not in response.headers:
                        raise HTTPException(502, "Upstream redirect limit")
                    url = urljoin(url, response.headers["location"])
                    await response.aclose()
                    response = None
                    continue
                if method == "HEAD" and response.status_code in (405, 501):
                    await response.aclose()
                    response = None
                    head_fallback = True
                    method = "GET"
                    # Preserve a caller's Range. Without one, sample one byte
                    # only to recover the full representation length below.
                    headers["Range"] = range_header or "bytes=0-0"
                    continue
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise HTTPException(502, "Unsupported upstream encoding")
                kind = response.headers.get("content-type", "").split(";")[0].lower()
                if kind == "application/dash+xml" or urlsplit(
                    url
                ).path.lower().endswith(".mpd"):
                    raise HTTPException(502, "DASH proxy is unsupported")
                head_length = None
                if head_fallback and range_header is None:
                    # A one-byte probe answers 206 with the real total. Present
                    # it as the un-ranged HEAD it replaced, without inventing a
                    # length when the origin ignores Range or sends an unknown
                    # total.
                    match = re.fullmatch(
                        r"bytes 0-0/([0-9]{1,20})",
                        response.headers.get("content-range", ""),
                    )
                    if response.status_code == 206 and match:
                        head_length = int(match.group(1))
                return Opened(
                    client,
                    response,
                    url,
                    head_length,
                    head_fallback and range_header is None,
                )
        raise HTTPException(502, "Upstream unavailable")
    except BaseException as exc:
        if response is not None:
            await response.aclose()
        await client.aclose()
        if isinstance(exc, (httpx.HTTPError, TimeoutError, OSError)):
            raise HTTPException(502, "Upstream unavailable") from None
        raise
    finally:
        _PRIVATE_HTTP.reset(private_log)
