from __future__ import annotations

from datetime import datetime, timedelta
import ipaddress
import socket
from typing import Mapping, Optional
from urllib.parse import urlsplit

import anyio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from loguru import logger
from sqlmodel import Session

from app.config import (
    STRM_PROXY_CACHE_TTL_SECONDS,
    STRM_PROXY_HLS_HINT_BANDWIDTH,
    STRM_PROXY_HLS_HINTS_ENABLED,
    STRM_PROXY_UPSTREAM_ALLOWLIST,
)
from app.db import (
    get_session,  # type: ignore
    get_strm_mapping,  # type: ignore
    upsert_strm_mapping,  # type: ignore
    delete_strm_mapping,  # type: ignore
    utcnow,  # type: ignore
)
from app.core.strm_proxy import (
    StrmIdentity,
    build_proxy_url,
    MEMORY_CACHE,
    REMUX_CACHE_MANAGER,
    StrmCacheEntry,
    build_synthetic_master_playlist,
    inject_stream_inf_bandwidth_hints,
    is_hls_media_playlist,
    require_auth,
    resolve_direct_url,
    rewrite_hls_playlist,
)


router = APIRouter()

_REFRESH_STATUSES = {403, 404, 410, 451, 429}
_ALLOWED_HEADERS = {
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
}
_HLS_CONTENT_TYPES = {
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
}
_STREAM_CHUNK_SIZE = 64 * 1024


def _is_fresh(resolved_at: datetime) -> bool:
    """
    Check whether a cached STRM mapping is still within the configured cache TTL.

    Parameters:
        resolved_at (datetime): Timestamp when the mapping was resolved.

    Returns:
        True if the mapping's age is less than or equal to the configured cache TTL (or if the TTL is set to a non-positive value), False otherwise.
    """
    logger.trace("Checking STRM cache freshness at {}", resolved_at)
    if STRM_PROXY_CACHE_TTL_SECONDS <= 0:
        return True
    return utcnow() - resolved_at <= timedelta(seconds=STRM_PROXY_CACHE_TTL_SECONDS)


def _filter_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """
    Filter an upstream response header mapping to the module's allowlist of safe headers.

    Parameters:
        headers (Mapping[str, str]): Mapping of headers received from the upstream response.

    Returns:
        filtered_headers (dict[str, str]): A new dict containing only headers whose names (case-insensitive) are present in the allowlist.
    """
    logger.trace("Filtering upstream headers: {}", list(headers.keys()))
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _ALLOWED_HEADERS:
            out[k] = v
    return out


def _ensure_content_type(headers: dict[str, str], default: str) -> dict[str, str]:
    """
    Ensure a Content-Type header exists in the given headers, using the provided default if missing.

    Parameters:
        headers (dict[str, str]): Mapping of header names to values; keys are treated case-insensitively.
        default (str): Content-Type value to insert when no Content-Type header is present.

    Returns:
        dict[str, str]: The same headers mapping with a Content-Type entry guaranteed to be present.
    """
    if not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = default
    return headers


def _set_header_case_insensitive(
    headers: dict[str, str], *, name: str, value: str
) -> None:
    """
    Replace a header value, removing existing variants case-insensitively.
    """
    for key in list(headers.keys()):
        if key.lower() == name.lower():
            headers.pop(key, None)
    headers[name] = value


def _is_hls_response(url: str, headers: Mapping[str, str]) -> bool:
    """
    Determine whether an upstream response represents an HLS playlist.

    Checks the `Content-Type` header against known HLS MIME types; if no decisive Content-Type is present, falls back to inspecting the URL path for `.m3u8` or `.m3u` extensions.

    Parameters:
        url (str): The upstream request URL.
        headers (Mapping[str, str]): The upstream response headers (case-insensitive keys expected).

    Returns:
        bool: `true` if the response is an HLS playlist, `false` otherwise.
    """
    logger.trace("Detecting HLS response for {}", _redact_upstream(url))
    content_type = headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type in _HLS_CONTENT_TYPES:
        return True
    path = urlsplit(url).path.lower()
    return path.endswith(".m3u8") or path.endswith(".m3u")


