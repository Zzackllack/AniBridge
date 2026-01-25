# Testing

## Test Runner

- Pytest configured via `pytest.ini`.

## Fixtures

- `tests/conftest.py` sets up FastAPI test client, DB fixtures, and env overrides.

## Key Suites

- `test_health.py` — `/health` endpoint.
- `test_qbittorrent_*.py` — qBittorrent shim behavior.
- `test_torznab*.py` — Torznab search/caps/errors.
- `test_magnet.py`, `test_naming.py`, `test_title_resolver*.py` — helpers.
- `test_models.py` — SQLModel behaviors and TTL logic.
- `test_update_notifier.py` — release checks.
- `test_version.py` — `_version.py` alignment with `VERSION`.

## Execution

- Run all tests: `pytest`.
- Optional coverage: `pytest --cov=app`.

## Coverage Goals

- Target near-total coverage for API endpoints, config parsing, helpers, and update notifier.

## CI

- `.github/workflows/tests.yml` runs on pushes/PRs touching `app/**` or `tests/**`.
