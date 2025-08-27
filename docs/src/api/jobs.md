---
title: Jobs & Events
outline: deep
---

# Jobs & Events

AniBridge exposes a simple job model with progress tracking and SSE.

## Enqueue Directly

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

Response:

```json
{ "job_id": "..." }
```

Fields also accepted: `link`, `provider`, `title_hint`.

## Poll Status

```http
GET /jobs/{job_id}
```

```json
{
  "id": "...",
  "status": "downloading|completed|failed|cancelled",
  "progress": 42.0,
  "downloaded_bytes": 123,
  "total_bytes": 456,
  "speed": 789,
  "eta": 12,
  "message": null,
  "result_path": "/path/to/file.mkv"
}
```

## Subscribe to Events (SSE)

```http
GET /jobs/{job_id}/events
Accept: text/event-stream
```

The stream emits `data: { ... }\n\n` as the job updates.

## Cancel

```http
DELETE /jobs/{job_id}
```

Returns `{ "status": "cancelling" | "not-running" }`.

