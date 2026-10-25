# Testing

## Frozen project checks

Run each uv project from its own directory:

```sh
(cd apps/api && uv run --python 3.14 --frozen pytest -q -rs --tb=short)
(cd packages/catalog-core && uv run --python 3.14 --frozen pytest -q)
(cd apps/catalog-worker && uv run --python 3.14 --frozen pytest -q)
(cd apps/api && uv run --frozen ruff check app && uv run --frozen ruff format --check app)
(cd apps/api && uv run --frozen pylint --fail-under=7.5 app)
actionlint
```

`apps/api/pytest.ini` enables API coverage; report its revision/platform and keep
it separate from mapping accuracy, scenario coverage and operational confidence.
Inspect skips/xfails. Mac success does not execute Linux-only resource checks.

## Suite map

- API `tests/integration/api`: health, Torznab, qBittorrent and STRM HTTP behavior.
- API `tests/unit`: config/core/DB/provider/host/script/utility behavior, including
  query caches, corrections, durable batches, progress and import handoff.
- API `tests/integration/test_real_aniworld_package.py`: installed upstream package
  contracts in subprocesses; do not replace them with import stubs.
- Core `tests`: identity/magnet/schema/reader/transport and process supervision.
- Worker `tests`: collection/reconciliation, canonical evidence/retries,
  publication/leases/last-good, migrations/backup/rollback and query serving.
- Worker `tests/fixtures`: small reproducible metadata inputs consumed by tests;
  keep these tracked, unlike generated run receipts.

Focused safety regressions include `test_feed_failure_isolation.py`,
`test_pipeline_fatal_writer.py`, `test_storage_inventory_errors.py`, canonical
failure/identity suites, publication migration/follow-up suites and API
authentication/login-body/progress/completion cases. Frozen mapping fixtures
are regression cases; their existing label chronology is not a blind trial.

## Native CI and images

`.github/workflows/tests.yml` runs independent frozen API/core/worker jobs and
native API/worker image jobs on AMD64/ARM64. Installed worker wheels run both
core and worker suites. API images run the full behavioral suite with their
native dependencies/FFmpeg. Jobs use UID1000, 2 CPU/2 GiB, no network and
Linux-local scratch; source is mounted read-only. Create the `data/` mountpoint
before mounting its isolated tmpfs, never bind developer persistent state.

`Tests / Required Gate` always runs and rejects failed/cancelled/skipped
dependencies. Required-check enforcement is a separate GitHub policy decision.
Publishing previews is separate from tests and does not deploy anything.

The ordinary API job installs FFmpeg. `media_limit_probe.py` uses finite generated
1080p input to compare 256/320/512-MiB virtual-address caps. Supported-control
failure must exit nonzero; run diagnostics after test/artifact capture. Native
remux/probe use 320 MiB; parser/transfer limits remain 256 MiB. A short probe is
not a capacity or general-format guarantee.

## Copied-state and real-client checks

Use existing helpers under `scripts/catalog/query_pilot` before inventing new
harnesses. `audit_snapshot.py` requires marked WAL-free consistent copies for
full-ledger accounting. Replay/benchmark writers use disposable copies only.
Compare pinned snapshots, not sequential live reads. Never open active WAL state
as immutable or copy only an active main DB. Keep backups and `/state/backup`.

Writable state must enforce process-lock exclusion. The runtime rejects shared
filesystems that accept conflicting locks; use tested named-volume/Linux-local
storage instead of deleting lock files or disabling ownership checks.

The [generated acceptance runner](../../scripts/catalog/query_pilot/ACCEPTANCE.md)
uses real Sonarr/Prowlarr, generated media and the production job path. It checks
intermediate progress, import and a bounded restart window. It does not prove
real provider extraction/playback, actual file movement or complete E2E coverage.
Never mix acceptance volumes with developer `data/` or ordinary/VPN dev stacks.

Keep generated reports/measurements under ignored `internal/local/`, with any
needed archive outside the checkout. Specifications contain current contracts
and concise findings, not dated execution histories or repeated audit matrices.
Open unverified acceptance work stays in
[the current list](../specs/020-catalog-query-api-evaluation/ISSUES.md).
