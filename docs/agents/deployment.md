# Deployment

## Dockerfile Highlights

- Base image: `python:3.12-slim`.
- Multi-stage build (`base`, `deps`, `final`).
- Installs `gosu` and build essentials for runtime compatibility.
- Non-root user `appuser` (UID/GID configurable).
- Healthcheck hits `/health` every 30s.
- Entrypoint: `docker/entrypoint.sh` sets UID/GID and ensures directories.

## Entrypoint Script (`docker/entrypoint.sh`)

- Configurable via `PUID`, `PGID`, `CHOWN_RECURSIVE`.
- Ensures directories exist and have correct ownership.
- Handles optional download/public paths.

## Images

- Published to `ghcr.io/zzackllack/anibridge` via `.github/workflows/publish.yml`.
- Tags derived from branch, commit SHA, `latest`, and `VERSION`.

## Docker Compose

### `docker-compose.yaml`

- Service `anibridge` uses `ghcr.io/zzackllack/anibridge:latest`.
- Ports: `8000:8000`.
- Volume: `./data:/data` (DB, downloads, logs).
- Healthcheck uses curl to `/health`.

### `docker-compose.dev.yaml`

- Optional Sonarr/Prowlarr containers for end-to-end testing.
- Shared network `anibridge-dev-net`.
