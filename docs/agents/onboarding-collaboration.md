# Onboarding and Collaboration

## Orientation Checklist

1. Read `README.md`, `LEGAL.md`, `CODE_OF_CONDUCT.md`.
2. Set up the local environment (see `docs/agents/dev-workflows.md`).
3. Run tests: `pytest`.
4. Start the API and check `/health`.
5. Review `.github/workflows` to understand automation triggers.
6. Review docs structure under `docs/src` and VitePress config.
7. Inspect `docker-compose.yaml` for runtime env defaults.

## Quality Checklist

1. Maintain modular boundaries, typing, and configuration hygiene.
2. Keep tests deterministic and cover key paths.
3. Update docs and release notes when behavior changes.
4. Preserve concurrency limits, structured logging, and `/health` responsiveness.
5. Maintain Python 3.12 baseline and document migrations/legal posture.

## Maintenance Notice

- Update `AGENTS.md` and the relevant `docs/agents/*` files whenever changes would make agent guidance outdated.

## Collaboration Patterns

- Use focused scopes per change: API, scheduler, downloader, docs.
- When updating docs, validate that docs reflect code behavior.
- When changing release flow, align `VERSION`, `pyproject.toml`, and release notes.
