# Testing

## Test Runner

- Pytest configured via `apps/api/pytest.ini`.

## Fixtures

- `tests/conftest.py` sets up FastAPI test client, DB fixtures, and env overrides.

## Suite Layout

- `tests/integration/api/` contains request/response coverage for FastAPI
  surfaces such as qBittorrent, STRM proxy, Torznab, and health endpoints.
- `apps/api/tests/unit/app/` covers app-level helpers such as config, CORS, and version
  resolution.
- `tests/unit/api/` contains non-request unit coverage for API helper modules.
- `tests/unit/core/` groups downloader, scheduler, and STRM proxy logic.
- `tests/unit/db/` covers SQLModel behavior and Alembic migrations.
- `tests/unit/providers/` groups catalogue-site-specific logic by source
  (`aniworld`, `megakino`, `sto`).
- `tests/unit/hosts/` covers direct-video host detection and wrapper behavior.
- `tests/integration/test_real_aniworld_package.py` runs isolated subprocess
  contracts against the actually installed upstream package; do not replace it
  with `sys.modules` stubs.
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
- `apps/api/tests/unit/app/test_version.py` — `_version.py` alignment with `VERSION`.

## Execution

- Run all tests: `cd apps/api && pytest`.
- Optional coverage: `cd apps/api && pytest --cov=app`.

## Coverage Goals

- Target near-total coverage for API endpoints, config parsing, helpers, and update notifier.

## CI

- `.github/workflows/tests.yml` runs on pushes/PRs touching `apps/api/app/**` or `apps/api/tests/**`.
- On pull requests, failed pytest runs upload the captured console output so CI
  can post or refresh a remediation comment on the PR thread.

## Request catalog pilot

Run each uv project's suite from its directory: `uv run pytest -q` in
`packages/catalog-core`, `apps/catalog-worker` and `apps/api`. New focused read
tests cover strict responses, coalescing, outages/corruption/revision scopes,
reader replacement/cancellation and local correction-aware discovery. Reused
lifecycle/migration tests preserve mainline state and local grab ownership.
The [Compose smoke](../../scripts/catalog/query_pilot/README.md) accepts a
paused generated grab; it does not prove live extraction, import or playback.
Historical snapshot validator timeouts remain failed; no endurance rerun.
Metadata/season-1 discovery is closed. The single generated-media production-job
acceptance scenario is [ACCEPTANCE.md](../../scripts/catalog/query_pilot/ACCEPTANCE.md).
Its test-only HTTP input hook must never be installed in normal deployments;
it does not substitute the executor/download child or fabricate completion.

Provider/large-title query cases are in `test_query_providers.py`. The normal
Linux collection command is tested through restart, real publication subprocess,
provider block isolation and backup by worker `test_private_operations.py`.
The publication child has a 1-GiB file cap; the parent supplies the 420-second
wall deadline. These are different arguments to `limit_child`/`run_child_async`.

Collector repair regressions: `test_collection_repairs.py`,
`test_provider_transport.py`, `test_episode_rows.py` and the v3-to-v4 upgrade
case. Linux-only checks retain parser termination/publication enforcement.
`scripts/catalog/collector_benchmark` compares finite metadata cohorts; raw
bodies and ledger copies stay in disposable private scratch, never in Git.

Resource profiles are independent: collector minimum 2 vCPU/2 GiB, recommended
4 vCPU/4 GiB (6 GiB optional after profiling), local metadata/search target
1 vCPU/512 MiB. The old 512-MiB collector and 1-GiB client runs retain their
historical proof level. A smaller stress test does not establish a production
requirement; no whole-job 512-MiB client claim has been validated.
