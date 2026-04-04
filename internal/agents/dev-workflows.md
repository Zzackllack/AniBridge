# Development Workflow

## Python Environment

- Use uv for dependency management.
- Create a virtualenv with `uv venv` and activate it.
- Sync dependencies: `uv sync --frozen`.

## Running the App

- `uv run python -m app.main` starts the FastAPI app.
- `uvicorn app.main:app --reload` is supported when `ANIBRIDGE_RELOAD=true`.
- Containerized dev stack: run `docker compose -f docker/docker-compose.dev.yaml up --watch`.
  - Compose `develop.watch` syncs `app/` changes into the running `anibridge` container.
  - Changes to `pyproject.toml`, `uv.lock`, `Dockerfile`, `docker/entrypoint.sh`, `VERSION`, or `alembic.ini` trigger an image rebuild.
  - Windows/Docker Desktop checkouts must keep shell scripts on LF line endings; the image now normalizes `docker/entrypoint.sh` during build, and `.gitattributes` enforces LF for shell and Docker files in the repo.

## CLI and Utilities

- `app/cli.py` provides the CLI entrypoint for `run_server`.
- Shared helpers live in `app/utils` and are used across CLI and API.

## Docs Development (Local)

- Node 20+ required.
- Install deps: `pnpm --prefix docs install`.
- Run dev server: `pnpm --prefix docs run dev` (VitePress).

## Cloudflare Worker Local Testing

- `wrangler dev` uses the build command in `wrangler.toml`:
  - `npm --prefix docs ci --no-audit --no-fund && npm --prefix docs run build`

## Formatting

- Format Python code with `ruff format app`.
