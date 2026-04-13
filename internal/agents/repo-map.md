# Repository Map

## Repository Root

- `AGENTS.md` — agent entrypoint and index.
- `.github/README.md` — project overview.
- `.github/copilot-instructions.md` — repository-level instructions for GitHub
  Copilot code reviews.
- `LICENSE` — BSD 3-Clause license.
- `VERSION` — current project version.
- `apps/api/pyproject.toml` — Python packaging metadata.
- `apps/api/uv.lock` — uv dependency lock.
- `apps/api/Dockerfile` — container build.
- `nixpacks.toml` — Nixpacks configuration.
- `docker/compose.yaml` / `docker/compose.dev.yaml` — compose configs.
- `wrangler.toml` — Cloudflare Workers config for docs.
- `apps/api/` — Python backend project root.
- `docs/` — VitePress documentation source.
- `internal/specs/` — specifications and planning artifacts.
- `apps/api/tests/` — pytest suite organized into `integration/api/` and
  domain-oriented `unit/` coverage.
- `scripts/` — helper scripts.
- `apps/api/hooks/` — PyInstaller hooks.
- `data/` — runtime data. Never commit artifacts here.

## `apps/api/app/` High-Level Layout

- `api/` — endpoint routers grouped by domain.
- `core/` — bootstrap, scheduler, downloader, lifespan.
- `hosts/` — direct-video host wrappers and extraction registry.
- `core/downloader/extractors/` — local extractor overrides for fragile
  upstream host logic such as VOE.
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
- `src/legal/index.md` — legal/compliance landing page.
- `src/legal/legal-notice.md` — main legal notice and project boundary
  statement.
- `src/legal/acceptable-use.md` — disallowed use and deployment patterns.
- `src/legal/dmca.md` — project-facing DMCA contact page.
- `src/legal/rights-holder-notice.md` — repository-specific notice routing.
- `src/legal/contributor-ip.md` — contributor provenance requirements.
- `worker.ts` — Cloudflare Worker entry for docs hosting.
- `package.json`, lockfiles — docs dependencies.

## `scripts/` Directory

- `local_build_release.sh` — local artifact build helper.
- `local_build_release.ps1` — PowerShell equivalent.
- `setup-codex-overlay.sh` — agent overlay helper.
- `startup-script.sh` — example startup script.

## File Reference Index

- `apps/api/app/main.py` — FastAPI app entry.
- `apps/api/app/cli.py` — CLI server runner.
- `apps/api/app/config.py` — environment configuration.
- `apps/api/app/core/bootstrap.py` — env bootstrap and log setup.
- `apps/api/app/core/lifespan.py` — FastAPI lifespan manager.
- `apps/api/app/core/scheduler.py` — thread pool management.
- `apps/api/app/core/downloader/*` — download orchestration.
- `apps/api/app/hosts/*` — direct-video host wrappers and registry.
- `apps/api/app/api/health.py` — health check router.
- `apps/api/app/api/legacy_downloader.py` — legacy download endpoint.
- `apps/api/app/api/torznab/api.py` — Torznab handlers.
- `apps/api/app/api/qbittorrent/*` — qBittorrent shim endpoints.
- `apps/api/app/db/models.py` — SQLModel definitions and CRUD.
- `apps/api/app/domain/models.py` — domain models.
- `apps/api/app/utils/*` — shared utilities.
- `apps/api/app/infrastructure/*` — logging, public-IP/network helpers, system info.
- `docs/.vitepress/config.mts` — docs site config.
- `docs/worker.ts` — Cloudflare Worker entry.
