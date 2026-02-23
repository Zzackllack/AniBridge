# AniBridge Deep Code Review

Date: 2026-02-23
Repository: /Users/zacklack/Developer/Own/Repos/AniBridge
Scope: whole repository (`app/`, `tests/`, `docs/`, `.github/`, `scripts/`, `hooks/`, packaging/config), plus test/lint/build evidence.

## Review Baseline (Python + Modular Maintainability)

This review used the following baseline principles before diving into module-level findings:

- Python conventions: consistent naming, clear function boundaries, predictable error handling, type-safe contracts, and minimal surprise behavior.
- API correctness: endpoint behavior must match documented query/body semantics.
- Security: sensitive endpoints require explicit auth enforcement (not just login endpoint existence).
- Concurrency safety: no shared mutable state without synchronization; startup logic must be safe in multi-worker deployments.
- Modularity: large orchestration paths should be decomposed into composable, testable units.
- Resilience: failure of optional integrations (indexes/domains/env typos) should degrade gracefully, not hard-fail process startup.

Reference guidance used for alignment:

- FastAPI lifespan/deployment guidance (Context7: `/fastapi/fastapi/0.128.0`)
- Python style/type-hint conventions (Context7: `/websites/python_3`)

## Executive Summary

- Total findings: 25
- Critical: 1
- Major: 16
- Minor: 8
- Nitpick: 0

Top priorities to fix first:

1. qBittorrent API authentication bypass (`/api/v2/*` currently unauthenticated)
2. SQLite migration execution inside lifespan across workers
3. Megakino URL normalization/index bootstrap bugs that can break resolution/search
4. Torznab contract mismatch (`offset` ignored)

---

## Findings (Prioritized)

### F-001 - Authentication bypass on qBittorrent-compatible API

