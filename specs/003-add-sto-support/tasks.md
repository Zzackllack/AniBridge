# Tasks: Dual Catalogue s.to Support

**Input**: Design documents from `/specs/003-add-sto-support/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test updates included where functional requirements introduce new behaviour.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare configuration scaffolding and tooling needed by all stories.

- [ ] T001 Document catalogue configuration variables in `docs/src/guide/configuration.md`
- [ ] T002 Update `.env.example` and configuration reference in `docs/src/api/environment.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core groundwork required before implementing user stories.

- [ ] T003 Expand site configuration schema in `app/config.py` (catalogue toggles, priorities, base URLs, languages)
- [ ] T004 [P] Add per-site configuration defaults and validation tests in `tests/unit/test_config.py`
- [ ] T005 [P] Introduce `site_id` enums/constants in `app/domain/models.py` and `app/utils/naming.py`
- [ ] T006 Create SQLModel migration script adding `source_site` field to job and availability tables under `scripts/migrations/`
- [ ] T007 [P] Extend SQLModel definitions in `app/db/models.py` for `source_site` and site-aware helpers
- [ ] T008 [P] Add migration/backfill tests covering legacy data handling in `tests/unit/test_models.py`
- [ ] T009 Update scheduler bootstrap in `app/core/bootstrap.py` (or related) to load enabled catalogues list from config
- [ ] T010 [P] Refresh developer quickstart noting migration steps in `specs/003-add-sto-support/quickstart.md`

**Checkpoint**: Configuration, models, and migrations support dual catalogues.

---

## Phase 3: User Story 1 - Sonarr finds s.to shows (Priority: P1) 🎯 MVP

**Goal**: Ensure AniBridge can search, merge, and download shows unique to s.to while querying catalogues in parallel.

**Independent Test**: Run Torznab search for s.to-only title and complete download via scheduler; verify results include s.to entries with correct site metadata.

### Tests for User Story 1

- [ ] T011 [P] [US1] Add Torznab contract test covering dual-site response in `tests/api/test_torznab.py`
- [ ] T012 [P] [US1] Add downloader integration test for `Episode(site="s.to")` in `tests/integration/test_downloader.py`
- [ ] T013 [P] [US1] Add scheduler test to ensure jobs retain `source_site` in `tests/integration/test_scheduler.py`

### Implementation for User Story 1

- [ ] T014 [P] [US1] Implement parallel catalogue query orchestration in `app/api/torznab/api.py`
- [ ] T015 [P] [US1] Update title resolver to maintain per-site indices in `app/utils/title_resolver.py`
- [ ] T016 [P] [US1] Implement per-site availability cache separation in `app/db/models.py` and `app/utils/cache` (if present)
- [ ] T017 [US1] Modify downloader pipeline to instantiate episodes with site hints in `app/core/downloader.py`
- [ ] T018 [US1] Ensure scheduler submits jobs with site metadata in `app/core/scheduler.py`
- [ ] T019 [US1] Update magnet builder and naming utilities to embed `site` parameter in `app/utils/magnet.py` and `app/utils/naming.py`
- [ ] T020 [US1] Add Torznab XML serializer changes for `<anibridge:sourceSite>` in `app/api/torznab/utils.py`
- [ ] T021 [US1] Implement fallback/timeout handling for parallel catalogue fetches in `app/api/torznab/api.py`
- [ ] T022 [US1] Update logs to include `source_site` for downloads in `app/utils/logger.py` or relevant module
- [ ] T023 [US1] Refresh docs `docs/src/api/torznab.md` describing dual-catalogue search behaviour

**Checkpoint**: Torznab and downloader flows operate with dual catalogues; MVP achievable.

---

## Phase 4: User Story 2 - Unified job tracking (Priority: P2)

**Goal**: Persist and expose source site information across job history, availability records, and API responses.

**Independent Test**: Trigger downloads from both catalogues, check qBittorrent sync, job history, and availability endpoints for correct site attribution.

### Tests for User Story 2

- [ ] T024 [P] [US2] Extend qBittorrent sync API test to assert `anibridge_source_site` field in `tests/api/test_qbittorrent_sync.py`
- [ ] T025 [P] [US2] Add unit test for availability cache ensuring site isolation in `tests/unit/test_availability.py`
- [ ] T026 [P] [US2] Add regression test verifying legacy job records default to `aniworld` in `tests/unit/test_models.py`

