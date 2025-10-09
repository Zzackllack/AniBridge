# Tasks: Absolute Numbering Support for Sonarr Anime Requests

**Input**: Design documents from `/specs/001-absolute-episode-numbers/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Validate current baseline before introducing changes.

- [ ] T001 [Setup] Run `pytest` to capture the current passing baseline before feature work.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story work begins.**

- [ ] T002 [Foundation] Add failing coverage in `tests/test_models.py` for the forthcoming `EpisodeNumberMapping` SQLModel (creation, unique constraints, timestamp defaults).
- [ ] T003 [Foundation] Implement the `EpisodeNumberMapping` table and helper CRUD utilities in `app/db/models.py` per data-model.md (ensure uniqueness and timestamp handling).
- [ ] T004 [Foundation] Extend database bootstrap flows (`app/db/models.py:create_db_and_tables`, any startup hooks) so the new mapping table is included in initialization and cleanup routines.
- [ ] T005 [Foundation] Introduce `ANIBRIDGE_FALLBACK_ALL_EPISODES` configuration in `app/config.py` with default `False`, typed accessors, and inline documentation.

**Checkpoint**: Episode mapping persistence and configuration toggle are available—user stories may now proceed.

---

## Phase 3: User Story 1 – Sonarr absolute search matches anime catalog (Priority: P1) 🎯 MVP

**Goal**: Detect absolute-numbered search requests, map them to season/episode pairs, and honour fallback behaviour.  
**Independent Test**: Issue a Torznab search for absolute episode “003” and confirm AniBridge returns the matching SxxEyy and logs fallback decisions correctly.

### Tests (write first, ensure they FAIL)

- [ ] T006 [P] [US1] Create `tests/test_absolute_numbering.py` covering detection of absolute identifiers, mapping lookups, and exclusion of specials.
- [ ] T007 [P] [US1] Add Torznab integration test `tests/test_torznab_absolute.py` validating search results, logging, and fallback toggle handling.

### Implementation

- [ ] T008 [US1] Implement absolute-number parsing and mapping helpers in `app/utils/absolute_numbering.py`, including detection heuristics and database integration.
- [ ] T009 [US1] Update Torznab request pipeline (`app/api/torznab/api.py` and supporting utilities) to invoke the conversion helper before AniWorld queries and to enrich responses with absolute metadata.
- [ ] T010 [US1] Wire fallback behaviour and logging: honour `ANIBRIDGE_FALLBACK_ALL_EPISODES`, surface “cannot map episode” errors, and optionally return the full catalogue in standard numbering.
- [ ] T011 [US1] Ensure AniWorld catalogue fetch routines (e.g., `app/utils/title_resolver.py` or equivalent) populate or refresh `EpisodeNumberMapping` entries when new data is observed.

**Checkpoint**: Torznab absolute searches succeed and existing SxxEyy behaviour remains unaffected.

---

## Phase 4: User Story 2 – Download metadata honours absolute numbering (Priority: P2)

**Goal**: Preserve absolute identifiers through job scheduling, qBittorrent sync, and naming flows.  
**Independent Test**: Grab an absolute-numbered episode and verify job status, torrent info, and final naming all reference the original absolute index.

### Tests (write first, ensure they FAIL)

- [ ] T012 [P] [US2] Add `tests/test_qbittorrent_absolute.py` to assert `/api/v2/sync/maindata` and `/api/v2/torrents/info` expose `anibridgeAbsolute` metadata.
- [ ] T013 [P] [US2] Extend downloader progress tests (e.g., `tests/test_qbittorrent_more.py` or new cases) to expect absolute-aware naming when the request originated in absolute mode.

### Implementation

- [ ] T014 [US2] Persist the originating absolute number on jobs/client tasks by extending `ClientTask` (and any related records) plus scheduler wiring in `app/core/scheduler.py`.
- [ ] T015 [US2] Update qBittorrent shim endpoints (`app/api/qbittorrent/sync.py`, `app/api/qbittorrent/torrents.py`) to surface absolute metadata and maintain compatibility with existing fields.
- [ ] T016 [US2] Adjust naming/downloader utilities (`app/utils/naming.py`, `app/core/downloader.py`) so completed files and progress updates reflect absolute numbering when applicable.

**Checkpoint**: Sonarr imports absolute-downloads seamlessly with consistent identifiers across lifecycle updates.

---

## Phase 5: User Story 3 – Indexer browsing tools respect numbering preference (Priority: P3)

**Goal**: Manual searches and previews display absolute identifiers alongside titles.  
**Independent Test**: Use Sonarr/Prowlarr preview tools in absolute mode and confirm returned rows show the requested absolute number.

### Tests (write first, ensure they FAIL)

- [ ] T017 [P] [US3] Add `tests/test_preview_absolute.py` covering manual search and capability previews for absolute-numbered series.

### Implementation

- [ ] T018 [US3] Update Torznab preview/caps responses (`app/api/torznab/api.py`, helpers) to include absolute identifiers in result metadata.
- [ ] T019 [US3] Ensure any shared rendering utilities (e.g., `app/api/torznab/utils.py`) format preview rows with absolute labels while leaving standard mode unchanged.

**Checkpoint**: Preview tooling reliably reflects absolute numbering preferences.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize documentation, validation, and release-ready artifacts.

- [ ] T020 [P] Update VitePress docs (`docs/src/guide/configuration.md`, `docs/src/api/torznab.md`, related sections) to describe absolute numbering support, fallback toggle, and limitations.
- [ ] T021 Run the full `pytest` suite to confirm all new tests pass and regressions are avoided.
- [ ] T022 Capture release notes/README updates summarizing the feature and configuration changes.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → **User Story Phases (3–5)** → **Polish (Phase 6)**
- User stories must be completed in priority order (US1 → US2 → US3) to maintain MVP sequencing.
- Within each user story, write failing tests before implementation tasks.
- Tasks touching identical files must be executed sequentially as listed; tasks marked [P] operate on separate files and may run in parallel.

### Story Dependency Graph

```
Foundational
   ↓
User Story 1 (P1)
   ↓
User Story 2 (P2)
   ↓
User Story 3 (P3)
   ↓
Polish
```

### Parallel Opportunities

- T006 and T007 can execute in parallel (distinct test files).
- T012 and T013 can execute in parallel (separate test modules).
- T017 runs independently once prior phases complete.
- Documentation (T020) can begin after US3 if implementation teams are split.

---

## Implementation Strategy

1. Complete Setup and Foundational phases to establish persistence and configuration.
2. Deliver User Story 1 as the MVP—ensuring Torznab absolute searches work end-to-end before proceeding.
3. Layer User Story 2 to extend absolute awareness through the download lifecycle and shim responses.
4. Finish User Story 3 to polish preview experiences.
5. Close with documentation, test verification, and release notes.
