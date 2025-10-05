# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)

```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions

- Application modules live in `app/` (e.g., `torznab.py`, `qbittorrent.py`, `downloader.py`, `scheduler.py`).
- Tests reside in `tests/` (`api/`, `integration/`, `regression/`) and MUST mirror the contracts they protect.
- Persistent data and runtime artifacts live under `data/`; tasks NEVER mutate committed artifacts there.
- Documentation and specs live in `.specify/`, `README.md`, `AGENTS.md`, and related docs.

## Phase 3.1: Setup

- [ ] T001 Verify environment prerequisites and update `requirements.txt`, Docker files, or scripts per plan decisions.
- [ ] T002 Document new configuration flags in `app/config.py` and `README.md` with safe defaults.
- [ ] T003 [P] Capture deterministic fixtures (e.g., AniWorld responses, qBittorrent payloads) in `tests/fixtures/` for contract tests.

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

- [ ] T004 [P] Contract test `/torznab/api` caps response in `tests/api/test_torznab_caps.py`
- [ ] T005 [P] Contract test `/api/v2/auth/login` flow in `tests/api/test_qbittorrent_auth.py`
- [ ] T006 [P] Integration test downloader job lifecycle in `tests/integration/test_downloader_flow.py`
- [ ] T007 [P] Health endpoint regression test reflecting scheduler/storage readiness in `tests/integration/test_health.py`

## Phase 3.3: Core Implementation (ONLY after tests are failing)

- [ ] T008 [P] Extend Torznab feed logic per spec in `app/torznab.py`
- [ ] T009 [P] Update qBittorrent session handling in `app/qbittorrent.py`
- [ ] T010 [P] Implement downloader orchestration changes in `app/downloader.py`
- [ ] T011 Persist progress telemetry and invariants in `app/models.py`
- [ ] T012 Wire configuration toggles and validation in `app/config.py`

## Phase 3.4: Integration & Resilience

- [ ] T013 Align scheduler logging and metrics with structured fields in `app/scheduler.py`
- [ ] T014 Update `/health` and associated routing in `app/main.py`
- [ ] T015 Validate migrations/data persistence steps and document recovery guidance
- [ ] T016 [P] Ensure sensitive data is redacted in logs and tests per compliance requirements

## Phase 3.5: Compliance & Polish

- [ ] T017 [P] Refresh README, AGENTS.md, and release notes with contract changes and migration steps
- [ ] T018 Record legal/compliance considerations in `LEGAL.md` or release notes
- [ ] T019 [P] Run full `pytest` suite and capture artifacts for PR validation
- [ ] T020 Remove dead code, translate lingering non-English comments, and run `black`

## Dependencies

- Tests (T004–T007) MUST precede implementation (T008–T012)
- T008/T009/T010 feed into observability tasks (T013–T016)
- Documentation and compliance polish (T017–T020) close out after implementation passes

## Parallel Example

```
# Launch T004–T007 together:
Task: "Contract test /torznab/api caps response in tests/api/test_torznab_caps.py"
Task: "Contract test /api/v2/auth/login in tests/api/test_qbittorrent_auth.py"
Task: "Integration test downloader job lifecycle in tests/integration/test_downloader_flow.py"
Task: "Health endpoint regression test in tests/integration/test_health.py"
```

## Notes

- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Document secrets handling and risk notes alongside code changes
- Commit after each task; avoid concurrent edits to the same file

## Task Generation Rules

*Applied during main() execution*

1. **From Contracts**:
   - Each FastAPI contract → contract test task [P] before implementation
   - Each endpoint/service change → corresponding implementation task with file path

2. **From Data Model & Scheduler**:
   - Entities/tables → model or migration task [P]
   - Scheduler/job orchestration updates → performance, resilience, and logging tasks

3. **From User Stories & Compliance Notes**:
   - User flows → integration tests and documentation tasks
   - Legal or configuration requirements → compliance/documentation tasks

4. **Ordering**:
   - Setup → Tests → Core implementation → Observability/Integration → Compliance & Polish
   - Dependencies block parallel execution; never parallelize edits on the same module

## Validation Checklist

*GATE: Checked by main() before returning*

- [ ] All contracts have corresponding failing tests before implementation tasks
- [ ] Scheduler, performance/resilience, logging, and compliance tasks exist for relevant changes
- [ ] All tests precede implementation tasks in ordering
- [ ] Parallel tasks operate on distinct files
- [ ] Each task specifies exact file paths or docs impacted
- [ ] Sensitive data handling and documentation updates are represented when required