- Severity: **critical**
- Category: Security
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/qbittorrent/torrents.py`
- Line/Method: `torrents_*` endpoints (approx. lines 29+), with related login in `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/qbittorrent/auth.py:10-17`
- Problem: Login sets a cookie, but no route dependency/guard validates session auth on sensitive routes.
- Impact: Any reachable client can add/delete torrents or inspect state without credentials.
- Recommendation: Add mandatory auth dependency for all `/api/v2/*` routes and reject requests without valid session/token.

### F-002 - Torznab `offset` parameter accepted but not implemented

- Severity: **major**
- Category: API Contract Correctness
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/torznab/api.py`
- Line/Method: `torznab_api` (approx. lines 1426-1834)
- Problem: `offset` is declared/logged but not applied to emitted results.
- Impact: Clients cannot paginate reliably; behavior diverges from expected Torznab contract.
- Recommendation: Implement `offset` before emission in preview/episode search pipelines.

### F-003 - qBittorrent `savepath` parsed but ignored

- Severity: **major**
- Category: API Contract Correctness
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/qbittorrent/torrents.py`
- Line/Method: `torrents_add` (approx. lines 29-124)
- Problem: `savepath` is read and metadata-updated, but not passed into `schedule_download` request.
- Impact: Downloads always land in default directory even when client requests explicit destination.
- Recommendation: Pass resolved `savepath` through scheduler and download execution path.

### F-004 - Language availability check can reject valid requested language

- Severity: **major**
- Category: Correctness
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/downloader/provider_resolution.py`
- Line/Method: `_validate_language_available` (approx. lines 142-156)
- Problem: Requested language is normalized, available languages are not consistently normalized before membership check.
- Impact: False `LanguageUnavailableError` even when provider has requested language variant.
- Recommendation: Normalize both requested and available language values before comparison.

### F-005 - Resolver fallback skipped when index fetch fails

- Severity: **major**
- Category: Resilience
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/utils/title_resolver.py`
- Line/Method: `slug_from_query` / `_search_sites` (approx. lines 714-722)
- Problem: Empty index + index-capable site causes early continue; search-only fallback path is skipped.
- Impact: Temporary index failure results in hard miss (`None`) even when query-derived slug fallback is possible.
- Recommendation: Allow fallback resolution path when index is empty due to failure conditions.

### F-006 - Megakino relative provider links not normalized before extraction

- Severity: **major**
- Category: Correctness
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/providers/megakino/client.py`
- Line/Method: `resolve_direct_url` + `_extract_provider_links` (approx. lines 167-199 and 294-334)
- Problem: `_extract_provider_links` may return raw relative iframe URLs; host-based extractor routing then fails.
- Impact: Direct URL extraction often degrades to generic embed fallback and may fail provider-specific resolution.
- Recommendation: Normalize/dedupe URLs before return and pass normalized values downstream.

### F-007 - Protocol-relative URLs (`//...`) incorrectly normalized

- Severity: **major**
- Category: URL Handling / Correctness
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/providers/megakino/client.py`
- Line/Method: `_normalize_url` (approx. lines 235-252)
- Problem: Protocol-relative URLs are treated as local paths and prefixed with megakino host.
- Impact: Wrong host inference, broken provider matching, invalid fallback URLs.
- Recommendation: Handle `//...` as absolute host URLs (prepend scheme only).

### F-008 - `MEGAKINO_TITLES_REFRESH_HOURS=0` can prevent initial index load

- Severity: **major**
- Category: Config/Behavior Mismatch
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/providers/megakino/client.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/providers/megakino/sitemap.py`
- Line/Method: `load_index` (approx. 84-93), `needs_refresh` (approx. 257-272)
- Problem: `refresh_hours <= 0` disables refresh and initial fetch path can be skipped when cache is empty.
- Impact: Empty catalog behavior under “0 = never reload” configuration.
- Recommendation: Force one bootstrap fetch when `_index is None` even with refresh disabled.

### F-009 - Migrations run in app lifespan for every worker

- Severity: **major**
- Category: Deployment/Concurrency
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/lifespan.py`
- Line/Method: startup block invoking migrations (approx. lines 111-130)
- Problem: Multi-worker startup can execute migrations concurrently against shared SQLite.
- Impact: `database is locked`, startup failures, migration race risk.
- Recommendation: Run migrations once pre-fork/pre-start, or guard with lock/leader election.

### F-010 - Unprotected numeric env parsing can crash import/startup

- Severity: **major**
- Category: Configuration Robustness
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/config.py`
- Line/Method: raw `int()/float()` env parsing (e.g., lines 49-52, 207-211 and similar)
- Problem: Malformed env value raises `ValueError` at import time.
- Impact: Service fails hard with low-quality diagnostics.
- Recommendation: Use safe parser helpers for all numeric env vars with warning + fallback default.

### F-011 - Race condition in unique STRM path allocation

- Severity: **major**
- Category: Concurrency / Data Integrity
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/utils/strm.py`
- Line/Method: `allocate_unique_strm_path` (approx. lines 65-86)
- Problem: Existence-check loop is non-atomic; concurrent workers can choose same filename.
- Impact: File clobbering or intermittent create failures.
- Recommendation: Reserve target path atomically (`O_CREAT|O_EXCL`) or include unique suffix + atomic write.

### F-012 - Shared global `requests.Session` used across resolver threads

- Severity: **minor**
- Category: Thread Safety
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/utils/domain_resolver.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/utils/http_client.py`
- Line/Method: `_resolver_http_get` (84-115), shared session (13-41)
- Problem: Many daemon threads call shared session concurrently.
- Impact: Sporadic connection errors/non-deterministic behavior under load.
- Recommendation: Use per-thread session or synchronize access to shared session.

### F-013 - Heavy system introspection blocks startup path

- Severity: **minor**
- Category: Performance / Operability
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/infrastructure/system_info.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/lifespan.py`
- Line/Method: `log_full_system_report` (183-211 path usage) invoked during startup (111-124)
- Problem: Startup performs expensive package/environment introspection.
- Impact: Slower startup and extra startup fragility in constrained environments.
- Recommendation: Make full introspection optional or defer to background post-start task.

### F-014 - Critical runtime paths have low test coverage

- Severity: **major**
- Category: Test Coverage / Risk
- Directory/Files:
  - `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/torznab/api.py` (50%)
  - `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/qbittorrent/torrents.py` (48%)
  - `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/downloader/provider_resolution.py` (14%)
  - `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/scheduler.py` (49%)
  - `/Users/zacklack/Developer/Own/Repos/AniBridge/app/providers/megakino/client.py` (30%)
- Problem: Highest-complexity logic has weak test protection.
- Impact: Regressions likely in edge-case flows and refactors.
- Recommendation: Add targeted branch/edge-case tests for these exact modules before large refactors.

### F-015 - `torznab_api` orchestrator is a high-risk monolith

- Severity: **major**
- Category: Modularity / Maintainability
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/torznab/api.py`
- Line/Method: `torznab_api` (1427), `emit_tvsearch_episode_items` (705), `_handle_preview_search` (1059), `_handle_special_search` (1222)
- Problem: High cyclomatic complexity / branch count / statement count in central search flow.
- Impact: Hard to reason about correctness; bug fixes likely introduce regressions.
- Recommendation: Split into explicit sub-pipelines (validation, query planning, retrieval, filtering, rendering) with unit tests per stage.

### F-016 - Download pipeline functions are oversized and branch-heavy

- Severity: **minor**
- Category: Modularity / Maintainability
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/downloader/download.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/downloader/episode.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/downloader/ytdlp.py`
- Line/Method: `download_episode` (18), `build_episode` (14), `_ydl_download` (25)
- Problem: High complexity indicates too many responsibilities in single functions.
- Impact: Difficult targeted testing and future extension (new providers/languages/formats).
- Recommendation: Extract deterministic pure helpers (selection/validation/path prep/options assembly) from IO-heavy orchestration.

### F-017 - Lifespan startup/shutdown logic is over-consolidated

- Severity: **minor**
- Category: Architecture / Separation of Concerns
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/core/lifespan.py`
- Line/Method: `lifespan` (95), `_start_ttl_cleanup_thread` (42)
- Problem: Migration execution, cleanup scheduling, system reporting, and other boot responsibilities are tightly bundled.
- Impact: Startup regressions are harder to isolate and test.
- Recommendation: Split startup concerns into independent bootstrap units with explicit failure policy per unit.

### F-018 - Packaging metadata references a missing root README

- Severity: **major**
- Category: Packaging / Distribution Hygiene
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/pyproject.toml`
- Line/Method: `readme = "README.md"` (line 9)
- Problem: Root `README.md` does not exist, while packaging metadata expects it.
- Impact: `uv build` emits setuptools warnings; published package metadata quality degrades and onboarding references become inconsistent.
- Recommendation: Either add a real root `README.md` or point `readme` to an existing file (for example `.github/README.md`) and keep docs consistent.

### F-019 - Agent/docs maps are stale and reference incorrect paths

- Severity: **major**
- Category: Documentation Accuracy
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/docs/agents/repo-map.md`, `/Users/zacklack/Developer/Own/Repos/AniBridge/docs/agents/onboarding-collaboration.md`
- Line/Method: `repo-map.md` line 6 (`README.md`), line 58 (`app/core/downloader.py`); `onboarding-collaboration.md` line 5 (`README.md`)
- Problem: Documentation points to files/paths that do not exist in current repo layout.
- Impact: New maintainers and agents follow wrong locations and lose trust in project docs.
- Recommendation: Update docs to the current layout (`.github/README.md`, `app/core/downloader/*`) and add a doc-link validation check in CI.

### F-020 - Python runtime policy is inconsistent across repo

- Severity: **major**
- Category: Build/Runtime Policy
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/AGENTS.md`, `/Users/zacklack/Developer/Own/Repos/AniBridge/pyproject.toml`, `/Users/zacklack/Developer/Own/Repos/AniBridge/.github/workflows/tests.yml`, `/Users/zacklack/Developer/Own/Repos/AniBridge/.github/workflows/format-and-run.yml`, `/Users/zacklack/Developer/Own/Repos/AniBridge/scripts/startup-script.sh`
- Line/Method: AGENTS line 7 (3.12 baseline), pyproject line 13 (`>=3.11`), tests workflow line 31 (`3.11`), CQ workflow lines 36/106 (`3.12`), startup script lines 9/19/22 (`3.11+`)
- Problem: Repo documents and executes against mixed Python baselines.
- Impact: Version-specific bugs can slip through; contributors cannot tell the true support matrix.
- Recommendation: Define one explicit policy (`supported` vs `preferred`) and enforce with CI matrix and docs.

### F-021 - CI path filters are too narrow for production safety

- Severity: **major**
- Category: CI Reliability
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/.github/workflows/tests.yml`, `/Users/zacklack/Developer/Own/Repos/AniBridge/.github/workflows/format-and-run.yml`
- Line/Method: `tests.yml` lines 5-15; `format-and-run.yml` lines 5-13
- Problem: Tests/lint only trigger for a subset of paths; changes in runtime-relevant files (for example scripts/config/docs-generated API contracts) can skip validation.
- Impact: Behavioral regressions can merge without automated checks.
- Recommendation: Run tests/lint on all pull requests or broaden include-paths to all runtime and contract-relevant files.

### F-022 - Test suite structure is flat and partially migrated

- Severity: **minor**
- Category: Test Architecture
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/pytest.ini`, `/Users/zacklack/Developer/Own/Repos/AniBridge/tests/`
- Line/Method: `pytest.ini` line 3 (`testpaths = tests`), plus flat `tests/test_*.py` with empty tracked `tests/unit`
- Problem: Most tests are in one flat directory; `tests/unit/` exists but has no tracked tests.
- Impact: As suite grows, ownership and scope boundaries become harder to maintain.
- Recommendation: Split by test type and domain (for example `tests/unit`, `tests/integration`, `tests/api`) and migrate incrementally.

### F-023 - Script portfolio lacks explicit ownership and usage contracts

- Severity: **minor**
- Category: DevEx / Operational Maintainability
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/scripts/`
- Line/Method: mixed scripts under single folder (`startup-script.sh`, `setup-codex-overlay.sh`, `local_build_release.*`, `release/*`)
- Problem: Runtime bootstrap, release automation, and local AI tooling scripts are colocated without a scripts index/README.
- Impact: New maintainers cannot quickly tell what is production-critical vs developer-local tooling.
- Recommendation: Add `scripts/README.md` with purpose, prerequisites, and support level; group scripts by concern (`scripts/release`, `scripts/dev`, `scripts/bootstrap`).

### F-024 - `.gitignore` is overly broad and fragile

- Severity: **minor**
- Category: Repository Hygiene
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/.gitignore`
- Line/Method: broad patterns around lines 515 (`*.lock`), 531 (`.gitignore`), with later exceptions lines 534-535
- Problem: Large multi-ecosystem ignore list includes risky blanket patterns then compensates with negations.
- Impact: Easy to accidentally hide important files or confuse contributors about what is tracked.
- Recommendation: Reduce to project-specific ignores and move personal/global patterns to a global gitignore.

### F-025 - File-size governance is missing for long-lived maintainability

- Severity: **minor**
- Category: Architecture Governance
- File: `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/torznab/api.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/providers/aniworld/specials.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/utils/title_resolver.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/api/strm.py`, `/Users/zacklack/Developer/Own/Repos/AniBridge/app/db/models.py`
- Line/Method: module sizes ~1834, 881, 844, 781, 772 lines respectively
- Problem: There is no explicit module-size/complexity guardrail in repo standards.
- Impact: Growth drifts toward monolith modules that are expensive to review/refactor.
- Recommendation: Define soft size limits and a complexity budget in coding standards, then enforce with lint thresholds and review policy.

---

## Python File-Length Guidance (Practical Convention)

There is no strict Python language rule for maximum file length. In production teams, the practical convention is maintainability, not an absolute line cap.

- Common healthy target: ~150-350 lines per module.
- Acceptable when cohesive: up to ~500 lines.
- Refactor trigger: ~600+ lines or when complexity/branching becomes hard to reason about.
- Urgent decomposition: ~900+ lines (especially when mixed responsibilities are present).

For this repo, the concern is valid: the largest modules are beyond “normal cohesive” size and already correlate with complexity hotspots. In other words, your React intuition is directionally right for maintainability, even though Python teams are often a bit more tolerant of larger files than frontend component files.

Suggested policy to add into coding standards:

- New modules should target <= 400 lines.
- Existing modules > 600 lines should only grow when accompanied by extraction/refactor tickets.
- Any function crossing complexity budget (branching/statements) requires decomposition before feature growth.

## Hooks Directory Purpose (`hooks/`)

The `hooks/` directory is for PyInstaller runtime packaging hooks, not FastAPI runtime hooks.

- `/Users/zacklack/Developer/Own/Repos/AniBridge/hooks/hook-fake_useragent.py` collects `fake_useragent` data files so the packaged binary can resolve browser data at runtime.
- It is consumed by release/build scripts via `pyinstaller --additional-hooks-dir hooks ...` in `/Users/zacklack/Developer/Own/Repos/AniBridge/scripts/local_build_release.sh` and `/Users/zacklack/Developer/Own/Repos/AniBridge/scripts/local_build_release.ps1`.
- It is also referenced in release docs at `/Users/zacklack/Developer/Own/Repos/AniBridge/docs/agents/release-ci.md`.

## Automated Evidence Used

- `uv run ruff check app` -> clean for configured rules.
- `uv run pytest -q` -> tests pass, but coverage report shows risk hotspots (overall 57%).
- `uv run ruff check app --select C90,PLR0912,PLR0915,PLR0911` -> highlights complexity hotspots used in F-015 to F-017.
- `uv build` -> succeeds but warns that `/Users/zacklack/Developer/Own/Repos/AniBridge/README.md` is missing.
- Repository metadata/docs/workflow scan -> used for F-018 to F-025.

## Suggested Remediation Order

1. F-001 (auth bypass)
2. F-018 + F-019 + F-020 (metadata/docs/runtime-policy consistency)
3. F-009 + F-010 (startup safety: migrations/env parsing)
4. F-002 + F-003 (API contract correctness)
5. F-006 + F-007 + F-008 + F-005 (resolver/provider correctness)
6. F-021 + F-022 (CI/test-structure hardening)
7. F-011 + F-012 (concurrency hardening)
8. F-014 + F-015 + F-016 + F-017 + F-025 (testability/modularization governance)
