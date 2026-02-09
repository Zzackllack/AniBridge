# Development Workflow

## Python Environment

- Use uv for dependency management.
- Create a virtualenv with `uv venv` and activate it.
- Sync dependencies: `uv sync --frozen`.

## Running the App

- `uv run python -m app.main` starts the FastAPI app.
- `uvicorn app.main:app --reload` is supported when `ANIBRIDGE_RELOAD=true`.

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
