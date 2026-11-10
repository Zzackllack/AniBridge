---
title: Overview
outline: deep
---

# AniBridge Overview

::: danger Legal Disclaimer
Before you start, read the [Legal and Compliance overview](/legal). You are
responsible for lawful use and compliance with third-party terms.
:::

AniBridge is a FastAPI-based bridge that exposes:

- Torznab endpoint for discovery and search by indexers (e.g., Prowlarr)
- qBittorrent-compatible API shim for download automation (e.g., Sonarr/Radarr)
- Background scheduler with job tracking, cancellation, and progress
- Simple health endpoint for orchestration

It targets AniWorld for anime, Serienstream/s.to for general series, megakino for additional series/movies, and optionally Filmo for movies. AniBridge orchestrates provider selection, language selection, quality probing, and smart file naming across catalogues.

[[toc]]

## Search Modes

- **Legacy** (default): live provider scraping on each Torznab search. It is
  deprecated but still available for AniWorld, s.to, and megakino.
- **Catalog query**: advanced, operator-configured search over metadata published
  by a collector you control. It adds canonical episode mappings and optional
  Filmo movies. There is no hosted zero-config catalog yet; a public one is
  planned. See [Catalog Query Mode](/guide/catalog-query).

Both modes download media locally. The collector is never in the media path.

## Architecture

- **FastAPI app** (`apps/api/app/main.py`): mounts Torznab and qBittorrent routers, health checks, jobs SSE, direct download enqueueing.
- **Torznab router** (`/torznab/api`): implements `caps`, `search`, and `tvsearch`, returning magnet-like entries with embedded metadata.
- **qBittorrent shim** (`/api/v2/*`): minimal subset Sonarr/Radarr/Prowlarr expect (`auth`, `torrents/*`, `sync/maindata`, etc.).
- **Scheduler** (`apps/api/app/core/scheduler.py`): thread pool executor, job registry, cancelation, and DB updates.
- **Downloader** (`apps/api/app/core/downloader/download.py`): provider fallback, yt-dlp, language validation, and final release renaming.
- **Models & DB** (`apps/api/app/db/models.py`): SQLModel/SQLite for Jobs, EpisodeAvailability cache, and ClientTask (qBittorrent torrent mirror).
- **Utilities**: title resolution, magnet building/parsing, quality probing, naming, and logging.

In query mode, `/torznab/api` is served by the catalog search layer instead of the
legacy router, and `/api/v2` adds durable local jobs. The collector supplies
metadata only; resolution, downloads, imports, STRM files, and cleanup stay on
the AniBridge host.

For a visual, algorithm-level walkthrough of module interactions, see the
[Developer Architecture Deep Dive](/developer/architecture).

## Key Endpoints

- `GET /health`: health check
- `POST /downloader/download`: enqueue a download job directly
- `GET /jobs/{job_id}`: job status
- `GET /jobs/{job_id}/events`: job Server-Sent Events
- `DELETE /jobs/{job_id}`: cancel a job
- `GET /torznab/api`: Torznab endpoint (caps/search/tvsearch/movie)
- `POST /api/v2/torrents/add`: qBittorrent shim to add a task
- `GET|POST /api/v1/jobs/{job_id}...`: optional query-mode management API
  (`MANAGEMENT_API_TOKEN`)

See the full [API Reference](/api/overview) for parameters and examples.

## Typical Flow

1. Prowlarr queries `/torznab/api?t=tvsearch` (or `t=movie`) to find releases.
2. Sonarr/Radarr posts the magnet to `/api/v2/torrents/add` (our shim), which enqueues a local download job.
3. AniBridge resolves the source, downloads via yt-dlp, and renames to a clean release name. Query mode may use canonical mappings for numbering.
4. The client polls `/api/v2/sync/maindata`, `/api/v2/torrents/info`, `/api/v2/torrents/files`, and `/api/v2/torrents/properties` to track progress and import the final file.

## Features

- Legacy provider fallback with language validation, or bounded collector-backed query search
- Preflight quality probe (yt-dlp) with semi-cached availability in legacy mode
- Durable local jobs with progress, cancel/retry, and completed-import handoff
- Structured logs to terminal and daily rotating files in `data/`
- Config via environment variables (Docker-friendly)
- Clean release filenames: `Series.S01E01.1080p.WEB.H264.GER-ANIWORLD.mkv`
- Optional Filmo movie releases in query mode with explicit audio/subtitle/quality evidence

Next: continue to [Quickstart](/guide/quickstart) and wire up Prowlarr/Sonarr in minutes.
