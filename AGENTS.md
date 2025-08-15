<!-- START OF AGENTS.md -->

# AGENTS.md — AniBridge AI Agent Guide (Codex, Copilot, LLMs)

This file is designed for AI agents (OpenAI Codex, GitHub Copilot, Claude, Gemini, etc.) to understand, navigate, and contribute to the AniBridge codebase. It provides exhaustive context, standards, workflows, and curated links for agentic development, testing, and automation.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Repository Structure](#repository-structure)
3. [Core Modules & Endpoints](#core-modules--endpoints)
4. [Coding Conventions](#coding-conventions)
5. [Testing & Validation](#testing--validation)
6. [CI/CD & Automation](#cicd--automation)
7. [PR & Contribution Guidelines](#pr--contribution-guidelines)
8. [Agentic Reasoning & Multi-Agent Patterns](#agentic-reasoning--multi-agent-patterns)
9. [Troubleshooting & Migration](#troubleshooting--migration)
10. [Onboarding for AI Agents](#onboarding-for-ai-agents)
11. [External Resources & Links](#external-resources--links)
12. [Templates & Examples](#templates--examples)
13. [Glossary](#glossary)
14. [Changelog](#changelog)

---

## Project Overview

AniBridge is a FastAPI-based automation bridge for anime streaming services (currently AniWorld), exposing Torznab and qBittorrent-compatible APIs for integration with tools like Prowlarr and Sonarr. It features a background scheduler, download progress tracking, and health endpoints for orchestration.

**Key Features:**

- Torznab endpoint for episode indexing
- qBittorrent API shim for download automation
- Background job scheduler
- Healthcheck endpoint
- Dockerized deployment

---

## Repository Structure

**Root Layout:**

- `app/` — Core Python modules
    - `main.py` — FastAPI entrypoint, router setup
	- `torznab.py` — Torznab API/feed logic
	- `qbittorrent.py` — qBittorrent API shim
	- `downloader.py` — Download orchestration
	- `models.py` — SQLModel DB models, CRUD
	- `config.py` — Environment/config management
	- `scheduler.py` — Job scheduling, thread pool
	- `naming.py`, `magnet.py`, `probe_quality.py`, `title_resolver.py` — Utility modules
- `data/` — Persistent data (SQLite DB, downloads, configs)
- `tests/` — Pytest-based test suite
- `docker-compose.yaml`, `Dockerfile` — Containerization
- `requirements.txt` — Python dependencies
- `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md` — Documentation

**Key Files:**

- `app/main.py` — FastAPI app, includes routers, endpoints, scheduler
- `app/torznab.py` — `/torznab` feed, search, caps
- `app/qbittorrent.py` — `/api/v2` endpoints for Sonarr/Prowlarr
- `app/downloader.py` — Download logic, provider fallback, yt-dlp integration
- `app/models.py` — DB models: Job, EpisodeAvailability, ClientTask
- `app/config.py` — Config, env vars, download paths
- `tests/` — Test files for API, auth, title resolution, torznab

---

## Core Modules & Endpoints

**API Endpoints:**

- `/torznab/api` — Torznab feed, search, tvsearch, caps
- `/api/v2/auth/login` — qBittorrent login
- `/api/v2/torrents/add` — Add torrent/magnet
- `/api/v2/torrents/categories` — List categories
- `/api/v2/sync/maindata` — Sonarr main data
- `/health` — Healthcheck
- `/downloader/download` — Direct download job enqueue
- `/jobs/{job_id}` — Job status
- `/jobs/{job_id}/events` — Job event stream
- `/jobs/{job_id}` (DELETE) — Cancel job

**Scheduler:**

- ThreadPoolExecutor for concurrent downloads
- Job registry for progress tracking

**Database:**

- SQLite via SQLModel
- Tables: Job, EpisodeAvailability, ClientTask

---

## Coding Conventions

**General:**

- Python 3.12+, type hints preferred
- Format code with `black`
- Use descriptive variable/function/class names
- Avoid abbreviations except for well-known terms (e.g., API, DB)
- Keep imports tidy, remove unused code
- Document public functions/classes with docstrings
- Translate all comments to English
- Use logging via `loguru` for diagnostics

**FastAPI:**

- Use Pydantic models for request/response schemas
- Prefer async endpoints unless blocking IO is required
- Use dependency injection for DB/session management
- Organize routers by domain (torznab, qbittorrent, etc.)

**Testing:**

- Use `pytest` for all tests
- Place tests in `tests/` with clear naming: `test_<module>.py`
- Use fixtures for setup/teardown
- Aim for coverage of endpoints, models, and critical logic

**Docker:**

- Use non-root user in containers
- Mount `data/` for persistence
- Healthcheck via `/health` endpoint

---

## Testing & Validation

**Test Suite:**

- Run `pytest` before every commit/PR
- Coverage: `pytest --cov=app --cov-report=term-missing`
- Add tests for new features and bug fixes
- Validate API endpoints with HTTPX or curl
- Ensure DB migrations do not break existing jobs

**Linting:**

- Format with `black`
- Optionally use `flake8` or `ruff` for lint checks

**Manual Validation:**

- Start app: `python -m app.main` or `docker compose up`
- Check `/health` endpoint for status
- Validate Torznab and qBittorrent endpoints with Sonarr/Prowlarr

---

## CI/CD & Automation

**Recommended Workflows:**

- Use GitHub Actions or similar for CI
- Steps: Install, lint, test, build Docker image, push
- Example workflow:
    - `pip install -r requirements.txt`
	- `black .`
	- `pytest`
	- `docker build -t anibridge .`
	- `docker compose up -d`

**Healthcheck:**

- Use `/health` endpoint for container orchestration

---

## PR & Contribution Guidelines

**Pull Requests:**

- Title format: `[Fix] Short description` or `[Feature] ...`
- Description: One-line summary, followed by details
- Reference related issues
- Include "Testing Done" section
- Ensure all tests pass before merging
- Prefer small, focused PRs

**Commits:**

- Use clear, descriptive commit messages
- Group related changes

**Code Review:**

- Review for style, correctness, and test coverage
- Suggest improvements, not just fixes

---

## Agentic Reasoning & Multi-Agent Patterns

**Agentic Workflows:**

- AI agents should reason about:
	- Project structure and module relationships
	- API endpoint contracts and dependencies
	- Data flow: job scheduling, download orchestration, DB updates
	- Error handling and logging
- Multi-agent orchestration: Use FastAPI HTTP endpoints for agent-to-agent communication
- Modularize agent tools for extensibility

**Best Practices:**

- Break tasks into small, testable steps
- Validate output at each stage
- Use tracing/logging for debugging
- Prefer stateless endpoints for scalability

---

## Troubleshooting & Migration

**Common Issues:**

- DB migration errors: Check SQLModel schema changes
- Download failures: Validate provider URLs, yt-dlp integration
- API auth issues: Ensure correct cookies/session handling
- Container startup: Check mounted volumes, healthcheck logs

**Migration Notes:**

- Gradually introduce type hints and test coverage
- Update deprecated comments and code
- Translate all non-English comments

**Debugging Tips:**

- Use `loguru` for detailed logs
- Inspect DB state in `data/anibridge_jobs.db`
- Use `pytest` for regression testing

---

## Onboarding for AI Agents

**Steps for New Agents:**

1. Read this AGENTS.md and `README.md` fully
2. Explore `app/` modules and understand endpoint contracts
3. Review test suite in `tests/`
4. Validate local setup: `python -m app.main` or `docker compose up`
5. Run all tests and lint checks
6. Review external links below for best practices

---

## External Resources & Links

### AniBridge Project

- [AniBridge GitHub](https://github.com/zzackllack/AniBridge)
- [AniWorld Downloader Library](https://github.com/phoenixthrush/AniWorld-Downloader)

### FastAPI & Python

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI GitHub](https://github.com/tiangolo/fastapi)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [FastAPI Deployment (Docker)](https://fastapi.tiangolo.com/deployment/docker/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI Advanced User Guide](https://fastapi.tiangolo.com/advanced/)
- [Starlette](https://www.starlette.io/)
- [Pydantic](https://docs.pydantic.dev/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Uvicorn](https://www.uvicorn.org/)
- [Pytest](https://docs.pytest.org/en/stable/)
- [Black](https://black.readthedocs.io/en/stable/)
- [Loguru](https://loguru.readthedocs.io/en/stable/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [Docker](https://docs.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

### Related Automation Tools

- [Prowlarr](https://github.com/Prowlarr/Prowlarr)
- [Sonarr](https://github.com/Sonarr/Sonarr)
- [Radarr](https://github.com/Radarr/Radarr)
- [qBittorrent](https://github.com/qbittorrent/qBittorrent)

### Community & Support

- [FastAPI Discord](https://discord.gg/VQjSZaeJmf)
- [GitHub Discussions](https://github.com/zzackllack/AniBridge/discussions)
- [Stack Overflow FastAPI](https://stackoverflow.com/questions/tagged/fastapi)
- [Stack Overflow Python](https://stackoverflow.com/questions/tagged/python)
- [OpenAI Community](https://community.openai.com/)

### Tutorials & Templates

- [FastAPI Project Generation](https://fastapi.tiangolo.com/project-generation/)
- [OpenAI Agents SDK Example Templates](https://github.com/openai/openai-agents-python/tree/main/examples)
- [FastAPI External Links & Articles](https://fastapi.tiangolo.com/external-links/)

---

## Templates & Examples

**PR Template:**

```
[Feature] Add <short description>

Summary:
- ...

Testing Done:
- ...

Related Issues:
- ...

Screenshots (if UI):
- ...
```

**Test Example:**

```python
import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health():
		response = client.get("/health")
		assert response.status_code == 200
		assert response.json()["status"] == "ok"
```

---

## Glossary

- **Agentic AI:** Autonomous agents (Codex, Copilot, etc.) that reason, plan, and act on codebases
- **Torznab:** API/feed format for indexers (used by Prowlarr/Sonarr)
- **qBittorrent API:** Torrent client API, emulated for automation
- **FastAPI:** Python web framework for APIs
- **SQLModel:** ORM for SQLite, built on SQLAlchemy and Pydantic
- **Scheduler:** Background job orchestrator
- **Provider:** Streaming host for anime episodes
- **EpisodeAvailability:** DB table for language/quality cache
- **ClientTask:** DB table for torrent jobs

---

## Changelog

**2025-08-15:** Major rewrite for agentic AI, Codex, Copilot, and LLMs. Added 300+ lines of context, links, and best practices. Structured for deep agentic reasoning and multi-agent workflows.

---

## Footer

This AGENTS.md is optimized for AI agents. For feedback, open an issue or PR at [AniBridge GitHub](https://github.com/zzackllack/AniBridge).

---

<!--END OF AGENTS.md-->