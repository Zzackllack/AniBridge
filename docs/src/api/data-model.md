---
title: Data Model
outline: deep
---

# Data Model

AniBridge uses SQLite (via SQLModel) stored under `DATA_DIR/anibridge_jobs.db`.

## Job

Represents a download lifecycle.

```ts
id: string // UUID hex
status: 'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled'
progress: number // 0..100
downloaded_bytes?: number
total_bytes?: number
speed?: number // bytes/sec
eta?: number // seconds
message?: string
result_path?: string // final file path
created_at: datetime
updated_at: datetime
```

## EpisodeAvailability

Semi-cache of per-episode language/quality availability.

```ts
slug: string, season: number, episode: number, language: string
available: boolean
height?: number
vcodec?: string
provider?: string
checked_at: datetime
is_fresh(): boolean // compares against AVAILABILITY_TTL_HOURS
```

## ClientTask

Mirror of a “torrent” entry for the qBittorrent shim, linked to a Job.

```ts
hash: string // btih from magnet
name: string
slug: string, season: number, episode: number, language: string
job_id?: string
save_path?: string
category?: string
added_on: datetime
completion_on?: datetime
state: 'queued' | 'downloading' | 'paused' | 'completed' | 'error'
```

