# Agent Overview

## Project Description

AniBridge is a FastAPI service that bridges anime/series streaming catalogs (AniWorld, Serienstream/s.to, megakino) to Torznab and qBittorrent-compatible APIs for *arr automation.

## Snapshot

- Repository: https://github.com/Zzackllack/AniBridge
- Primary maintainer: @Zzackllack
- Runtime: Python 3.12 (packaging metadata allows >=3.11)
- Frameworks: FastAPI, SQLModel, Uvicorn, Loguru, yt-dlp, AniWorld library
- Database: SQLite at `data/anibridge_jobs.db` with Alembic migrations
- Deployments: Docker (GHCR), bare-metal Python, PyInstaller single-binary, docs on Cloudflare Workers
- Documentation: VitePress site under `docs/`
- Testing: pytest
- Observability: Loguru + TerminalLogger + `/health`
- License: BSD 3-Clause with `LEGAL.md` disclaimer

## Tech Stack Matrix

| Layer | Technology | Purpose | Key Files |
| --- | --- | --- | --- |
| API Framework | FastAPI | HTTP routing, dependency binding, request handling | `app/main.py`, `app/api/*` |
| ASGI Server | Uvicorn | Production server, websockets support | `app/main.py`, `app/cli.py` |
| ORM/DB | SQLModel + SQLAlchemy | SQLite persistence for jobs and availability cache | `app/db/models.py` |
| Migrations | Alembic | Schema migration management | `app/db/migrations/*`, `alembic.ini` |
| Background Jobs | ThreadPoolExecutor | Download orchestration, TTL cleanup, IP monitor | `app/core/scheduler.py`, `app/core/lifespan.py` |
| Downloader | yt-dlp, AniWorld lib | Episode retrieval and provider fallback | `app/core/downloader.py` |
| Logging | Loguru | Structured logs and file mirroring | `app/utils/logger.py`, `app/infrastructure/terminal_logger.py` |
| Configuration | dotenv + env vars | Centralized config resolution | `app/config.py` |
| Docs Site | VitePress | Static documentation | `docs/.vitepress/*`, `docs/src/*` |
| Docs Hosting | Cloudflare Workers + Wrangler | Serve docs build output | `wrangler.toml`, `src/worker.ts` |
| Packaging | setuptools + build + PyInstaller | Python package distribution and binaries | `pyproject.toml`, `anibridge.spec` |
| Containerization | Docker, docker-compose | Images and local orchestration | `Dockerfile`, `docker-compose*.yaml` |
| Automation | GitHub Actions | CI/CD pipelines | `.github/workflows/*` |
