# AniBridge Agent Guide

AniBridge is a FastAPI service that bridges AniWorld/Serienstream/megakino catalogs to Torznab and qBittorrent-compatible APIs for *arr automation.

Essentials

- Python runtime baseline: 3.14.
- Package manager: uv for Python dependencies.
- Repo-wide: do not commit artifacts under `data/`.
- Database: SQLite with Alembic migrations in `apps/api/app/db/migrations`.
- Use of Context7 for up-to-date external documentation.
- On change of any environment variable, update `apps/api/.env.example`.
- Keep upstream state under `ANIWORLD_INSTALL_FOLDER` (default
  `${DATA_DIR}/aniworld`); do not mutate process `HOME` for library imports.
- Keep the code vocabulary explicit: `providers/` means catalogue sites
  (`aniworld.to`, `s.to`, `megakino`), while direct video hosts belong under
  `apps/api/app/hosts/`.

Request API private pilot

- Shared identities/read contract/cache: `packages/catalog-core`; collector and
  bounded read-serving command: `apps/catalog-worker` (separate uv projects).
- Selected contract: `internal/specs/020-catalog-query-api-evaluation/IMPLEMENTATION.md`.
  This supersedes 019 client snapshot distribution only. Historical gate failures
  remain historical failures; no public default or remote deployment is approved.
- `CATALOG_CONFIG_FILE` is opt-in: absent keeps mainline routes; query mode supports
  configured AniWorld/Serienstream and optional Megakino. Local corrections precede
  canonical filtering.
- Search never crawls or extracts video. Jobs freeze source identity and resolve
  on the user's instance. Do not introduce snapshot client download machinery.
- Total collector/service storage is 30,000,000,000 bytes, including state, read
  catalog/staging, backups, logs and 1,000,000,000-byte runtime reserve.
- Use disposable pilot volumes and `scripts/catalog/query_pilot/compose.yaml`;
  never mix those with a real installation. No query/IP access logs by default.
- Keep `EVIDENCE.md` current; synthetic/client/live extraction/import/playback
  proofs are distinct. The maintainer guide is `scripts/catalog/query_pilot/README.md`.
- Normal Linux collection/server and separate local-client commands are in
  `scripts/catalog/query_pilot/SERVER.md`; Megakino live language gaps remain explicit.
- The original AniWorld metadata/season-1 discovery is closed. The finite generated
  media acceptance handoff is `scripts/catalog/query_pilot/ACCEPTANCE.md`; its HTTP input hook is
  test-only and must never be installed in a normal deployment.

Common pitfalls

- The README of this repository is not at ./README.md but at ./.github/README.md.

Non-standard commands

- Tests: `cd apps/api && pytest`
- Format: `cd apps/api && ruff format app`
- Docs build (local): `pnpm --prefix docs run build`
- Docs build (Cloudflare/wrangler): `pnpm --prefix docs install --frozen-lockfile && pnpm --prefix docs run build`

More guidance

- [Overview](internal/agents/overview.md)
- [Architecture](internal/agents/architecture.md)
- [Repository Map](internal/agents/repo-map.md)
- [Domain Models](internal/agents/domain-models.md)
- [API Contracts](internal/agents/api.md)
- [Configuration](internal/agents/configuration.md)
- [Coding Standards](internal/agents/coding-standards.md)
- [Development Workflow](internal/agents/dev-workflows.md)
- [Testing](internal/agents/testing.md)
- [Deployment](internal/agents/deployment.md)
- [Docs Site](internal/agents/docs-site.md)
- [Release & CI](internal/agents/release-ci.md)
- [Security & Legal](internal/agents/security-legal.md)
- [Onboarding & Collaboration](internal/agents/onboarding-collaboration.md)
- [References](internal/agents/references.md)

Maintenance notice

- Update `AGENTS.md` and the relevant `internal/agents/*` files whenever changes would make agent guidance outdated.
