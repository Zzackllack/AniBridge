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

### `docker/compose.dev.yaml`

- Optional Sonarr/Prowlarr containers for end-to-end testing.
- Shared network `anibridge-dev-net`.
- `anibridge` enables `ANIBRIDGE_RELOAD=true` for containerized development.
- Compose `develop.watch` syncs `apps/api/app/` into `/app/app` and rebuilds the image when build inputs change.

## Catalog services

Use [SERVER.md](../../scripts/catalog/query_pilot/SERVER.md) for a new authorized
private installation and [WORKER_UPDATES.md](../../scripts/catalog/query_pilot/WORKER_UPDATES.md)
for an existing service. The generated Compose fixture is not a production
collector. Collector minimum is 2 CPU/2 GiB; serving has a separate budget.

Pin tested immutable images, preserve every configuration/volume/backup and
use the private plan's version-guarded snapshot/verification/rollback commands.
No image build or documentation change authorizes a deployment, restart,
resource/routing change or state reset. Coolify writes use authenticated Zen
after approval; its read-only token is not broadened. Keep NetBird routes and
Docker/backend subnet allocations intact.

Writable state must enforce process-lock exclusion; move unsafe Mac binds through
a reviewed consistent backup plan instead of bypassing the guard. Maintain a
WAL-inclusive backup and retain newer observations during code rollback. Current
acceptance/release gaps are in [ISSUES.md](../specs/020-catalog-query-api-evaluation/ISSUES.md).
