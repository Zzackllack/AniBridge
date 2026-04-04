# Data Model – Dual Catalogue s.to Support

## CatalogueSite
- **Purpose**: Represents an enabled content source (AniWorld or s.to) with configurable behaviour.
- **Fields**:
  - `site_id` (enum: `aniworld`, `sto`) – primary identifier.
  - `display_name` (string) – human-readable label for logs/docs.
  - `base_url` (URL string) – default root endpoint, overrideable via configuration.
  - `search_priority` (integer) – ordering used when presenting merged results.
  - `default_languages` (list of strings) – ordered language preferences for the site.
  - `enabled` (boolean) – derived from configuration toggle.
  - `search_timeout_seconds` (integer) – per-site timeout budget for remote queries.
- **Relationships**: One-to-many with `TitleMapping`, `AvailabilityRecord`, and `DownloadJob`.
- **Validation Rules**: `search_priority` must be unique among enabled catalogues; `base_url` must be HTTPS or documented IP per configuration.
- **State Transitions**: `enabled` toggles controlled via configuration reload/startup; all dependent caches must refresh when the state changes.

## TitleMapping
- **Purpose**: Connects user-facing titles to site-specific slugs.
- **Fields**:
  - `title_key` (string) – normalized title text used for lookups.
  - `site_id` (enum) – foreign key to `CatalogueSite`.
  - `slug` (string) – path segment used by downloader.
  - `last_refreshed_at` (timestamp) – cache freshness indicator.
- **Relationships**: Belongs to `CatalogueSite`.
- **Validation Rules**: (`title_key`, `site_id`) must be unique; slug must match site-specific pattern (`/anime/stream/...` vs `/serie/stream/...`).
- **State Transitions**: Refresh triggered by scheduled index sync or cache expiry; updates must not overwrite entries from other sites.

## AvailabilityRecord
- **Purpose**: Tracks whether a specific episode is available on a site.
- **Fields**:
  - `site_id` (enum) – foreign key to `CatalogueSite`.
  - `slug` (string) – reference to show.
  - `season` (integer) – season number (0 allowed for specials).
  - `episode` (integer) – episode number; `None` for season packs.
  - `language` (string) – value from site language map.
  - `quality` (string) – aggregated resolution/codec descriptor.
  - `checked_at` (timestamp) – last verification time.
  - `is_available` (boolean) – current availability flag.
- **Relationships**: Belongs to `CatalogueSite`; referenced by `DownloadJob`.
- **Validation Rules**: Composite primary key (`site_id`, `slug`, `season`, `episode`, `language`); `checked_at` must increase monotonically per record.
- **State Transitions**: Updated on probe completion; TTL-based cleanup respects per-site policies.

## DownloadJob
- **Purpose**: Records the lifecycle of downloads initiated by clients.
- **Key Additions**:
  - `source_site` (enum) – new required field referencing `CatalogueSite`.
  - `magnet_metadata` (JSON) – includes site identifier for downstream consumers.
- **Validation Rules**: `source_site` must match the site used for download URLs; migrations enforce non-null values for new jobs while defaulting legacy records to `aniworld`.
- **State Transitions**: Existing `queued → downloading → completed/failed/cancelled`; transitions now log `source_site` for audits.

## ResultEntry (response projection)
- **Purpose**: Represents merged search results returned to Torznab/qBittorrent clients.
- **Fields**:
  - `site_id` (enum) – indicates origin.
  - `title` (string) – display title shown to clients.
  - `season` / `episode` (integers) – same semantics as today.
  - `priority_rank` (integer) – derived from `CatalogueSite.search_priority`.
  - `download_link` (URL) – job trigger link encoded with site metadata.
  - `language`, `quality`, `size_bytes` (optional) – metadata for sorting.
- **Validation Rules**: Results sorted by `priority_rank` while retaining duplicates across sites; duplicates must not be collapsed if `site_id` differs.
