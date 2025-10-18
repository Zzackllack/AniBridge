# Implementation Plan: Dual Catalogue s.to Support

**Branch**: `003-add-sto-support` | **Date**: 2025-10-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-add-sto-support/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Integrate the s.to catalogue alongside AniWorld so AniBridge can answer searches and downloads from both sources. Deliver parallel fan-out queries across enabled catalogues, tag every job with its originating site, surface both sources in merged results, and maintain per-site availability caches while keeping the existing FastAPI/Python/SQLite stack unchanged.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, SQLModel, Loguru, yt-dlp, aniworld-downloader (AniWorld/s.to library)  
**Storage**: SQLite (file-backed via SQLModel)  
**Testing**: pytest with existing unit, integration, and API suites  
**Target Platform**: Linux containers (Docker) and bare-metal Python services  
**Project Type**: Backend service (FastAPI application with background schedulers)  
**Performance Goals**: Maintain <200 ms p95 for Torznab/qBittorrent endpoints; keep merged catalogue responses under 5 s end-to-end as per spec SC-001  
**Constraints**: Preserve current tech stack (FastAPI/Python/SQLite); all configuration via `app.config`; honour concurrency limits without blocking event loop  
**Scale/Scope**: Serves Sonarr/Prowlarr/qBittorrent clients for dual catalogues; expected catalogue size in tens of thousands of titles with concurrent download jobs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Code Quality Stewardship**: Plan maintains Python 3.12 targets, keeps logic within existing module boundaries (`app/api`, `app/core`, `app/utils`, `app/db`), and routes new configuration through `app.config`. ✅
- **Test-Centric Reliability**: Will add/extend pytest suites covering dual catalogue search, download, cache segregation, and metadata exposure before implementation. ✅
- **User Experience Consistency**: Torznab/qBittorrent payload shapes remain compliant; documentation updates scoped into deliverables. ✅
- **Performance & Resilience Discipline**: Parallel queries implemented with non-blocking patterns respecting scheduler limits; maintain <200 ms p95 and document performance expectations. ✅
- **Operational Constraints**: Retain FastAPI/Python/SQLite stack, add libraries only as required with notes; configuration remains environment-driven. ✅

Gate status: ✅ Proceed to Phase 0.

**Post-Phase 1 Re-check**: Proposed design artifacts keep module boundaries intact, mandate new tests, preserve contract compatibility, and document operational changes. Constitution alignment remains ✅.

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```
app/
├── api/
│   ├── torznab/
│   └── qbittorrent/
├── core/
├── db/
├── domain/
├── infrastructure/
└── utils/

tests/
├── api/
├── integration/
└── unit/

docs/
└── src/
    ├── guide/
    ├── api/
    └── integrations/
```

**Structure Decision**: Extend existing FastAPI backend (`app/`) and pytest suites (`tests/`) while updating documentation under `docs/src`; no new top-level projects introduced.

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _None_ |  |  |
