# AniBridge Repository Structure Refactor Spec

Date: 2026-04-03
Status: In Progress
Scope: Repository layout, root hygiene, internal-vs-public documentation boundaries, future Web UI onboarding

## 1. Purpose

This spec defines a repository structure for AniBridge that:

- preserves conventional tooling entrypoints
- reduces category drift and root-level ambiguity
- adopts an `apps/`-style layout for runnable product surfaces
- keeps history traceable during moves
- improves day-to-day comfort without hiding problems behind deeper nesting

This is a structure and migration spec, not an implementation patch.

## 2. Main Conclusion

AniBridge should move toward an `apps/`-based repository layout because that
matches the maintainer's working style and will make the future Web UI easier to
introduce cleanly.

However, `apps/` must be used for runnable applications and services, not as a
generic bucket for everything in the repository.

The correct target is:

- `apps/` for product runtimes
- `docs/` for published documentation
- `internal/` for agent guidance and planning material
- `scripts/` and `docker/` for operational tooling
- a conventional root for ecosystem entrypoints

## 3. Current Problems

The current repo discomfort is caused less by raw file count and more by mixed
audiences and mixed responsibilities at the top level.

### 3.1 Real problems

- Backend runtime, backend tests, packaging hooks, and Python config are split
  across unrelated top-level paths.
- `docs/` mixes published docs-site content with internal agent guidance.
- `specs/` and `docs/agents/` both contain internal maintenance material, but
  for different purposes.
- Several operational files exist at root even though a `docker/` directory
  already exists.
- The repo is about to gain a Web UI, but the current layout does not express
  "product applications live here" clearly.

### 3.2 Things that feel noisy but are mostly normal

- `.gitignore`, `.gitattributes`, `.dockerignore`
- `package.json` and `pnpm-workspace.yaml` once a Node workspace exists
- `Makefile`
- `LICENSE`

These files are normal root entrypoints. Moving them deeper would usually make
the repository less conventional, not more maintainable.

## 4. Target Structure

```text
/
  apps/
    api/
      app/
      tests/
      hooks/
      pyproject.toml
      uv.lock
      pytest.ini
      alembic.ini
      .env.example
      Dockerfile
      anibridge.spec
    web/
  docs/
    src/
    .vitepress/
    worker.ts
    package.json
  internal/
    agents/
    specs/
  docker/
    compose.yaml
    compose.dev.yaml
    compose.dev.vpn.yaml
    entrypoint.sh
  scripts/
  .github/
  .gitignore
  .gitattributes
  .dockerignore
  AGENTS.md
  LICENSE
  Makefile
  VERSION
  context7.json
  package.json
  pnpm-workspace.yaml
```

## 5. Decisions By Area

## 5.1 `apps/`

### Decision

Create `apps/` as the container for runnable product applications.

### Why this improves the repository

- It matches a familiar and widely used monorepo convention.
- It gives the backend and future frontend a shared home.
- It reduces the feeling that the backend is "floating" beside docs and specs.
- It creates a natural place for future services without forcing a JS-only
  worldview onto the repo.

### What belongs here

- `apps/api/` for the existing Python backend
- `apps/web/` for the future Web UI

### What does not belong here

- internal planning docs
- agent guidance
- general scripts
- repo metadata

## 5.2 Python backend -> `apps/api/`

### Decision

Move the current backend-oriented material under `apps/api/`.

### Files and directories to move

- `app/` -> `apps/api/app/`
- `tests/` -> `apps/api/tests/`
- `hooks/` -> `apps/api/hooks/`
- `pyproject.toml` -> `apps/api/pyproject.toml`
- `uv.lock` -> `apps/api/uv.lock`
- `pytest.ini` -> `apps/api/pytest.ini`
- `.env.example` -> `apps/api/.env.example`
- `alembic.ini` -> `apps/api/alembic.ini`
- `anibridge.spec` -> `apps/api/anibridge.spec`
- `Dockerfile` -> `apps/api/Dockerfile`

### Why this improves feel and structure

- Runtime code, tests, packaging, and Python tooling become one coherent unit.
- Backend contributors can work primarily inside `apps/api/`.
- The future repo reads naturally on GitHub: apps first, support material later.

### Tradeoffs

- Commands and CI paths must be updated.
- Paths in docs, scripts, PyInstaller config, Docker config, and workflows must
  change together.
- This should be done in a dedicated rename-first migration, not mixed with
  logic changes.

## 5.3 Docs stay in `docs/`

### Decision

Keep the published documentation site in top-level `docs/`.

### Why

- `docs/` is a strong convention and easy to discover.
- The docs site is important, but it is not a product runtime in the same sense
  as `api` or `web`.
- Putting docs under `apps/` would mostly satisfy symmetry, not clarity.

### Related change

Keep `docs/` focused on publishable/site-facing content only.

## 5.4 Internal guidance and planning -> `internal/`

### Decision

Create `internal/` and move non-published maintenance material there.

### Files and directories to move

- `docs/agents/` -> `internal/agents/`
- `specs/` -> `internal/specs/`

### Why this improves the repo

- It separates public docs from maintainer/agent-only guidance.
- It reduces the conceptual overlap between `docs/` and `specs/`.
- It gives the repository a clear "internal working material" area.

### Why `specs/` should not move into `docs/agents/`

That would mostly hide clutter rather than improve structure.

Problems with `docs/agents/specs`:

