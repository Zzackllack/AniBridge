---
title: FAQ
outline: deep
---

# Frequently Asked Questions

## Is AniBridge a real torrent client?

No. It emulates a subset of the qBittorrent Web API so that automation tools can talk to it. Under the hood, AniBridge downloads directly from supported providers via yt-dlp. Catalog query mode changes search only; media downloads stay local.

## What is catalog query mode?

An advanced, operator-configured search path that reads metadata previously
published by a collector you control. It supports canonical episode mappings and
optional Filmo movies. It is not the default and there is no hosted zero-config
catalog yet. See [Catalog Query Mode](/guide/catalog-query).

## Do I need a metadata URL or token?

Not for legacy mode. Query mode requires a collector origin, source ID, and
bearer token that you supply. An official public catalog without user-entered
metadata settings is planned and is not available yet.

## Which languages are supported?

Legacy labels include German Dub, German Sub, English Sub, English Dub, and
`Deutsch` for megakino. Site defaults differ: AniWorld uses German Dub/Sub and
English Sub; s.to uses German Dub and English Dub; megakino uses Deutsch/German Dub.
Filmo uses each offer's declared audio languages and does not advertise unknown
audio as a known language.

## Do I need an API key for Torznab?

Optional. Set `INDEXER_API_KEY` to require `apikey` on `/torznab/api`.

## Does AniBridge require qBittorrent login?

No. Authentication is optional. Set `QBIT_USERNAME`, `QBIT_PASSWORD` (16+ bytes),
and `QBIT_SESSION_SECRET` (32+ random bytes) together to require a signed session;
leave them empty for unauthenticated compatibility on a trusted private network.

## Where are files saved?

To `DOWNLOAD_DIR`. The DB and logs live in `DATA_DIR`. Sonarr can see a mapped path via `QBIT_PUBLIC_SAVE_PATH`.

## How are file names constructed?

`Series.S01E01.1080p.WEB.H264.GER-ANIWORLD.mkv`. Legacy names use the requested
season/episode and measured height/codec where available. Query names use
canonical `SxxEyy` when published, native numbering otherwise, and retain the
provider suffix (`-ANIWORLD`, `-STO`, `-MEGAKINO`, `-FILMO`). Filmo movies append
the year.

## Does AniBridge handle Sonarr's Anime/Absolute numbering?

No. AniBridge does not translate absolute episode requests into provider
seasons/episodes or rewrite outputs to absolute numbers. Sonarr must send
coordinates that match the source or a published query-mode mapping.

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
