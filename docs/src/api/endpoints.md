---
title: Endpoints
outline: deep
---

# Endpoints

This page summarizes all public endpoints. See subpages for details.

## Health

```http
GET /health
```

Returns `{ "status": "ok" }`.

## Jobs

- `POST /downloader/download` — enqueue a direct job
- `GET /jobs/{job_id}` — job status
- `GET /jobs/{job_id}/events` — Server-Sent Events (SSE)
- `DELETE /jobs/{job_id}` — cancel

## Torznab

```http
GET /torznab/api?t=caps|search|tvsearch&apikey=...&q=...&season=...&ep=...
```

See [Torznab](/api/torznab) for parameters and XML examples.

## qBittorrent API Shim

Base path: `/api/v2`

- Auth: `POST /auth/login`, `POST /auth/logout`
- App: `GET /app/version`, `GET /app/webapiVersion`, `GET /app/buildInfo`, `GET /app/preferences`
- Categories: `GET /torrents/categories`, `POST /torrents/createCategory`, `POST /torrents/editCategory`, `POST /torrents/removeCategories`
- Torrents: `POST /torrents/add`, `GET /torrents/info`, `GET /torrents/files`, `GET /torrents/properties`, `POST /torrents/delete`
- Sync: `GET /sync/maindata`
- Transfer: `GET /transfer/info`

See [qBittorrent Shim](/api/qbittorrent) for payloads and responses.

