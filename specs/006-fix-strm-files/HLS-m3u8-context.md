# context.md — HLS (.m3u8) STRM playback via AniBridge proxy (fix CDN IP/ASN binding)

## Background

AniBridge runs behind a VPN sidecar (e.g. Gluetun). Many providers/CDNs bind resolved URLs to the resolver’s IP/ASN and/or include IP/ASN hints inside the tokenized URL (seen in query params like `i=` and `asn=`). STRM files currently store the resolved provider URL directly (often a HLS `.m3u8` master playlist). Jellyfin/ffmpeg then requests that URL from a different egress (non-VPN) and gets HTTP 403.

## Key insight: HLS requires playlist rewriting

Most STRM URLs are `.m3u8` (HLS). HLS playback is NOT a single HTTP request:

- Client fetches the master playlist
- Then fetches referenced variant/media playlists
- Then fetches many segment resources (`.ts`, `.m4s`, `.mp4`)
- And may fetch key/init resources referenced via tags:
  - `#EXT-X-KEY:URI="..."`
  - `#EXT-X-MAP:URI="..."`
  - `#EXT-X-MEDIA:URI="..."` (renditions)
  - `#EXT-X-I-FRAME-STREAM-INF:URI="..."` (master)
  - `#EXT-X-SESSION-KEY:URI="..."` (master)
If we proxy only the master playlist and do NOT rewrite URIs, ffmpeg will fetch segments directly from the CDN again → still 403.

Therefore: we must implement a HLS-aware proxy that rewrites all URIs inside `.m3u8` to AniBridge proxy URLs and then proxies bytes for those URIs.

## Design overview

### STRM content

Instead of writing the CDN URL into `.strm`, write an AniBridge URL:
`https://<ANIBRIDGE_PUBLIC_BASE_URL>/strm/hls/master?site=...&slug=...&s=...&e=...&lang=...&provider=...&token=...`

This endpoint returns a rewritten HLS playlist whose internal URIs all point back to AniBridge.

### Endpoints (suggested)

1) `GET /strm/hls/master` (or generic `/strm/hls?kind=playlist`)
   - resolves upstream master URL (via existing resolver logic under VPN)
   - fetches upstream `.m3u8`
   - rewrites ALL URIs to AniBridge proxy URLs
   - returns rewritten playlist with correct content-type (`application/vnd.apple.mpegurl`)

2) `GET /strm/hls/proxy?u=<signed>` (generic byte proxy for segments/keys/init/child playlists)
   - `u` encodes the absolute upstream URL + required headers + expiry
   - streams bytes from upstream to the client (Jellyfin/ffmpeg)
   - must forward Range headers if present
   - must preserve upstream content-type/status (200/206)

### Why not redirects

Never 302/307 redirect to the CDN. Redirect makes Jellyfin/ffmpeg hit the CDN directly again, defeating VPN egress binding.

## Playlist rewriting requirements

When rewriting an `.m3u8`, handle both “bare URI lines” and “URI=...” attributes.

### Rewrite cases

- Master playlists:
  - Variant playlist URI lines after `#EXT-X-STREAM-INF`
  - `#EXT-X-I-FRAME-STREAM-INF:...URI="..."`
  - `#EXT-X-MEDIA:...URI="..."`
  - `#EXT-X-SESSION-KEY:...URI="..."`
- Media playlists:
  - segment URI lines (non-`#` lines)
  - `#EXT-X-KEY:...URI="..."`
  - `#EXT-X-MAP:URI="..."` (init segment)
  - subtitle/audio URI attributes (EXT-X-MEDIA)
- Relative URLs: resolve against the base URL of the playlist (urljoin)
- Preserve query tokens exactly (don’t lose `+`, `&`, etc.)

### Recommended tooling

Use the Python `m3u8` library to parse and regenerate playlists where possible. It supports loading from strings and dumping playlists, and it has explicit support for tags like `EXT-X-KEY`. If you do manual rewriting, you must also rewrite URI attributes, not only segment lines.

## Handling keys / encryption

HLS can reference encryption keys via `EXT-X-KEY` (and `EXT-X-SESSION-KEY`). Clients fetch the key URI and use it to decrypt segments. Those key URIs must also be rewritten to the proxy, otherwise decryption will fail due to 403 on key fetch.

## Proxy behavior details (important for ffmpeg/Jellyfin)

- Must support streaming responses efficiently (chunked).
- Should forward `Range` to upstream. ffmpeg might use range for some resources or byte-range playlists.
- Propagate:
  - `Content-Type`
  - `Content-Length` (if present)
  - `Accept-Ranges`, `Content-Range` for 206
- Timeouts and retries:
  - upstream failures may be temporary; do limited retry

## Refresh-on-failure (dead link recovery)

If any upstream request returns 403/404/410/451/429 or times out:

1) re-run the existing resolver logic (under VPN egress) to obtain a fresh URL
2) retry once
3) update cache/mapping
This can be done without DB by being stateless (episode identity in URL). Add a TTL cache to avoid re-resolving too often.

## Caching strategy (DB-less MVP)

- In-memory TTL cache keyed by episode identity:
  `(site, slug, s, e, lang, provider)`
- Store:
  - resolved master URL
  - last fetched rewritten playlist (optional)
  - timestamp + failure counters
- TTL 5–30 minutes is usually enough; token expiry often hours, but refresh can be triggered on failure.

## Security (avoid open proxy)

Because this exposes a byte proxy endpoint:

- Add auth/signing:
  - `STRM_PROXY_AUTH=token|apikey|none`
  - Token mode: HMAC of (upstream URL + expiry + optional headers) using secret env var
- Optionally restrict to private networks

## Configuration knobs (suggested)

- `STRM_PLAYBACK_MODE=direct|hls_proxy` (direct=store CDN URL, proxy=store AniBridge URL)
- `STRM_PUBLIC_BASE_URL=https://anibridge.example` (reachable by Jellyfin)
- `STRM_PROXY_SECRET=...` (for HMAC signing)
- `STRM_PROXY_CACHE_TTL_SECONDS=...`

## Test plan

1) Generate STRM pointing to AniBridge HLS master endpoint.
2) Confirm playlist rewrite: variant playlists, segments, EXT-X-KEY, EXT-X-MAP all point to AniBridge.
3) Run Jellyfin/ffmpeg playback outside VPN: should succeed since AniBridge fetches upstream via VPN.
4) Seek/scrub: verify 206/Range works when applicable.
5) Force a stale token: upstream 403 should trigger re-resolve + retry and then play.
