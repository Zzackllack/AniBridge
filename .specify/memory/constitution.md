<!--
Sync Impact Report
Version change: none → 1.0.0
Modified principles:
- N/A → Service Contract Fidelity
- N/A → Agent-Oriented Code Quality
- N/A → Test-Driven Assurance
- N/A → Operational Observability
- N/A → Controlled Automation & Compliance
Added sections:
- none (populated existing template placeholders)
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

### Service Contract Fidelity
- AniBridge MUST preserve compatibility for Torznab, qBittorrent, downloader, and health endpoints; any contract change ships with updated FastAPI schemas, automated tests, and migration notes before merge.
- Breaking changes MUST provide downstream guidance for Sonarr, Prowlarr, and other clients in README or release notes, including configuration updates when required.
- Every new or modified endpoint MUST declare explicit request/response models, status codes, and error envelopes to keep integrations predictable.
Rationale: Downstream automation depends on stable contracts; regressions translate directly into failed downloads and scheduler stalls.

### Agent-Oriented Code Quality
- Production code MUST include Python 3.12 type hints, English docstrings, and concise comments that explain intent for both humans and AI agents.
- Modules within `app/` MUST remain single-responsibility; reuse shared helpers (naming, magnet, scheduler) instead of duplicating logic.
- Configuration, secrets, and file-system paths MUST flow through `app.config` or environment variables—never hard-coded.
Rationale: Consistent structure and clear guidance let contributors and automation agents act safely without rediscovering context each time.

### Test-Driven Assurance
- All behavioral changes MUST begin with failing `pytest` coverage (unit, integration, or contract) that captures the expected outcome before implementation.
- CI and local workflows MUST run `pytest` and `black` with no failures before code review; skip-failing tests are prohibited except under documented hotfix procedures.
- Bug fixes MUST add regression tests alongside documentation of root cause to stop repeating incidents.
Rationale: Tests are the enforcement arm of the constitution—without them automation cannot guarantee reliability.

### Operational Observability
- Logging MUST use `loguru` with structured fields for job ids, titles, and provider metadata; silent failures are unconstitutional.
- The `/health` endpoint MUST reflect downloader, scheduler, and storage readiness; regressions require immediate test coverage.
- Background jobs MUST emit progress events and persist status to SQLModel tables so operators can audit and recover work.
Rationale: Observability keeps automated operations debuggable and auditable, enabling fast recovery when providers change behavior.

### Controlled Automation & Compliance
- Features MUST respect the Legal Disclaimer; document any geo-routing, proxy, or scraping changes alongside risk notes before release.
- Experimental capabilities (e.g., proxy toggles) MUST remain opt-in with defaults that favor safe execution and clear warnings in docs.
- Sensitive identifiers (accounts, cookies, tokens) MUST enter via runtime configuration and stay out of logs, repos, and default data files.
Rationale: Responsible automation protects contributors and users from legal, security, and reputational fallout.

## Operational Constraints

- Runtime baseline is Python 3.12 with FastAPI, SQLModel, Loguru, and yt-dlp; adding or upgrading dependencies requires design review and compatibility testing.
- Persistent artifacts live under `data/`; migrations MUST preserve forward compatibility and document rebuild steps when unavoidable.
- Scheduler concurrency, download directories, and proxy behavior MUST remain configurable via environment variables or `config.py`—never hard-coded.
- Docker images MUST run as non-root, expose `/health`, and document required volumes for persistence.

## Workflow & Review Gates

1. Every feature begins with `/plan` and `/tasks` outputs; constitution checks MUST pass before implementation proceeds.
2. Pull requests MUST show passing tests, formatting, and updated documentation (README, AGENTS.md, or specs) for any user-visible change.
3. Release notes MUST summarize contract changes, migrations, and observability impacts for operators.
4. Contributors MUST translate non-English comments before merge and remove dead code discovered during review.

## Governance

- Amendments require an RFC or issue describing the rationale, evidence of downstream impact, and updates to dependent templates before merge.
- Constitution versioning follows SemVer: MAJOR for incompatible governance changes, MINOR for new principles or sections, PATCH for clarifications.
- A compliance review (at least once per quarter or before major releases) MUST confirm templates, specs, and runtime guidance reflect the current constitution.
- Ratified amendments MUST update this file, the Sync Impact Report, and notify maintainers via release notes or changelog entry.

**Version**: 1.0.0 | **Ratified**: 2025-09-21 | **Last Amended**: 2025-09-21
