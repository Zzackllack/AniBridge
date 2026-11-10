---
title: Radarr
outline: deep
---

# Radarr Integration

::: danger Legal Disclaimer
Read the [Legal and Compliance overview](/legal) before using clients. You are
responsible for ensuring lawful use.
:::

Point Radarr at AniBridge’s qBittorrent-compatible API.

## Add Download Client

1. Radarr → Settings → Download Clients → + → qBittorrent
2. Set Host and Port to AniBridge:
   - Host: `anibridge` (or `localhost`)
   - Port: `8000`
3. Username/Password: any when `QBIT_USERNAME`, `QBIT_PASSWORD`, and
   `QBIT_SESSION_SECRET` are unset. Otherwise use the configured credentials.
4. Category: `prowlarr` or none (or a custom one you create via API)
5. Test and Save

## Configure AniBridge Indexer to only use the AniBridge Download Client

1. Radarr → Settings → Indexers → [your Indexer Name (Prowlarr)] → Make sure the hidden/advanced settings are shown (gear icon bottom right) → Downloader → Select `AniBridge` (or whatever you named the qBittorrent client above)

## Filmo Movies (Query Mode)

Filmo movie support requires `CATALOG_MODE=query`, `filmo.to` in
`CATALOG_SITES`, and a collector that publishes Filmo metadata. Movie releases use
category `2000`.

Filmo exposes each native offer as an explicit variant. ID searches need a
published `tmdb-movie` or `imdb` mapping; text searches work without one but
automatic matching can be unreliable. Only VOE and Byse offers are selectable.
Declared quality labels may be omitted from the title when Radarr cannot represent
them without guessing; they remain in Torznab attributes and the description.
See [Filmo](/integrations/providers/filmo) and
[Catalog Query Mode](/guide/catalog-query#filmo-movies-optional).

## Completed Download Handling

AniBridge reports progress, save path, and final `content_path` so Radarr can import the file when the job completes.

When Radarr imports and moves or deletes the source file, AniBridge keeps the
torrent completed: progress remains `1`, query mode reports `pausedUP` (legacy
rows keep their completed projection), and `anibridge_output_missing` becomes
`true`. No `content_path` or file list is reported for the missing source.
AniBridge does not report `missingFiles` and does not rewrite the completed job to
`failed` or `error`.

If Radarr runs in a different container with a different mount, set `QBIT_PUBLIC_SAVE_PATH` to the path Radarr sees (inside the Radarr container), and ensure both containers mount the same host folder to that path.

### Required Docker volume mapping

- AniBridge container: mount your host downloads folder to `/data/downloads` (default) or any path you prefer.
- Radarr container: mount the same host folder to the exact path you choose for `QBIT_PUBLIC_SAVE_PATH` (e.g. `/downloads`).

Example (host path shown as `/path/to/downloads`):

- AniBridge: `-v /path/to/downloads:/data/downloads`
- Radarr: `-v /path/to/downloads:/downloads`
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
- Ensure both containers mount the same host folder to that path (`-v /host/downloads:/downloads` for radarr; `-v /host/downloads:/data/downloads` for AniBridge).
- Verify via the API endpoints above that AniBridge publishes `/downloads`.
