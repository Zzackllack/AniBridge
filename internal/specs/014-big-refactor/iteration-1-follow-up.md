# AniBridge Repository Refactor Follow-Up

Date: 2026-04-03
Status: Updated after iteration 2 follow-up work
Scope: Broken references, deferred deletions, and next-iteration work after the
initial `git mv`-style restructure

## 1. What iteration 1 intentionally did

Iteration 1 was limited to path moves and directory restructuring.

Completed move groups:

- backend runtime and backend tooling moved to `apps/api/`
- agent docs moved to `internal/agents/`
- specs moved to `internal/specs/`
- compose files consolidated under `docker/`
- empty future placeholder directory created locally at `apps/web/`

This iteration intentionally did **not** update path references, commands,
scripts, CI, or docs content to match the new layout.

## 2. Important note about `anibridge.spec`

`anibridge.spec` was not tracked by Git at the time of the move, so it could not
be moved with `git mv`.

Current state:

- file moved on disk to `apps/api/anibridge.spec`
- no rename history exists for that file because Git was not already tracking it

If keeping rename history for that file matters later, it must first exist as a
tracked file before any future move.

## 3. Broken or outdated references to fix in iteration 2

These categories are expected to be stale after the move.

### 3.1 Root-level agent entrypoint

`AGENTS.md` still references:

- `docs/agents/*`
- `app/db/migrations`
- root `.env.example`

It needs to be updated to point at:

- `internal/agents/*`
- `apps/api/app/db/migrations`
- `apps/api/.env.example`

### 3.2 Internal agent docs

Files under `internal/agents/` still reference old paths such as:

- `app/*`
- `tests/*`
- `hooks/*`
- `pyproject.toml`
- `Dockerfile`
- `docker-compose.yaml`
- `docs/agents/*`
- `specs/*`

These need a full path refresh in a dedicated follow-up pass.

### 3.3 Specs and planning docs

Files under `internal/specs/` still contain many references to:

- `specs/*`
- `app/*`
- `tests/*`
- root `pyproject.toml`
- root `.env.example`
- root `alembic.ini`
- root `Dockerfile`
- root `docker-compose.yaml`

The user requested that these links not be rewritten in iteration 1. They
should be updated later as a bulk documentation pass.

### 3.4 Docker and compose references

Documentation and scripts still reference the old paths:

- `docker-compose.yaml`
- `docker/docker-compose.dev.yaml`
- `docker/docker-compose.dev.vpn.yaml`
- root `Dockerfile`

Canonical new paths are:

- `docker/compose.yaml`
- `docker/compose.dev.yaml`
- `docker/compose.dev.vpn.yaml`
- `apps/api/Dockerfile`

### 3.5 Python project and test tooling references

Many commands and docs still assume these files live at repo root:

- `pyproject.toml`
- `uv.lock`
- `pytest.ini`
- `alembic.ini`
- `.env.example`

They now live under `apps/api/`.

### 3.6 PyInstaller references

Release scripts and docs still reference:

- `hooks/`
- `app/main.py`
- root `anibridge.spec`

They now need to target:

- `apps/api/hooks/`
- `apps/api/app/main.py`
- `apps/api/anibridge.spec`

### 3.7 Test paths

Anything assuming top-level `tests/` is now stale.

Current backend test location:

- `apps/api/tests/`

### 3.8 Backend source paths

Anything assuming top-level `app/` is now stale.

Current backend source location:

- `apps/api/app/`

## 4. Deferred decisions and deletions

The following were intentionally deferred from iteration 1.

### 4.1 Completed in iteration 2

- `LEGAL.md` deleted after root-facing references were updated
- `docs/package-lock.json` deleted to standardize Node package management on
  `pnpm`

### 4.3 Root Node workspace files

User decision:

- do **not** add root `package.json`
- do **not** add root `pnpm-workspace.yaml`
- do this later, likely when `apps/web/` becomes real

### 4.4 `nixpacks.toml`

Leave at root for now.

### 4.5 `wrangler.toml`

Leave at root for now.

## 5. Iteration 2 completion status

Completed in iteration 2:

- updated root entrypoints and developer commands
- updated CI workflows and release/build scripts
- updated Docker and compose references
- updated maintained internal agent docs
- updated maintained public developer docs
- fixed backend test runner path assumptions after the move
- deleted `LEGAL.md`
- deleted `docs/package-lock.json`

Still intentionally not mass-rewritten:

- older historical documents under `internal/specs/` that mention the pre-move
  paths as part of past planning context
- broader content cleanup for long-form historical specs where current-path
  normalization is optional rather than required for day-to-day operation

## 6. Recommended next work

1. Update root entrypoints and developer commands:
   - `AGENTS.md`
   - `Makefile`
   - top-level docs references
2. Update backend tooling and operational references:
   - Docker files and compose references
   - release scripts
   - PyInstaller paths
3. Update internal markdown references:
   - `internal/agents/*`
   - `internal/specs/*`
4. Optional historical-doc normalization:
   - update older `internal/specs/*` references from `app/`, `tests/`, and
     `specs/` to the current layout where that improves readability
5. Start the Web UI bootstrap work in `apps/web/`

## 7. Verification from iteration 2

- `cd apps/api && uv run pytest -q` -> passed
- `pnpm --prefix docs run build` -> passed
- `docker compose -f docker/compose.yaml config` -> passed
- `docker compose -f docker/compose.dev.yaml config` -> passed
- `docker compose -f docker/compose.dev.vpn.yaml config` -> passed

Compose parsing emitted only non-blocking warnings about unset optional env vars
and the obsolete `version` key in `docker/compose.yaml`.

## 8. Commit guidance for this iteration

This iteration is suitable for a dedicated rename-only commit plus the
follow-up report document.

Recommended discipline:

- commit moves first
- do not mix in path-fix edits yet
- start the next iteration from that clean baseline
