# Caching And Persistence Spec

## Status

Draft

## Scope

Define caching options for resolved URLs and rewritten playlists without immediate DB migrations, and document a future persistence path using Alembic/SQLModel.

## Last updated

2026-02-03

## In-Memory Cache (MVP)

- Key: `(site, slug, season, episode, language, provider)`.
- Value: `resolved_url`, `resolved_headers`, `resolved_at`, `last_status`, `fail_count`.
- TTL: configurable (e.g., `STRM_PROXY_CACHE_TTL_SECONDS`).
- On refresh-eligible failures, invalidate cache entry and re-resolve.

## Optional File-Based Cache (If Needed)

- Simple JSON or SQLite-backed cache file stored under `DATA_DIR`.
- Must tolerate process restarts and be safe for concurrent workers (decision gate).

## Future Persistence (StrmUrlMapping)

A persistent mapping table is already sketched in prior STRM refresh notes and should be used once migrations are approved.

- Proposed schema includes `strm_path`, `resolved_url`, `resolved_at`, episode identity, and optional `provider_used`. See `specs/004-strm-file-support/refresh-boilerplate.md:32`.
- When added, it should be implemented via Alembic migrations (current project already uses Alembic). See `app/db/models.py:170` and `app/db/migrations/versions/20260203_0001_initial_schema.py:1`.

## Interaction With Current DB Reality

- AniBridge uses SQLite and Alembic migrations at startup (`DB_MIGRATE_ON_STARTUP`). See `app/db/models.py:133` and `app/core/lifespan.py:130`.
- The current Docker entrypoint does not delete the DB file; persistence depends on volume mounts. See `docker/entrypoint.sh:33` and `docker-compose.yaml:90`.

## Cache Invalidation Rules

1. Invalidate cache entry on refresh-eligible failures.
2. Invalidate cache entry when provider resolver fails or returns a different host.
3. Allow manual cache purge via admin endpoint (future).

## Decision Gates

- Whether to require persistence in Phase 1.
- Whether to store resolved headers (e.g., `Referer`, `User-Agent`) in cache/persistence.
- Whether to cache rewritten playlists or only resolved URLs.
