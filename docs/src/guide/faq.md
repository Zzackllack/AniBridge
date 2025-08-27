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

