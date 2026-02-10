---
title: qBittorrent API Shim
outline: false
post_title: qBittorrent API Shim
author1: Zack Lack
post_slug: qbittorrent-api-shim
microsoft_alias: zzackllack
featured_image: /logo.png
categories:
  - API
tags:
  - qbittorrent
  - api
  - sonarr
  - prowlarr
ai_note: Updated with AI assistance; reviewed by maintainers.
summary: Minimal qBittorrent-compatible endpoints used by *arr clients, backed by AniBridge jobs.
post_date: 2026-02-03
---

# qBittorrent API Shim

Base: `/api/v2`

AniBridge implements a minimal subset that Sonarr/Prowlarr use. Authentication is stubbed; any credentials are accepted and a `SID` cookie is set.

## Operations

<ApiOperations
  :tags="[
    'qBittorrent Auth',
    'qBittorrent Torrents',
    'qBittorrent Categories',
    'qBittorrent Sync',
    'qBittorrent Transfer',
    'qBittorrent App'
  ]"
  hide-branding
/>

## Behavior Notes

- `torrents/add` parses AniBridge magnet payload and enqueues an internal job.
- `torrents/info` mirrors progress, state, size, paths, and times from the job.
- `torrents/files` returns a single-file view with progress and size.
- `torrents/properties` exposes save path and size; values stabilize after completion.
- `savePath` defaults to `DOWNLOAD_DIR` and can be overridden via `QBIT_PUBLIC_SAVE_PATH`.
