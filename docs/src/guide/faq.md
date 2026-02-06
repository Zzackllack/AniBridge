---
title: FAQ
outline: deep
---

# Frequently Asked Questions

## Is AniBridge a real torrent client?

No. It emulates a subset of the qBittorrent Web API so that automation tools can talk to it. Under the hood, AniBridge downloads directly from supported providers via yt-dlp.

## Which languages are supported?

German Dub, German Sub, and English Sub. Aliases like `GER`, `GERDub`, `EngSub` are normalized internally.

## Do I need an API key for Torznab?

Optional. Set `INDEXER_API_KEY` to require `apikey` on `/torznab/api`.

## Where are files saved?

To `DOWNLOAD_DIR`. The DB and logs live in `DATA_DIR`. Sonarr can see a mapped path via `QBIT_PUBLIC_SAVE_PATH`.

## How are file names constructed?

`Series.S01E01.1080p.WEB.H264.GER-ANIWORLD.mkv`. The height/codec are extracted from yt-dlp info or via `ffprobe`.

## Why does Jellyfin show 0 kbps bitrate?

Jellyfin relies on the HLS master playlist to read `BANDWIDTH` values from
`#EXT-X-STREAM-INF`. If the master playlist is not reachable (or the upstream
only serves a media playlist), Jellyfin may report 0 kbps. Ensure AniBridge can
serve the master playlist over HTTPS and that your `.strm` URLs resolve to it.

## Why doesn't Direct Play work in browser clients?

Browsers block mixed content. If Jellyfin is served over HTTPS and AniBridge is
HTTP, the browser will refuse to load the stream and Jellyfin will fall back to
server-side transcoding. Put AniBridge behind HTTPS and set
`STRM_PUBLIC_BASE_URL` to the HTTPS URL. Also confirm the public URL is reachable
by both the client device and the media server. If the client cannot reach AniBridge,
Direct Play will fail even if HTTPS is configured.

## Do I need a reverse proxy for AniBridge?

If your media server is HTTPS and you want Direct Play in browser clients, yes.
Expose AniBridge over HTTPS (reverse proxy or TLS-terminating load balancer) and
set `STRM_PUBLIC_BASE_URL` accordingly.
