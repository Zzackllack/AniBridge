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

## Local query pilot

Use the isolated [Compose guide](../../scripts/catalog/query_pilot/README.md).
Build images from the selected local commit, keep all pilot volumes disposable,
and publish ports on loopback only. The generated fixture has no Internet
access or media. Do not provision a source, SSH, or alter a real installation
without explicit authorization. Job/resource enforcement is Linux-only; Docker
is the supported maintainer path.

Confirmed pilot defects and production collection requirements are tracked in
[the catalog issue backlog](../specs/020-catalog-query-api-evaluation/ISSUES.md).
The current pilot's rate/backoff defaults are not production throughput promises.
Check Docker/VPN subnet overlap before deployment; retain disposable state and
explicit test profiles when validating collection improvements on the authorized
host. Production collector minimum is 2 vCPU/2 GiB, recommended 4 vCPU/4 GiB;
the original 512-MiB collector was a constrained test. The authorized October 11
preview rollout uses 2 vCPU/2 GiB for collection and 512 MiB for metadata.
Specs alone do not change live allocations.

For the existing fra-node-01 Coolify pilot, use the pinned GHCR procedure
and exact rollback in [SERVER.md](../../scripts/catalog/query_pilot/SERVER.md#october-11-published-preview-deployment).
`stage_upgrade.py` is the historical local-image-only helper; it does not support
the current registry references. Do not start a
manual competing stack, alter allocations or restore ledgers for this compatible
code rollback. Deployment/restart/resource changes need explicit approval.

October 14 mapping rollout is now authorized and matching native previews are
published for `2240b91`; the pilot and separate local client cutovers completed
through the approved workflow. The initializer source and config volume both
need the reviewed worker JSON; otherwise startup overwrites the language setting.
SERVER.md has a
guarded registry preparation helper, additive v5 upgrade and exact code-only
worker/client rollback. Downgrade removes private v5 tables only after the durable
canonical admission window expires; retain every v4 table and both pre-v4/pre-v5
backups. Coolify writes require the existing authenticated Zen UI after explicit
approval; its read-only token must not be broadened. Do not start a competing
collector or restore an old ledger over newer observations.

For repeat updates use [WORKER_UPDATES.md](../../scripts/catalog/query_pilot/WORKER_UPDATES.md).
`prepare_worker_update.py` checks the selected commit's CI and native manifests,
pins its digest, preserves worker configuration and stages exact rollback bytes.
Its stopped-state commands snapshot committed WAL data and verify release/map/
retry preservation. They do not automate Coolify writes or host-wide disk
admission. Current supported private migration formats are v5/v6; do not use a
moving `latest`/PR tag or an unattended updater for this pilot.

October 19's approved Zen cutover runs `52065c7`, private state v6/schema2 read
artifacts, at the digest in SERVER.md. Full stopped release/map/history comparisons
and real Sonarr metadata search passed. Keep the durable operator plan and all
backup generations. Its `rollback-v5` command uses the new image before restoring
the retained d85ed05 Compose; it never restores an old ledger. One-off update/
binary-export containers disable Docker logging; the initial archive's transient
log peak was not measured, while final disk accounting remains under the cap.
