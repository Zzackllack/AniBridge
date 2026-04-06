# Implementation Plan: Absolute Numbering Support for Sonarr Anime Requests

**Branch**: `001-absolute-episode-numbers` | **Date**: 2025-10-08 | **Spec**: [Absolute Numbering Support for Sonarr Anime Requests](spec.md)
**Input**: Feature specification from `/specs/001-absolute-episode-numbers/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Deliver absolute-numbering awareness across AniBridge so that Sonarr/Prowlarr requests using anime absolute indices are translated to AniWorld’s season/episode format for lookups, while responses and download metadata preserve the client’s numbering expectations. Implement detection based on numeric-only identifiers, exclude specials from conversions, add a controlled fallback that can return the full catalogue, persist mappings in SQLite, and update FastAPI endpoints plus VitePress docs to describe the new behaviour and configuration toggles.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, SQLModel, Loguru, AniWorld client library, yt-dlp  
**Storage**: SQLite (via SQLModel)  
**Testing**: pytest with existing API and integration suites  
**Target Platform**: Linux containers and bare-metal hosts running AniBridge services  
**Project Type**: Backend service with FastAPI-based HTTP APIs  
**Performance Goals**: Maintain <200 ms p95 for `/torznab/api` and qBittorrent endpoints; preview/fallback responses complete in ≤5 s as per spec  
**Constraints**: Honour existing concurrency limits, ensure background conversions stay off the event loop, keep configuration through `app.config`, and guard fallback behind an environment toggle defaulting to disabled  
**Scale/Scope**: Supports medium Sonarr/Prowlarr deployments managing hundreds of anime episodes per series with mappings persisted per title

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Code Quality Stewardship**: Plan maintains module boundaries by extending episode-mapping logic within `app/utils`/`app/core` and exposing behaviour through `app/api`; all new Python will include type hints and docstrings; configuration flows through `app.config` with an environment toggle. ✅
- **Test-Centric Reliability**: We will author failing pytest coverage (Torznab search, qBittorrent sync, conversion utilities) before implementation and expand fixtures as needed. ✅
- **User Experience Consistency**: HTTP responses remain Sonarr/qBittorrent compatible; new fallback toggle and behaviour will be documented in VitePress and README snippets; error messages remain actionable. ✅
- **Performance & Resilience Discipline**: Conversion runs off the main event loop, mappings cached in SQLModel, and response targets (<200 ms p95, ≤5 s preview) stay within guardrails. ✅
- **Operational Constraints**: No new dependencies; persisted data remains in SQLite under `data/`; environment-driven configuration preserved. ✅

All gates satisfied—Phase 0 research may proceed.

**Post-Phase 1 review**: Design artifacts (research, data model, contracts, quickstart, agent context) maintain module boundaries, enforce test-first requirements, and document user-facing changes; no constitutional risks identified.

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
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
app/
├── api/
├── core/
├── db/
├── utils/
└── config.py

docs/
└── src/
    ├── guide/
    └── api/

tests/
├── api/
├── integration/
└── unit/
```

**Structure Decision**: Extend existing FastAPI backend (`app/`) with new utilities, persistence helpers, and API adjustments; update complementary pytest suites under `tests/` and refresh VitePress documentation in `docs/src`.

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |

No constitutional violations anticipated at this stage.
