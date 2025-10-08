# Feature Specification: Absolute Numbering Support for Sonarr Anime Requests

**Feature Branch**: `001-absolute-episode-numbers`  
**Created**: 2025-10-08  
**Status**: Draft  
**Input**: User description: "I want to add an implementation of converting absolute series/episode numbers, so, for instance, 001, 002, 003, and so on, to the appropriate standard format, so S01E01. This is needed for Sonarr. Currently, when the user sets the series type to anime/absolute, Sonarr will try to search for an episode with its absolute number, but Aniworld (the endpoint where we get the episodes from and download them via the library from aniworld.models import Anime, Episode found under /app/core/downloader.py) only returns episodes/series with the standard format, for instance, with S01E03. So we will need to convert them in order for our app to find them even when Sonarr is set to series type absolute/anime, also we need, when we name them for returning them to Sonarr, to change series/episode numbers to absolute again. We need some sort of function to detect if the request from Sonarr/Prowlarr is in the schema of absolute/anime."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sonarr absolute search matches anime catalog (Priority: P1)

An automation admin configures Sonarr to manage an anime using absolute numbering and triggers a search for episode "003". The AniBridge indexer recognises the absolute format, translates it to the matching season/episode combination used by AniWorld, and returns the correct episode so Sonarr can queue the download.

**Why this priority**: Without this flow, anime libraries configured with absolute numbering fail to find episodes, breaking the primary use case motivating the feature.

**Independent Test**: Configure an anime series in Sonarr with absolute numbering, request a specific absolute episode, and verify that the indexer delivers the matching result without manual intervention.

**Acceptance Scenarios**:

1. **Given** Sonarr requests an anime episode using an absolute number, **When** AniBridge processes the search, **Then** the system maps the absolute value to the correct season and episode and surfaces the episode in the search results.
2. **Given** Sonarr requests an anime episode using a standard season/episode format, **When** AniBridge processes the search, **Then** the existing behaviour remains unchanged and results are returned without double conversion.

---

### User Story 2 - Download metadata honours absolute numbering (Priority: P2)

After Sonarr grabs an anime episode, AniBridge should return progress updates and completed download details using the absolute numbering that Sonarr expects, even though the underlying source tracked it as season/episode.

**Why this priority**: Sonarr relies on consistent numbering to match completed downloads to its library; mismatched numbering causes import failures or requires manual renaming.

**Independent Test**: Grab an episode via AniBridge while Sonarr is in absolute mode and confirm the queued task, progress updates, and completed item all reference the same absolute episode identifier that Sonarr requested.

**Acceptance Scenarios**:

1. **Given** Sonarr queues an absolute-numbered download, **When** AniBridge reports job status, **Then** each status payload references the absolute identifier alongside any descriptive fields.
2. **Given** a download completes successfully, **When** AniBridge hands back file details to Sonarr, **Then** the naming metadata reflects the original absolute number so Sonarr can import automatically.

---

### User Story 3 - Indexer browsing tools respect numbering preference (Priority: P3)

An administrator tests AniBridge connectivity in Prowlarr or Sonarr’s “preview” screens while the series is configured with absolute numbering. The preview responses display absolute numbers so users can confirm the matching episodes before initiating downloads.

**Why this priority**: Admins need confidence that searches and previews reflect their numbering preference, reducing support incidents for anime libraries.

**Independent Test**: Use the manual search or capability test in Sonarr/Prowlarr for an anime set to absolute mode and verify that preview results include absolute identifiers alongside titles.

**Acceptance Scenarios**:

1. **Given** a manual search request includes absolute numbering, **When** AniBridge returns preview rows, **Then** each row shows the absolute identifier Sonarr expects.

---

### Edge Cases

