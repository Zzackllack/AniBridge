# Web UI Monorepo Plan for AniBridge

Date: 2026-02-23  
Repository: `/Users/zacklack/Developer/Own/Repos/AniBridge`

## Goals

- Keep AniBridge as a monorepo.
- Add a future React-based web UI without destabilizing the Python backend.
- Preserve maintainability and clear boundaries for a production-grade codebase.
- Avoid renaming existing backend folders right now.

## Short Answer

- Yes, you can add a new top-level folder like `web/`.
- Prefer lowercase names (`web`, `frontend`) over `WebUI`.
- You do **not** need to rename `app/` now.
- Python does **not** require `src` like Java; `src/` is a common Python packaging convention, but not mandatory for app repos.

## Recommended Structure (Minimal Disruption)

Use this first:

- `app/` -> existing Python backend (keep as-is)
- `web/` -> new UI application (Next.js / Astro / TanStack Start / etc.)
- `docs/` -> docs site (already present)
- `tests/` -> backend tests (keep, but improve structure over time)
- `scripts/` -> shared operational scripts

Why this is best now:

- Lowest migration risk.
- No backend import/path churn.
- Fastest path to shipping UI.
- Easy to evolve later into `apps/` + `packages/` if needed.

## Alternative Structure (Future-Ready, More Opinionated)

If you want a classic JS-style workspace later:

- `apps/api` (Python backend)
- `apps/web` (frontend)
- `packages/*` (shared TS configs/types/UI libs)

Given your current repo, do this only when you have bandwidth for controlled migration, not now.

## About Git History and Renaming `app/`

Common concern: “If I rename folders, history is lost.”

- Git does not store renames as first-class metadata; it detects them heuristically.
- In practice, `git mv` + small edits usually keeps history traceable (`git log --follow`).
- But large simultaneous edits + rename can make blame/history noisier.

Practical advice:

- Keep `app/` unchanged now.
- If you ever rename, do it in a dedicated PR: rename only, then refactor in later PRs.

## Python Folder Naming Conventions (What is “normal”?)

There is no single mandatory folder name in Python projects.

Common patterns:

- App/service repos: `app/` or package root directly.
- Library-style repos: `src/<package_name>/...` (“src layout”).
- Package/module names: lowercase, underscores allowed, no CamelCase.

For AniBridge (a service), keeping `app/` is completely acceptable.

## Naming Recommendation for the New UI Folder

Preferred order:

1. `web/` (best default, short and clear)
2. `frontend/` (also clear)
3. avoid `WebUI/` (non-idiomatic casing)

## Monorepo Operations Model

Use a “multi-runtime monorepo” model:

- Python runtime for backend (`uv`, `pytest`, `ruff`).
- Node runtime for UI (`pnpm` or `npm`, depending on final choice).
- Keep runtime boundaries explicit in docs and CI.

## CI/CD Expectations After Adding UI

At minimum, add separate checks:

- Backend CI: current Python checks.
- Web CI: install/lint/typecheck/test/build for `web/`.
- PR gating: run relevant jobs by changed paths, but ensure critical shared files trigger both pipelines.

## Suggested Implementation Phases (No Code Yet)

1. Create `web/` and define stack choice criteria.
2. Decide package manager policy for frontend (prefer one tool across `docs/` and `web/`).
3. Define API integration contract (auth/session strategy, base URL handling, error model).
4. Add CI job for `web/` with basic quality gates.
5. Add docs section: local dev commands for backend + web side-by-side.
6. Revisit repo structure after UI is stable (optional migration to `apps/` layout).

## Decision Guidance: Next.js vs Astro vs TanStack Start

- Next.js: strongest full-stack React ecosystem, SSR/RSC maturity, most hiring familiarity.
- Astro: best for content-heavy/static-first experiences, lighter client JS.
- TanStack Start: strong data/router model for app-like experiences; newer ecosystem footprint.

If AniBridge Web UI is primarily dashboard/app UX with forms, tables, stateful views:

- Next.js or TanStack Start are usually better fits than Astro.

## Recommended Policy to Adopt Now

- Keep backend at `app/`.
- Add UI at `web/`.
- Keep names lowercase.
- Treat this as one monorepo with two runtimes.
- Defer any backend folder renaming until there is a concrete payoff.
