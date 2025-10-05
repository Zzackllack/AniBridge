<!--
Sync Impact Report
Version change: 1.0.0 → 2.0.0
Modified principles:
- Service Contract Fidelity → User Experience Consistency
- Agent-Oriented Code Quality → Code Quality Stewardship
- Test-Driven Assurance → Test-Centric Reliability
- Operational Observability → Performance & Resilience Discipline
Removed sections:
- Controlled Automation & Compliance (guidance consolidated under Operational Constraints)
Added sections:
- none
Removed sections:
- none
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
Follow-up TODOs:
- none
-->
# AniBridge Constitution

## Core Principles

### Code Quality Stewardship

- Production Python code MUST target 3.12, include explicit type hints, and carry intent-revealing docstrings so contributors and agents can safely reason about scheduler, downloader, and API flows.
- Module boundaries in `app/` MUST stay cohesive: shared behavior lives in `app/utils` or `app/config`, API contracts stay under `app/api`, and background orchestration remains in `app/core`—duplicate logic or unchecked side effects are unconstitutional.
- Configuration, filesystem paths, and secrets MUST pass through `app.config` and environment variables; hard-coded values, inline credentials, or silent mutations of `data/` assets are prohibited.
Rationale: High-quality, structured code keeps the service maintainable and predictable for both human reviewers and automation.

### Test-Centric Reliability

- Every behavioral change MUST begin with failing `pytest` coverage—contract, unit, or integration—before implementation; skipping red tests or retrofitting coverage after the fact is disallowed.
- API and scheduler contracts MUST be guarded by deterministic tests under `tests/api/` and `tests/integration/`, including qBittorrent shims, Torznab feeds, downloader lifecycles, and `/health` readiness.
- Regression fixes MUST document the root cause in tests or commit notes and keep fixtures (e.g., AniWorld snapshots, download payloads) up to date for repeatable automation.
Rationale: Tests are the enforcement layer that protects downstream automation from regressions.

### User Experience Consistency

- HTTP responses, status codes, and payload shapes MUST remain compatible with Sonarr, Prowlarr, and qBittorrent expectations; any deviation ships with updated FastAPI schemas, client guidance, and release notes.
- User-facing assets—`README.md`, VitePress docs, CLI output, and health reporting—MUST be updated in the same change that alters behavior or configuration so operators never guess the new workflow.
- Error messaging and logging MUST stay in English, be actionable, and avoid leaking secrets, enabling consistent troubleshooting across environments.
Rationale: A stable, well-documented interface keeps automation chains and human operators aligned.

### Performance & Resilience Discipline

- Scheduler and downloader code MUST honor configurable concurrency limits, avoid blocking the FastAPI event loop, and prove long-running work executes in background threads with progress persisted to SQLModel tables.
- `/health`, `/torznab/api`, and qBittorrent endpoints MUST maintain sub-200 ms p95 responses under nominal load; performance-sensitive changes require profiling evidence or load-test notes in the PR.
- Logging via Loguru MUST remain structured (job ids, provider metadata, durations) and exception-safe, ensuring recovery data exists after failures or provider changes.
Rationale: Performance guardrails keep AniBridge responsive while protecting reliability during heavy download windows.

## Operational Constraints

- Runtime baseline is Python 3.12 with FastAPI, SQLModel, Loguru, and yt-dlp; adding or upgrading dependencies demands design review, compatibility testing, and updated deployment notes.
- Persistent artifacts live under `data/`; schema or storage migrations MUST preserve forward compatibility and document rebuild or cleanup steps when unavoidable.
- Proxy, scheduler, and download configuration MUST remain environment-driven; defaults favor safe execution with opt-in flags for experimental behavior.
- Legal and compliance requirements from `LEGAL.md` remain binding: escalations involving proxies, scraping, or geo-routing MUST include risk commentary and secure secret handling.

## Workflow & Review Gates

1. Every feature begins with `/plan` and `/tasks`; Constitution checks MUST pass before implementation proceeds.
2. Pull requests MUST demonstrate passing tests, formatting, and updated documentation/releases for any user-facing or configuration change.
3. Release notes MUST summarize contract impacts, performance considerations, and migration actions required for operators.
4. Contributors MUST translate non-English comments before merge, remove dead code, and ensure codeowners/maintainers can trace decisions to specs or tests.

## Governance

- Amendments require an RFC or issue documenting rationale, downstream impacts, and updates to dependent templates before merge.
- Constitution versioning follows SemVer: MAJOR for incompatible governance or principle overhauls, MINOR for new principles/sections, PATCH for clarifications.
- Compliance reviews (at least quarterly or before major releases) MUST confirm templates, specs, and runtime guidance reflect this constitution and the legal posture.
- Ratified amendments MUST update this file, the Sync Impact Report, and notify maintainers via release notes or changelog entries.

**Version**: 2.0.0 | **Ratified**: 2025-09-21 | **Last Amended**: 2025-10-05
