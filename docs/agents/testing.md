# Testing

## Test Runner

- Pytest configured via `pytest.ini`.

## Fixtures

- `tests/conftest.py` sets up FastAPI test client, DB fixtures, and env overrides.

## Suite Layout

- `tests/integration/api/` contains request/response coverage for FastAPI
  surfaces such as qBittorrent, STRM proxy, Torznab, and health endpoints.
- `tests/unit/app/` covers app-level helpers such as config, CORS, and version
  resolution.
- `tests/unit/api/` contains non-request unit coverage for API helper modules.
- `tests/unit/core/` groups downloader, scheduler, and STRM proxy logic.
- `tests/unit/db/` covers SQLModel behavior and Alembic migrations.
- `tests/unit/providers/` groups provider-specific logic by source
  (`aniworld`, `megakino`, `sto`).
- `tests/unit/scripts/` covers repository automation scripts.
- `tests/unit/utils/` contains utility coverage, including nested
  `title_resolver/` tests.

## Key Suites

- `tests/integration/api/test_health.py` — `/health` endpoint.
- `tests/integration/api/qbittorrent/` — qBittorrent shim behavior.
- `tests/integration/api/torznab/` — Torznab search/caps/errors.
- `tests/unit/utils/` and `tests/unit/utils/title_resolver/` — helper modules.
- `tests/unit/db/test_models.py` — SQLModel behaviors and TTL logic.
- `tests/unit/utils/test_update_notifier.py` — release checks.
- `tests/unit/app/test_version.py` — `_version.py` alignment with `VERSION`.

## Execution

- Run all tests: `pytest`.
- Optional coverage: `pytest --cov=app`.

## Coverage Goals

- Target near-total coverage for API endpoints, config parsing, helpers, and update notifier.

## CI

- `.github/workflows/tests.yml` runs on pushes/PRs touching `app/**` or `tests/**`.
- On pull requests, failed pytest runs upload the captured console output so CI
  can post or refresh a remediation comment on the PR thread.
