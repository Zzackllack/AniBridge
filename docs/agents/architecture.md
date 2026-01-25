# Architecture

## Runtime Architecture Overview

- Entrypoint flow:
  1. `app/main.py` calls bootstrap to load env vars and configure logging.
  2. FastAPI app created with custom lifespan (`app/core/lifespan.py`).
  3. Routers for Torznab, qBittorrent, health, and legacy downloader attached.
  4. Lifespan initializes DB, scheduler, cleanup threads, proxy env, and update notifier.

- Layered structure:
  - API layer: `app/api` exposes HTTP endpoints and validation.
  - Core services: `app/core` manages bootstrap, scheduler, downloads.
  - Domain models: `app/domain` defines domain data classes.
  - Persistence: `app/db` manages SQLModel models and CRUD.
  - Infrastructure: `app/infrastructure` handles logging, proxy env, system reports.
  - Utilities: `app/utils` contains shared helpers.

## Request Lifecycle Example (Torznab Search)

1. Client hits `/torznab/api` with query parameters.
2. Router delegates to `app/api/torznab/api.py`.
3. Title resolution uses `app/utils/title_resolver.py`.
4. Providers queried via AniWorld library; results formatted to Torznab XML.
5. Response returned; job scheduling triggered if download requested.

## Download Lifecycle

- Jobs created in DB via `app/db/models.create_job`.
- `app/core/scheduler` manages a thread pool respecting `MAX_CONCURRENCY`.
- `app/core/downloader` orchestrates provider fallback and progress updates.
- Completion updates job and client task states for qBittorrent shim.

## Download Pipeline and Providers

- Provider ordering is controlled by `PROVIDER_ORDER`.
- Quality probing uses `app/utils/probe_quality.py` (yt-dlp metadata).
- Results stored under `DOWNLOAD_DIR`, optionally mapped to a public save path.
- TTL cleanup removes old downloads when `DOWNLOADS_TTL_HOURS` > 0.

## Scheduler & Background Services

- Thread pool size controlled by `MAX_CONCURRENCY` (default 3).
- Cleanup thread deletes downloads older than `DOWNLOADS_TTL_HOURS`.
- Public IP monitor runs when proxy is enabled or `PUBLIC_IP_CHECK_ENABLED`.
- Lifespan ensures graceful shutdown of scheduler, DB engine, and background threads.

## Logging & Observability

- Loguru configuration lives in `app/utils/logger.py`.
- `TerminalLogger` duplicates stdout/stderr to `data/terminal-YYYY-MM-DD.log`.
- `/health` endpoint provides liveness/readiness details.
- Update notifier logs when new GitHub releases are available.
