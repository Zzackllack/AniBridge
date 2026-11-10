"""Cancellable provider HTTP with DNS pinning, verified TLS and no ambient proxy."""

import asyncio
import ipaddress
import math
import re
import socket
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urljoin, urlsplit

import httpx

from catalog_core.json_codec import require

NAT64 = ipaddress.ip_network("64:ff9b::/96")


@dataclass(frozen=True)
class Fetch:
    outcome: str
    body: bytes = b""
    retry_after: int | None = None
    status: int | None = None
    error_class: str | None = None
    requests: int = 0
    duration_s: float = 0


class AdmissionDeferred(Exception):
    """Local scheduling delay, deliberately outside the transport error family."""

    def __init__(self, seconds: int) -> None:
        self.seconds = max(1, seconds)
        self.requests = 0
        self.duration_s = 0.0


def retry_after(value: str | None, now: float | None = None) -> int:
    """Honor seconds and HTTP dates; cap pathological server instructions at 24h."""
    try:
        if value is not None and value.isdecimal():
            seconds = int(value)
        else:
            date = parsedate_to_datetime(value or "")
            require(date.tzinfo is not None, "Retry-After timezone")
            seconds = math.ceil(
                date.timestamp() - (time.time() if now is None else now)
            )
        return max(1, min(86400, seconds))
    except ValueError, TypeError, OverflowError:
        return 60


class Session:
    """One origin, bounded pool, no implicit cookies or credential storage.

    Use a transport directly so HTTPX cannot merge a cookie jar into pinned-IP
    requests. Every hop still resolves and validates DNS before using the pool.
    """

    def __init__(self, origin: str, concurrency: int = 2, headers=None) -> None:
        self.origin = origin
        # Direct transport requests don't inherit AsyncClient's default headers.
        # Skyhook rejects an absent User-Agent with 400; retain identifying
        # defaults for canonical calls as well as configured provider profiles.
        self.headers = {
            "User-Agent": "AniBridge-Metadata/1.0",
            "Accept": "*/*",
            **(headers or {}),
        }
        self.transport = httpx.AsyncHTTPTransport(
            trust_env=False,
            verify=True,
            retries=0,
            limits=httpx.Limits(
                max_connections=concurrency,
                max_keepalive_connections=concurrency,
                keepalive_expiry=30,
            ),
        )

    async def fetch(self, origin: str, path: str, **options) -> Fetch:
        require(origin == self.origin, "session origin mismatch")
        return await _fetch(origin, path, _session=self, **options)

    async def close(self) -> None:
        await self.transport.aclose()


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


