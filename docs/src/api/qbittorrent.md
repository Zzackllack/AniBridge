---
title: qBittorrent API Shim
outline: deep
---

# qBittorrent API Shim

Base: `/api/v2`

AniBridge implements a minimal subset that Sonarr/Prowlarr use. Authentication is stubbed; any credentials are accepted and a `SID` cookie is set.

## Auth

```http
POST /api/v2/auth/login
POST /api/v2/auth/logout
```

## Torrents

```http
POST /api/v2/torrents/add
  urls={magnet}\n{magnet2}\n...
  category=prowlarr
  savepath=/path

GET  /api/v2/torrents/info?category=prowlarr
GET  /api/v2/torrents/files?hash={btih}
GET  /api/v2/torrents/properties?hash={btih}
POST /api/v2/torrents/delete?hashes={btih}
```

Behavior notes:

- `torrents/add` parses AniBridge magnet payload and enqueues an internal job.
- `torrents/info` mirrors progress, state, size, paths, and times from the job.
- `torrents/files` returns a single-file view with progress and size.
- `torrents/properties` exposes save path and size; values stabilize after completion.

## Categories

```http
GET  /api/v2/torrents/categories
POST /api/v2/torrents/createCategory
POST /api/v2/torrents/editCategory
POST /api/v2/torrents/removeCategories
```

`savePath` defaults to `DOWNLOAD_DIR` and can be overridden via `QBIT_PUBLIC_SAVE_PATH`.

## Sync

```http
GET /api/v2/sync/maindata
```

Minimal object with `torrents`, `categories`, and `server_state` that Sonarr expects.

## App

```http
GET /api/v2/app/version
GET /api/v2/app/webapiVersion
GET /api/v2/app/buildInfo
GET /api/v2/app/preferences
```

Preferences include `save_path` and a few harmless defaults.

