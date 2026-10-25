## Description

Implement the opt-in catalog query architecture for AniBridge v3: a standalone
collector maintains durable provider observations and conservative mappings,
publishes validated catalogs atomically, and serves bounded metadata queries.
The local FastAPI client applies corrections and filtering, freezes grab source
identity, and exposes durable qBittorrent-compatible job progress and history.

This draft targets protected `v3`; `main` remains default/stable. It is private
pilot work, not approval for deployment, merging or public release. The latest
candidate uses private worker state v7 and public schema2. Migration creates a
consistent no-overwrite backup; rollback removes only owned bookkeeping and
retains newer observations. Writable state must enforce process locks.

Follow-up fixes validate complete cached canonical evidence, preserve due
retries, separate recent-feed failures from inventory deadlines, commit failed
checkpoints atomically, propagate fatal writer failures, and reject incomplete
quota inventories. The client adds optional credentialed sessions, bounds login
input before parsing, fixes mixed-history filters and progress/handoff behavior,
uses startup-only PBKDF2 for session keys, and removes private input logging at
the repaired boundaries. Native remux/probe
uses a separately measured 320-MiB address-space bound; parsers/transfers retain
their existing 256-MiB limit.

The unconditional test gate now includes frozen API/core/worker tests and native
AMD64/ARM64 image behavior checks. Publishing uses separate preview packages and
immutable source/digest identities; builds do not deploy. Dependency patches and
the existing operational guides are included.

The dated audit artifacts in
`internal/specs/020-catalog-query-api-evaluation/` distinguish current hosted
results, live `52065c7`/v6 observations, small fixtures and prior full-copy v6
proof. Full-size v7 upgrade/rollback/concurrency, prospective independent mapping
evidence, and fresh real Sonarr credentialed/scene-order/file-move acceptance
remain open. Aggregate disk admission is unresolved; historical backups and
experiment state are preserved. No provider media was acquired in these audits.

## Type of Change

- [x] Bug fix (non-breaking change which fixes an issue)
- [x] New feature (non-breaking change which adds functionality)
- [x] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [x] Documentation update

## Testing

- [x] I have performed a self-review of my own code
- [x] I have commented my code, particularly in hard-to-understand areas
- [x] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [x] I have added tests that prove my fix is effective or that my feature works
- [x] New and existing unit tests pass locally with my changes

Local macOS tests retain explicitly reported Linux-only skips. Hosted native
tests and image identities must be checked on the final PR SHA; a passing older
run is not final-source proof. Existing TestClient/resource warnings remain
visible. Generated media and real-client results retain their dated scope;
they do not prove live acquisition, playback, complete mappings or capacity.

Tested code `3064faf`: native AMD64/ARM64 API 352 passed each; installed
core/worker suites 322/324 each, no skips. Tests / Required Gate, lint/CodeQL
and both preview manifests pass. The complete current accounting is in
`TURN2_READINESS_2026-10-25.md`; later documentation commits need their own
hosted checks. This body is prepared locally and has not edited the draft PR.

## Screenshots (if applicable)

N/A. No new visible progress-bar or playback proof is claimed.

## Additional Notes

The protected `v3` branch still needs deliberate enforcement of the aggregate
test/build gate and human/CODEOWNER approval. Public hosting additionally needs
an explicit scope/rights/authentication/TLS/release policy, all-router security
review, recovery evidence and sustained freshness/capacity measurements.
Issue #175's broad E2E expansion remains unimplemented.

Worker upgrades must select a tested immutable preview digest, preserve the
existing service/configuration/volumes, and pass admitted stopped-state
snapshot/publication/preservation checks. Restore v6 code only after the
candidate's stopped-writer `rollback-v6` procedure. Never restore an old ledger
over observations collected later. Unsafe Mac bind storage must move through an
admitted consistent migration plan before candidate startup. Operational writes,
protection changes, draft transition, merging and default-branch changes require
separate authorization.