def _global_address(value: str) -> bool:
    """Reject transition addresses that hide a non-public embedded IPv4."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        elif address.sixtofour is not None:
            address = address.sixtofour
        elif address.teredo is not None:
            return all(_global_address(str(item)) for item in address.teredo)
        elif address in NAT64:
            address = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not address.is_link_local
        and not address.is_loopback
        and not address.is_private
    )


def _text(value: object, maximum: int = 512) -> bool:
    return type(value) is str and 0 < len(value.encode("utf-8")) <= maximum


def _year(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 4
        and value.isascii()
        and value.isdecimal()
        and 1800 <= int(value) <= 2200
    )


def _canonical_query(origin: str, path: str, query: dict[str, str]) -> bool:
    """Only the shapes the canonical adapters actually issue leave this process."""
    if origin == "https://skyhook.sonarr.tv":
        if path == "/v2/tvdb/search":
            return (
                set(query) == {"term", "language"}
                and _text(query["term"])
                and query["language"] == "eng"
            )
        return bool(
            re.fullmatch(r"/v1/tvdb/search/[a-z]{2,3}/", path)
            and set(query) == {"term"}
            and _text(query["term"])
        )
    if origin == "https://api.themoviedb.org":
        if path == "/3/search/movie":
            return (
                set(query) == {"query", "year"}
                and _text(query["query"])
                and _year(query["year"])
            )
        return bool(
            re.fullmatch(r"/3/find/tt[0-9]{7,12}", path)
            and query == {"external_source": "imdb_id"}
        )
    if origin == "https://api.radarr.video":
        return bool(
            path == "/v1/search"
            and set(query) == {"q", "year"}
            and _text(query["q"])
            and _year(query["year"])
        )
    return False


def _provider_query(path: str, query: dict[str, str]) -> bool:
    if path == "/movies":
        return bool(
            set(query) == {"page"}
            and type(query["page"]) is str
            and query["page"].isascii()
            and query["page"].isdecimal()
            and 1 <= int(query["page"]) <= 10000
        )
    if path == "/serien":
        return bool(
            query.get("by") == "alpha"
            and set(query) <= {"by", "page"}
            and (
                "page" not in query
                or type(query["page"]) is str
                and query["page"].isascii()
                and query["page"].isdecimal()
                and 0 < int(query["page"]) <= 9999
            )
        )
    return False


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
    _session: Session | None = None,
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
            or _canonical_query(origin, path, query)
            or _provider_query(path, query),
            "query only permitted for canonical adapter",
        )
        url += "?" + expected_query
    session = _session or Session(origin)
    require(session.origin == origin, "session origin mismatch")
    started, requests, status = time.monotonic(), 0, None

    def result(outcome, body=b"", retry=None, error=None):
        return Fetch(
            outcome, body, retry, status, error, requests, time.monotonic() - started
        )

    try:
        for hop in range(3):
            target = urlsplit(url)
            require(
                target.scheme == "https"
                and (target.scheme, target.netloc) == (base.scheme, base.netloc),
                "cross-origin redirect",
            )
            require(
                target.query == expected_query
                and (not _token or target.path == "/index.php")
                and not target.fragment
                and not target.username,
                "invalid provider URL",
            )
            # Admission may defer a redirect too. Never charge that local wait
            # to a network timeout or turn it into a provider circuit failure.
            if before_request:
                await before_request()
            async with asyncio.timeout(deadline):
                addresses = await asyncio.get_running_loop().getaddrinfo(
                    target.hostname, target.port or 443, type=socket.SOCK_STREAM
                )
                require(
                    bool(addresses)
                    and all(_global_address(a[4][0]) for a in addresses),
                    "unsafe DNS",
                )
                logical = httpx.Request("GET", url)
                if _cookies is not None:
                    _cookies.set_cookie_header(logical)
                    require(
                        len(logical.headers.get("cookie", "").encode()) <= 8192,
                        "cookie header overflow",
                    )
                headers = {
                    **session.headers,
                    "Host": target.netloc,
                    "Accept-Encoding": "identity",
                    **(
                        {"Cookie": logical.headers["cookie"]}
                        if "cookie" in logical.headers
                        else {}
                    ),
                    **({"Authorization": "Bearer " + bearer} if bearer else {}),
                }
                pinned = httpx.URL(url).copy_with(host=addresses[0][4][0])
                request = httpx.Request(
                    "GET",
                    pinned,
                    headers=headers,
                    extensions={
                        "sni_hostname": target.hostname,
                        "timeout": {"connect": 5, "read": 10, "write": 10, "pool": 1},
                    },
                )
                requests += 1
                response = await session.transport.handle_async_request(request)
                try:
                    status = response.status_code
                    if _cookies is not None:
                        from .megakino_session import extract_cookies

                        extract_cookies(_cookies, response, logical)
                    if _token and status == 204:
                        return result("ok")
                    if status in {301, 302, 303, 307, 308}:
                        require(
                            hop < 2 and "location" in response.headers, "redirect limit"
                        )
                        url = urljoin(url, response.headers["location"])
                        continue
                    if status in {401, 403}:
                        return result("challenge_or_block")
                    if status == 429:
                        return result(
                            "rate_limited",
                            retry=retry_after(response.headers.get("retry-after")),
                        )
                    if status in {404, 410}:
                        return result("not_found")
                    if status == 503 and "retry-after" in response.headers:
                        return result(
                            "transport_failure",
                            retry=retry_after(response.headers["retry-after"]),
                        )
                    if status != 200:
                        return result(
                            "transport_failure" if status >= 500 else "http_error"
                        )
                    require(
                        response.headers.get("content-encoding", "identity")
                        == "identity",
                        "unexpected content encoding",
                    )
                    data = bytearray()
                    async for chunk in response.aiter_raw(65536):
                        require(len(data) + len(chunk) <= body_bytes, "body overflow")
                        data.extend(chunk)
                    body = bytes(data)
                    return result(
                        "challenge_or_block" if challenge(body) else "ok", body
                    )
                finally:
                    await response.aclose()
    except AdmissionDeferred as exc:
        exc.requests = requests
        exc.duration_s = time.monotonic() - started
        raise
    except httpx.PoolTimeout as exc:
        return result("local_resource", error=type(exc).__name__)
    except (httpx.HTTPError, TimeoutError, OSError) as exc:
        return result("transport_failure", error=type(exc).__name__)
    except ValueError as exc:
        return result("unexpected_structure", error=type(exc).__name__)
    finally:
        if _session is None:
            await session.close()
    return result("unexpected_structure")


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
