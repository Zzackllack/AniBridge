---
title: Jobs & Events
outline: false
---

# Jobs & Events

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

Fields also accepted: `link`, `provider`, `title_hint`.

## SSE Notes

`/jobs/{job_id}/events` emits `data: { ... }\n\n` as the job updates.
