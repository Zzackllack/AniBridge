# Phase 0 Research — Absolute Numbering Support for Sonarr Anime Requests

## Decision: Episode numbering detection

- **Rationale**: Sonarr/Prowlarr issue absolute-mode searches as numeric identifiers without season markers. Pattern-based detection works regardless of client version and avoids coupling to optional series-type metadata that some clients omit.
- **Alternatives considered**:
  - Series-type flag inspection: unreliable when intermediaries strip metadata.
  - Manual configuration per indexer: increases operational burden and risks drift.

## Decision: Mapping persistence strategy

- **Chosen approach**: Introduce a dedicated SQLModel table (`EpisodeNumberMapping`) keyed by series identifier and absolute index, populated from AniWorld episode listings and refreshed on demand.
- **Rationale**: Persisted mappings give deterministic conversions for future requests, survive restarts, and allow reuse during download/job lifecycle reporting.
- **Alternatives considered**:
  - In-memory caching only: risks loss on restart and duplicates logic across workers.
  - Recomputing per request: adds latency and repeated AniWorld fetches.

## Decision: Fallback behaviour for unmapped requests

- **Chosen approach**: Default to empty responses while logging an error and warning; when `ANIBRIDGE_FALLBACK_ALL_EPISODES` is enabled, return the full catalogue using standard season/episode numbers.
- **Rationale**: Preserves current contract by default, offers operators an opt-in escape hatch, and provides clear telemetry for troubleshooting.
- **Alternatives considered**:
  - Automatic fallback always on: could mislead Sonarr into importing incorrect episodes.
  - Hard failure with HTTP error: harsher than necessary and breaks existing flows that expect empty lists.

## Decision: Documentation updates

- **Chosen approach**: Update VitePress sections covering configuration (guide/configuration.md), Torznab behaviour (api/torznab.md), and qBittorrent integration notes to describe absolute numbering support, mapping limitations (specials excluded), and the fallback toggle.
- **Rationale**: Keeps operators informed per Constitution’s UX principle and reduces support churn.
- **Alternatives considered**: README-only update (insufficient depth); changelog without how-to (lacks actionable steps).

## Decision: Testing scope

- **Chosen approach**: Add pytest cases covering conversion utilities, Torznab search results in absolute mode, qBittorrent sync metadata, and fallback responses; leverage existing FastAPI test client fixtures.
- **Rationale**: Ensures coverage across API surfaces and background job reporting per Test-Centric Reliability principle.
- **Alternatives considered**: Unit-only tests (miss cross-layer contracts).
