# Repository Map

## Repository Root

- `AGENTS.md` — agent entrypoint and index.
- `README.md` — project overview.
- `LEGAL.md` — legal disclaimer and usage restrictions.
- `LICENSE` — BSD 3-Clause license.
- `VERSION` — current project version.
- `pyproject.toml` — Python packaging metadata.
- `uv.lock` — uv dependency lock.
- `Dockerfile` — container build.
- `nixpacks.toml` — Nixpacks configuration.
- `docker-compose.yaml` / `docker-compose.dev.yaml` — compose configs.
- `wrangler.toml` — Cloudflare Workers config for docs.
- `app/` — Python application package.
- `docs/` — VitePress documentation source.
- `specs/` — specifications and planning artifacts.
- `tests/` — pytest suite.
- `scripts/` — helper scripts.
- `hooks/` — PyInstaller hooks.
- `data/` — runtime data. Never commit artifacts here.

## `app/` High-Level Layout

- `api/` — endpoint routers grouped by domain.
- `core/` — bootstrap, scheduler, downloader, lifespan.
- `db/` — SQLModel definitions and helpers.
- `domain/` — domain-level models.
- `infrastructure/` — logging, networking helpers, system diagnostics.
- `utils/` — shared helpers.
- `cli.py` — CLI entrypoint.
- `_version.py` — version helper.
- `config.py` — environment configuration.

## `docs/` Structure

- `.vitepress/` — VitePress config and theme.
- `src/` — Markdown and Vue content.
- `worker.ts` — Cloudflare Worker entry for docs hosting.
- `package.json`, lockfiles — docs dependencies.

## `scripts/` Directory

- `local_build_release.sh` — local release automation.
- `local_build_release.ps1` — PowerShell equivalent.
- `setup-codex-overlay.sh` — agent overlay helper.
- `startup-script.sh` — example startup script.

## File Reference Index

- `app/main.py` — FastAPI app entry.
- `app/cli.py` — CLI server runner.
- `app/config.py` — environment configuration.
- `app/core/bootstrap.py` — env bootstrap and log setup.
- `app/core/lifespan.py` — FastAPI lifespan manager.
- `app/core/scheduler.py` — thread pool management.
- `app/core/downloader.py` — download orchestration.
- `app/api/health.py` — health check router.
- `app/api/legacy_downloader.py` — legacy download endpoint.
- `app/api/torznab/api.py` — Torznab handlers.
- `app/api/qbittorrent/*` — qBittorrent shim endpoints.
- `app/db/models.py` — SQLModel definitions and CRUD.
- `app/domain/models.py` — domain models.
- `app/utils/*` — shared utilities.
- `app/infrastructure/*` — logging, public-IP/network helpers, system info.
- `docs/.vitepress/config.mts` — docs site config.
- `docs/worker.ts` — Cloudflare Worker entry.