- it makes planning material look like a subset of agent instructions
- it couples architecture/planning docs to one consumer group
- it keeps internal material inside the published docs tree's conceptual space

`internal/specs/` is cleaner than `docs/agents/specs/`.

## 5.5 Operational container files -> `docker/`

### Decision

Use `docker/` as the home for compose files and related container helpers.

### Files to move

- `docker-compose.yaml` -> `docker/compose.yaml`
- keep `docker/docker-compose.dev.yaml` but rename to `docker/compose.dev.yaml`
- keep `docker/docker-compose.dev.vpn.yaml` but rename to
  `docker/compose.dev.vpn.yaml`

### Why

- The repo already has a `docker/` directory.
- Consolidating container entrypoints there removes a small but real source of
  root noise.
- This is a genuine structural improvement, not just a cosmetic shuffle.

### Caveat

If some external platform assumes a root `docker-compose.yaml`, keep a thin root
wrapper only if necessary. Otherwise prefer one canonical location.

## 5.6 Root files that should stay at root

These should remain at root because they are conventional repo or tool
entrypoints:

- `.gitignore`
- `.gitattributes`
- `.dockerignore`
- `.github/`
- `AGENTS.md`
- `LICENSE`
- `Makefile`
- `VERSION`
- `package.json`
- `pnpm-workspace.yaml`
- `context7.json`

### Notes

- `AGENTS.md` should stay at root as the repo-level entrypoint and index.
- `package.json` at root is appropriate once `docs/` and `apps/web/` share a
  Node workspace.
- Root dotfiles are not clutter in the same way as arbitrary product files.

## 5.7 `LEGAL.md`

### Decision

Delete the root `LEGAL.md` pointer once root-facing references point directly to
the canonical docs page.

### Rationale

- The legal content already lives canonically in `docs/src/legal/`.
- Keeping a root pointer adds one more root file without adding new content.
- The repository README and docs can link directly to the published legal page.

## 5.8 `nixpacks.toml` and deployment-specific config

### Decision

Re-evaluate deployment-specific root configs one by one. Do not move them
automatically.

### Rule

Keep a deployment config at root only if the deployment platform expects it
there. Otherwise move it closer to the deployed app or into a dedicated
deployment area later.

### Current recommendation

- leave `nixpacks.toml` alone until its deployment assumptions are verified
- move only after confirming the platform supports a non-root path or app-local
  config

## 5.9 `packages/`

### Decision

Do not create `packages/` yet.

### Why

- There is no current shared UI package or shared TS configuration package that
  justifies it.
- Creating `packages/` before real reuse appears adds abstraction without value.

### Add `packages/` later only if needed

Good reasons:

- shared UI library across multiple frontend apps
- shared TS config, ESLint config, or generated API client package
- shared JS/TS tooling package with real consumers

## 6. What Actually Improves Feel

The following changes improve both aesthetics and maintainability:

- introducing `apps/` for runnable surfaces
- moving backend code, tests, hooks, and Python config under `apps/api/`
- separating published docs from internal agent/spec material
- consolidating container-related files under `docker/`
- reducing audience mixing more than raw file count

## 7. What Only Hides Files

The following changes mostly hide clutter without improving structure:

- moving dotfiles out of root
- moving `docs/` into `apps/` just for symmetry
- moving `specs/` under `docs/agents/`
- creating `packages/` before there is reusable package-level code
- moving standard tool entrypoints into obscure folders and then teaching every
  command how to find them
- relocating `LICENSE` or other standard repo metadata just to shorten the root

## 8. Migration Order

This should be done in phases, with rename-only commits where possible.

### Phase 1 - Internal separation

- create `internal/`
- move `docs/agents/` to `internal/agents/`
- move `specs/` to `internal/specs/`
- update `AGENTS.md` links and any docs references

### Phase 2 - Introduce `apps/`

- create `apps/api/`
- move backend code and backend support files into `apps/api/`
- update Python tooling, scripts, CI, docs, and local commands

### Phase 3 - Container cleanup

- consolidate compose files under `docker/`
- update docs, scripts, and workflows

### Phase 4 - Add the Web UI

- create `apps/web/`
- add root `package.json`
- add root `pnpm-workspace.yaml`
- make `docs/` and `apps/web/` workspace members

### Phase 5 - Optional follow-up cleanup

- remove `LEGAL.md` once root references are direct
- review `nixpacks.toml`, `wrangler.toml`, and other deployment configs
- introduce `packages/` only if reuse emerges

## 9. Rename and History Policy

Use `git mv` for repository moves and keep rename commits focused.

Recommended rules:

- one commit for directory/file moves
- follow-up commits for path fixes and code changes
- avoid mixing large rewrites with large renames
- update docs and CI immediately after moves

Important note:

Git does not store renames as a first-class history object. It detects them
heuristically. `git mv` still helps by making the intent explicit in the commit
and usually improves history traceability when the commit stays focused.

## 10. Final Recommendation

Adopt this target model:

- `apps/` for runnable applications
- `apps/api/` for the current backend
- `apps/web/` for the future Web UI
- `docs/` for published documentation only
- `internal/agents/` for agent guidance
- `internal/specs/` for planning and refactor material
- `docker/` for compose and container helpers
- a conventional root for repo and tool entrypoints

This improves repository feel for real reasons:

- clearer audiences
- clearer ownership
- cleaner GitHub root
- less cross-cutting ambiguity
- a natural path to add the Web UI without forcing JS-centric abstractions too
  early
