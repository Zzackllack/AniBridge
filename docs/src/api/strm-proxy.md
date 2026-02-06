---
title: STRM Proxy
outline: deep
---

# STRM Proxy

AniBridge can generate `.strm` files that point to a stable AniBridge URL instead of a provider/CDN URL. The STRM proxy endpoints stream bytes, support HTTP Range, and rewrite HLS playlists so every segment/key request routes back through AniBridge.

## When To Use

- You need stable `.strm` files that keep working even when provider URLs change.
- Jellyfin is outside the VPN while AniBridge is inside the VPN.
- You want HLS segment/key requests to always egress from AniBridge.

## Required Configuration

`STRM_PROXY_MODE=proxy`  
`STRM_PUBLIC_BASE_URL=https://<your-anibridge-host>`
`STRM_PROXY_HLS_REMUX=true` (default)

Auth mode is controlled by `STRM_PROXY_AUTH`:

- `token` (default): HMAC signature in `sig`
- `apikey`: shared key in `apikey`
- `none`: no auth (LAN only)

## Direct Play Requirements

Browser-based clients (Jellyfin, Plex, Emby) enforce mixed content rules. If your media
server is served over HTTPS, AniBridge must also be served over HTTPS or the browser
will block the stream and force server-side transcoding.

Recommended setup:

- Place AniBridge behind a reverse proxy with TLS.
- Ensure the public URL is reachable by both the browser client and the media server.
- Set `STRM_PUBLIC_BASE_URL` to the HTTPS URL that Jellyfin and clients use to reach AniBridge.
  If clients can’t reach AniBridge (even over HTTPS), Direct Play will fail and the
  server will fall back to proxying/transcoding.

### Nginx (example)

```nginx
server {
  listen 443 ssl;
  server_name anibridge.example;

  location / {
    proxy_pass http://127.0.0.1:8083;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
  }
}
```

### Caddy (example)

```caddy
anibridge.example {
  reverse_proxy 127.0.0.1:8083
}
```

### Traefik (Docker labels example)

```yaml
labels:
  - "traefik.http.routers.anibridge.rule=Host(`anibridge.example`)"
  - "traefik.http.routers.anibridge.entrypoints=websecure"
  - "traefik.http.routers.anibridge.tls=true"
  - "traefik.http.services.anibridge.loadbalancer.server.port=8083"
```

## Endpoints

<ApiOperations :tags="['STRM Proxy']"/>

## HLS Rewriting

AniBridge rewrites:

- URI lines (including the line following `#EXT-X-STREAM-INF`)
- Tags with `URI=` attributes: `EXT-X-KEY`, `EXT-X-MAP`, `EXT-X-MEDIA`,
  `EXT-X-I-FRAME-STREAM-INF`, `EXT-X-SESSION-KEY`, `EXT-X-SESSION-DATA`,
  `EXT-X-PRELOAD-HINT`, `EXT-X-RENDITION-REPORT`

Relative URLs are resolved against the playlist URL before proxying.

## Bitrate Detection

Some HLS providers expose TS segments where ffprobe cannot read a per-video
bitrate, causing media servers to display `Video-Bitrate: 0 kbps`.

AniBridge mitigates this on `/strm/stream` by remuxing HLS inputs to fragmented MP4
when `STRM_PROXY_HLS_REMUX=true` (default). This keeps video codec data but gives
ffprobe/Jellyfin stream-level bitrate metadata.

Notes:

- Video is copied (no video re-encode). Audio is normalized to AAC for MP4 compatibility.
- If remux startup fails or `STRM_PROXY_HLS_REMUX=false`, AniBridge falls back to
  normal playlist rewriting.
- `BANDWIDTH` in HLS is still preserved and proxied unchanged.

## Refresh On Failure

If upstream returns `403/404/410/451/429` or times out, AniBridge re-resolves the provider URL and retries once.

## Examples

### STRM URL

```text
https://anibridge.example/strm/stream?site=s.to&slug=9-1-1&s=1&e=3&lang=German+Dub&sig=...
```

### Rewritten HLS Playlist

```m3u8
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1360921,RESOLUTION=1280x720
https://anibridge.example/strm/proxy/index-v1-a1.m3u8?u=https%3A%2F%2Fcdn.example%2Findex-v1-a1.m3u8&sig=...
#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=144009,RESOLUTION=1280x720,URI="https://anibridge.example/strm/proxy/iframes-v1-a1.m3u8?u=https%3A%2F%2Fcdn.example%2Fiframes-v1-a1.m3u8&sig=..."
```

### Segment Fetch

```text
GET /strm/proxy/seg-1-v1-a1.ts?u=https%3A%2F%2Fcdn.example%2Fseg-1-v1-a1.ts&sig=...
```

## Notes

::: warning
Sonarr can occasionally reject `.strm` imports with “No audio tracks detected” even when playback works. This
usually happens when Sonarr’s ffprobe succeeds on the `.strm` file and reports zero audio streams. Workaround:
use manual import or disable “Analyze video files” in Sonarr. See [Issue #50](https://github.com/zzackllack/anibridge/issues/50).
:::

- AniBridge never redirects STRM playback; bytes are streamed.
- `STRM_PUBLIC_BASE_URL` must match how your media server reaches AniBridge (LAN host, reverse proxy, etc.).
