# AniBridge Agent Guide

AniBridge is a FastAPI service that bridges AniWorld/Serienstream/megakino catalogs to Torznab and qBittorrent-compatible APIs for *arr automation.

Essentials

- Python runtime baseline: 3.14.
- Package manager: uv for Python dependencies.
- Repo-wide: do not commit artifacts under `data/`.
- Database: SQLite with Alembic migrations in `apps/api/app/db/migrations`.
- Use of Context7 for up-to-date external documentation.
- On change of any environment variable, update `apps/api/.env.example`.

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
- [Change Log](internal/agents/change-log.md)

Maintenance notice

- Update `AGENTS.md` and the relevant `internal/agents/*` files whenever changes would make agent guidance outdated.
