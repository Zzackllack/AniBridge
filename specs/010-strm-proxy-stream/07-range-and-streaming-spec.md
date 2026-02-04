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
5. Ensure `Accept-Ranges` is preserved when present, as it advertises byte-range support. citeturn2view2turn2view3

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

- Use `httpx.AsyncClient.stream(...)` and iterate `response.aiter_bytes()` to stream chunks to the client. citeturn13view0

Option B: aiohttp streaming.

- Use `aiohttp.ClientSession` and `response.content.iter_chunked(...)`. citeturn14view0

Decision gate: select the HTTP client based on maintainer preference and consistency with existing dependencies.

## FastAPI/Starlette Response Strategy

- Use `StreamingResponse` for streaming upstream bytes with minimal buffering; it accepts generators/iterators for streaming output. citeturn2view1turn5view0
- Do not use `FileResponse` for proxying because it is intended for local filesystem files, although it does support Range when serving local files. citeturn5view1

## Backpressure And Chunking

- Choose a default chunk size (e.g., 64KB or 256KB) and make it configurable.
- Do not buffer entire responses in memory.
- Preserve streaming flow even when downstream is slower than upstream.

## Timeouts And Retries

- Configure connect/read/write timeouts for upstream requests; do not set `timeout=None` for all operations.
- For refresh-on-failure, retry only once per request cycle to avoid hammering providers.

## Reverse Proxy Buffering Considerations

- Nginx: if used in front of AniBridge, `proxy_buffering` can be disabled to avoid buffering large streaming responses. citeturn11view0
- Traefik: buffering middleware reads request/response bodies for size limiting; avoid enabling it for streaming endpoints or set permissive limits. citeturn10view1

## HEAD Requests

- If the client sends `HEAD`, forward to upstream when possible.
- If upstream does not support HEAD, perform a `GET` with `Range: bytes=0-0` or a `GET` with no body read to approximate metadata, then return headers only.

## Content-Type Defaults

- If upstream does not include `Content-Type`, infer from URL extension only as a last resort; otherwise use `application/octet-stream`.
- For HLS playlists, set `application/vnd.apple.mpegurl` as content type. citeturn3view3
