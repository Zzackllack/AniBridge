# Web UI Monorepo Plan for AniBridge

Date: 2026-02-23  
Repository: `/Users/zacklack/Developer/Own/Repos/AniBridge`

## Goals

- Keep AniBridge as a monorepo.
- Add a future React-based web UI without destabilizing the Python backend.
- Preserve maintainability and clear boundaries for a production-grade codebase.
- Avoid renaming existing backend folders right now.
- Use the Web UI as the primary operator surface for challenge/captcha-assisted flows.

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

Additional reason:

- the future browser-assisted verification feature can live naturally beside the Web UI
  without forcing browser logic into the Python package layout.

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
- Treat browser automation / browser-assisted verification as backend-owned
  infrastructure, surfaced through the Web UI.

## Browser-Assisted Verification Architecture

The future Web UI should not be treated only as a dashboard.

It should also be the primary operator interface for protected flows that require:

- Cloudflare Turnstile solving
- browser session reuse
- human-in-the-loop verification
- explicit pause/resume behavior for jobs

### Recommended Model

Use three cooperating layers:

1. Backend API and scheduler
2. Browser resolver service
3. Web UI verification center

### 1. Backend API and scheduler

Backend responsibilities:

- detect challenge/captcha pages during provider resolution
- move affected jobs into explicit states such as `challenge_required` or
  `waiting_for_user`
- enqueue browser-assisted resolution work
- persist verification session metadata and audit events
- expose status and control APIs to the UI

### 2. Browser resolver service

This should be a dedicated subsystem, not a hidden helper inside a provider extractor.

Recommended characteristics:

- persistent browser profile per environment or operator
- browser state reused across multiple jobs
- normal HTTP remains the fast path; browser is only used for protected steps
- protected navigation continues inside the same browser session after solve
- support both local desktop mode and server mode

Recommended server mode:

- Chromium/Playwright-compatible backend
- persistent user-data-dir
- Xvfb-backed visible browser when needed
- optional noVNC or equivalent remote operator view

### 3. Web UI verification center

The Web UI should include a dedicated verification area instead of burying this
inside generic download logs.

Recommended UX capabilities:

- list jobs waiting for verification
- show blocked domain/provider and current challenge reason
- open or attach to active browser verification session
- show countdown/expiry hints where known
- resume, cancel, or retry jobs explicitly
- show audit trail of verification attempts and outcomes

## What the Web UI should NOT do

The Web UI should not:

- ask the user to paste raw cookies as the primary workflow
- depend on unofficial auto-solver repositories as the main production path
- force all downloads through a browser even when plain HTTP works
- treat challenge-required jobs as generic opaque failures

## API / Backend Contract Additions

The Web UI plan should assume new backend capabilities for challenge-aware job control.

Suggested backend concepts:

- `ChallengeRequired` internal error/state
- `verification_session_id`
- `challenge_reason`
- `browser_resolution_status`
- `verification_started_at`
- `verification_expires_at` when derivable

Suggested API surfaces:

- list challenge-blocked jobs
- request browser verification session
- attach to existing verification session
- mark verification complete / cancel / retry
- fetch challenge event history

## Security and Enterprise-Grade Expectations

If this is implemented, it should be built like an operator feature, not a scraping hack.

Requirements:

- explicit auth around verification controls
- audit logging for session start/stop/solve/resume actions
- least-privilege storage for browser profiles and secrets
- clear retention policy for verification artifacts
- no silent background solving claims when a human solve is actually required

## CI/CD Expectations After Adding UI

At minimum, add separate checks:

- Backend CI: current Python checks.
- Web CI: install/lint/typecheck/test/build for `web/`.
- PR gating: run relevant jobs by changed paths, but ensure critical shared files trigger both pipelines.

## Suggested Implementation Phases (No Code Yet)

1. Create `web/` and define stack choice criteria.
2. Decide package manager policy for frontend (prefer one tool across `docs/` and
   `web/`).
3. Define API integration contract, including challenge-aware job states and
   verification session APIs.
4. Build a minimal browser resolver service with persistent profile support.
5. Add a first Web UI verification center for `challenge_required` jobs.
6. Add CI job for `web/` with basic quality gates.
7. Add docs section: local dev commands for backend + web side-by-side.
8. Revisit repo structure after UI is stable (optional migration to `apps/` layout).

## Decision Guidance: Next.js vs Astro vs TanStack Start

- Next.js: strongest full-stack React ecosystem, SSR/RSC maturity, most hiring familiarity.
- Astro: best for content-heavy/static-first experiences, lighter client JS.
- TanStack Start: strong data/router model for app-like experiences; newer ecosystem footprint.

If AniBridge Web UI is primarily dashboard/app UX with forms, tables, stateful views:

- Next.js or TanStack Start are usually better fits than Astro.

Because AniBridge is also likely to need authenticated operator workflows,
session-driven views, and browser-verification control panels, this further
pushes the recommendation toward Next.js or TanStack Start over Astro.

## Recommended Policy to Adopt Now

- Keep backend at `app/`.
- Add UI at `web/`.
- Keep names lowercase.
- Treat this as one monorepo with two runtimes.
- Design the UI from the start to include a verification center for
  browser-assisted challenge handling.
- Keep browser-assisted verification as a dedicated subsystem with persistent
  session management, not as scattered extractor-specific hacks.
- Defer any backend folder renaming until there is a concrete payoff.
