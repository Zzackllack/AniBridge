# 017 Provider Catalog Index - Scheduled Provider Indexing

## Goal

Move provider discovery work out of the request path and into a scheduled indexing pipeline that builds and refreshes a local SQLite-backed catalog.

The implementation must remain modular and provider-scoped so that changing one provider does not create cross-provider regressions.

## Problem Statement

Current search and `tvsearch` behavior still performs meaningful live work on demand:

- provider title lookup may need a live or warm index refresh
- season discovery can fall back to sequential live probing
- episode language discovery can require provider page fetches
- availability and quality cache entries are populated reactively per request

This keeps request latency variable and makes cold or broad searches expensive.

## Proposed Direction

Instead of discovering provider data only when Sonarr or Radarr asks for it, AniBridge should periodically walk each supported provider catalog and persist a local index of:

- titles available on that provider
- provider-specific slugs and URL suffixes
- provider-specific season and episode structure
- provider-side language availability per episode
- provider-side movie entries for providers that expose them
- lightweight provider or host hints when they are available without deep resolution

The request path should query SQLite first and should not perform request-time targeted refresh of missing titles, seasons, or episodes.

## Version One Scope

Version one should index the full provider catalog surface that AniBridge can serve:

- all enabled providers
- all series on those providers
- all episodes of those series
- all provider-exposed movies

Each provider should have its own indexing implementation and refresh handling behind a shared orchestration contract.

## Refresh Model

Use a background refresh pipeline, not a blocking full recrawl during normal operation.

### Startup behavior

- app startup should initialize the refresh scheduler
- app startup should check whether the local provider index is missing or stale
- if no usable index exists yet, catalog-dependent interactions should fail until the first complete index build for all enabled providers completes
- blocked catalog-dependent requests should return a suitable HTTP error, include a short explanation, and log the reason clearly
- if an older index already exists, AniBridge should continue serving it while a replacement index is built in parallel

### Recurring behavior

- run a scheduled refresh every 24 hours by default
- make refresh cadence configurable through environment variables
- support provider-specific refresh intervals through environment variables
- do not perform request-time targeted refresh for one title, season, or episode

## Scope of the Indexed Data

Persist data that is relatively stable and expensive to recompute:

- provider title lists
- provider slug mappings
- provider URL suffixes or paths
- provider season and episode existence
- provider language availability
- provider-to-canonical entity mappings
- last indexed timestamps and refresh status

Do not persist data that is short-lived or operationally volatile as part of the main index:

- final direct media URLs
- temporary redirect URLs
- host redirect chains
- full probe payloads
- large raw HTML responses
- response headers from resolved stream URLs

These should remain short-TTL operational caches, not permanent catalog records.

## Provider Crawl Strategy

### Title discovery

For each enabled provider:

- load the provider-wide title index or search endpoint equivalent
- persist one row per provider title entry
- persist stable provider identifiers such as slug, URL suffix or path, and media type hints

### Episode discovery

For each provider title:

- enumerate seasons and episodes from the provider structure
- persist provider-native season and episode coordinates
- persist provider language availability
- persist only lightweight host or provider hints when they are available without deep resolution
- do not resolve deeper into ephemeral redirect or direct stream URLs

### Refresh checkpoints

Track per-provider and per-title progress so the crawler can resume safely after restart:

- last successful provider refresh timestamp
- last successful title refresh timestamp
- cursor or page state where applicable
- failure count and last error summary

## Request Path Implications

After this feature, the request path should prefer:

1. local provider catalog index
2. local canonical mapping tables
3. short-TTL operational caches

Expected effects:

- lower `tvsearch` latency
- fewer provider page fetches on search
- fewer sequential live probes for season discovery
- more deterministic behavior under repeated Sonarr scans

Misses caused by absent or unresolved index data should not trigger ad-hoc live re-indexing.

## Anti-Bot and Rate-Limit Considerations

Full indexing increases background traffic and must be bounded carefully.

Required controls:

- per-provider concurrency limits
- global crawler concurrency limits
- retry with backoff on `429`, `403`, and transient upstream failures
- refresh checkpoints to avoid restarting whole crawls

The system should assume that provider anti-bot behavior may change over time.

## Storage Strategy

SQLite growth is acceptable only if the data is normalized aggressively.

Safe principles:

- store canonical entities once
- store provider mappings separately
- store availability as compact, current-state rows
- avoid duplicating long text or JSON across episode rows
- store current state only, not history, unless a later feature requires it

Optimize for performance and functionality first while keeping the database ideally under 1 GB and at most around 5 GB when justified.

Potentially expensive data should be excluded from the permanent catalog unless there is a clear request-path need.

## Refresh Semantics

- refreshed index data should overwrite the previous current-state rows
- if a provider refresh fails, AniBridge may continue serving the older indexed data
- if a provider base URL changes, persisted provider-relative suffixes or paths should remain valid when reassembled against the current base URL
- if a title, episode, or movie was present in the previous successful index but is absent from the next successful refresh, AniBridge should delete that stale row during the refresh replacement process

## Suggested Deliverables

- new refresh scheduler surface for provider indexing
- persistent provider catalog tables and migrations
- refresh status and checkpoint tables
- operational metrics for index freshness, crawl duration, and fallback rate
- clear provider-specific indexing boundaries in the codebase

## Non-Goals

- replacing SQLite at this stage
- storing every transient stream resolution artifact permanently
- request-time targeted re-indexing of cache misses
- tightly coupling provider implementations to each other

## Selected Decisions

- all enabled providers should be indexed
- version one should index full provider coverage for series, episodes, and provider-exposed movies
- refresh cadence should default to 24 hours and remain configurable through environment variables, including provider-specific overrides
- if no index exists yet, catalog-dependent routes should fail until bootstrap indexing completes
- first bootstrap indexing should be complete and fully blocking before catalog-dependent routes become usable
- if an index exists but is stale, AniBridge should keep serving the old index while a new one is built in parallel
- request-time targeted refresh is explicitly out of scope
- indexing should include only non-ephemeral, non-probe-intensive data
- provider URLs should be stored as provider-relative suffixes or paths, not as full base URLs
- current-state data should be overwritten on refresh
- entries missing from the next successful refresh should be deleted at refresh time
