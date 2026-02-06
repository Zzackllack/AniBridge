# Range And Streaming Spec

## Status

Draft

## Scope

Define how the proxy handles HTTP Range requests, streaming backpressure, header propagation, timeouts, and reverse proxy buffering considerations.

## Last updated

2026-02-03

## HTTP Range Handling (Normative)

1. If the client sends a `Range` header, forward it upstream unchanged.
2. If upstream responds with `206 Partial Content`, forward status and `Content-Range` to the client.
3. If upstream responds with `416 Range Not Satisfiable`, forward `416` and include any upstream `Content-Range` if provided.
4. If upstream ignores Range and returns `200`, return `200` to the client and continue streaming.
5. Ensure `Accept-Ranges` is preserved when present, as it advertises byte-range support. [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)

## Header Pass-Through Policy

Preserve the following response headers when present:

- `Content-Type`
- `Content-Length` (if provided by upstream)
- `Content-Range` (for `206` responses)
- `Accept-Ranges`
- `ETag` and `Last-Modified` if present (for client caching)

Drop or normalize hop-by-hop headers such as `Connection`, `Transfer-Encoding`, and `Keep-Alive`.

## Streaming Implementation Options

Option A: HTTPX streaming.

- Use `httpx.AsyncClient.stream(...)` and iterate `response.aiter_bytes()` to stream chunks to the client. [HTTPX Async Streaming](https://www.python-httpx.org/async/)

Option B: aiohttp streaming.

- Use `aiohttp.ClientSession` and `response.content.iter_chunked(...)`. [aiohttp Streams](https://docs.aiohttp.org/en/stable/streams.html)

Decision gate: select the HTTP client based on maintainer preference and consistency with existing dependencies.

## FastAPI/Starlette Response Strategy

- Use `StreamingResponse` for streaming upstream bytes with minimal buffering; it accepts generators/iterators for streaming output. [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/), [Starlette Responses](https://www.starlette.io/responses/)
- Do not use `FileResponse` for proxying because it is intended for local filesystem files, although it does support Range when serving local files. [Starlette Responses](https://www.starlette.io/responses/)

## Backpressure And Chunking

- Choose a default chunk size (e.g., 64KB or 256KB) and make it configurable.
- Do not buffer entire responses in memory.
- Preserve streaming flow even when downstream is slower than upstream.

## Timeouts And Retries

- Configure connect/read/write timeouts for upstream requests; do not set `timeout=None` for all operations.
- For refresh-on-failure, retry only once per request cycle to avoid hammering providers.

## Reverse Proxy Buffering Considerations

- Nginx: if used in front of AniBridge, `proxy_buffering` can be disabled to avoid buffering large streaming responses. [Nginx proxy_buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering)
- Traefik: buffering middleware reads request/response bodies for size limiting; avoid enabling it for streaming endpoints or set permissive limits. [Traefik Buffering Middleware](https://doc.traefik.io/traefik/middlewares/http/buffering/)

## HEAD Requests

- If the client sends `HEAD`, forward to upstream when possible.
- If upstream does not support HEAD, perform a `GET` with `Range: bytes=0-0` or a `GET` with no body read to approximate metadata, then return headers only.

## Content-Type Defaults

- If upstream does not include `Content-Type`, infer from URL extension only as a last resort; otherwise use `application/octet-stream`.
- For HLS playlists, set `application/vnd.apple.mpegurl` as content type. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
