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

October 18 canonical failure regressions are `test_canonical_failures.py` and
`test_canonical_episode_identity.py`. They distinguish successful HTTP responses
rejected by validation from transport/admission failures, retain retry deadlines
and old maps/releases, and accept either complete TVDB episode identity pair.
Contradictory, mixed or partial pairs cannot fall back to numbering. The small
metadata-only fixture freezes four independently selected series' explicit IDs;
it does not establish whole-catalog mapping precision.

`recorded_failure_replay.py` runs the real Enricher on marked consistent copies
with recorded metadata and no network. Mount baseline read-only, use 2 CPU/2 GiB
and bounded writable `/tmp`; full-ledger comparison uses in-memory SQL scratch.
It advances the experiment clock to existing retry deadlines instead of clearing
failures. Raw recordings and ledger copies stay in private scratch; commit only
sanitized metadata fixtures and aggregate preservation/coverage evidence.

Publication follow-up regressions live in `test_publication_followup.py`,
`test_publication_migrations.py` and `test_publication_harness.py`: durable
semantic/freshness admission, independent full/incremental equality, new and
removed rows, reparenting, tombstones, policy/digest invalidation, writes outside
planned partitions, external staging writers, clock rollback, concurrent WAL
commits, interrupted v6 upgrades and acknowledgement crash recovery. Full validator
admission remains the default for untrusted artifacts. `publication_benchmark.py`
compares generated edits on marked, consistent private ledger copies at 2 CPU/2 GiB
with networking disabled; seed → legacy → incremental are sequential phases.
Source startup checks are timed separately and never bypassed on the new worker.
Keep its private source rows/errors outside Git; sanitized aggregate results can
be committed. A short publication experiment does not establish collection
throughput or a freshness SLA.

`apps/api/tests/unit/catalog/test_legacy_qbit_history.py` exercises query-mode
qBittorrent torrent-list and sync streams with mixed pre-existing legacy aliases
and durable jobs. Keep populated legacy history in compatibility coverage: an
empty generated acceptance database cannot exercise the legacy projection.

Worker `test_finale_announcements.py` uses six frozen metadata cases plus
negative grammar/ambiguity checks. The labels predate the code change; its
held-out split is fixed regression evidence, not a blind precision trial. Full
source history can reveal additional duplicate names absent from a compact
alias-conflict case; both must abstain. Linux suite scratch needs enough free
space for the existing storage reserves even with a bounded memory cgroup.

`test_cached_retry.py` covers due failures with usable cached names, real retry
success/failure, restart and newer cross-provider descriptor recovery.
`test_canonical_progress.py` separates canonical retry age from page failures;
zero/new-evidence deadlines do not imply epoch-old work. The finite
`cached_retry_replay.py` harness refuses unmarked backups and existing candidate
directories. Its simulated HTTP failures prove queue progress and full-ledger
preservation, not successful live enrichment. `test_cached_retry_harness.py`
exercises those guards and retained retry state.
