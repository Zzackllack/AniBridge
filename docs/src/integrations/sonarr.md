---
title: Sonarr
outline: deep
---

# Sonarr Integration

Point Sonarr at AniBridge’s qBittorrent-compatible API.

## Add Download Client

1. Sonarr → Settings → Download Clients → + → qBittorrent
2. Set Host and Port to AniBridge:
   - Host: `anibridge` (or `localhost`)
   - Port: `8000`
3. Username/Password: any (auth is stubbed)
4. Category: `prowlarr` (or a custom one you create via API)
5. Test and Save

## Completed Download Handling

AniBridge reports progress, save path, and final `content_path` so Sonarr can import the file when the job completes.

If Sonarr runs in a different container with a different mount, set `QBIT_PUBLIC_SAVE_PATH` to the path Sonarr sees.

## What Sonarr Calls

- `POST /api/v2/torrents/add` (magnet from Prowlarr)
- `GET /api/v2/sync/maindata`
- `GET /api/v2/torrents/info`
- `GET /api/v2/torrents/files?hash=...`
- `GET /api/v2/torrents/properties?hash=...`

