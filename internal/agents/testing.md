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

- `.github/workflows/tests.yml` runs on branch pushes and PRs into `main`/`v3`, without path filters. Independent API, core and worker projects use frozen uv locks.
- Core/worker jobs run offline regressions and build/install wheels; the always-running `Tests / Required Gate` rejects failed, cancelled or skipped project jobs. GitHub required-check protection remains an operator decision.
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

Catalog repair tools `repair_benchmark.py` and `metadata_replay.py` use disposable
consistent ledger copies and finite offline workloads. Keep raw live HTML and
private state outside Git; commit sanitized aggregate evidence. Short Linux
profile runs do not establish full-bootstrap capacity, freshness SLA or media
acceptance. No live pilot writer or long crash campaign is implied.

October 14 mapping regressions: `test_matching_followup.py` covers verified
multilingual episode IDs, source annotations, distinct context anchors,
ambiguity/conflicts, unchanged fingerprints, shared admission across restart,
late arrivals and outage recovery. Private v5 migration interruption/rollback
checks retain all v4 data and no-overwrite recovery copies. The fixed 215-case
metadata fixture records label chronology and review errata; its held-out split
is regression evidence, not a blind prospective precision trial.

Finite copied-state tools are `mapping_replay.py`, `targeted_parent_replay.py`,
`evaluate_mapping_labels.py` and `verify_copied_catalog.py`; `maintenance_trace.py`
is a separate synthetic controlled-clock fairness/admission trace. Never point
replay writers at live state. The diagnostic module opens read-only SQLite and
uses the same allowlisted decision path. `--immutable-copy` is only for a
WAL-free consistent frozen backup, never an active database.

`test_canonical_rate.py` checks configurable shared admission across providers,
restart and limit reductions, cache stability, safe HTTP metrics and stopping a
copied-state rate probe on throttling. `canonical_rate_probe.py` is a finite
canonical-only network experiment on explicitly marked disposable copies. Pause
the ordinary collector to avoid two unmeasured budgets. It smooths HTTP starts,
includes redirects and stops escalation on blocking, repeated errors or increased
latency; no provider pages, publication, crawl reset or live ledger writes.