### Implementation for User Story 2

- [ ] T027 [P] [US2] Surface `source_site` in qBittorrent sync responses in `app/api/qbittorrent/sync.py`
- [ ] T028 [P] [US2] Update job serialization endpoints (if any) in `app/api` to include site metadata
- [ ] T029 [US2] Ensure availability API/helpers expose site field in `app/api/availability` or `app/db/models.py`
- [ ] T030 [US2] Update magnet payload JSON to include site identifier in `app/utils/magnet.py`
- [ ] T031 [US2] Adjust logging/audit outputs to show `source_site` in `app/infrastructure/terminal_logger.py` or relevant
- [ ] T032 [US2] Document job tracking updates in `docs/src/api/qbittorrent-shim.md`

**Checkpoint**: All job and availability surfaces clearly report origin site.

---

## Phase 5: User Story 3 - Catalogue control (Priority: P3)

**Goal**: Provide operators with configuration and health visibility to enable/disable/reorder catalogues without code changes.

**Independent Test**: Toggle catalogue configuration and verify health, search, and logs reflect the change immediately after restart.

### Tests for User Story 3

- [ ] T033 [P] [US3] Add configuration toggle test ensuring disabled site skipped in `tests/unit/test_config.py`
- [ ] T034 [P] [US3] Add health endpoint test verifying enabled catalogues list in `tests/api/test_health.py`

### Implementation for User Story 3

- [ ] T035 [P] [US3] Implement configuration parsing for priority order in `app/config.py`
- [ ] T036 [P] [US3] Update health check payload to list enabled catalogues in `app/api/health.py`
- [ ] T037 [US3] Ensure Torznab and scheduler honour disabled sites (skip fetch/queue) in `app/api/torznab/api.py` and `app/core/scheduler.py`
- [ ] T038 [US3] Update docs `docs/src/guide/running.md` with catalogue toggle instructions
- [ ] T039 [US3] Add environment variable reference for catalogue control to `docs/src/api/environment.md`

**Checkpoint**: Operators can manage catalogues via configuration; health/logs reflect state.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final refinements across stories.

- [ ] T040 [P] Add changelog entry summarizing dual catalogue support in `CHANGELOG.md`
- [ ] T041 [P] Review and update sample configs or compose files in `docker-compose.yaml` and `docker-compose.dev.yaml`
- [ ] T042 Execute quickstart validation steps described in `specs/003-add-sto-support/quickstart.md`
- [ ] T043 [P] Run full pytest suite and address any regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → prerequisite for configuration awareness.
- **Foundational (Phase 2)** → must finish before any user story begins (models, config, migration).
- **User Story 1 (Phase 3)** → highest priority; depends on Foundational.
- **User Story 2 (Phase 4)** → depends on Foundational and benefits from US1 data structures but remains independently testable.
- **User Story 3 (Phase 5)** → depends on Foundational; can start after US1 groundwork but ideally after US2 to reuse exposed metadata.
- **Polish (Phase 6)** → final cleanup after stories complete.

### User Story Dependency Graph

- US1 → provides core dual-catalogue capabilities (MVP).
- US2 → builds on US1 job metadata but can mock US1 outputs if necessary.
- US3 → relies on configuration foundation; can proceed once config toggles from Phase 2 are ready.
- Execution Order: US1 → US2 → US3 (sequential for MVP), with option for US2 and US3 to run parallel after US1 if team capacity allows.

### Parallel Execution Examples

- During Phase 2: T004, T005, T007, T008, T010 can proceed in parallel.
- Within US1: T014–T020 operate on different modules and can be parallelized after orchestration plan is agreed.
- US2 tests (T024–T026) can be written concurrently; likewise documentation tasks across phases.

---

## Implementation Strategy

### MVP First
1. Complete Phases 1–2 to establish configuration and persistence foundations.
2. Deliver Phase 3 (US1) to unlock s.to searches and downloads — constitutes MVP.
3. Validate using independent test criteria before progressing.

### Incremental Delivery
- After MVP, implement Phase 4 for full tracking transparency.
- Follow with Phase 5 to empower operators with control toggles.
- Finish with Phase 6 polish to ensure documentation and deployment assets are aligned.