- Requests include leading zeros or omit them (e.g., “3”, “03”, “003”); the system should recognise all forms as the same absolute number.
- Absolute numbers beyond the known episode count are requested; the system should respond gracefully (e.g., no results) without attempting conversion.
- Mixed-format multi-episode requests (e.g., absolute ranges or specials) should fall back to existing behaviour with clear signalling that conversion was not applied.
- Conversion failures should write explicit “cannot map episode” errors and “using fallback…” warnings to the logs and, when the fallback toggle is enabled, respond with the full catalogue labelled using standard season/episode numbers to avoid leaving Sonarr without options.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect when incoming search or download requests use anime absolute numbering by analysing the episode identifier pattern (e.g., standalone numeric values with optional leading zeros) and capture the absolute identifier present in the request payload.
- **FR-002**: The system MUST translate detected absolute identifiers into corresponding season and episode numbers before querying AniWorld so the correct source episode can be located.
- **FR-003**: The system MUST maintain a reliable mapping between absolute numbers and season/episode combinations for each anime series—excluding specials or season 0 entries—updating it when fresh catalogue data is received.
- **FR-004**: The system MUST supply absolute numbering back to client applications in all user-facing responses (search previews, job status, completed download metadata) whenever the initiating request used absolute numbering.
- **FR-005**: The system MUST fall back to standard season/episode handling when a request does not match the absolute numbering pattern, ensuring existing workflows remain unaffected.
- **FR-006**: The system MUST, when conversion fails because no matching season/episode exists, log an error message stating “cannot map episode,” emit a warning indicating a fallback decision, and respect an environment toggle that—when enabled—returns all available episodes for the series using standard season/episode numbers and—when disabled—returns an empty result set to the requesting client.

### Key Entities *(include if feature involves data)*

- **Episode Number Mapping**: Represents the relationship between an anime’s absolute episode index and its season/episode designation; includes series identifier, absolute number, season, episode, title, and source-of-truth timestamp.
- **Request Context**: Captures details about an inbound search or download request, including numbering mode (absolute or standard), the original identifier provided by the client, and the resolved identifier passed to AniWorld.

## Assumptions & Dependencies

- AniWorld continues to expose comprehensive season and episode metadata so absolute numbers can be mapped without manual entry.
- Episode identifier patterns supplied by Sonarr or Prowlarr (e.g., numeric-only values without explicit season fields) are reliable indicators of absolute numbering mode.
- Absolute numbering follows sequential order across an anime series, allowing deterministic conversion between absolute indexes and season/episode identifiers.
- The feature depends on existing AniBridge mechanisms for fetching episode catalogues and for returning job metadata to client applications.
- Specials (season 0) are excluded from the absolute numbering conversion to avoid mismatching Sonarr requests that rely on main season sequences only.
- The fallback mechanism is controlled via a new environment toggle that defaults to disabled, ensuring existing clients continue to receive empty responses when mappings fail unless operators explicitly opt in to the fallback catalogue behaviour.
- When the fallback toggle is enabled, AniBridge presents catalogue results using standard season/episode identifiers so downstream tools can still process the responses consistently.

## Clarifications

### Session 2025-10-08

- Q: Should the absolute-to-standard conversion count specials/season 0 episodes when building mappings? → A: No
- Q: When AniBridge cannot map an absolute episode to a season/episode, what response should the client receive? → A: Log error and warning, optional fallback returning all episodes when env toggle enabled
- Q: Which incoming request signal should AniBridge treat as authoritative when deciding to apply absolute numbering? → A: Episode identifier pattern
- Q: If fallback returns the full episode catalogue, how should each episode be numbered in the response? → A: Standard season/episode only

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of automated searches for anime configured with absolute numbering return the correct episode on the first attempt during validation.
- **SC-002**: Manual verification shows 0 discrepancies between the absolute number requested by the client and the identifier included in AniBridge’s completed download metadata for the same job.
- **SC-003**: Support tickets related to “anime absolute episodes not found” decrease by 80% within one release cycle after rollout.
- **SC-004**: Preview and capability checks for anime absolute series complete in under 5 seconds while displaying the correct absolute identifiers in every result row.
