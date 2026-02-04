from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional
from urllib.parse import urlsplit

import anyio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from sqlmodel import Session

from app.config import STRM_PROXY_CACHE_TTL_SECONDS
from app.db import (
    get_session,
    get_strm_mapping,
    upsert_strm_mapping,
    delete_strm_mapping,
)
from app.core.strm_proxy import (
    StrmIdentity,
    resolve_direct_url,
    build_proxy_url,
    rewrite_hls_playlist,
    MEMORY_CACHE,
    StrmCacheEntry,
    require_auth,
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


def _utcnow() -> datetime:
    """
    Return current UTC time as timezone-aware datetime.
    """
    return datetime.now(timezone.utc)


def _is_fresh(resolved_at: datetime) -> bool:
    """
    Determine whether a cached mapping is still within the configured TTL.
    """
    logger.trace("Checking STRM cache freshness at {}", resolved_at)
    if STRM_PROXY_CACHE_TTL_SECONDS <= 0:
        return True
    return _utcnow() - resolved_at <= timedelta(seconds=STRM_PROXY_CACHE_TTL_SECONDS)


def _filter_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """
    Filter upstream headers to a safe pass-through allowlist.
    """
    logger.trace("Filtering upstream headers: {}", list(headers.keys()))
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _ALLOWED_HEADERS:
            out[k] = v
    return out


def _ensure_content_type(headers: dict[str, str], default: str) -> dict[str, str]:
    """
    Ensure a Content-Type header is present, falling back to default.
    """
    if not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = default
    return headers


def _is_hls_response(url: str, headers: Mapping[str, str]) -> bool:
    """
    Detect whether an upstream response is an HLS playlist.
    """
    logger.trace("Detecting HLS response for {}", _redact_upstream(url))
    content_type = headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type in _HLS_CONTENT_TYPES:
        return True
    path = urlsplit(url).path.lower()
    return path.endswith(".m3u8") or path.endswith(".m3u")


def _redact_upstream(url: str) -> str:
    """
    Produce a redacted identifier for logging upstream URLs.
    """
    try:
        parsed = urlsplit(url)
        host = parsed.netloc
        path = parsed.path or "/"
        return f"{host}:{hash(path) & 0xFFFF_FFFF:x}"
    except Exception:
        return "<redacted>"


def _parse_identity(params: Mapping[str, str]) -> StrmIdentity:
    """
    Parse required episode identity fields from query parameters.
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


def _validate_upstream_url(url: str) -> None:
    """
    Ensure the upstream URL uses an allowed HTTP(S) scheme.
    """
    logger.trace("Validating upstream URL scheme: {}", _redact_upstream(url))
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="invalid upstream url scheme")


def _build_async_client() -> httpx.AsyncClient:
    """
    Build an AsyncClient for upstream streaming without env proxies.
    """
    logger.trace("Building upstream AsyncClient")
    timeout = httpx.Timeout(30.0, connect=10.0, read=60.0, write=30.0, pool=30.0)
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        trust_env=False,
    )


async def _open_upstream(
    url: str, *, method: str, headers: Mapping[str, str]
) -> tuple[httpx.Response, httpx.AsyncClient]:
    """
    Open an upstream streaming response and return the response + client.
    """
    logger.trace("Opening upstream {} {}", method, _redact_upstream(url))
    client = _build_async_client()
    request = client.build_request(method, url, headers=headers)
    response = await client.send(request, stream=True)
    return response, client


def _streaming_body(response: httpx.Response, client: httpx.AsyncClient):
    """
    Create an async generator that streams upstream bytes and closes resources.
    """
    logger.trace("Streaming body start (status={})", response.status_code)
    async def _gen():
        try:
            async for chunk in response.aiter_bytes(chunk_size=_STREAM_CHUNK_SIZE):
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return _gen()


def _cache_get(session: Session, identity: StrmIdentity) -> Optional[StrmCacheEntry]:
    """
    Load a cached mapping from memory or persistence when fresh.
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
    Persist the resolved mapping and update the in-memory cache.
    """
    logger.debug("Persisting STRM mapping for {}", identity.cache_key())
    entry = StrmCacheEntry(url=url, provider_used=provider_used, resolved_at=_utcnow())
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
    Remove cached mappings from memory and persistence.
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
    Resolve an upstream URL using cache and persistence, refreshing when needed.
    """
    logger.trace("Resolving upstream with cache (refresh={})", force_refresh)
    if not force_refresh:
        cached = _cache_get(session, identity)
        if cached:
            logger.info("Using cached STRM mapping for {}", identity.cache_key())
            return cached.url, cached.provider_used

    try:
        direct_url, provider_used = await anyio.to_thread.run_sync(
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
) -> tuple[httpx.Response, httpx.AsyncClient, str]:
    """
    Fetch upstream content with refresh-on-failure and cache invalidation.
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
            response, client = await _open_upstream(
                url, method=method, headers=headers
            )
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
            raise HTTPException(status_code=502, detail="upstream request failed") from exc

        if response.status_code in _REFRESH_STATUSES and attempt == 0:
            logger.warning(
                "STRM refresh on status {} (upstream={})",
                response.status_code,
                _redact_upstream(url),
            )
            await response.aclose()
            await client.aclose()
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
        return response, client, url

    raise HTTPException(status_code=502, detail="upstream request failed")


async def _handle_head(
    session: Session,
    identity: StrmIdentity,
    *,
    headers: Mapping[str, str],
) -> Response:
    """
    Handle HEAD requests against resolved upstream URLs.
    """
    logger.trace("Handling STRM HEAD request")
    response, client, _url = await _fetch_with_refresh(
        session, identity, method="HEAD", headers=headers
    )
    if response.status_code in (405, 501):
        await response.aclose()
        await client.aclose()
        fallback_headers = dict(headers)
        fallback_headers.setdefault("Range", "bytes=0-0")
        response, client, _url = await _fetch_with_refresh(
            session, identity, method="GET", headers=fallback_headers
        )
        await response.aread()
    filtered = _filter_headers(response.headers)
    _ensure_content_type(filtered, "application/octet-stream")
    await response.aclose()
    await client.aclose()
    return Response(content=b"", status_code=response.status_code, headers=filtered)


@router.api_route("/strm/stream", methods=["GET", "HEAD"])
async def strm_stream(
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Stream episode content or rewrite HLS playlists via the STRM proxy.
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

    response, client, url = await _fetch_with_refresh(
        session, identity, method="GET", headers=upstream_headers
    )

    if _is_hls_response(url, response.headers):
        logger.debug("Detected HLS playlist for {}", _redact_upstream(url))
        body = await response.aread()
        await response.aclose()
        await client.aclose()
        charset = response.encoding or "utf-8"
        playlist_text = body.decode(charset, errors="replace")
        try:
            rewritten = rewrite_hls_playlist(
                playlist_text, base_url=url, rewrite_url=build_proxy_url
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        out_bytes = rewritten.encode("utf-8")
        headers = _filter_headers(response.headers)
        headers["Content-Length"] = str(len(out_bytes))
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
        _streaming_body(response, client),
        status_code=response.status_code,
        headers=headers,
    )


async def _proxy_head(
    url: str, *, headers: Mapping[str, str]
) -> Response:
    """
    Handle HEAD requests for arbitrary proxied upstream URLs.
    """
    logger.trace("Handling STRM proxy HEAD request")
    try:
        response, client = await _open_upstream(url, method="HEAD", headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="upstream request failed") from exc
    if response.status_code in (405, 501):
        await response.aclose()
        await client.aclose()
        fallback_headers = dict(headers)
        fallback_headers.setdefault("Range", "bytes=0-0")
        try:
            response, client = await _open_upstream(
                url, method="GET", headers=fallback_headers
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, detail="upstream request failed"
            ) from exc
        await response.aread()
    filtered = _filter_headers(response.headers)
    _ensure_content_type(filtered, "application/octet-stream")
    await response.aclose()
    await client.aclose()
    return Response(content=b"", status_code=response.status_code, headers=filtered)


@router.api_route("/strm/proxy", methods=["GET", "HEAD"])
@router.api_route("/strm/proxy/{path_hint:path}", methods=["GET", "HEAD"])
async def strm_proxy(request: Request, path_hint: str = ""):
    """
    Proxy arbitrary upstream URLs (segments, keys, playlists) with streaming.
    """
    params = dict(request.query_params)
    require_auth(params)
    upstream_url = (params.get("u") or "").strip()
    if not upstream_url:
        raise HTTPException(status_code=400, detail="missing upstream url")
    _validate_upstream_url(upstream_url)

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
        response, client = await _open_upstream(
            upstream_url, method="GET", headers=upstream_headers
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="upstream request failed") from exc

    if _is_hls_response(upstream_url, response.headers):
        logger.debug("Detected HLS playlist for {}", _redact_upstream(upstream_url))
        body = await response.aread()
        await response.aclose()
        await client.aclose()
        charset = response.encoding or "utf-8"
        playlist_text = body.decode(charset, errors="replace")
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
        headers["Content-Length"] = str(len(out_bytes))
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
        _streaming_body(response, client),
        status_code=response.status_code,
        headers=headers,
    )
