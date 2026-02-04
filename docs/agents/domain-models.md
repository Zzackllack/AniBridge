# Domain and Data Models

## Job Lifecycle Entities

- Job (SQLModel): `id`, `status`, `progress`, `downloaded_bytes`, `total_bytes`, `speed`, `eta`, `message`, `result_path`, timestamps.
- Status transitions: `queued` -> `downloading` -> (`completed` | `failed` | `cancelled`).

- ClientTask (SQLModel): qBittorrent-compatible task state.
  - Maps magnet hash to job ID and stores category, save path, completion timestamp.
  - States mirror qBittorrent enumerations (`queued`, `downloading`, `paused`, `completed`, `error`).

## Episode Availability Cache

- EpisodeAvailability (SQLModel)
  - Composite key: slug, season, episode, language, site.
  - Tracks provider availability and quality metadata.
  - `is_fresh` validates TTL against `AVAILABILITY_TTL_HOURS`.

## STRM Proxy Mapping

- StrmUrlMapping (SQLModel)
  - Composite key: site, slug, season, episode, language, provider.
  - Persists resolved upstream URLs and provider metadata for STRM proxying.

## Domain Models (Python)

- `app/domain/models.py` mirrors DB models but is decoupled for domain logic and API serialization.

## SQL Engine Helpers

- `apply_migrations()` runs Alembic migrations (default at app startup).
- `create_db_and_tables()` creates tables directly (used for tests/legacy paths).
- `cleanup_dangling_jobs()` resets jobs stuck in non-terminal state to `failed`.
- `dispose_engine()` closes engine on shutdown/testing.

## Migrations

- Alembic configuration lives in `alembic.ini`.
- Migration scripts live in `app/db/migrations/versions`.

## Data Directory

- SQLite database: `${DATA_DIR}/anibridge_jobs.db` (default `data/anibridge_jobs.db`).
- Downloads: `${DOWNLOAD_DIR}` (default `data/downloads/anime`).
- Logs: `data/logs` (ensured by `ensure_log_path`).
