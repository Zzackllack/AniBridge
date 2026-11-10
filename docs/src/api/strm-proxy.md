---
title: STRM Proxy
outline: deep
---

# STRM Proxy

AniBridge can generate `.strm` files that point to a stable AniBridge URL instead of a provider/CDN URL. The STRM proxy endpoints stream bytes, support HTTP Range, and rewrite HLS playlists so every segment/key request routes back through AniBridge.

Legacy jobs use `/strm/stream`. Catalog query jobs use `/strm/catalog`, which is
bound to a completed local request and resolves playback locally. In proxy mode,
imported query `.strm` files remain playable after the download client removes its
alias because playback registration is tied to the completed request, not the
torrent entry.

`STRM_PROXY_MODE=redirect` is not implemented and is treated as `proxy` streaming.

## When To Use

- You need stable `.strm` files that keep working even when provider URLs change.
- Jellyfin is outside the VPN while AniBridge is inside the VPN.
- You want HLS segment/key requests to always egress from AniBridge.

## Required Configuration

`STRM_PROXY_MODE=proxy`  
`STRM_PUBLIC_BASE_URL=https://<your-anibridge-host>`

Auth mode is controlled by `STRM_PROXY_AUTH`:

- `token` (default): HMAC signature in `sig`
- `apikey`: shared key in `apikey`
- `none`: no auth (LAN only)

STRM auth is independent of `INDEXER_API_KEY`, the qBittorrent credentials, the
collector bearer token, and `MANAGEMENT_API_TOKEN`. Protecting one does not
protect the others.

For query jobs, the top-level `.strm` URL is stable. Nested HLS resources carry
their own expiring signature and are never written to the catalog or sent to the
metadata service. In `direct` mode the `.strm` contains the resolved provider URL
and AniBridge is not in the playback path.

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

## Endpoints

<ApiOperations :tags="['STRM Proxy']" hide-branding />

## HLS Rewriting

AniBridge rewrites:

- URI lines
- `EXT-X-KEY`, `EXT-X-MAP`, `EXT-X-MEDIA`, `EXT-X-STREAM-INF`, `EXT-X-I-FRAME-STREAM-INF`, `EXT-X-SESSION-KEY`

Relative URLs are resolved against the playlist URL before proxying.

## Refresh On Failure

If upstream returns `403/404/410/451/429` or times out, AniBridge re-resolves the provider URL and retries once.

## Examples

### STRM URL

```text
https://anibridge.example/strm/stream?site=s.to&slug=9-1-1&s=1&e=3&lang=German+Dub&sig=...
```

### Query STRM URL

```text
https://anibridge.example/strm/catalog?job=<job-id>&ab_scope=catalog-playback-1&sig=...
```

The top-level URL is stable and does not carry the upstream URL. Nested HLS
resources use an expiring signature and an encoded upstream `u` parameter.

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

::: warning
Known limitation: STRM proxy playback can be unstable in some media players (notably Jellyfin) for certain HLS
streams. A common symptom is `Video-Bitrate: 0 kbps`, and there is currently no reliable AniBridge-side fix that
does not risk playback regressions (timeline/duration issues, early stop, or auto-next behavior). Track status can be monitored in [Issue #51](https://github.com/Zzackllack/anibridge/issues/51).
:::

- AniBridge never redirects STRM playback; bytes are streamed.
- `STRM_PUBLIC_BASE_URL` must match how your media server reaches AniBridge (LAN host, reverse proxy, etc.).
