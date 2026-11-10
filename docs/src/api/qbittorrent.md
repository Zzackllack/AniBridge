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
  - radarr
  - prowlarr
ai_note: Updated with AI assistance; reviewed by maintainers.
summary: Minimal qBittorrent-compatible endpoints used by *arr clients, backed by AniBridge jobs.
post_date: 2026-02-03
---

# qBittorrent API Shim

Base: `/api/v2`

AniBridge implements a minimal subset that Sonarr, Radarr, and Prowlarr use.

## Authentication

Authentication is optional. With `QBIT_USERNAME`, `QBIT_PASSWORD` (16+ bytes),
and `QBIT_SESSION_SECRET` (32+ random bytes) configured together,
`/api/v2/auth/login` issues a signed one-hour `SID` session cookie and every other
`/api/v2` route requires that session. Rotating the credentials or secret
invalidates existing sessions. Partial configuration refuses startup.

Leaving all three empty keeps unauthenticated compatibility for a trusted private
network. `QBIT_COOKIE_SECURE` defaults to `true` for HTTPS ingress; set it to
`false` only for trusted private HTTP. See
[qBittorrent authentication](/api/environment#qbittorrent-authentication).

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

- `torrents/add` parses the AniBridge magnet payload and enqueues a local job.
  Legacy items use provider fields (`aw_*`/`sto_*`). Query items use the opaque,
  versioned `ab_v` payload. Invalid identity, disabled providers, full queues, and
  storage pressure are rejected with explicit errors.
- Query mode limits concurrent downloads to two (or `MAX_CONCURRENCY` if lower).
  Legacy mode uses `MAX_CONCURRENCY`.
- `torrents/info` and `sync/maindata` report progress from `0` to `1`, state,
  size, paths, and timestamps. Common states are `queuedDL`, `metaDL`,
  `downloading`, `pausedDL`, `stalledDL`, `error`, `uploading`, and `pausedUP`.
- `torrents/files` returns a single-file view with progress and size, or an empty
  list when the completed source is unavailable.
- `torrents/properties` exposes save path and size; values stabilize after
  completion.
- `savePath` defaults to `DOWNLOAD_DIR` and can be overridden via
  `QBIT_PUBLIC_SAVE_PATH`.
- Items may include `anibridge_size_estimated: true` when an HLS total is
  estimated rather than measured.

## Completed Import and Missing Sources

Completion records a verified publication, not permanent ownership of the file.
If Sonarr or Radarr imports the file and then moves or deletes the source,
AniBridge keeps the torrent completed:

- `progress` remains `1`
- `state` remains a completed state (query mode reports `pausedUP`; legacy
  projections keep their released completion state)
- `eta` is `0`
- `content_path` is empty
- `torrents/files` returns an empty list
- `anibridge_output_missing` is `true`

It does not report `missingFiles`, does not turn the job into `failed` or
`error`, and does not rewrite the completion record. AniBridge does not
automatically redownload a completed transfer whose imported source was moved or
removed.

## Deletion and TTL

- `torrents/delete` removes the torrent alias. With `deleteFiles=true` or
  `DELETE_FILES_ON_TORRENT_DELETE=true` (default), AniBridge also deletes the
  AniBridge-owned source after the final alias is removed. Paths outside the
  download root are never deleted.
- `DOWNLOADS_TTL_HOURS` (default `0`, disabled) removes old video files from
  `DOWNLOAD_DIR` on the `CLEANUP_SCAN_INTERVAL_MIN` cadence (default 30 minutes).
  TTL cleanup does not delete `.strm` files and skips directories owned by active
  jobs. Expired completed files use the same completed-and-missing representation
  above.
- `QBIT_PUBLIC_SAVE_PATH` only changes what clients see. It does not change where
  AniBridge writes files.

## Management API

Query mode also exposes optional local management endpoints when
`MANAGEMENT_API_TOKEN` is set:

- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/retry`
- `POST /api/v1/jobs/{job_id}/cancel`

The token must be base64url of at least 32 random bytes and is independent of the
qBittorrent credentials, `INDEXER_API_KEY`, the collector token, and STRM auth.
Without it, these endpoints return 503. Retry is only available for failed or
blocked jobs.
