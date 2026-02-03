---
title: Overview
outline: deep
---

# AniBridge Overview

::: danger Legal Disclaimer
Before you start, read the [Legal Disclaimer](/legal). You are responsible for lawful use and compliance with third‑party terms.
:::

AniBridge is a FastAPI-based bridge that exposes:

- Torznab endpoint for discovery and search by indexers (e.g., Prowlarr)
- qBittorrent-compatible API shim for download automation (e.g., Sonarr)
- Background scheduler with job tracking, cancellation, and progress
- Simple health endpoint for orchestration

It targets AniWorld for anime, Serienstream/s.to for general series, and megakino for additional series/movies, orchestrating provider selection, language selection, quality probing, and smart file naming across catalogues.

[[toc]]

## Architecture

- **FastAPI app** (`app/main.py`): mounts Torznab and qBittorrent routers, health checks, jobs SSE, direct download enqueueing.
- **Torznab router** (`/torznab/api`): implements `caps`, `search`, and `tvsearch`, returning magnet-like entries with embedded metadata.
- **qBittorrent shim** (`/api/v2/*`): minimal subset Sonarr/Prowlarr expect (`auth`, `torrents/*`, `sync/maindata`, etc.).
- **Scheduler** (`app/core/scheduler.py`): thread pool executor, job registry, cancelation, and DB updates.
- **Downloader** (`app/core/downloader.py`): provider fallback, yt-dlp, language validation, and final release renaming.
- **Models & DB** (`app/models.py`): SQLModel/SQLite for Jobs, EpisodeAvailability cache, and ClientTask (qBittorrent torrent mirror).
- **Utilities**: title resolution, magnet building/parsing, quality probing, naming, and logging.

## Key Endpoints

- `GET /health`: health check
- `POST /downloader/download`: enqueue a download job directly
- `GET /jobs/{job_id}`: job status
- `GET /jobs/{job_id}/events`: job Server-Sent Events
- `DELETE /jobs/{job_id}`: cancel a job
- `GET /torznab/api`: Torznab endpoint (caps/search/tvsearch)
- `POST /api/v2/torrents/add`: qBittorrent shim to add a task

See the full [API Reference](/api/overview) for parameters and examples.

## Typical Flow

1. Prowlarr queries `/torznab/api?t=tvsearch` to find releases for a series/episode.
2. Sonarr posts the magnet to `/api/v2/torrents/add` (our shim), which enqueues an AniBridge download job.
3. AniBridge probes availability and quality, downloads via yt-dlp, and renames to a clean release name.
4. Sonarr polls `/api/v2/sync/maindata`, `/api/v2/torrents/info`, `/api/v2/torrents/files`, and `/api/v2/torrents/properties` to track progress and import the final file.

## Features

- Provider fallback with language validation
- Preflight quality probe (yt-dlp) with semi-cached availability
- Structured logs to terminal and daily rotating files in `data/`
- Config via environment variables (Docker-friendly)
- Clean release filenames: `Series.S01E01.1080p.WEB.H264.GER-ANIWORLD.mkv`

Next: continue to [Quickstart](/guide/quickstart) and wire up Prowlarr/Sonarr in minutes.