def _redact_upstream(url: str) -> str:
    """
    Create a compact identifier for an upstream URL suitable for logs.

    Returns:
        str: "<redacted>" if the URL cannot be parsed; otherwise "<host>:<short-hash>" where <short-hash> is a four-byte hexadecimal fingerprint of the URL path.
    """
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        path = parsed.path or "/"
        return f"{host or '<unknown>'}:{hash(path) & 0xFFFF_FFFF:x}"
    except Exception:
        return "<redacted>"


async def _resolve_upstream_ips(
    host: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """
    Resolve the host to all A/AAAA records or return the literal IP.
    """
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        return [literal_ip]
    try:
        infos = await anyio.to_thread.run_sync(  # type: ignore
            lambda: socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        )
    except socket.gaierror:
        return []
    resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for _, _, _, _, sockaddr in infos:
        addr = sockaddr[0]
        try:
            resolved.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    unique: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for ip in resolved:
        if ip in seen:
            continue
        seen.add(ip)
        unique.append(ip)
    return unique


def _parse_identity(params: Mapping[str, str]) -> StrmIdentity:
    """
    Parse episode identity fields from query parameters into a StrmIdentity.

    Extracts the following values from params (with synonyms and defaults):
    - slug (required)
    - site (optional, defaults to "aniworld.to")
    - language via "lang" or "language" (required)
    - season via "s" or "season" (required, parsed as int)
    - episode via "e" or "episode" (required, parsed as int)
    - provider (optional)

    Parameters:
        params (Mapping[str, str]): Query parameter mapping.

    Returns:
        StrmIdentity: Parsed identity with fields site, slug, season, episode, language, and optional provider.

    Raises:
        HTTPException: 400 if any required field is missing or if season/episode cannot be parsed as integers.
    """
    logger.trace("Parsing STRM identity params: {}", sorted(params.keys()))
    slug = (params.get("slug") or "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="missing slug")
    site = (params.get("site") or "aniworld.to").strip()
    lang = (params.get("lang") or params.get("language") or "").strip()
    if not lang:
        raise HTTPException(status_code=400, detail="missing lang")
    s_raw = params.get("s") or params.get("season")
    e_raw = params.get("e") or params.get("episode")
    if s_raw is None or e_raw is None:
        raise HTTPException(status_code=400, detail="missing season/episode")
    try:
        season = int(s_raw)
        episode = int(e_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid season/episode") from exc
    provider = (params.get("provider") or "").strip() or None
    return StrmIdentity(
        site=site,
        slug=slug,
        season=season,
        episode=episode,
        language=lang,
        provider=provider,
    )


async def _validate_upstream_url(url: str) -> None:
    """
    Validate that the provided upstream URL uses the HTTP or HTTPS scheme.

    Raises:
        HTTPException: with status code 400 if the URL's scheme is not "http" or "https".
    """
    logger.trace("Validating upstream URL scheme: {}", _redact_upstream(url))
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="invalid upstream url scheme")
    host = (parsed.hostname or "").strip().lower()
    if not host or host == "localhost":
        raise HTTPException(status_code=400, detail="invalid upstream host")
    if host in STRM_PROXY_UPSTREAM_ALLOWLIST:
        return
    if host and "." not in host:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid upstream host")
    resolved_ips = await _resolve_upstream_ips(host)
    if not resolved_ips:
        raise HTTPException(status_code=400, detail="unresolvable upstream host")
    for ip in resolved_ips:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise HTTPException(status_code=400, detail="upstream host not allowed")


_UPSTREAM_CLIENT: httpx.AsyncClient | None = None
_UPSTREAM_CLIENT_LOCK = anyio.Lock()


def _build_async_client() -> httpx.AsyncClient:
    """
    Constructs an httpx.AsyncClient configured for upstream streaming requests.
    """
    logger.trace("Building upstream AsyncClient")
    timeout = httpx.Timeout(30.0, connect=10.0, read=60.0, write=30.0, pool=30.0)
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        trust_env=False,
    )


async def _get_async_client() -> httpx.AsyncClient:
    """
    Return a shared AsyncClient for upstream streaming requests.
    """
    global _UPSTREAM_CLIENT
    async with _UPSTREAM_CLIENT_LOCK:
        if _UPSTREAM_CLIENT is None or _UPSTREAM_CLIENT.is_closed:
            _UPSTREAM_CLIENT = _build_async_client()
        return _UPSTREAM_CLIENT


async def _open_upstream(
    url: str, *, method: str, headers: Mapping[str, str]
) -> httpx.Response:
    """
    Open an upstream HTTP request and return the active streaming response.

    Parameters:
        url (str): Upstream URL to request.
        method (str): HTTP method to use (e.g., "GET", "HEAD").
        headers (Mapping[str, str]): Headers to include in the upstream request.

    Returns:
        httpx.Response: The streaming `httpx.Response`; the caller is responsible for closing it to release network resources.
    """
    logger.trace("Opening upstream {} {}", method, _redact_upstream(url))
    client = await _get_async_client()
    request = client.build_request(method, url, headers=headers)
    response = await client.send(request, stream=True)
    return response


def _streaming_body(response: httpx.Response):
    """
    Stream bytes from an upstream response and ensure the response is closed when streaming ends.

    Returns:
        An asynchronous iterator that yields bytes chunks from the upstream response.
    """
    logger.trace("Streaming body start (status={})", response.status_code)

    async def _gen():
        """
        Yield successive byte chunks from an upstream HTTP response and ensure resources are closed when iteration ends.

        Yields:
            bytes: Consecutive chunks of the upstream response body.

        Notes:
            Ensures `response.aclose()` is awaited when the generator exits or an error occurs.
        """
        try:
            async for chunk in response.aiter_bytes(chunk_size=_STREAM_CHUNK_SIZE):
                yield chunk
        finally:
            await response.aclose()

    return _gen()


def _cache_get(session: Session, identity: StrmIdentity) -> Optional[StrmCacheEntry]:
    """
    Return a fresh cached STRM mapping from memory or persistent storage if available.

    If an in-memory entry exists, it is returned immediately. Otherwise the persistent store is queried; if a fresh record is found it is converted to a StrmCacheEntry, stored in the memory cache, and returned. Stale or missing records result in `None`.

    Returns:
        StrmCacheEntry: The fresh cached mapping with resolved URL and metadata, `None` otherwise.
    """
    logger.trace("Checking STRM cache for {}", identity.cache_key())
    entry = MEMORY_CACHE.get(identity)
    if entry:
        logger.debug("STRM cache hit (memory) for {}", identity.cache_key())
        return entry

    rec = get_strm_mapping(
        session,
        site=identity.site,
        slug=identity.slug,
        season=identity.season,
        episode=identity.episode,
        language=identity.language,
        provider=identity.provider,
    )
    if not rec:
        logger.debug("STRM cache miss (db) for {}", identity.cache_key())
        return None
    if not _is_fresh(rec.resolved_at):
        logger.debug("STRM cache stale (db) for {}", identity.cache_key())
        return None
    entry = StrmCacheEntry(
        url=rec.resolved_url,
        provider_used=rec.provider_used,
        resolved_at=rec.resolved_at,
    )
    MEMORY_CACHE.set(identity, entry)
    return entry


def _cache_set(
    session: Session,
    identity: StrmIdentity,
    url: str,
    provider_used: Optional[str],
) -> None:
    """
    Persist a resolved STRM mapping to memory and the database.

    Updates the in-memory cache for the provided identity and persists the resolved URL and provider information to persistent storage.

    Parameters:
        identity: Episode identity (site, slug, season, episode, language, provider) used as the cache key.
        url: The resolved direct upstream URL to cache and persist.
        provider_used: Identifier of the provider that produced the resolved URL, or `None` if unknown.
    """
    logger.debug("Persisting STRM mapping for {}", identity.cache_key())
    entry = StrmCacheEntry(url=url, provider_used=provider_used, resolved_at=utcnow())
    MEMORY_CACHE.set(identity, entry)
    upsert_strm_mapping(
        session,
        site=identity.site,
        slug=identity.slug,
        season=identity.season,
        episode=identity.episode,
        language=identity.language,
        provider=identity.provider,
        resolved_url=url,
        provider_used=provider_used,
        resolved_headers=None,
    )


def _cache_invalidate(session: Session, identity: StrmIdentity) -> None:
    """
    Invalidate the resolved STRM mapping for an episode in both the in-memory cache and persistent storage.

    Parameters:
        identity (StrmIdentity): Episode identity whose mapping will be removed; identified by site, slug, season, episode, language, and provider.
    """
    logger.warning("Invalidating STRM mapping for {}", identity.cache_key())
    MEMORY_CACHE.invalidate(identity)
    delete_strm_mapping(
        session,
        site=identity.site,
        slug=identity.slug,
        season=identity.season,
        episode=identity.episode,
        language=identity.language,
        provider=identity.provider,
    )


async def _resolve_with_cache(
    session: Session, identity: StrmIdentity, *, force_refresh: bool
) -> tuple[str, Optional[str]]:
    """
    Resolve and return the upstream direct URL for a STRM identity, using a cached mapping when available.

    If `force_refresh` is true, bypasses any cached mapping and resolves a fresh upstream URL.

    Parameters:
        force_refresh (bool): When true, skip cache and perform a fresh resolution.

    Returns:
        tuple[str, Optional[str]]: `(direct_url, provider_used)` where `direct_url` is the resolved upstream URL and `provider_used` is the identifier of the provider used to resolve the URL, or `None` if unknown.

    Raises:
        HTTPException: Raised with status 502 if upstream resolution fails.
    """
    logger.trace("Resolving upstream with cache (refresh={})", force_refresh)
    if not force_refresh:
        cached = _cache_get(session, identity)
        if cached:
            logger.info("Using cached STRM mapping for {}", identity.cache_key())
            return cached.url, cached.provider_used

    try:
        direct_url, provider_used = await anyio.to_thread.run_sync(  # type: ignore
            resolve_direct_url, identity
        )
    except Exception as exc:
        logger.error("STRM resolver failed: {}", exc)
        raise HTTPException(
            status_code=502, detail="upstream resolution failed"
        ) from exc
    _cache_set(session, identity, direct_url, provider_used)
    logger.success(
        "Resolved STRM upstream provider={} for {}", provider_used, identity.cache_key()
    )
    return direct_url, provider_used


async def _fetch_with_refresh(
    session: Session,
    identity: StrmIdentity,
    *,
    method: str,
    headers: Mapping[str, str],
) -> tuple[httpx.Response, str]:
    """
    Attempt to fetch upstream content for the given STRM identity, retrying once after invalidating the cached mapping if the first attempt fails or returns a refresh-triggering status.

    If the first request raises a network error or returns a status in the refresh set, the cache entry for the identity is invalidated and the function resolves the upstream URL again before a single retry. On persistent failure the function raises an HTTP 502 error.

    Parameters:
        identity (StrmIdentity): The episode/stream identity used to resolve the upstream URL.
        method (str): HTTP method to use when requesting the upstream resource (e.g., "GET", "HEAD").
        headers (Mapping[str, str]): Headers to pass to the upstream request.

    Returns:
        tuple[httpx.Response, str]: The upstream HTTPX response and the resolved upstream URL.
    """
    logger.trace("Fetching upstream (attempts up to 2)")
    attempt = 0
    force_refresh = False
    last_error: Exception | None = None
    while attempt < 2:
        url, _provider_used = await _resolve_with_cache(
            session, identity, force_refresh=force_refresh
        )
        try:
            response = await _open_upstream(url, method=method, headers=headers)
        except httpx.RequestError as exc:
            last_error = exc
            if attempt == 0:
                logger.warning(
                    "STRM refresh on request error (upstream={}): {}",
                    _redact_upstream(url),
                    exc,
                )
                _cache_invalidate(session, identity)
                force_refresh = True
                attempt += 1
                continue
            raise HTTPException(
                status_code=502, detail="upstream request failed"
            ) from exc

        if response.status_code in _REFRESH_STATUSES and attempt == 0:
            logger.warning(
                "STRM refresh on status {} (upstream={})",
                response.status_code,
                _redact_upstream(url),
            )
            await response.aclose()
            _cache_invalidate(session, identity)
            force_refresh = True
            attempt += 1
            continue

        if last_error:
            logger.debug("Refresh recovered from error: {}", last_error)
        logger.trace(
            "Upstream response status={} for {}",
            response.status_code,
            _redact_upstream(url),
        )
        return response, url

    raise HTTPException(status_code=502, detail="upstream request failed")


async def _handle_head(
    session: Session,
    identity: StrmIdentity,
    *,
    headers: Mapping[str, str],
) -> Response:
    """
    Handle a HEAD request by probing the resolved upstream and returning its status and allowed headers.

    If the upstream does not support HEAD (405 or 501), this will perform a ranged GET to obtain headers and the effective status. The returned Response has an empty body but preserves filtered upstream headers and the upstream status code.

    Parameters:
        identity (StrmIdentity): Episode identity used to resolve the upstream URL.
        headers (Mapping[str, str]): Headers forwarded to the upstream request (e.g., Range, User-Agent).

    Returns:
        Response: A FastAPI Response with an empty body, the upstream status code, and filtered headers (ensuring a Content-Type).
    """
    logger.trace("Handling STRM HEAD request")
    response, url = await _fetch_with_refresh(
        session, identity, method="HEAD", headers=headers
    )
    if response.status_code in (405, 501):
        await response.aclose()
        fallback_headers = dict(headers)
        fallback_headers.setdefault("Range", "bytes=0-0")
        response, url = await _fetch_with_refresh(
            session, identity, method="GET", headers=fallback_headers
        )
        await response.aread()
    filtered = _filter_headers(response.headers)
    _ensure_content_type(filtered, "application/octet-stream")
    await response.aclose()
    return Response(content=b"", status_code=response.status_code, headers=filtered)


@router.api_route("/strm/stream", methods=["GET", "HEAD"])
async def strm_stream(
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Stream an episode or rewrite an upstream HLS playlist through the STRM proxy.

    Returns:
        A Response or StreamingResponse containing the upstream content or a rewritten HLS playlist.

    Raises:
        HTTPException: Raised with status 500 if HLS playlist rewriting fails.
    """
    params = dict(request.query_params)
    require_auth(params)
    identity = _parse_identity(params)

    req_id = f"strm-{hash(identity.cache_key()) & 0xFFFF:x}"
    logger.info(
        "STRM stream {} site={} slug={} s={} e={} lang={} provider={}",
        req_id,
        identity.site,
        identity.slug,
        identity.season,
        identity.episode,
        identity.language,
        identity.provider or "",
    )

    upstream_headers: dict[str, str] = {}
    if "range" in request.headers:
        upstream_headers["Range"] = request.headers["range"]
    if "user-agent" in request.headers:
        upstream_headers["User-Agent"] = request.headers["user-agent"]

    if request.method == "HEAD":
        return await _handle_head(session, identity, headers=upstream_headers)

    response, url = await _fetch_with_refresh(
        session, identity, method="GET", headers=upstream_headers
    )

    if _is_hls_response(url, response.headers):
        logger.debug("Detected HLS playlist for {}", _redact_upstream(url))
        if REMUX_CACHE_MANAGER.enabled:
            try:
                remux = await REMUX_CACHE_MANAGER.ensure_artifact(
                    identity=identity,
                    upstream_url=url,
                    request_id=req_id,
                )
            except Exception:
                remux = None
                logger.exception(
                    "STRM remux cache path failed unexpectedly for {}", req_id
                )
            else:
                if remux.artifact_path is not None:
                    await response.aclose()
                    logger.success(
                        "Serving STRM remux artifact request_id={} key={} source={}",
                        req_id,
                        remux.cache_key,
                        remux.source_fingerprint,
                    )
                    return FileResponse(
                        path=remux.artifact_path,
                        media_type="video/mp4",
                    )
                logger.warning(
                    "STRM remux fallback request_id={} key={} reason={}",
                    req_id,
                    remux.cache_key,
                    remux.fallback_reason or remux.state,
                )

        body = await response.aread()
        await response.aclose()
        charset = response.encoding or "utf-8"
        playlist_text = body.decode(charset, errors="replace")
        if STRM_PROXY_HLS_HINTS_ENABLED:
            playlist_text = inject_stream_inf_bandwidth_hints(
                playlist_text,
                default_bandwidth=STRM_PROXY_HLS_HINT_BANDWIDTH,
            )
        if STRM_PROXY_HLS_HINTS_ENABLED and is_hls_media_playlist(playlist_text):
            rewritten = build_synthetic_master_playlist(
                build_proxy_url(url),
                bandwidth=STRM_PROXY_HLS_HINT_BANDWIDTH,
            )
        else:
            try:
                rewritten = rewrite_hls_playlist(
                    playlist_text, base_url=url, rewrite_url=build_proxy_url
                )
            except ValueError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
        try:
            out_bytes = rewritten.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        headers = _filter_headers(response.headers)
        _set_header_case_insensitive(
            headers, name="Content-Length", value=str(len(out_bytes))
        )
        _set_header_case_insensitive(
            headers,
            name="Content-Type",
            value="application/vnd.apple.mpegurl",
        )
        logger.success("Rewrote HLS playlist ({} bytes)", len(out_bytes))
        return Response(
            content=out_bytes,
            status_code=response.status_code,
            media_type="application/vnd.apple.mpegurl",
            headers=headers,
        )

    headers = _filter_headers(response.headers)
    _ensure_content_type(headers, "application/octet-stream")
    logger.debug("Streaming non-HLS response (status={})", response.status_code)
    return StreamingResponse(
        _streaming_body(response),
        status_code=response.status_code,
        headers=headers,
    )


async def _proxy_head(url: str, *, headers: Mapping[str, str]) -> Response:
    """
    Handle HEAD requests for arbitrary proxied upstream URLs.

    Sends a HEAD request to the upstream and, if the upstream responds with 405 or 501, falls back to a GET with `Range: bytes=0-0` to obtain response headers. Filters allowed headers, ensures a Content-Type is present, closes upstream connections, and returns an empty Response carrying the upstream status code and filtered headers.

    Parameters:
        headers (Mapping[str, str]): Headers to forward to the upstream request (for example `Range` and `User-Agent`).

    Returns:
        Response: A FastAPI Response with an empty body, the upstream status code, and the filtered/ensured headers.

    Raises:
        HTTPException: With status code 502 if the upstream request fails.
    """
    logger.trace("Handling STRM proxy HEAD request")
    try:
        response = await _open_upstream(url, method="HEAD", headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="upstream request failed") from exc
    if response.status_code in (405, 501):
        await response.aclose()
        fallback_headers = dict(headers)
        fallback_headers.setdefault("Range", "bytes=0-0")
        try:
            response = await _open_upstream(url, method="GET", headers=fallback_headers)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, detail="upstream request failed"
            ) from exc
        await response.aread()
    filtered = _filter_headers(response.headers)
    _ensure_content_type(filtered, "application/octet-stream")
    await response.aclose()
    return Response(content=b"", status_code=response.status_code, headers=filtered)


@router.api_route("/strm/proxy", methods=["GET", "HEAD"])
@router.api_route("/strm/proxy/{path_hint:path}", methods=["GET", "HEAD"])
async def strm_proxy(request: Request, path_hint: str = ""):
    """
    Proxy an arbitrary upstream URL, returning either a rewritten HLS playlist or a streamed proxy response.

    Parameters:
        path_hint (str): Optional path hint used for logging to indicate the proxied resource path.

    Returns:
        Response or StreamingResponse: If the upstream response is an HLS playlist, returns a Response with the rewritten playlist and appropriate Content-Type and Content-Length. Otherwise returns a StreamingResponse that streams the upstream bytes with filtered headers and the upstream status code.

    Raises:
        HTTPException: Raised with status 400 when the upstream URL parameter `u` is missing or uses an invalid scheme.
        HTTPException: Raised with status 502 when the upstream request fails.
        HTTPException: Raised with status 500 when playlist rewriting fails.
    """
    params = dict(request.query_params)
    require_auth(params)
    upstream_url = (params.get("u") or "").strip()
    if not upstream_url:
        raise HTTPException(status_code=400, detail="missing upstream url")
    await _validate_upstream_url(upstream_url)

    upstream_headers: dict[str, str] = {}
    if "range" in request.headers:
        upstream_headers["Range"] = request.headers["range"]
    if "user-agent" in request.headers:
        upstream_headers["User-Agent"] = request.headers["user-agent"]

    logger.info(
        "STRM proxy upstream={} hint={}",
        _redact_upstream(upstream_url),
        path_hint or "<none>",
    )

    if request.method == "HEAD":
        return await _proxy_head(upstream_url, headers=upstream_headers)

    try:
        response = await _open_upstream(
            upstream_url, method="GET", headers=upstream_headers
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="upstream request failed") from exc

    if _is_hls_response(upstream_url, response.headers):
        logger.debug("Detected HLS playlist for {}", _redact_upstream(upstream_url))
        body = await response.aread()
        await response.aclose()
        charset = response.encoding or "utf-8"
        playlist_text = body.decode(charset, errors="replace")
        if STRM_PROXY_HLS_HINTS_ENABLED:
            playlist_text = inject_stream_inf_bandwidth_hints(
                playlist_text,
                default_bandwidth=STRM_PROXY_HLS_HINT_BANDWIDTH,
            )
        try:
            rewritten = rewrite_hls_playlist(
                playlist_text,
                base_url=upstream_url,
                rewrite_url=build_proxy_url,
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        out_bytes = rewritten.encode("utf-8")
        headers = _filter_headers(response.headers)
        _set_header_case_insensitive(
            headers, name="Content-Length", value=str(len(out_bytes))
        )
        _set_header_case_insensitive(
            headers,
            name="Content-Type",
            value="application/vnd.apple.mpegurl",
        )
        logger.success("Rewrote HLS playlist ({} bytes)", len(out_bytes))
        return Response(
            content=out_bytes,
            status_code=response.status_code,
            media_type="application/vnd.apple.mpegurl",
            headers=headers,
        )

    headers = _filter_headers(response.headers)
    _ensure_content_type(headers, "application/octet-stream")
    logger.debug("Streaming proxied response (status={})", response.status_code)
    return StreamingResponse(
        _streaming_body(response),
        status_code=response.status_code,
        headers=headers,
    )


async def close_upstream_client() -> None:
    """
    Close the shared upstream AsyncClient (called from app lifespan shutdown).
    """
    global _UPSTREAM_CLIENT
    if _UPSTREAM_CLIENT is None:
        return
    await _UPSTREAM_CLIENT.aclose()
    _UPSTREAM_CLIENT = None
