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

## Demo: Video Embed (Docs‑only)

Below is a demo of the custom video component used in this documentation site. You can use it in any Markdown page as shown.

<VideoPlayer
  src="https://streamtape.com/e/wZQq0JaVZ9cJz3e/"
  poster="https://images.unsplash.com/photo-1501004318641-b39e6451bec6?q=80&w=1200&auto=format&fit=crop"
  title="Sample: Flower in 4K"
  caption="Custom player UI, brand‑matched accent"
  :autoplay="false"
  :muted="true"
  aspect="16 / 9"
  radius="16px"
/>

<iframe src="https://streamtape.com/e/wZQq0JaVZ9cJz3e/" width="800" height="600" allowfullscreen allowtransparency allow="autoplay" scrolling="no" frameborder="0"></iframe>

Usage:

```vue
<VideoPlayer
  src="https://youtu.be/dQw4w9WgXcQ"
  poster="/path/to/poster.jpg"
  title="YouTube Embed"
  caption="Custom UI with YouTube/Vimeo (play/mute)"
  :autoplay="true"
  :muted="true"
  aspect="21 / 9"
  radius="20px"
/> 
```
