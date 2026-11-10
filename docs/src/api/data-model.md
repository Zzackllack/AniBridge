---
title: Data Model
outline: deep
---

# Data Model

AniBridge uses SQLite stored under `DATA_DIR/anibridge_jobs.db`. Legacy jobs use
the SQLModel tables below. Catalog query mode adds durable request and alias
tables in the same database; it does not move media or job state to the
collector.

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

## StrmUrlMapping

Persistent mapping for legacy STRM proxying (resolved upstream URLs).

```ts
site: string
slug: string
season: number
episode: number
language: string
provider: string // empty string when no provider hint
resolved_url: string
provider_used?: string
resolved_headers?: object
resolved_at: datetime
updated_at: datetime
```

## Catalog Query Mode

Query jobs reuse `job` and `clienttask`, and add:

- `durable_request`: the frozen accepted magnet payload, generation, lease,
  retry/error state, and version. A request survives cache eviction and collector
  loss because its source selection is self-contained.
- `grab_alias`: maps a release infohash to a durable job.
- `catalog_task`: queued alias-removal intents, so a crash cannot lose a delete.
- `catalog_cache`: completion-bound playback registration for proxy STRM
  requests.
- `catalog_override`: local mapping corrections, bounded per provider.

The migrations also retain `catalog_source`, `catalog_clock`, `catalog_trust`,
`catalog_version`, `catalog_active`, `catalog_control` and `catalog_update` for
schema compatibility. They do not distribute snapshots to query clients. The
active request cache and revision floors live separately in
`DATA_DIR/catalog/query-cache.sqlite`.

Query job states include `queued`, `resolving`, `downloading`, `retry_wait`,
`paused`, `blocked`, `cancelling`, `cancelled`, `failed`, and `completed`.
Completed records publication, not permanent file ownership. The qBittorrent
projection keeps a completed job at `pausedUP` with progress `1` even when the
imported source was moved or removed, exposing `anibridge_output_missing: true`
instead of `missingFiles`.
