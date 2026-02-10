# AniBridge Agent Guide

AniBridge is a FastAPI service that bridges AniWorld/Serienstream/megakino catalogs to Torznab and qBittorrent-compatible APIs for *arr automation.

Essentials

- Python runtime baseline: 3.12.
- Package manager: uv for Python dependencies.
- Repo-wide: do not commit artifacts under `data/`.
- Database: SQLite with Alembic migrations in `app/db/migrations`.
- Use of Context7 for up-to-date external documentation.
- On change of any environment variable, update `.env.example`.

Non-standard commands

- Tests: `pytest`
- Format: `ruff format app`
- Docs build (local): `pnpm --prefix docs run build`
- Docs build (Cloudflare/wrangler): `npm --prefix docs ci --no-audit --no-fund && npm --prefix docs run build`

More guidance

- [Overview](docs/agents/overview.md)
- [Architecture](docs/agents/architecture.md)
- [Repository Map](docs/agents/repo-map.md)
- [Domain Models](docs/agents/domain-models.md)
- [API Contracts](docs/agents/api.md)
- [Configuration](docs/agents/configuration.md)
- [Coding Standards](docs/agents/coding-standards.md)
- [Development Workflow](docs/agents/dev-workflows.md)
- [Testing](docs/agents/testing.md)
- [Deployment](docs/agents/deployment.md)
- [Docs Site](docs/agents/docs-site.md)
- [Release & CI](docs/agents/release-ci.md)
- [Security & Legal](docs/agents/security-legal.md)
- [Onboarding & Collaboration](docs/agents/onboarding-collaboration.md)
- [References](docs/agents/references.md)
- [Change Log](docs/agents/change-log.md)

Maintenance notice

- Update `AGENTS.md` and the relevant `docs/agents/*` files whenever changes would make agent guidance outdated.
