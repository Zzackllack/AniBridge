---
title: qBittorrent API Shim
outline: false
---

# qBittorrent API Shim

Base: `/api/v2`

AniBridge implements a minimal subset that Sonarr/Prowlarr use. Authentication is stubbed; any credentials are accepted and a `SID` cookie is set.

<OASpec
  :tags="[
    'qBittorrent Auth',
    'qBittorrent Torrents',
    'qBittorrent Categories',
    'qBittorrent Sync',
    'qBittorrent Transfer',
    'qBittorrent App'
  ]"
  :group-by-tags="true"
  hide-info
  hide-servers
  hide-branding
/>

## Behavior Notes

- `torrents/add` parses AniBridge magnet payload and enqueues an internal job.
- `torrents/info` mirrors progress, state, size, paths, and times from the job.
- `torrents/files` returns a single-file view with progress and size.
- `torrents/properties` exposes save path and size; values stabilize after completion.
- `savePath` defaults to `DOWNLOAD_DIR` and can be overridden via `QBIT_PUBLIC_SAVE_PATH`.
