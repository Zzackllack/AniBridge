# Implementation sequence and agent handoff

## Start here

Read README and all numbered documents before implementing. The branch contains specifications only. No application code, dependency lock, environment default, or deployment has been changed. Research copies under /tmp are disposable and must not be treated as permanent dependencies of this handoff. The sanitized evidence is committed-file-ready under this directory, but the user requested no commit during research.

The intended implementation is independent of PR #119. Preserve that PR's work and do not use it as the baseline for this task. It will need a separate compatibility pass after the mainline update.

## Phase A — Baseline refresh

- [ ] Inspect current workspace changes and local agent instructions.
- [ ] Verify remote main and the latest upstream release. The research base is six lock-only commits behind the recorded remote main.
- [ ] Refresh the implementation base without discarding the specification or unrelated user changes.
- [ ] Reproduce original-pin full tests in an isolated environment with correct repository metadata/default-path behavior.
- [ ] Record Python, OS/architecture, uv version, base SHA, package version, and test output.
- [ ] Keep an original-lock environment for differential checks.

Acceptance: a reproducible baseline with failures distinguished from harness/environment problems. Never edit tests to hide an unchanged baseline failure.

## Phase B — Dependency candidate

- [ ] Change the pin to the assessed released target (5.0.6 unless the specification is refreshed).
- [ ] Regenerate the lock with `--upgrade-package aniworld`; inspect the complete diff.
- [ ] Preserve remote main's independent Mako/AnyIO/SoupSieve updates or their current successors.
- [ ] Run locked/frozen installation and `uv pip check`.
- [ ] Re-run all existing tests before compatibility code changes.
- [ ] Add subprocess real-package symbol/model/language contracts.

Acceptance: installation and existing behavior remain testable. Passing this phase does not authorize release or establish a fix for #158.

## Phase C — Control reachable upstream behavior

- [ ] Introduce/use the local episode protocol at the current facade boundary.
- [ ] Keep s.to metadata requests on verified, configured transport. Prefer reusing the existing local parser if upstream transport is not injectable; see design document.
- [ ] Add regression tests for automatic mirror/IP fallback and ignored base URL.
- [ ] Keep browser execution outside default request paths; test the failure path rather than assuming missing Chromium prevents it safely.
- [ ] Translate missing language, absent host, blocked access, terminal source failure, and transient error distinctly.
- [ ] Bound retry/request work and preserve useful diagnostics without signed URLs or cookies.
- [ ] Establish upstream config-directory ownership before first import; test explicit override and non-root behavior.
- [ ] Update `.env.example`, Compose forwarding, and internal configuration guidance for any new exposed setting or changed default.

Acceptance: the version update cannot silently disable TLS verification, route around configured origins, launch an unprovisioned browser, or change language selection. Tests demonstrate those properties.

## Phase D — Runtime validation

- [ ] Run API/state/STRM regressions and meaningful new contract/failure tests.
- [ ] Build/install distributions and both supported Linux image architectures.
- [ ] Verify actual release PyInstaller commands and dynamic resources where those artifacts are shipped.
- [ ] Repeat bounded live AniWorld and Serienstream checks with sanitized evidence.
- [ ] Run complete real-client *arr flow as specified in G7, including observed import.
- [ ] Check the relevant direct/proxy STRM path separately.
- [ ] Verify restart, cancellation, and controlled failure without false completion.
- [ ] Explicitly label any unavailable platform or unexercised challenge path.

Acceptance: each required gate has evidence for the actual runtime environment. Record unresolved external-provider failures honestly.

## Phase E — Review and rollout preparation

- [ ] Review only the final implementation scope; avoid pulling in catalog/WebUI/rename work.
- [ ] Update relevant agent guidance if implementation changes documented behavior.
- [ ] Use the repository PR template when producing a PR body.
- [ ] Explain the problem, final behavior, test evidence, and remaining provider limitations.
- [ ] Do not use `Fixes #158` unless the reporter's failure condition is demonstrably fixed.
- [ ] Use Conventional Commits; separate dependency/compatibility and independent packaging fixes if that improves review.
- [ ] Follow repository release tooling; do not hand-create release tags or versions.

This document is a handoff, not authorization to publish or deploy. Follow the user's implementation-turn instructions and repository release workflow.

## Expected file scope

Required: `apps/api/pyproject.toml`, `apps/api/uv.lock`, real-package compatibility tests.

Likely: `apps/api/app/core/downloader/episode.py`, `app/utils/aniworld_compat.py`, local s.to facade/parser integration, `app/core/downloader/extractors/voe.py`, local error classification, and affected tests. A narrowly scoped compatibility submodule is reasonable; do not enlarge an already large episode module unnecessarily.

Conditional: `.env.example`, `docker/compose.yaml`, configuration guidance, Dockerfile/hooks/workflows if runtime evidence requires a packaging fix. Do not reformat unrelated files.

Not expected: migrations, catalog tables/indexer, WebUI, upstream-provided new catalog models, hosted catalog service, rename.

## Suggested reviewable slices

1. Dependency candidate plus real-package contracts (not independently release-ready if transport gates are open).
2. Minimal transport/config/error compatibility changes that make the candidate meet the service contract.
3. Only demonstrated packaging gaps and final runtime evidence.

Do not confuse multiple commits with multiple releases: the final shipped set must satisfy all gates.

## Rollback

The candidate should require no schema change. Preserve the prior image digest and configuration backup. Roll back the pin and its complete lock changes together, then redeploy the prior verified image if a release regresses. Do not delete DATA_DIR, job records, or downloads.

Upstream may rewrite its own .env on import; preserve a pre-upgrade copy of upstream configuration separately from AniBridge settings. If the implementation adds a new upstream config directory, document whether rollback simply leaves that directory unused. Do not restore browser/session data from another user or environment.

## Required final implementation report

Include commit/base/package identity, exact file scope, test counts, real-package versus mocked coverage, container/platform results, live-probe stage, actual Sonarr import evidence, configuration changes, known limitations, and rollback steps. Clearly distinguish a prepared local fix from a published or deployed release.
