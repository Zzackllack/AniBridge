# Feature Specification: Dual Catalogue s.to Support

**Feature Branch**: `003-add-sto-support`  
**Created**: 2025-10-18  
**Status**: Draft  
**Input**: User description: "I want to integrate the platform s.to into the AniBridge app/project; the underlying library aniworld-downloader already has support for the platform s.to, so we need to update everything accordingly. You can look at the library implementation under .venv/lib/python3.13/site-packages/aniworld. In the file data/githubissue.md you will find a GitHub issue regarding this topic."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sonarr finds s.to shows (Priority: P1)

Operators using Sonarr/Prowlarr route a search or download request for a series that only exists on s.to and expect AniBridge to locate, present, and trigger downloads without manual intervention.

**Why this priority**: Without this capability the integration delivers no new value; s.to catalogues remain unreachable and automation workflows fail.

**Independent Test**: Submit a Sonarr-style search against AniBridge for a title known to exist on s.to, verify search results enumerate the correct episodes, and confirm a download request succeeds end to end.

**Acceptance Scenarios**:

1. **Given** a configured AniBridge instance with s.to enabled, **When** a client searches for a show that exists only on s.to, **Then** the response includes matching releases sourced from s.to with correct season and episode metadata.
2. **Given** a search result selected from s.to, **When** the client requests the download, **Then** the resulting job completes using s.to links and reports success through the usual status endpoints.

---

### User Story 2 - Unified job tracking (Priority: P2)

Operations staff need every job, magnet, and availability record to disclose which catalogue supplied it so downstream monitoring, storage policies, and troubleshooting remain accurate.

**Why this priority**: Without site attribution, mixed catalogues cause mislabelled downloads, inaccurate reporting, and support escalations.

**Independent Test**: Trigger separate downloads from AniWorld and s.to, then inspect job history, qBittorrent sync responses, and exported metadata to confirm the source site is visible and correct for each record.

**Acceptance Scenarios**:

1. **Given** a completed download sourced from s.to, **When** an operator reviews the job detail or qBittorrent sync output, **Then** the record clearly states that the source site was s.to.
2. **Given** an availability cache entry initiated for an AniWorld title, **When** a subsequent query reads that entry, **Then** it reflects AniWorld-specific freshness without being overwritten by s.to checks.

---

### User Story 3 - Catalogue control (Priority: P3)

Administrators must be able to enable, disable, or reorder the supported catalogues to respect legal, performance, or preference constraints without further code changes.

**Why this priority**: Different deployments have varying compliance requirements or bandwidth budgets; the bridge must adapt quickly.

**Independent Test**: Adjust configuration to disable s.to, restart AniBridge, and verify searches now return only AniWorld results while the UI/logs confirm the change; re-enable s.to and confirm dual catalogue behaviour resumes.

**Acceptance Scenarios**:

1. **Given** s.to is disabled in configuration, **When** a client searches for a title exclusive to s.to, **Then** AniBridge returns a clear "not found" style response and does not attempt to contact s.to.
2. **Given** both catalogues are enabled with a configured priority order, **When** a query matches releases on both sites, **Then** results honour the configured order or merge rule and expose the source site for each option.

---

### Edge Cases

- Requests referencing a title that exists on both catalogues with differing season structures; the system must deduplicate without hiding relevant releases.
- A site is temporarily unreachable; AniBridge must degrade gracefully, surface the outage, and continue serving results from the remaining catalogue.
- Language preferences conflict between catalogues (e.g., English dub on s.to vs German sub on AniWorld); responses must reflect the closest available match and note mismatches.
- Migrated downloads with legacy AniWorld-only metadata must remain readable while new jobs adopt site-aware tagging.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The bridge MUST aggregate search and browse requests across the enabled catalogues and return a unified response that includes s.to results alongside AniWorld entries when applicable.
- **FR-002**: The system MUST resolve user queries to site-specific slugs by maintaining per-site title indices and return both the slug and originating site with each match.
- **FR-003**: Download scheduling MUST respect the originating site, ensuring every job, availability check, and retry uses links, language maps, and fallbacks appropriate for that catalogue.
- **FR-004**: The bridge MUST persist and expose the source site for every job, availability entry, magnet payload, and API response consumed by Sonarr, qBittorrent, or other clients.
- **FR-005**: Operators MUST be able to configure which catalogues are active, define their priority order, and override site-specific defaults (such as base URLs or preferred languages) without modifying code.
- **FR-006**: The system MUST prevent cross-site cache contamination by tracking freshness, episode counts, and availability independently per catalogue.
- **FR-007**: Naming, magnet metadata, and audit logs MUST incorporate clear site identifiers so downstream systems can distinguish AniWorld releases from s.to releases.
- **FR-008**: Official documentation, onboarding materials, and configuration guides MUST describe the new dual-catalogue behaviour, configuration options, and observable differences for end users.

### Key Entities *(include if feature involves data)*

- **Catalogue Site**: Represents an enabled content source (e.g., AniWorld, s.to) and holds attributes such as display name, base URL, language defaults, search priority, and availability refresh rules.
- **Title Mapping**: Captures the association between a user-facing show title, the catalogue site, and the site-specific slug or identifier used for lookups.
- **Download Job**: Records the lifecycle of a user-requested download, including the originating catalogue, metadata presented to clients, status history, and linkage to availability cache entries.

## Assumptions

- The upstream downloader library already supports issuing requests to both AniWorld and s.to when provided the correct site hint.
- Access to s.to does not require additional authentication or rate-limit negotiation beyond what the existing library handles.
- Downstream automation tools (e.g., Sonarr, Prowlarr) can display multiple results for a single query and rely on AniBridge to convey source details for informed selection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of automated searches for titles known to exist on s.to return relevant results within 5 seconds under normal network conditions.
- **SC-002**: 100% of downloads triggered from either catalogue include the correct source site identifier in job history, qBittorrent sync responses, and exported magnets.
- **SC-003**: Configuration changes that disable or re-prioritise a catalogue take effect on the next service restart and are reflected in subsequent health/status checks without manual code edits.
- **SC-004**: Post-release feedback from support/onboarding sessions indicates that 90% of operators can explain how to enable or disable each catalogue after reviewing the updated documentation.
