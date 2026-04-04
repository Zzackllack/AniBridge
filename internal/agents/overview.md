# Agent Overview

## Project Description

AniBridge is a FastAPI service that bridges anime/series streaming catalogs (AniWorld, Serienstream/s.to, megakino) to Torznab and qBittorrent-compatible APIs for *arr automation.

## Snapshot

- Repository: https://github.com/Zzackllack/AniBridge
- Primary maintainer: @Zzackllack
- Runtime: Python 3.14
- Frameworks: FastAPI, SQLModel, Uvicorn, Loguru, yt-dlp, AniWorld library
- Database: SQLite at `data/anibridge_jobs.db` with Alembic migrations
- Deployments: Docker (GHCR), bare-metal Python, PyInstaller single-binary, docs on Cloudflare Workers
- Documentation: VitePress site under `docs/`
- Testing: pytest
- Observability: Loguru + TerminalLogger + `/health`
- License: BSD 3-Clause with legal documentation under `docs/src/legal.md`

## Tech Stack Matrix

| Layer | Technology | Purpose | Key Files |
| --- | --- | --- | --- |
| API Framework | FastAPI | HTTP routing, dependency binding, request handling | `apps/api/app/main.py`, `apps/api/app/api/*` |
| ASGI Server | Uvicorn | Production server, websockets support | `apps/api/app/main.py`, `apps/api/app/cli.py` |
| ORM/DB | SQLModel + SQLAlchemy | SQLite persistence for jobs and availability cache | `apps/api/app/db/models.py` |
| Migrations | Alembic | Schema migration management | `apps/api/app/db/migrations/*`, `apps/api/alembic.ini` |
| Background Jobs | ThreadPoolExecutor | Download orchestration, TTL cleanup, IP monitor | `apps/api/app/core/scheduler.py`, `apps/api/app/core/lifespan.py` |
| Downloader | yt-dlp, AniWorld lib | Episode retrieval and provider fallback | `apps/api/app/core/downloader/*` |
| Logging | Loguru | Structured logs and file mirroring | `apps/api/app/utils/logger.py`, `apps/api/app/infrastructure/terminal_logger.py` |
| Configuration | dotenv + env vars | Centralized config resolution | `apps/api/app/config.py` |
| Docs Site | VitePress | Static documentation | `docs/.vitepress/*`, `docs/src/*` |
| Docs Hosting | Cloudflare Workers + Wrangler | Serve docs build output | `wrangler.toml`, `docs/worker.ts` |
| Packaging | setuptools + build + PyInstaller | Python package distribution and binaries | `apps/api/pyproject.toml`, `apps/api/anibridge.spec` |
| Containerization | Docker, docker-compose | Images and local orchestration | `apps/api/Dockerfile`, `docker/compose*.yaml` |
| Automation | GitHub Actions | CI/CD pipelines | `.github/workflows/*` |
