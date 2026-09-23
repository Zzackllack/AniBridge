# Deployment

## `apps/api/Dockerfile` Highlights

- Base image: `python:3.14-slim`.
- Multi-stage build (`base`, `deps`, `final`).
- Installs `gosu` and build essentials for runtime compatibility.
- Non-root user `appuser` (UID/GID configurable).
- Healthcheck hits `/health` every 30s.
- Entrypoint: `docker/entrypoint.sh` sets UID/GID and ensures directories.

## Entrypoint Script (`docker/entrypoint.sh`)

- Configurable via `PUID`, `PGID`, `CHOWN_RECURSIVE`.
- Ensures directories exist and have correct ownership.
- Handles optional download/public paths.
- Does not run migrations; schema changes are applied in app startup.

## Images

- Published to `ghcr.io/zzackllack/anibridge` via `.github/workflows/publish.yml`.
- Tags derived from branch, commit SHA, `latest`, and `VERSION`.

## Packaged application

- Release executables use the PyInstaller hooks under `apps/api/hooks/`.
- `hook-app.db.py` includes the Alembic migration tree because packaged
  startup loads those scripts by file path instead of ordinary imports.

## Docker Compose

### `docker/compose.yaml`

- Service `anibridge` uses `ghcr.io/zzackllack/anibridge:latest`.
- Ports: `8000:8000`.
- Volume: `./data:/data` (DB, downloads, logs).
- Upstream configuration/session state defaults to `/data/aniworld` through
  `ANIWORLD_INSTALL_FOLDER`; the process user's home is not repurposed.
- Healthcheck uses curl to `/health`.
- Migrations run at app startup when `DB_MIGRATE_ON_STARTUP=true` (default).

### `docker-compose.dev.yaml`

- Optional Sonarr/Prowlarr containers for end-to-end testing.
- Shared network `anibridge-dev-net`.
- `anibridge` enables `ANIBRIDGE_RELOAD=true` for containerized development.
- Compose `develop.watch` syncs `apps/api/app/` into `/app/app` and rebuilds the image when build inputs change.
