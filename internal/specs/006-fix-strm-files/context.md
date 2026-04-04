# context.md — STRM playback via AniBridge Proxy (VPN/CDN IP binding fix)

## Problem statement

Providers/CDNs often issue resolved media URLs that are bound to the resolver’s egress identity (IP/ASN) and/or request metadata (headers, referer, token TTL). In typical deployments, AniBridge runs behind a VPN sidecar (e.g., Gluetun), but Jellyfin does not. AniBridge generates `.strm` containing a resolved CDN URL (valid from VPN IP), then Jellyfin plays it from a different IP → CDN returns 403 → playback fails.

## Core design change

`.strm` files must NOT contain the final CDN URL anymore (at least in VPN setups).
Instead, `.strm` must contain a stable AniBridge URL which Jellyfin can reach.

Example STRM content (single line):
`https://<ANIBRIDGE_PUBLIC_BASE_URL>/strm/stream?site=aniworld.to&slug=...&s=1&e=1&lang=German%20Dub&provider=VOE`

Jellyfin always requests AniBridge. AniBridge fetches upstream bytes using its own network namespace (VPN egress), so IP/ASN binding no longer breaks playback.

## Non-goals

- Do not require Sonarr to “understand” STRM semantics.
- Do not require Jellyfin to run behind the same VPN.
- Do not require a DB migration story for the MVP.

## Why redirect is not enough

A 302/307 redirect from AniBridge to the provider/CDN URL will still make Jellyfin hit the CDN directly (wrong IP), causing the same 403. Therefore:

- The endpoint must implement a full **byte-streaming reverse proxy**.

## Endpoint requirements (FastAPI)

Implement an HTTP endpoint that proxies media bytes:

### `GET /strm/stream`

Inputs:

- query params: `site`, `slug`, `s`, `e`, `lang`, optional `provider`
- optionally: `quality` or `format` if supported
- headers: must respect `Range` header if present

Behavior:

1. Resolve the upstream media URL (and any required headers) using existing AniBridge resolver logic.
2. Perform upstream request (GET, optionally HEAD) from AniBridge.
3. Stream response to client while forwarding critical headers:
   - `Content-Type`
   - `Content-Length` (if known)
   - `Accept-Ranges` / `Content-Range` if upstream supports range
4. Support `Range` requests:
   - If request includes `Range`, forward it upstream.
   - If upstream returns `206`, forward status + Content-Range.
   - If upstream does not support ranges, fallback to full `200` stream.

### HEAD support

Jellyfin may probe with `HEAD`. Implement HEAD passthrough where possible:

- If upstream supports HEAD, pass it through.
- Otherwise emulate minimal headers via GET-without-body (best effort).

## “Refresh on playback” behavior (automatic dead-link recovery)

The proxy is the perfect place to handle dead links:

- If upstream returns `403/404/410/451/429` or times out:
  1) treat as stale/blocked
  2) re-run the resolver to obtain a fresh URL (same logic used when generating STRM)
  3) retry upstream once
  4) if successful, optionally update cache/persistent mapping

Important nuance:

- 403 can mean “IP mismatch” OR “token expired”. Proxy fixes IP mismatch by design; if 403 still occurs, it may require re-resolution or different provider fallback.

## Stateless MVP (avoid DB/migrations)

To avoid DB migrations and still support refresh:

- Encode episode identity in the proxy URL (slug/season/episode/lang/site/provider).
- On each playback request, resolve URL “just-in-time”.
- Add a short TTL in-memory cache to reduce resolver calls.

Recommended caching:

- Key: `(site, slug, s, e, lang, provider?)`
- Store: `resolved_url`, `resolved_headers`, `resolved_at`, `fail_count`, `last_status`
- TTL: small (e.g., 5–30 minutes) to balance stability vs token expiry

## Optional persistence (future)

A persistent mapping helps debugging and bulk refresh:

- `StrmUrlMapping` (or similar):
  - episode identity
  - `resolved_url`
  - `resolved_at`
  - `last_http_status`, `last_error`
  - optional `headers_json`
- BUT: do not block MVP on DB migrations. Keep it optional.

## Capturing required headers

Some providers require headers like `Referer` / `User-Agent`.
When resolving the URL, capture any extractor-provided headers and store them in cache/mapping, then apply them to upstream requests.

If the resolver stack is `yt-dlp` based:

- Prefer using extract_info(download=False) / info dict headers if available.
- Use consistent UA across resolution + playback.

## Security considerations

A public proxy endpoint can be abused.
Add an auth strategy:

- `STRM_PROXY_AUTH=none|token|apikey`
- For token mode:
  - `.strm` includes `token` param
  - token is HMAC over query params + expiry using a secret env var
  - reject missing/invalid tokens
- Optionally allow LAN-only deployments with `none`.

## Environment variables (suggested)

- `STRM_PROXY_MODE=direct|proxy|redirect`
  - direct: current behavior (write provider URL into `.strm`)
  - proxy: write AniBridge proxy URL into `.strm` (fixes VPN/CDN binding)
  - redirect: only for cases where URLs are not IP-bound (reduces server load)
- `STRM_PUBLIC_BASE_URL=https://anibridge.example` (what Jellyfin can reach)
- `STRM_PROXY_AUTH=token` and `STRM_PROXY_SECRET=...` (optional)
- `STRM_PROXY_CACHE_TTL_SECONDS=...` (optional)

## Operational notes with Gluetun

AniBridge must be reachable by Jellyfin, but still use VPN for outbound.
Typical docker approach:

- AniBridge runs with `network_mode: service:gluetun` so outbound goes through VPN.
- Expose AniBridge port via Gluetun’s port mappings so Jellyfin can reach it.
- Ensure Jellyfin points its STRM library path to the folder where `.strm` files live.

## Testing plan

1) Local: generate `.strm` pointing to AniBridge proxy; play in Jellyfin.
2) Simulate IP mismatch: run Jellyfin outside VPN; AniBridge inside VPN; confirm CDN 403 disappears.
3) Range test: scrub/seek in Jellyfin; verify `206` and `Content-Range`.
4) Dead link test: force resolver to rotate URL (or invalidate token) and verify proxy refresh retry works.

## Incremental rollout

- Phase 1: Add proxy endpoint + STRM writes proxy URL (no DB).
- Phase 2: Add in-memory caching + refresh-on-failure.
- Phase 3 (optional): Add persistence / UI/CLI refresh commands once migrations are solved.

<!-- Also see HLS-m3u8-context.md -->