# Data Model — Absolute Numbering Support

## EpisodeNumberMapping
- **Purpose**: Persist deterministic translations between AniWorld’s season/episode identifiers and Sonarr absolute numbering requests per anime series.
- **Key Fields**:
  - `id`: surrogate primary key.
  - `series_slug`: text identifier aligning with AniWorld slug / internal series key.
  - `absolute_number`: positive integer (>=1) excluding specials.
  - `season_number`: positive integer (>=1).
  - `episode_number`: positive integer (>=1).
  - `episode_title`: optional text for reference and docs.
  - `last_synced_at`: datetime timestamp of when mapping was confirmed.
- **Constraints**:
  - Unique constraint on (`series_slug`, `absolute_number`).
  - Unique constraint on (`series_slug`, `season_number`, `episode_number`) to prevent duplicates.
  - Validation ensures season/episode values remain within AniWorld-reported range.
- **Lifecycle**:
  - Created/updated during catalogue sync when new episodes appear or metadata changes.
  - Soft-updated on demand when conversion encounters stale data (refresh from AniWorld then upsert).
  - Removed only if catalogue refresh reports missing episodes (rare; must log).
- **Relationships**:
  - Linked to existing job/task records via `series_slug` and season/episode pairs when reporting status.

## ConversionRequestContext (transient object)
- **Purpose**: Track per-request numbering mode during API handling.
- **Attributes**:
  - `series_slug`
  - `requested_identifier` (string as provided by client)
  - `numbering_mode` (`"absolute"` or `"standard"`)
  - `absolute_number` (optional int when parsed)
  - `season_number`/`episode_number` (filled after mapping)
- **Behavior**:
  - Instantiated at the beginning of Torznab/qBittorrent flows.
  - Supplies metadata to downstream schedulers and response formatting.
  - Not persisted; passed through FastAPI dependency or helper methods.
