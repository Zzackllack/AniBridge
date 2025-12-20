<!--
AGENTS.md — Comprehensive Agent Enablement Guide for AniBridge
This document is auto-maintained by contributors. Update responsibly.
-->

# AniBridge Agent Operations Manual

> **Purpose:** Equip AI and human contributors with exhaustive, operational knowledge of the AniBridge repository, tooling, infrastructure, and workflows. This edition supersedes any prior AGENTS.md snapshots.

---

## 0. Meta Information

- **Repository:** `https://github.com/Zzackllack/AniBridge`
- **Primary Maintainer:** `@Zzackllack`
- **Last Full Refresh:** 2025-09-21
- **Documentation Version:** `2025.09-agents-v1`
- **Change Drivers:** Constitution v1.0.0, VitePress documentation site, Cloudflare Workers deployment pipeline, expanded module boundaries

---

## Table of Contents

1. [Orientation Checklist](#1-orientation-checklist)
2. [Project Snapshot](#2-project-snapshot)
3. [Tech Stack Matrix](#3-tech-stack-matrix)
4. [Runtime Architecture Overview](#4-runtime-architecture-overview)
5. [Directory & File Atlas](#5-directory--file-atlas)
6. [Python Application Modules](#6-python-application-modules)
7. [Domain & Data Models](#7-domain--data-models)
8. [API Surface & Contracts](#8-api-surface--contracts)
9. [Scheduler & Background Services](#9-scheduler--background-services)
10. [Configuration & Environment Variables](#10-configuration--environment-variables)
11. [Download Pipeline & Providers](#11-download-pipeline--providers)
12. [qBittorrent Shim Semantics](#12-qbittorrent-shim-semantics)
13. [Torznab Feed Semantics](#13-torznab-feed-semantics)
14. [CLI & Utilities](#14-cli--utilities)
15. [Logging & Observability](#15-logging--observability)
16. [Testing Strategy](#16-testing-strategy)
17. [Local Development Setup](#17-local-development-setup)
18. [Docker & Containerization](#18-docker--containerization)
19. [Compose Topologies](#19-compose-topologies)
20. [Documentation System (VitePress)](#20-documentation-system-vitepress)
21. [Cloudflare Workers Deployment](#21-cloudflare-workers-deployment)
22. [Scripts & Tooling](#22-scripts--tooling)
23. [Build, Release & Distribution](#23-build-release--distribution)
24. [CI/CD Workflows](#24-cicd-workflows)
25. [Automation Framework (.specify)](#25-automation-framework-specify)
26. [Constitution Alignment Checklist](#26-constitution-alignment-checklist)
27. [Onboarding Playbooks](#27-onboarding-playbooks)
28. [Multi-Agent Collaboration Patterns](#28-multi-agent-collaboration-patterns)
29. [Troubleshooting Playbooks](#29-troubleshooting-playbooks)
30. [Security & Compliance Notes](#30-security--compliance-notes)
31. [Legal Considerations](#31-legal-considerations)
32. [Glossary](#32-glossary)
33. [External Resources](#33-external-resources)
34. [Appendix A: Environment Variable Catalog](#appendix-a-environment-variable-catalog)
35. [Appendix B: File Reference Index](#appendix-b-file-reference-index)
36. [Appendix C: Test Suite Overview](#appendix-c-test-suite-overview)
37. [Appendix D: Release Playbook](#appendix-d-release-playbook)
38. [Appendix E: Documentation Editing Guide](#appendix-e-documentation-editing-guide)
39. [Appendix F: Agent Execution FAQ](#appendix-f-agent-execution-faq)
40. [Change Log](#change-log)

---

## 1. Orientation Checklist

1. Clone repository and verify Python ≥ 3.12 availability (`pyenv` or system Python recommended).
2. Install dev dependencies: `pip install -r requirements-dev.txt`.
3. Run the baseline test suite: `pytest` (ensures local environment matches CI).
4. Start FastAPI instance (`python -m app.main`) and hit `/health` to confirm green status.
5. Build docs locally (`npm --prefix docs install`, `npm --prefix docs run dev`) to validate VitePress workflow.
6. Review `.specify/memory/constitution.md` (v1.0.0) and ensure planned work satisfies all enforceable principles.
7. Inspect `.github/workflows` to understand automation triggered by pushes and tags.
8. Familiarize yourself with Cloudflare Workers deployment configuration (`wrangler.toml`, `src/worker.ts`).
9. Review `docker-compose.yaml` for runtime environment variables and default container behavior.
10. Update AGENT-specific overlays via `scripts/setup-codex-overlay.sh` when customizing local agent contexts.

---

## 2. Project Snapshot

- **Product Domain:** Automation bridge translating AniWorld streaming catalogues into Torznab feeds and qBittorrent-compatible APIs for the *arr ecosystem (Prowlarr, Sonarr, etc.).
- **Primary Language:** Python 3.12 (runtime). Packaging metadata allows >=3.11 for compatibility.
- **Frameworks:** FastAPI, SQLModel, Uvicorn, Loguru, yt-dlp, AniWorld library.
- **Database:** SQLite (file stored under `data/anibridge_jobs.db`).
- **Deployment Targets:** Docker containers (GHCR images), bare-metal Python, PyInstaller single-binary, docs on Cloudflare Workers.
- **Documentation:** VitePress site (`docs`) deployed via Cloudflare Workers using Wrangler.
- **Testing:** Pytest suite covering API endpoints, models, utilities, logging, update notifier, and version invariants.
- **Automation:** Constitution-driven `.specify` templates for planning/spec/task generation. GitHub Actions for formatting, testing, builds, releases, and GHCR publishing.
- **Observability:** Loguru-based structured logging with duplication to daily files via `TerminalLogger` and health endpoints for container orchestration.
- **Legal:** BSD 3-Clause license plus `LEGAL.md` disclaimer cautioning about usage and jurisdictional compliance.

---

## 3. Tech Stack Matrix

| Layer | Technology | Purpose | Key Files |
| --- | --- | --- | --- |
| API Framework | FastAPI | HTTP routing, dependency binding, request handling | `app/main.py`, `app/api/*`
| ASGI Server | Uvicorn (standard extras) | Production server, websockets support, HTTP/2 optional | Docker CMD `python -m app.main`, local CLI `run_server`
| ORM/DB | SQLModel + SQLAlchemy | SQLite persistence for jobs, availability cache, qBittorrent shim state | `app/db/models.py`
| Background Jobs | ThreadPoolExecutor | Download orchestration, TTL cleanup threads, public IP monitoring | `app/core/scheduler.py`, `app/core/lifespan.py`
| Downloader | yt-dlp, AniWorld lib | Episode retrieval, provider fallback, progress events | `app/core/downloader.py`, `app/utils/probe_quality.py`
| Logging | Loguru | Structured console logging, file mirroring, level control | `app/utils/logger.py`, `app/infrastructure/terminal_logger.py`
| Configuration | dotenv + environment variables | Centralized config resolution, proxy handling, path management | `app/config.py`
| Docs Site | VitePress (Vue 3, Vite 7) | Static documentation, interactive components | `docs/*`, `docs/.vitepress/config.mts`
| Docs Hosting | Cloudflare Workers + Wrangler | CDN-backed static hosting for docs/dist | `wrangler.toml`, `src/worker.ts`
| Packaging | setuptools + build + PyInstaller | Python package distribution, single binary builds | `pyproject.toml`, `Makefile`, `.github/workflows/release-on-tag.yml`
| Containerization | Docker, docker-compose | Production image, local orchestration | `Dockerfile`, `docker-compose.yaml`
| Automation | GitHub Actions, `.specify` framework | CI/CD pipelines, agent workflows | `.github/workflows/*`, `.specify/templates/*`

---

## 4. Runtime Architecture Overview

- **Entrypoint Flow:**
  1. `app/main.py` imports `bootstrap_init()` to load environment variables, configure logging, and attach terminal mirroring.
  2. FastAPI app created with custom lifespan (`app/core/lifespan.py`).
  3. Routers for Torznab, qBittorrent, health, and legacy downloader attached.
  4. When served (CLI or Uvicorn), lifespan context initializes DB, scheduler, cleanup threads, proxy environment, and update notifier.

- **Layered Structure:**
  - **API Layer:** `app/api` exposes HTTP endpoints, organizes qBittorrent or Torznab namespaces, handles request validation.
  - **Core Services:** `app/core` manages bootstrap, scheduler, and download orchestration triggered by API or CLI calls.
  - **Domain Models:** `app/domain` defines domain-specific data classes separate from DB/ORM concerns.
  - **Persistence Layer:** `app/db` manages SQLModel models and CRUD helpers.
  - **Infrastructure:** `app/infrastructure` handles system integrations (logging to terminal, proxy environment, system reporting).
  - **Utilities:** `app/utils` centralizes shared helpers: magnet link construction, naming, HTTP clients, update checks, progress bars.

- **Request Lifecycle Example (Torznab Search):**
  1. Client hits `/torznab/api` with query parameters.
  2. Router delegates to search functions inside `app/api/torznab/api.py`.
  3. Title resolution uses `app/utils/title_resolver.py` to map AniWorld slugs.
  4. Download candidates fetched via AniWorld library; results converted to Torznab XML.
  5. Response returned; job scheduling triggered if downloads requested.

- **Download Lifecycle:**
  - Jobs created in DB via `app/db/models.create_job`.
  - `app/core/scheduler` manages thread pool for concurrent downloads respecting `MAX_CONCURRENCY`.
  - `app/core/downloader` orchestrates provider fallback, progress updates, and writes outputs to configured download directory.
  - Completion updates job and client task states, allowing qBittorrent shim to report finished status.

- **Health Monitoring:**
  - `/health` endpoint provides liveness plus readiness details (DB, scheduler, data directory).
  - Background threads monitor public IP (proxy) and cleanup old downloads when TTL configured.

---

## 5. Directory & File Atlas

> **Note:** This directory map reflects the live repository at commit time. Keep synchronized when new files appear.

### Repository Root

- `AGENTS.md` — This manual.
- `CODE_OF_CONDUCT.md` — Contributor behavior policies.
- `CONTRIBUTING.md` — Contribution workflow summary.
- `Dockerfile` — Multi-stage build for production image.
- `LEGAL.md` — Legal disclaimer and usage restrictions.
- `LICENSE` — BSD 3-Clause license text.
- `Makefile` — Release version bump and build targets.
- `README.md` — High-level project overview.
- `SECURITY.md` — Security policy and disclosure process.
- `VERSION` — Current project version, used by release pipelines.
- `anibridge.spec` — Spec file for PyInstaller builds.
- `app/` — Python application package (see Section 6).
- `data/` — Persisted runtime data (logs, SQLite, downloads). **Never commit artifacts here.**
- `docker/` — Container entrypoint scripts.
- `docker-compose.yaml` — Production-oriented compose file (GHCR image reference).
- `docker-compose.dev.yaml` — Developer convenience compose overlay with Sonarr/Prowlarr.
- `docs/` — VitePress documentation source (see Section 20).
- `example-aniworld.html` — Sample HTML snapshot used for parsing tests or debugging.
- `hooks/` — PyInstaller hooks (fake_useragent data bundling).
- `node_modules/` — Installed JS dependencies (only present when docs deps installed at repo root; prefer local `.gitignore`).
- `pyproject.toml` — Python packaging metadata.
- `pytest.ini` — Pytest configuration options.
- `requirements.txt` — Legacy requirements aggregator (kept for compatibility; prefer `requirements.runtime.txt`).
- `requirements-dev.txt` — Development dependencies for CI/local.
- `requirements.runtime.txt` — Runtime dependency lock.
- `scripts/` — Bash and PowerShell helper scripts.
- `src/` — Cloudflare Worker TypeScript source (`worker.ts`).
- `tests/` — Pytest suite (see Appendix C).
- `uv.lock` — uv dependency lock file (Python packaging alternative).
- `wrangler.toml` — Cloudflare Workers deployment configuration.

### Hidden / Meta Directories

- `.github/` — GitHub configuration (actions, issue templates, prompt instructions).
- `.specify/` — Agent automation templates, constitution, scripts.
- `.gitignore` — Git ignore rules (not shown above but present).

### `.github` Subdirectories

- `workflows/` — GitHub Actions definitions (`tests.yml`, `format-and-run.yml`, `publish.yml`, `release-on-tag.yml`).
- `instructions/` — Prompt engineering assets for GitHub Copilot/agents.
- `chatmodes/` — Additional chatbot configuration.
- `img/` — Repository images (logo used by README).
- `prompts/` — Example prompts.
- `ISSUE_TEMPLATE/` — Issue templates for GitHub.

### `.specify` Contents

- `memory/constitution.md` — Constitution v1.0.0 (Sync Impact Report included).
- `templates/plan-template.md` — Implementation plan template aligned with constitution.
- `templates/spec-template.md` — Feature specification template.
- `templates/tasks-template.md` — Task generation template with AniBridge-specific guidance.
- `templates/agent-file-template.md` — Base instructions for agent overlays.
- `scripts/` — Utility scripts for `.specify` workflows.

### `app/` High-Level Layout (Detailed breakdown in Section 6)

- `api/` — Endpoint routers grouped by domain (health, torznab, qbittorrent, legacy downloads).
- `core/` — Bootstrap, downloader, scheduler, lifespan management.
- `db/` — SQLModel definitions and engine helpers.
- `domain/` — Domain-level models (decoupled from persistence).
- `infrastructure/` — Terminal logging, network helpers, system diagnostics.
- `utils/` — Shared utilities (naming, magnets, HTTP client, update notifier, logging configuration, etc.).
- `cli.py` — CLI entrypoint used by `app.main` or standalone.
- `_version.py` — Version helper aligning with package metadata.

### `docs/` Structure

- `.vitepress/` — VitePress config, custom theme, static assets.
- `src/` — Markdown and Vue content for the documentation site.
- `node_modules/`, `package.json`, lockfiles — Node dependencies for docs.

### `scripts/` Directory

- `local_build_release.sh` — Shell automation for local builds and GitHub release prep.
- `local_build_release.ps1` — PowerShell equivalent for Windows contributors.
- `setup-codex-overlay.sh` — Bootstraps agent overlay instructions.
- `startup-script.sh` — Example startup script for container or systemd usage.

### `tests/` Directory (Detailed mapping in Appendix C)

- `conftest.py` — Shared fixtures.
- Individual `test_*.py` modules covering config, health endpoint, magnet utility, models, qBittorrent, Torznab, title resolution, update notifier, versioning, and logging.

---

## 6. Python Application Modules

### `app/main.py`

- Initializes logging/bootstrap via `app.core.bootstrap.init`.
- Creates FastAPI app titled `AniBridge-Minimal` with lifespan context.
- Registers routers from `app/api` packages.
- Provides CLI entry via `app.cli.run_server` when executed directly.

### `app/core/bootstrap.py`

- Loads `.env`, configures Loguru, ensures log directories exist, and attaches terminal mirroring to daily files in `data/terminal-YYYY-MM-DD.log`.
- Designed for idempotent invocation (safe on repeated imports).

### `app/core/lifespan.py`

- Implements async lifespan context for FastAPI.
- Applies proxy configuration (via `app.infrastructure.network`).
- Logs system info (`app.infrastructure.system_info`).
- Triggers update notifier (`app.utils.update_notifier.notify_on_startup`).
- Creates DB and thread pool (`app.db`, `app.core.scheduler`).
- Starts TTL cleanup and public IP monitoring threads.
- Ensures graceful shutdown of scheduler, DB engine, and background threads.

### `app/core/scheduler.py`

- Manages a global `ThreadPoolExecutor` respecting `MAX_CONCURRENCY`.
- Provides job submission, cancellation, and status reporting utilities.
- Integrates with DB to track progress updates in `Job` entries.

### `app/core/downloader.py`

- Orchestrates download tasks using AniWorld API and `yt-dlp`.
- Handles provider prioritization based on `PROVIDER_ORDER` env var.
- Emits progress callbacks to update jobs and client task states.
- Applies proxy configurations when required.

### `app/api/health.py`

- Exposes `/health` endpoint returning JSON with service status (e.g., DB connectivity, scheduler state, download directory checks).

### `app/api/legacy_downloader.py`

- Provides legacy direct download endpoint (`/downloader/download`) for backward compatibility with prior automation flows.

### `app/api/torznab/`

- `api.py` — Implements Torznab feed, search, `tvsearch`, and `caps` endpoints.
- `utils.py` — Helper functions for query parsing, slug resolution, and XML response formatting.

### `app/api/qbittorrent/`

- `app_meta.py` — Metadata endpoints replicating qBittorrent behavior.
- `auth.py` — Login/logout with cookie-based session handling.
- `categories.py` — Category listing consistent with Sonarr expectations.
- `common.py` — Shared responses (error handling, validation).
- `sync.py` — `/api/v2/sync/maindata` main data endpoint for Sonarr integration.
- `torrents.py` — Torrent/magnet management (add, delete, info).
- `transfer.py` — Transfer status endpoints.

### `app/db/models.py`

- Defines SQLModel `Job`, `EpisodeAvailability`, `ClientTask` tables.
- Provides helper functions for CRUD operations and engine lifecycle.
- Includes TTL freshness logic for availability cache.

### `app/domain/models.py`

- Declares domain-level dataclasses/typed models used by higher layers without binding to SQLModel.

### `app/utils/*`

- `logger.py` — Configures Loguru sinks, levels, formatting.
- `terminal.py` — Terminal output helpers.
- `http_client.py` — Shared HTTP session with proxy awareness and retries.
- `magnet.py` — Magnet URI builder, info hash handling.
- `naming.py` — Title normalization and slug management.
- `probe_quality.py` — Video quality probing before downloads.
- `title_resolver.py` — Maps AniWorld titles to canonical forms.
- `update_notifier.py` — Checks GitHub for new releases and logs updates.

### `app/infrastructure/*`

- `terminal_logger.py` — Duplicates stdout/stderr to rotating files.
- `network.py` — Applies proxy env vars to process-level environment, public IP check scheduling.
- `system_info.py` — Logs environment metadata for debugging.

### `app/cli.py`

- Provides CLI entry using typer/uvicorn integration; ensures consistent server startup.

### `app/config.py`

- Central configuration hub for environment variables.
- Handles proxy URL assembly, data directory resolution, default values, type conversions.
- Exposes constants used across the application (e.g., `DOWNLOAD_DIR`, `INDEXER_NAME`, `TORZNAB_*`).

### `app/_version.py`

- Keeps version synchronization with `VERSION` file and packaging metadata.

---

## 7. Domain & Data Models

### Job Lifecycle Entities

- **Job (SQLModel)**
  - Columns: `id`, `status`, `progress`, `downloaded_bytes`, `total_bytes`, `speed`, `eta`, `message`, `result_path`, timestamps.
  - Status transitions: `queued` → `downloading` → (`completed` | `failed` | `cancelled`).
  - Persisted for auditability and API exposure.

- **ClientTask (SQLModel)**
  - Represents qBittorrent-compatible torrent entry.
  - Stores mapping between magnet hash and job ID, plus metadata (category, save path, completion timestamp).
  - States mirror qBittorrent enumerations (e.g., `queued`, `downloading`, `paused`, `completed`, `error`).

### Episode Availability Cache

- **EpisodeAvailability (SQLModel)**
  - Composite primary key on slug, season, episode, language.
  - Tracks provider availability, quality (height, codec), last checked timestamp.
  - `is_fresh` method validates TTL against `AVAILABILITY_TTL_HOURS`.

### Domain Models (Python)

- `app/domain/models.py` replicates aspects of DB models but decoupled for domain logic and API serialization.
- Used to ensure consistent typing and separation between API payloads and persistence forms.

### SQL Engine Helpers

- `create_db_and_tables()` ensures tables exist on startup.
- `cleanup_dangling_jobs()` resets jobs stuck in non-terminal state to `failed` during startup, protecting from stale data on crash.
- `dispose_engine()` closes engine to avoid resource warnings on shutdown/testing.

### Data Directory

- SQLite database stored at `${DATA_DIR}/anibridge_jobs.db` (defaults to `data/anibridge_jobs.db`).
- Downloaded media stored under `DOWNLOAD_DIR` (default `data/downloads/anime`).
- Log files under `data/logs` (ensured by `ensure_log_path`).

---

## 8. API Surface & Contracts

### Base URLs

- FastAPI defaults to `http://localhost:8000` when run locally.
- Reverse proxies or Docker mapping configured via `docker-compose.yaml` (port 8000).

### Health Endpoint (`/health`)

- Method: `GET`
- Response: JSON with keys `status`, `database`, `scheduler`, `download_dir`, `version`, `runtime`.
- Used for readiness checks in Docker healthcheck and CI smoke tests.

### Torznab Namespace (`/torznab/api`)

- Routes support `t=caps`, `t=search`, `t=tvsearch`, `t=episode` patterns.
- Returns XML responses conforming to Torznab specification with fake seeders/leechers values from env.
- Accepts `apikey` when configured (`INDEXER_API_KEY`).

### qBittorrent Shim (`/api/v2/*`)

- **Auth:** `/auth/login`, `/auth/logout` (form-based, sets `SID` cookie `anibridge`).
- **Categories:** `/torrents/categories` returns configured categories (default `AniBridge`).
- **Torrents:** `/torrents/add`, `/torrents/delete`, `/torrents/info` mimic qBittorrent responses.
- **Sync:** `/sync/maindata` returns job states for Sonarr integration.
- **Transfer:** `/transfer/info`, `/transfer/speedLimitsMode`, etc., implemented with safe defaults.

### Legacy Downloader (`/downloader/download`)

- Accepts slug/episode requests and triggers download via scheduler; primarily for backward compatibility.

### Response Models

- Many endpoints return `PlainTextResponse` (`Ok.`) to mirror qBittorrent semantics.
- JSON responses use Pydantic models defined within modules or inline dictionaries; ensure tests cover schema assumptions.

### Error Handling

- Exceptions logged via Loguru; API returns structured errors aligning with qBittorrent/Torznab expectations.
- `common.py` defines helpers for consistent error payloads.

---

## 9. Scheduler & Background Services

- **Thread Pool:** Configured by `MAX_CONCURRENCY` (default 3). Jobs submitted via `app/core/scheduler.submit_download`.
- **Cleanup Thread:** Deletes completed downloads older than `DOWNLOADS_TTL_HOURS` (disabled when ≤0).
- **Public IP Monitor:** When proxy enabled (or `PUBLIC_IP_CHECK_ENABLED`), background thread logs IP changes at `PROXY_IP_CHECK_INTERVAL_MIN` intervals.
- **Graceful Shutdown:** `lifespan` context ensures executor shutdown, event flags for threads, DB disposal.
- **Progress Updates:** Scheduler updates DB and client tasks, surfaces progress via qBittorrent sync endpoint and `/jobs/{job_id}` (legacy).

---

## 10. Configuration & Environment Variables

AniBridge centralizes configuration in `app/config.py`. Values are derived from environment variables, `.env`, and sensible defaults. See Appendix A for a comprehensive list.

Key groups include:

- **Paths:** `DATA_DIR`, `DOWNLOAD_DIR`, `QBIT_PUBLIC_SAVE_PATH`.
- **Torznab:** `INDEXER_NAME`, `INDEXER_API_KEY`, `TORZNAB_*` values controlling fake seeders/leechers/test entries.
- **Downloader:** `PROVIDER_ORDER`, `MAX_CONCURRENCY`, `DOWNLOADS_TTL_HOURS`, `CLEANUP_SCAN_INTERVAL_MIN`.
- **Proxy:** `PROXY_ENABLED`, `PROXY_URL`, `PROXY_HOST/PORT/SCHEME`, `PROXY_USERNAME/PASSWORD`, protocol-specific overrides, certificate verification toggles, IP monitoring.
- **Update Notifier:** `ANIBRIDGE_UPDATE_CHECK`, GitHub owner/repo/token, GHCR image reference.
- **Logging:** `LOG_LEVEL`, force progress bars, terminal duplication toggles (handled by `TerminalLogger`).
- **Legal/Compliance:** Proxy defaults ensure remote DNS for SOCKS when `PROXY_FORCE_REMOTE_DNS` true (default).

When running via Docker Compose, environment variables are pre-wired with defaults; override via `.env` or compose overrides.

---

## 11. Download Pipeline & Providers

- **Provider Ordering:** Controlled by `PROVIDER_ORDER` (CSV). Defaults: `VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza`.
- **Quality Probing:** `app/utils/probe_quality.py` uses `yt-dlp` to probe stream metadata before committing to download.
- **Download Execution:** `app/core/downloader.py` orchestrates actual retrieval (using AniWorld + direct provider links). Respects proxies and concurrency limits.
- **TTL Cleanup:** Media files older than TTL removed automatically to maintain disk hygiene.
- **Result Storage:** Completed downloads stored under `DOWNLOAD_DIR`, with optional public save path for qBittorrent clients.

---

## 12. qBittorrent Shim Semantics

- Mimics `/api/v2` endpoints expected by Sonarr and similar tools.
- Accepts login without credentials (auth stub) but sets cookie to satisfy clients.
- Tracks torrents via `ClientTask` table mapping to internal job IDs.
- Reports progress, states, speeds via `/sync/maindata` and `/torrents/info` endpoints.
- Deletion endpoints update DB state and optionally remove files when `DELETE_FILES_ON_TORRENT_DELETE` true.
- Category endpoints allow Sonarr to assign downloads to categories (`AniBridge` default).
- Transfer endpoints supply static or computed data (e.g., speed limit modes always returning safe default).

---

## 13. Torznab Feed Semantics

- Implements Torznab spec for integration with Prowlarr/Sonarr.
- Caps endpoint returns categories, limits, search types, and supported operations.
- Search endpoints map queries to AniWorld titles using `title_resolver` (handles slug differences and caching via `EpisodeAvailability`).
- Fake seeders/leechers defaults set high to encourage priority; customizable via environment.
- Test result toggled by `TORZNAB_RETURN_TEST_RESULT` (enables connectivity checks).
- Responses formatted as XML with proper namespaces.

---

## 14. CLI & Utilities

- `app/cli.py` provides `run_server` function, starting Uvicorn with proper settings.
- CLI ensures FastAPI app served with reload toggles (`ANIBRIDGE_RELOAD`) when needed.
- Additional CLI tasks (if any) should integrate with Typer/Click to maintain consistency.
- Utilities under `app/utils` available for reuse in CLI or other scripts.

---

## 15. Logging & Observability

- **Loguru Configuration:**
  - Configured by `app/utils/logger.py` considering `LOG_LEVEL`.
  - Formats include timestamp, level, module, function, line.

- **Terminal Mirroring:**
  - `app/infrastructure/terminal_logger.TerminalLogger` duplicates stdout/stderr to `data/terminal-YYYY-MM-DD.log` for audit.
  - Useful for debugging automation runs and container logs.

- **Structured Fields:**
  - Download/scheduler logs include job IDs, provider names, progress metrics.
  - Proxy configuration and IP checks logged at startup.

- **Health Endpoint:**
  - Exposes status metrics for monitoring.

- **Update Notifier:**
  - Logs when new GitHub releases available, including GHCR tags.

- **System Reporting:**
  - Startup logs include OS details, Python version, CPU info (via `app.infrastructure.system_info.log_full_system_report`).

---

## 16. Testing Strategy

- **Test Runner:** Pytest configured via `pytest.ini`.
- **Fixtures:** `tests/conftest.py` sets up FastAPI test client, database fixtures, and environment overrides.
- **Coverage Goals:** Target near-total coverage for API endpoints, config parsing, download helpers, naming utilities, and update notifier.
- **Key Suites:**
  - `test_health.py` — Validates `/health` endpoint data.
  - `test_qbittorrent_*.py` — Ensures shim endpoints conform to Sonarr expectations.
  - `test_torznab*.py` — Exercises search, caps, errors, and utils.
  - `test_magnet.py`, `test_naming.py`, `test_title_resolver*.py` — Validate helper correctness.
  - `test_models.py` — Verifies SQLModel behaviors, TTL logic.
  - `test_update_notifier.py` — Confirms release checks operate as expected.
  - `test_version.py` — Aligns `_version.py` with `VERSION` file.
- **Execution:** `pytest` (with optional `--cov=app` for coverage).
- **CI:** `tests.yml` runs on pushes/PRs touching `app/` or `tests/` directories.

---

## 17. Local Development Setup

1. **Python Environment:**
   - Optional: `pyenv install 3.12.x`, `pyenv virtualenv 3.12.x anibridge`.
   - Alternatively: `python3 -m venv .venv`.
   - Activate environment, upgrade pip.
2. **Dependencies:**
   - Runtime: `pip install -r requirements.runtime.txt`.
   - Development: `pip install -r requirements-dev.txt` (includes pytest, black, pyinstaller, httpx).
3. **Environment Variables:**
   - Copy `.env.example` if available (if not, create `.env` referencing Appendix A defaults).
4. **Database:**
   - No manual setup required; SQLite file auto-created under `data/`.
5. **Running the App:**
   - `python -m app.main` or `uvicorn app.main:app --reload` (set `ANIBRIDGE_RELOAD=true`).
6. **Docs Development:**
   - Install Node 20+ (recommend nvm).
   - `pnpm --prefix docs install`.
   - `pnpm --prefix docs run dev` to launch VitePress at `http://localhost:5173`.
7. **Cloudflare Worker Testing:**
   - Install Wrangler CLI (`npm install -g wrangler`).
   - `wrangler dev` uses `wrangler.toml` to serve built docs (requires prior `pnpm --prefix docs run build`).
8. **Linting:**
   - `black app` (aligns with CI `format-and-run.yml`).
9. **Pre-commit (Optional):**
   - While no `.pre-commit-config.yaml` is provided, consider configuring locally for black/pytest.

---

## 18. Docker & Containerization

- **Dockerfile Highlights:**
  - Base image: `python:3.12-slim`.
  - Multi-stage: `base`, `deps` (install runtime requirements), `final` (copy app, runtime deps).
  - Installs `gosu`, `build-essential` for runtime compatibility.
  - Non-root user `appuser` (UID/GID adjustable at runtime).
  - Healthcheck hitting `/health` every 30s.
  - Entry point: `/entrypoint.sh` sets UID/GID, ensures directories, and execs command as `appuser`.

- **Entrypoint Script (`docker/entrypoint.sh`):**
  - Configurable via `PUID`, `PGID`, `CHOWN_RECURSIVE`.
  - Ensures directories exist and have correct ownership.
  - Handles optional download/public paths via helper function.

- **Images:**
  - Published to `ghcr.io/zzackllack/anibridge` via `publish.yml` workflow.
  - Tags derived from branch, commit SHA, and `VERSION` file.

- **Running Locally:**
  - `docker compose up -d` (uses GHCR image by default).
  - Override environment via `.env` or environment variables in compose file.

---

## 19. Compose Topologies

### `docker-compose.yaml`

- Service: `anibridge` (image `ghcr.io/zzackllack/anibridge:latest`).
- Ports: `8000:8000`.
- Environment variables: exhaustive list covering user/group IDs, logging, download directories, AniWorld settings, Torznab config, cleanup, progress display, update notifier, networking/proxy options.
- Volume: `./data:/data` (persist DB, downloads, logs).
- Healthcheck uses curl to `http://localhost:8000/health`.

### `docker-compose.dev.yaml`

- Provides optional Sonarr and Prowlarr containers preconfigured to integrate with AniBridge.
- Example (commented) service definition for building AniBridge locally.
- Shared network `anibridge-dev-net` for inter-service communication.
- Developer instructions: uncomment `anibridge` service for end-to-end testing.

---

## 20. Documentation System (VitePress)

- **Location:** `docs/` directory.
- **Tooling:** VitePress 2.0.0-alpha.12, Vue 3.5, Vite 7.
- **Scripts:**
  - `pnpm --prefix docs run dev` — local server with live reload.
  - `pnpm --prefix docs run build` — builds static output to `docs/.vitepress/dist`.
  - `pnpm --prefix docs run preview` — preview build output.
- **Config:** `docs/.vitepress/config.mts` defines site metadata, navigation, sidebar, algolia/local search, base path.
- **Custom Theme:** `docs/.vitepress/theme/index.ts` plus `custom.css`, `VideoPlayer.vue`.
- **Content Structure:**
  - `docs/src/guide/*` — User guides (overview, quickstart, running, configuration, networking, troubleshooting, FAQ).
  - `docs/src/developer/*` — Developer guides (running locally, testing, logging).
  - `docs/src/api/*.md` — API documentation (endpoints, environment metadata, qBittorrent shim, jobs, Torznab, data model).
  - `docs/src/integrations/*` — Integration guides (Docker, Sonarr, Prowlarr).
  - `docs/src/legal.md` — Legal considerations mirroring `LEGAL.md`.
  - `docs/src/api-examples.md` — Example API calls.
- **Assets:** `docs/.vitepress/dist` (generated) served via Cloudflare Worker (do not commit).
- **Node Tooling:** `pnpm-workspace.yaml` present; supports PNPM usage.

---

## 21. Cloudflare Workers Deployment

- **Configuration File:** `wrangler.toml`.
  - Worker name: `anibridge-docs`.
  - Main entry: `src/worker.ts` (delegates requests to static assets).
  - Compatibility date: `2025-08-15`.
  - Routes: `anibridge-docs.zacklack.de` under zone `zacklack.de`.
  - Build command: `pnpm --prefix docs ci` + `pnpm --prefix docs run build`.
  - Watch directories for live deploy preview: `docs/src`, `docs/.vitepress/config.mts`, `docs/.vitepress/theme`.
  - Assets directory: `docs/.vitepress/dist` with binding `ASSETS`.
- **Worker Implementation:** `src/worker.ts` proxies all requests to static asset binding.
- **Deployment Steps:**
  1. Ensure Node dependencies installed.
  2. `wrangler publish` (requires Cloudflare account and authentication).
  3. Custom domain configured via `routes` block.

- **Local Testing:**
  - `wrangler dev` builds docs and serves using local worker emulator.

---

## 22. Scripts & Tooling

- `scripts/local_build_release.sh`
  - Builds Python package, creates release artifacts, optionally pushes tags.
  - Set executable before use (`chmod +x`).

- `scripts/local_build_release.ps1`
  - Windows equivalent for PowerShell environments.

- `scripts/setup-codex-overlay.sh`
  - Initializes agent-specific overlay instructions (Codex) for `.specify` or other automation flows.
  - Should be re-run when new tools or languages introduced.

- `scripts/startup-script.sh`
  - Example script for launching AniBridge with environment variable exports; helpful for systemd or manual deployments.

---

## 23. Build, Release & Distribution

- **Version Management:**
  - `VERSION` file holds semantic version used by packaging and docker tags.
  - `Makefile` includes `patch`, `minor`, `major` targets using `bump2version` (installs automatically before running).
  - `make tag` creates annotated git tag from `VERSION`.

- **Packaging:**
  - `python -m build` generates sdist and wheel (also run in `release-on-tag.yml`).
  - PyInstaller builds (Linux/macOS/Windows) generated by GitHub Actions on tag push.
  - `anibridge.spec` informs PyInstaller bundling (hooks included for `fake_useragent`).

- **Distribution Channels:**
  - GitHub Releases: Tarballs/zip from PyInstaller and Python dists.
  - GHCR: Docker images tagged by branch, commit, and version.

- **Artifact Checksums:**
  - `release-on-tag.yml` creates `SHA256SUMS` for built distributions.

---

## 24. CI/CD Workflows

### `.github/workflows/tests.yml`

- Trigger: push/PR affecting `app/**` or `tests/**`.
- Steps: checkout → setup Python 3.11 → install `requirements-dev.txt` → run pytest → upload `.coverage` artifact.

### `.github/workflows/format-and-run.yml`

- Trigger: push/PR affecting `app/**` or `requirements.txt`.
- Steps: checkout → setup Python 3.11 → install dev deps + black → format `app/` → auto-commit/push formatting changes.
- Permissions: `contents` and `pull-requests` write to allow pushing format commits.

### `.github/workflows/publish.yml`

- Trigger: push to `main`, tags (`v*`), or manual dispatch; path filter ensures build on relevant changes.
- Builds multi-arch (currently linux/amd64) image via Buildx.
- Reads `VERSION` file, logs in to GHCR, pushes tags (branch, tag, SHA, `latest`, explicit version).
- Caches builds for faster subsequent runs.

### `.github/workflows/release-on-tag.yml`

- Trigger: `v*` tags.
- Jobs:
  - Build Python distributions (`python -m build`) and upload to release.
  - PyInstaller builds across OS matrix, packages artifacts, uploads to release via `softprops/action-gh-release`.
- Includes custom PyInstaller hook `hooks/hook-fake_useragent.py`.

---

## 25. Automation Framework (.specify)

- **Constitution (`.specify/memory/constitution.md`):**
  - Version 2.0.0, ratified 2025-09-21.
  - Principles: Code Quality Stewardship, Test-Centric Reliability, User Experience Consistency, Performance & Resilience Discipline.
  - Additional sections: Operational Constraints, Workflow & Review Gates, Governance.
  - Sync Impact Report appended as HTML comment summarizing version changes.

- **Templates:**
  - `plan-template.md` — Guides `/plan` command with constitution check gate, repository structure reference, and progress tracking.
  - `spec-template.md` — Feature specification guidelines focusing on user value, contract impacts, user experience alignment, performance guardrails, and compliance.
  - `tasks-template.md` — Defines TDD-first task generation with AniBridge-specific path conventions, performance/resilience hardening, and compliance tasks.
  - `agent-file-template.md` — Baseline instructions for agent overlays (Codex, Copilot, etc.).

- **Scripts:** `.specify/scripts` contains automation helpers (inspect before use).

- **Usage Notes:**
  - Always update templates when constitution changes.
  - Ensure constitution check sections in plan/spec/tasks align with latest principles.

---

## 26. Constitution Alignment Checklist

For every initiative, confirm adherence:

1. **Code Quality Stewardship** — Maintain modular boundaries, type hints, docstrings, and configuration hygiene.
2. **Test-Centric Reliability** — Author failing tests first, run `pytest` and `black`, keep fixtures deterministic.
3. **User Experience Consistency** — Document API impacts, update docs/releases, keep error messaging actionable.
4. **Performance & Resilience Discipline** — Preserve concurrency limits, structured logging, and `/health` responsiveness.
5. **Operational Constraints** — Maintain Python 3.12 baseline, coordinate dependency updates, document migrations and legal posture.
6. **Workflow & Review Gates** — Produce `/plan` and `/tasks`, update docs/changelogs, ensure reviewers can verify compliance.

---

## 27. Onboarding Playbooks

### Human/Agent Quick Start

1. Read `README.md`, `LEGAL.md`, `CODE_OF_CONDUCT.md`.
2. Review this AGENTS.md entirely (yes, all ≥1000 lines) to internalize processes.
3. Set up local environment per Section 17.
4. Run docs site locally to get familiar with published content.
5. Explore tests to understand expected behaviors.
6. Review `.github/workflows` to know automation triggers.
7. Inspect `.specify` templates to align future contributions.
8. Join development by addressing open issues or drafting specs using `.specify` system.

### AI Agent Execution Flow

1. Parse instruction set, confirm constitution references.
2. Load relevant templates before generating plan/spec/tasks.
3. Validate environment (Python packages, Node, docker) before running commands.
4. Update docs (`docs/` and README) when code behavior changes.
5. Provide final summaries referencing specific files/lines altered.

---

## 28. Multi-Agent Collaboration Patterns

- **Spec/Plan/Tasks Pipeline:**
  - Agent A: Generate feature spec using `.specify/templates/spec-template.md`.
  - Agent B: Produce implementation plan referencing constitution gates.
  - Agent C: Generate task list ensuring TDD order.
  - Agent D: Execute tasks, commit changes.

- **Doc Review Loop:**
  - Agent updates docs -> second agent validates docs vs code.

- **Testing Coordination:**
  - One agent writes failing tests, another implements fix, third validates coverage.

- **Deployment Prep:**
  - Agent ensures docs built, Cloudflare worker configuration up-to-date, updates `wrangler.toml` when base path/domain changes.

- **Release Automation:**
  - When bumping version, ensure `VERSION`, `pyproject.toml`, changelog entries, and release notes aligned.
  - For prompts requesting commit summaries (e.g., "Summarize the last 38 commits back to the last version update commit 'Bump version 1.14.4 -> 1.15.0'"), generate `changelog.md` using the structure: Overview, Highlights, Breaking Changes, Detailed Changes grouped by theme, and cite each referenced commit with GitHub hash links.

---

## 29. Troubleshooting Playbooks

### Download Failures

- Check logs in `data/terminal-YYYY-MM-DD.log`.
- Verify proxy settings effective (`PROXY_ENABLED`, `PROXY_URL`).
- Confirm AniWorld reachable from host (outbound connectivity).
- Ensure `DOWNLOAD_DIR` writable.
- Validate provider order includes functioning hosts.

### Torznab Empty Results

- Confirm `ANIWORLD_ALPHABET_URL` reachable and exposures preloaded.
- Check `EpisodeAvailability` TTL — maybe stale data; consider clearing DB entry.
- Verify slug mapping via `app/utils/title_resolver.py` logs.

### qBittorrent Client Not Syncing

- Confirm `/api/v2/auth/login` returns `SID` cookie.
- Use Sonarr logs to inspect error; ensure `INDEXER_API_KEY` configured if required.
- Check `ClientTask` entries in SQLite for stuck states and cleanup if necessary.

### Health Endpoint Failing

- Inspect `/health` JSON to identify failing component.
- DB: ensure `data/` volume persisted and writable.
- Scheduler: verify `MAX_CONCURRENCY` not set to 0.

### Proxy Issues

- Log output from `apply_global_proxy_env` for active proxies.
- Ensure `PROXY_FORCE_REMOTE_DNS` set appropriately; some providers require remote DNS.
- Validate credentials in `PROXY_USERNAME/PASSWORD`.

### Docs Build Errors

- Delete `docs/node_modules`, reinstall dependencies.
- Ensure Node 20+ installed.
- Clear VitePress cache by removing `docs/.vitepress/cache`.

### Cloudflare Deployment Fails

- Check Wrangler authentication (`wrangler whoami`).
- Confirm build command in `wrangler.toml` finishes without errors.
- Validate `docs/.vitepress/dist` generated before publish.

### PyInstaller Build Issues

- Ensure `hooks/hook-fake_useragent.py` included to bundle fake-useragent data.
- Run `pyinstaller --additional-hooks-dir hooks --onefile app/main.py` locally for debugging.

### Tests Failing Locally but Passing CI

- Remove `.pyc` and cached data (`find . -name '__pycache__' -delete`).
- Ensure `PYTHONPATH` not polluted by other projects.
- Recreate virtual environment if dependency mismatch.

---

## 30. Security & Compliance Notes

- **Credential Handling:**
  - No secrets committed; rely on environment variables and `.env` files excluded from git.
  - Update notifier token (`ANIBRIDGE_GITHUB_TOKEN`) should use GitHub PAT with read access.

- **Legal Disclaimer:**
  - Refer to `LEGAL.md` and docs/legal for usage guidance.
  - Highlight that proxy features are experimental and not a substitute for VPN compliance.

- **Data Protection:**
  - Downloads stored locally; cleanup TTL recommended to avoid retention issues.
  - Logs may contain URLs; redact when sharing externally.

- **Security Policy:**
  - `SECURITY.md` outlines vulnerability reporting path via GitHub security advisories or email.

---

## 31. Legal Considerations

- `LEGAL.md` warns about jurisdictional risks; users responsible for compliance with local laws and streaming providers' terms.
- Documentation replicates caution (docs/legal.md) and emphasises VPN/proxy recommendations.
- Contributors should avoid merging features that bypass hard legal constraints without approval.

---

## 32. Glossary

- **AniWorld:** Source site for anime content.
- **Torznab:** API specification for search/indexers used by *arr ecosystem.
- **qBittorrent Shim:** Fake qBittorrent API enabling automation tools to interact without real torrent client.
- **ThreadPoolExecutor:** Python concurrency primitive for download jobs.
- **TTL (Time-to-Live):** Duration before downloaded files cleaned up or cache entries refreshed.
- **WRANGLER:** Cloudflare CLI for managing workers.
- **VitePress:** Static site generator used for docs.
- **GHCR:** GitHub Container Registry.
- **yt-dlp:** Fork of youtube-dl optimized for streaming site downloads.
- **SQLModel:** Pydantic + SQLAlchemy hybrid ORM for Python.

---

## 33. External Resources

- **Project:**
  - GitHub Repository: https://github.com/Zzackllack/AniBridge
  - Documentation: https://anibridge-docs.zacklack.de (served via Cloudflare Workers)

- **Dependencies:**
  - FastAPI docs: https://fastapi.tiangolo.com/
  - SQLModel docs: https://sqlmodel.tiangolo.com/
  - yt-dlp: https://github.com/yt-dlp/yt-dlp
  - AniWorld Downloader: https://github.com/phoenixthrush/AniWorld-Downloader

- **Tools:**
  - Wrangler: https://developers.cloudflare.com/workers/wrangler/
  - VitePress: https://vitepress.dev/
  - GitHub Actions: https://docs.github.com/en/actions

---

## Appendix A: Environment Variable Catalog

> Source references: `app/config.py`, `docker-compose.yaml`, docs configuration pages. Defaults reflect runtime behavior when variable unset.

1. `LOG_LEVEL` — Controls Loguru logging level (default `INFO`).
2. `DATA_DIR` — Root data directory (default `./data`).
3. `DOWNLOAD_DIR` — Location for downloaded files (default `${DATA_DIR}/downloads/anime`).
4. `QBIT_PUBLIC_SAVE_PATH` — Alternate public path seen by qBittorrent clients (default empty).
5. `ANIBRIDGE_RELOAD` — Enables reload server mode for development (`false` by default).
6. `PUID` — UID for container user (default `1000`).
7. `PGID` — GID for container group (default `1000`).
8. `CHOWN_RECURSIVE` — Whether entrypoint recursively chowns mount directories (`true`).
9. `ANIWORLD_ALPHABET_HTML` — Allows overriding local HTML (default empty, triggers remote fetch).
10. `ANIWORLD_ALPHABET_URL` — AniWorld alphabet page (default `https://aniworld.to/animes-alphabet`).
11. `ANIWORLD_TITLES_REFRESH_HOURS` — Refresh interval for AniWorld titles (default `24`).
12. `SOURCE_TAG` — Release source tag appended to metadata (default `WEB`).
13. `RELEASE_GROUP` — Release group label (default `aniworld`).
14. `PROVIDER_ORDER` — Comma-separated providers priority list.
15. `MAX_CONCURRENCY` — Thread pool size for downloads (default `3`).
16. `INDEXER_NAME` — Torznab indexer display name (default `AniBridge Torznab`).
17. `INDEXER_API_KEY` — Optional API key required by Torznab endpoints.
18. `TORZNAB_CAT_ANIME` — Category mapping for anime (default `5070`).
19. `AVAILABILITY_TTL_HOURS` — Cache TTL for episode availability (default `24`).
20. `TORZNAB_FAKE_SEEDERS` — Seeders displayed in Torznab results (default `999`).
21. `TORZNAB_FAKE_LEECHERS` — Leechers displayed (default `787`).
22. `TORZNAB_RETURN_TEST_RESULT` — Whether to return test item in results (default `true`).
23. `TORZNAB_TEST_TITLE` — Test item title (`AniBridge Connectivity Test`).
24. `TORZNAB_TEST_SLUG` — Test slug (`connectivity-test`).
25. `TORZNAB_TEST_SEASON` — Test season number (`1`).
26. `TORZNAB_TEST_EPISODE` — Test episode number (`1`).
27. `TORZNAB_TEST_LANGUAGE` — Test language label (`German Dub`).
28. `DELETE_FILES_ON_TORRENT_DELETE` — Remove files when torrent deleted (default `true`).
29. `DOWNLOADS_TTL_HOURS` — TTL cleanup threshold (default `0`, disabled).
30. `CLEANUP_SCAN_INTERVAL_MIN` — Cleanup loop interval minutes (default `30`).
31. `STRM_FILES_MODE` — Controls whether Torznab emits STRM variants and whether the qBittorrent shim writes `.strm` files instead of downloading media (`no`, `both`, `only`, default `no`).
32. `PROGRESS_FORCE_BAR` — Force progress bar rendering (default `false`).
33. `PROGRESS_STEP_PERCENT` — Progress logging step percentage (default `5`).
34. `ANIBRIDGE_UPDATE_CHECK` — Enable GitHub release polling (default `true`).
35. `ANIBRIDGE_GITHUB_TOKEN` — Token used for rate-limited GitHub API calls.
36. `ANIBRIDGE_GITHUB_OWNER` — GitHub owner (default `zzackllack`).
37. `ANIBRIDGE_GITHUB_REPO` — Repo name (default `AniBridge`).
38. `ANIBRIDGE_GHCR_IMAGE` — GHCR image slug (default `zzackllack/anibridge`).
39. `PROXY_ENABLED` — Master toggle for proxy usage (`false`).
40. `PROXY_URL` — Full proxy URL with optional credentials.
41. `PROXY_HOST` — Host when building proxy URL from parts.
42. `PROXY_PORT` — Port for constructed proxy.
43. `PROXY_SCHEME` — Proxy scheme (default `socks5`).
44. `PROXY_USERNAME` — Proxy auth username.
45. `PROXY_PASSWORD` — Proxy auth password.
46. `HTTP_PROXY_URL` — Protocol-specific override.
47. `HTTPS_PROXY_URL` — Protocol-specific override.
48. `ALL_PROXY_URL` — Generic override for all protocols.
49. `NO_PROXY` — Domains bypassing proxy.
50. `PROXY_FORCE_REMOTE_DNS` — Force remote DNS for SOCKS proxies (default `false` in config? actual default `True` due to config logic; note compose default `false` to respect operator choice).
51. `PROXY_DISABLE_CERT_VERIFY` — Disable TLS verification for proxies (default `false`).
52. `PROXY_APPLY_ENV` — Apply proxies to process env (default `true`).
53. `PROXY_IP_CHECK_INTERVAL_MIN` — Interval minutes for IP checks (default `30`).
54. `PROXY_SCOPE` — Scope of proxy usage (`all`, `requests`, `ytdlp`).
55. `PUBLIC_IP_CHECK_ENABLED` — Run IP monitor even when proxy disabled (default `false`).
56. `PUBLIC_IP_CHECK_INTERVAL_MIN` — Override for IP check interval (defaults to proxy interval).
57. `HTTP_PROXY_URL`, `HTTPS_PROXY_URL`, `ALL_PROXY_URL` interplay documented in config docstrings.
58. `PYTHONUNBUFFERED` — Set to `1` in Docker to keep logs flush.
59. `ANIBRIDGE_DOCS_BASE_URL` — (If introduced in docs; check config before use.)
60. `QBIT_PUBLIC_SAVE_PATH` — Mapped path for completed downloads.
61. `SONARR_*`, `PROWLARR_*` — Not direct env vars but relevant when integrating (documented in docs/integrations).

*(Extend this list when new environment variables introduced. Ensure documentation lines remain updated.)*

---

## Appendix B: File Reference Index

> Comprehensive yet concise index. Include new files as they appear.

- `app/api/torznab/api.py` — Torznab request handlers (search, caps, tvsearch).
- `app/api/torznab/utils.py` — Query parsing, XML formatting.
- `app/api/qbittorrent/app_meta.py` — App metadata endpoints.
- `app/api/qbittorrent/auth.py` — Login/logout handlers.
- `app/api/qbittorrent/categories.py` — Category listing.
- `app/api/qbittorrent/common.py` — Common helpers for qBittorrent responses.
- `app/api/qbittorrent/sync.py` — Sync endpoints returning main data.
- `app/api/qbittorrent/torrents.py` — Torrent operations.
- `app/api/qbittorrent/transfer.py` — Transfer metrics endpoints.
- `app/api/health.py` — Health check router.
- `app/api/legacy_downloader.py` — Legacy download endpoint.
- `app/core/bootstrap.py` — Environment bootstrap and log setup.
- `app/core/downloader.py` — Download orchestration logic.
- `app/core/lifespan.py` — FastAPI lifespan manager.
- `app/core/scheduler.py` — Thread pool management and job submission.
- `app/db/models.py` — SQLModel definitions and CRUD helpers.
- `app/domain/models.py` — Domain-level models.
- `app/infrastructure/network.py` — Proxy environment management and IP checks.
- `app/infrastructure/system_info.py` — System diagnostics logging.
- `app/infrastructure/terminal_logger.py` — Log duplication to file.
- `app/utils/http_client.py` — HTTP session with proxy awareness.
- `app/utils/logger.py` — Loguru configuration.
- `app/utils/magnet.py` — Magnet link utility functions.
- `app/utils/naming.py` — Title/slug normalization.
- `app/utils/probe_quality.py` — Quality probing for streams.
- `app/utils/terminal.py` — Terminal formatting helpers.
- `app/utils/title_resolver.py` — Title resolution logic.
- `app/utils/update_notifier.py` — GitHub release check.
- `app/cli.py` — CLI server runner.
- `app/config.py` — Environment configuration aggregator.
- `app/main.py` — FastAPI application entry.
- `Dockerfile` — Container build instructions.
- `docker/entrypoint.sh` — Container entrypoint script.
- `docker-compose.yaml` — Production compose file.
- `docker-compose.dev.yaml` — Development compose stack.
- `docs/.vitepress/config.mts` — VitePress site configuration.
- `docs/.vitepress/theme/index.ts` — Custom theme entry.
- `docs/src/guide/overview.md` — User overview doc.
- `docs/src/guide/quickstart.md` — Quickstart instructions.
- `docs/src/guide/running.md` — Running AniBridge documentation.
- `docs/src/guide/configuration.md` — Config documentation aligning with Appendix A.
- `docs/src/guide/networking.md` — Proxy/VPN guidance.
- `docs/src/guide/troubleshooting.md` — Troubleshooting docs.
- `docs/src/guide/faq.md` — Frequently asked questions.
- `docs/src/developer/running.md` — Developer environment instructions.
- `docs/src/developer/testing.md` — Testing docs for contributors.
- `docs/src/developer/logging.md` — Logging & observability docs.
- `docs/src/integrations/docker.md` — Docker integration guide.
- `docs/src/integrations/sonarr.md` — Sonarr configuration.
- `docs/src/integrations/prowlarr.md` — Prowlarr configuration.
- `docs/src/api/endpoints.md` — API overview.
- `docs/src/api/environment.md` — Environment reference.
- `docs/src/api/qbittorrent.md` — qBittorrent API docs.
- `docs/src/api/jobs.md` — Job endpoints documentation.
- `docs/src/api/torznab.md` — Torznab docs.
- `docs/src/api/data-model.md` — Data model docs.
- `docs/src/api-examples.md` — Example API calls.
- `docs/src/legal.md` — Legal documentation.
- `hooks/hook-fake_useragent.py` — PyInstaller hook bundling fake_useragent data.
- `scripts/local_build_release.sh` — Local release script.
- `scripts/local_build_release.ps1` — Windows release script.
- `scripts/setup-codex-overlay.sh` — Agent overlay helper.
- `scripts/startup-script.sh` — Example startup script.
- `src/worker.ts` — Cloudflare Worker entrypoint.
- `wrangler.toml` — Cloudflare configuration.
- `.github/workflows/tests.yml` — Test pipeline.
- `.github/workflows/format-and-run.yml` — Formatting pipeline.
- `.github/workflows/publish.yml` — Docker publish pipeline.
- `.github/workflows/release-on-tag.yml` — Release artifacts pipeline.
- `.specify/memory/constitution.md` — Project constitution.
- `.specify/templates/plan-template.md` — Plan template.
- `.specify/templates/spec-template.md` — Spec template.
- `.specify/templates/tasks-template.md` — Task template.

---

## Appendix C: Test Suite Overview

- `tests/conftest.py` — Fixtures for FastAPI TestClient, environment patching, DB resets.
- `tests/test_config.py` — Validates configuration parsing and defaults.
- `tests/test_health.py` — Checks health endpoint JSON structure.
- `tests/test_magnet.py` — Ensures magnet link builder works with BTIH and parameters.
- `tests/test_models.py` — SQLModel CRUD behavior, TTL logic for availability.
- `tests/test_qbittorrent_auth.py` — Auth endpoint behavior (`SID` cookie).
- `tests/test_qbittorrent_misc.py` — Misc qBittorrent endpoints.
- `tests/test_qbittorrent_more.py` — Additional qBittorrent coverage (categories, add, delete).
- `tests/test_qbittorrent_torrents.py` — `torrents` endpoints verifying job integration.
- `tests/test_title_resolver.py` — Title resolution logic.
- `tests/test_title_resolver_extra.py` — Additional edge cases.
- `tests/test_torznab.py` — Basic Torznab search/caps behavior.
- `tests/test_torznab_errors.py` — Error paths for Torznab.
- `tests/test_torznab_search_extra.py` — Extended search coverage.
- `tests/test_torznab_utils.py` — Utility function tests.
- `tests/test_update_notifier.py` — Update notifier logic.
- `tests/test_version.py` — Version file alignment.
- `tests/test_terminal_logging.py` — Terminal logger duplication behavior.

Run `pytest -q` for quick validation or `pytest --cov=app --cov-report=term-missing` for coverage details.

---

## Appendix D: Release Playbook

1. Ensure tests pass locally (`pytest`).
2. Update docs for new features (`docs/src` and VitePress nav if needed).
3. Bump version using `make patch`, `make minor`, or `make major` as appropriate.
4. Commit changes and push to origin.
5. Tag release (`make tag` or manually `git tag -a vX.Y.Z`).
6. Push tags; GitHub Actions `release-on-tag.yml` and `publish.yml` trigger automatically.
7. Draft release notes summarizing key changes, migrations, API impacts, compliance notes.
8. Verify GHCR image published with new tag.
9. Deploy docs update: run `wrangler publish` after building docs.
10. Announce release via README badge updates or docs changelog entry.

---

## Appendix E: Documentation Editing Guide

1. Modify Markdown under `docs/src/*`.
2. Update navigation and sidebar in `docs/.vitepress/config.mts` if new pages added.
3. For custom components, edit `docs/.vitepress/theme` (TypeScript + Vue).
4. Run `pnpm --prefix docs run dev` to preview changes locally.
5. Before publishing, run `pnpm --prefix docs run build` to ensure site builds cleanly.
6. Update Cloudflare Worker if deployment structure changes.
7. Keep docs in sync with constitution and AGENTS.md.
8. Document environment variables and configuration changes within `docs/src/guide/configuration.md`.

---

## Appendix F: Agent Execution FAQ

- **Q:** Where should agents log newly introduced decisions?
  - **A:** In PR descriptions, update docs, and if structural change, extend AGENTS.md accordingly.

- **Q:** How to regenerate `.specify` plan/spec/tasks templates after constitution change?
  - **A:** Manually update templates referencing new principles; run `scripts/setup-codex-overlay.sh` for overlays.

- **Q:** What if Cloudflare deployment fails due to authentication?
  - **A:** Re-run `wrangler login`, ensure credentials stored. Document issues under docs/developer logging if persistent.

- **Q:** How to add new providers?
  - **A:** Update `PROVIDER_ORDER` default, adjust download logic, add tests, document in docs/integrations.

- **Q:** Where to place new integration docs?
  - **A:** `docs/src/integrations/<tool>.md`; update VitePress sidebar.

- **Q:** How to handle environment-specific overrides during tests?
  - **A:** Use pytest fixtures with `monkeypatch` (see `tests/conftest.py`).

---

## Change Log

- **2025-09-21:**
  - Rebuilt AGENTS.md to ≥1000 lines with full repository coverage.
  - Documented constitution v1.0.0 alignment, updated templates references.
  - Added Cloudflare Workers deployment details, VitePress workflow, CI/CD breakdown.
  - Expanded environment variable catalog and file index.

<!-- END OF AGENTS.md -->
