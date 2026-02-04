# Requirements

## Status

Draft

## Scope

Define functional and non-functional requirements for STRM proxy streaming, HLS rewriting, Range handling, refresh-on-failure, security, caching, and observability.

## Last updated

2026-02-03

## Functional Requirements

1. STRM proxy mode must write a stable AniBridge URL into `.strm` files instead of provider/CDN URLs, while preserving the current direct mode as the default. Evidence for current direct-write behavior is in `app/core/scheduler.py:215` and `app/utils/strm.py:8`.
2. The proxy endpoint must stream bytes directly (no 3xx redirects) to prevent client egress changes; redirect behavior is explicitly rejected in existing STRM proxy context. See `specs/006-fix-strm-files/context.md:23`.
3. The proxy must support HTTP Range requests end-to-end and preserve `Accept-Ranges` / `Content-Range` semantics. Range behavior and status codes are defined by HTTP semantics. citeturn2view2turn2view3
4. The proxy must detect HLS playlists and rewrite all URI-bearing entries so that downstream playlist, segment, and key requests route back through AniBridge. HLS playlists are line-based and contain URI lines and tags. citeturn3view3
5. The rewrite must cover URI-bearing HLS tags including `EXT-X-KEY`, `EXT-X-MAP`, `EXT-X-MEDIA`, `EXT-X-STREAM-INF`, `EXT-X-I-FRAME-STREAM-INF`, and `EXT-X-SESSION-KEY`, which are defined in the HLS spec. citeturn3view3turn3view4
6. Relative URIs in playlists must be resolved against the playlist URL before signing/rewriting. citeturn3view4
7. Refresh-on-failure must re-resolve provider URLs and retry once on specific failure conditions (403/404/410/451/429/timeouts) as outlined in the issue and prior spec notes. See `specs/010-strm-proxy-stream/github-issue.md:103` and `specs/006-fix-strm-files/context.md:65`.
8. The proxy must preserve essential response headers (`Content-Type`, `Content-Length` when available) and avoid exposing hop-by-hop headers. Streaming support is available via FastAPI/Starlette `StreamingResponse`. citeturn2view1turn5view0
9. Security must prevent open proxy abuse by requiring configurable auth (token/HMAC, API key, or allowlist). HMAC semantics are defined in RFC 2104. citeturn16view0
10. The solution must work without requiring immediate DB migrations, but must define a path to a persistent mapping table (`StrmUrlMapping`) once migrations are approved. See `specs/004-strm-file-support/refresh-boilerplate.md:32` and `app/db/models.py:170`.

## Non-Functional Requirements

1. Streaming must be memory-efficient, using chunked streaming rather than buffering entire upstream responses. HTTPX and aiohttp both support streaming iteration patterns for large responses. citeturn13view0turn14view0
2. The proxy must tolerate slow clients via backpressure-aware streaming and avoid timeouts for long-lived HLS playback sessions.
3. The proxy should operate correctly behind common reverse proxies (Traefik/Nginx) when buffering is configured appropriately; buffering middleware/proxy settings can affect streaming behavior. citeturn10view1turn11view0
4. The design must support multi-worker deployments without correctness regressions (cache coherence, token validation, and stateless URL identity where possible).
5. Logging must avoid leaking sensitive URLs, tokens, or HLS keys, and must redact security parameters.

## Explicit Constraints

1. No runtime behavior changes in this phase; this spec must not introduce code or migrations.
2. No immediate DB migrations are required, but the future migration path must be documented and feasible within the current Alembic setup. See `app/db/models.py:170`.
3. Any new environment variables must be additive and not break existing deployments when unset.

## Compatibility Constraints (Media Clients)

1. Jellyfin and ffmpeg-style clients must be able to seek within streams; Range behavior must be preserved. citeturn2view2turn23view0
2. HLS playlists must be returned with a correct HLS media type (e.g., `application/vnd.apple.mpegurl`) to ensure proper client handling. citeturn3view3

## Observability Requirements

1. Log each proxy request with a unique request ID and a redacted upstream identifier.
2. Track refresh-on-failure attempts and outcomes (status, retry count, resolver provider used).
3. Emit metrics for cache hits/misses, resolver latency, upstream latency, and failure categories.
4. Provide opt-in debug logging that can capture playlist rewrite decisions without exposing sensitive tokens or key URIs.
