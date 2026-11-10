---
title: Jobs & Events
outline: false
---

# Jobs & Events

The endpoints on this page are the legacy job API used by direct downloads and
legacy search. Query mode uses durable local jobs exposed through the
qBittorrent shim, plus optional `/api/v1/jobs/*` management endpoints. Both paths
download media locally.

## Legacy Job API

AniBridge exposes a simple job model with progress tracking and SSE.

## Operations

<ApiOperations :tags="['Jobs']" hide-branding />

## Enqueue Example

```http
POST /downloader/download
Content-Type: application/json

{
  "slug": "naruto",
  "season": 1,
  "episode": 1,
  "language": "German Dub"
}
```

Accepted fields are `link`, `slug`, `season`, `episode`, `provider`, `language`,
and `title_hint`. `provider` is a direct-host preference (default `VOE`) and
`language` defaults to `German Dub`. This endpoint bypasses search and creates a
legacy job; query-mode clients should use the qBittorrent shim instead.

## SSE Notes

`/jobs/{job_id}/events` emits `data: { ... }\n\n` as the job updates.

## Query Mode Jobs

Query mode is driven by the qBittorrent shim (`/api/v2/torrents/add`,
`/torrents/info`, `/sync/maindata`, and related routes). Jobs are durable local
records; progress is reported from 0 to 1 and reaches completion only after the
final file is published.

Optional local management endpoints:

- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/retry` with an empty JSON object and `If-Match`
- `POST /api/v1/jobs/{job_id}/cancel` with an empty JSON object and `If-Match`

They require `Authorization: Bearer <MANAGEMENT_API_TOKEN>` and return 503 when
no management token is configured. See [qBittorrent Shim](/api/qbittorrent#management-api).
