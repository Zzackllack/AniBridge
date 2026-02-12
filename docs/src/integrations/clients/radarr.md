---
title: Radarr
outline: deep
---

# Radarr Integration

::: danger Legal Disclaimer
Read the [Legal Disclaimer](/legal) before using clients. You are responsible for ensuring lawful use.
:::

Point Radarr at AniBridge’s qBittorrent-compatible API.

## Add Download Client

1. Radarr → Settings → Download Clients → + → qBittorrent
2. Set Host and Port to AniBridge:
   - Host: `anibridge` (or `localhost`)
   - Port: `8000`
3. Username/Password: any (auth is stubbed)
4. Category: `prowlarr` or none (or a custom one you create via API)
5. Test and Save

## Configure AniBridge Indexer to only use the AniBridge Download Client

1. Radarr → Settings → Indexers → [your Indexer Name (Prowlarr)] → Make sure the hidden/advanced settings are shown (gear icon bottom right) → Downloader → Select `AniBridge` (or whatever you named the qBittorrent client above)

## Completed Download Handling

AniBridge reports progress, save path, and final `content_path` so Radarr can import the file when the job completes.

If Radarr runs in a different container with a different mount, set `QBIT_PUBLIC_SAVE_PATH` to the path Radarr sees (inside the Radarr container), and ensure both containers mount the same host folder to that path.

### Required Docker volume mapping

- AniBridge container: mount your host downloads folder to `/data/downloads/anime` (default) or any path you prefer.
- Radarr container: mount the same host folder to the exact path you choose for `QBIT_PUBLIC_SAVE_PATH` (e.g. `/downloads`).

Example (host path shown as `/path/to/downloads/anime`):

- AniBridge: `-v /path/to/downloads/anime:/data/downloads/anime`
- Radarr: `-v /path/to/downloads/anime:/downloads`
- AniBridge env: `QBIT_PUBLIC_SAVE_PATH=/downloads`

AniBridge’s qBittorrent shim will now publish:

- `save_path` = `/downloads` in `/api/v2/app/preferences`, `/sync/maindata`, `/torrents/info`, `/torrents/properties`
- `content_path` = `/downloads/<file>` once the file is known

### Verify mapping via API

Use a browser or curl:

- `GET /api/v2/app/preferences` → contains `"save_path": "/downloads"`
- `GET /api/v2/torrents/info` → for each item: `save_path` is `/downloads`; after completion `content_path` is `/downloads/<file>`
- `GET /api/v2/sync/maindata` → per torrent: `save_path` is `/downloads`
- `GET /api/v2/torrents/properties?hash=<btih>` → `save_path` is `/downloads`

## What Radarr Calls

- `POST /api/v2/torrents/add` (magnet from Prowlarr)
- `GET /api/v2/sync/maindata`
- `GET /api/v2/torrents/info`
- `GET /api/v2/torrents/files?hash=...`
- `GET /api/v2/torrents/properties?hash=...`

## Common error: path not found in container

Radarr error:

> You are using docker; download client qBittorrent places downloads in /host/path but this directory does not appear to exist inside the container. Review your remote path mappings and container volume settings.

Fix:

- Ensure `QBIT_PUBLIC_SAVE_PATH` is set to the path inside the Radarr container (e.g. `/downloads`).
- Ensure both containers mount the same host folder to that path (`-v /host/downloads:/downloads` for radarr; `-v /host/downloads:/data/downloads/anime` for AniBridge).
- Verify via the API endpoints above that AniBridge publishes `/downloads`.
