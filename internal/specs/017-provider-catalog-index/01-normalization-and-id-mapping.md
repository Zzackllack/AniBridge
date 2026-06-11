# 017 Provider Catalog Index - Normalization and ID Mapping

## Goal

Define a canonical mapping layer so AniBridge can match provider-specific series, seasons, episodes, and movies to the metadata models expected by Sonarr and Radarr with a higher hit rate than the current on-the-fly approach.

## Problem Statement

Provider catalogs do not align cleanly with Sonarr and Radarr expectations:

- provider titles may differ from canonical metadata titles
- aliases and localized names vary
- specials and extras often use provider-specific numbering
- provider season and episode structures may not match TVDB ordering
- some providers expose only partial identifiers or no canonical IDs at all

Today this mismatch is handled by a mix of live title matching, special-case mapping, and request-time probing. That limits correctness and repeatability.

## Canonical Metadata Targets

### Sonarr-facing canonical model

Use TVDB-style series and episode numbering as the primary canonical model for TV content.

Persist at least:

- `tvdb_id`
- canonical series title
- canonical season number
- canonical episode number

Secondary IDs are optional and should be stored only when they materially improve matching:

- `tmdb_id`
- `imdb_id`
- `tvmaze_id`
- `anilist_id`
- `mal_id`

The schema should be designed so AniBridge can support additional non-provider-native canonical orderings later when they improve Sonarr compatibility.
When these secondary TV identifiers are cheap to obtain and do not add disproportionate engineering complexity, AniBridge should persist them.

### Radarr-facing canonical model

Use TMDb as the primary canonical model for movies.

Persist at least:

- `tmdb_id`
- canonical movie title
- release year

Optional secondary IDs:

- `imdb_id`
- `tvdb_id`

For version one, TMDb should be treated as the authoritative movie identity. Secondary IDs may be null or omitted when they do not materially help.

## Mapping Layers

Split the model into explicit layers.

### Canonical entity layer

Stores metadata-system identity independent of any provider:

- canonical series
- canonical seasons
- canonical episodes
- canonical movies

### Provider entity layer

Stores how a provider represents the same title:

- provider title row
- provider slug
- provider URL suffix or path
- provider media type hint
- provider-native season and episode coordinates
- provider-native language availability

### Mapping layer

Stores the relationship between provider entities and canonical entities:

- provider title -> canonical series or movie
- provider episode -> canonical episode
- provider special or film entry -> canonical special episode or movie
- mapping confidence
- mapping source and last verification time

## Matching Strategy

Use a staged mapping strategy rather than a single fuzzy-title match.

### Preferred match order for series

1. explicit canonical ID from provider metadata, if available
2. existing confirmed local mapping
3. exact title or alias match against canonical metadata
4. constrained fuzzy title match
5. unresolved or low-confidence automatic mapping

### Preferred match order for episodes

1. existing confirmed provider episode mapping
2. direct canonical numbering alignment
3. provider special or extra mapping rules
4. alias-based remap to canonical special or extra episode
5. unresolved best-effort automatic mapping

### Preferred match order for movies

1. explicit `tmdb_id`
2. explicit `imdb_id`
3. title plus year exact match
4. constrained fuzzy match

## Specials, Extras, and Films

Specials should be first-class mapping records, not ad-hoc request-time exceptions.

Store:

- provider source season and episode
- canonical alias season and episode when TV-mapped
- mapping rationale or source
- confidence flag

This allows AniBridge to answer Sonarr requests consistently even when the provider exposes the content under `film-N`, season `0`, or another non-canonical structure.

If provider content is clearly represented as a film or movie rather than a TV special, AniBridge should preserve that distinction and map it into the movie model for Radarr instead of force-normalizing it into TV season `0`.

## Confidence and Verification

Not all mappings are equally trustworthy.

Suggested states:

- `confirmed`
- `high_confidence`
- `low_confidence`
- `unresolved`
- `conflict`

Why this matters:

- request path can trust confirmed mappings immediately
- low-confidence mappings can be eligible for background re-check
- conflicting mappings can be excluded from automatic response emission

Version one may still emit low-confidence matches on a best-effort basis when no better candidate exists.
If one provider episode plausibly maps to multiple canonical episodes, AniBridge should emit all plausible matches rather than suppressing output.

## Request Path Usage

When Sonarr or Radarr requests content:

1. resolve the request to the canonical ID model expected by the client
2. query the local mapping tables for matching provider entities
3. return provider-backed results derived from confirmed or sufficiently strong mappings
4. do not perform request-time targeted metadata enrichment just because the local mapping is absent

For generic AniBridge search that is not explicitly Sonarr or Radarr ID-driven, provider titles may still be returned even when canonical enrichment is not yet complete.

This should raise both:

- probability of finding the correct title
- probability of returning the correct season and episode numbering

## Suggested Data to Persist

Persist:

- canonical IDs
- canonical titles and aliases
- provider slugs and URL suffixes or paths
- provider-native season and episode coordinates
- mapping confidence and timestamps
- language availability per mapped episode

Prefer compact persistence:

- provider-relative URL suffixes or paths instead of full base URLs
- current-state records instead of history tables
- only those secondary IDs that materially improve Sonarr or Radarr matching

Avoid persisting in the canonical mapping tables:

- raw HTML
- large API payloads
- direct stream URLs
- large probe artifacts

## Failure Modes to Plan For

- one provider title maps to multiple plausible canonical series
- one provider episode maps to multiple plausible canonical episodes
- one canonical episode is split or merged differently by a provider
- specials are exposed as films instead of episodes
- provider title aliases drift over time
- canonical metadata source updates numbering after the initial mapping

The design should support re-mapping without rebuilding the entire catalog from scratch.

Canonical metadata changes should remap automatically on the next successful refresh.

## Recommended Outcome

The indexing feature and this mapping layer should ship together conceptually:

- indexing without canonical mapping improves speed but not match quality enough
- canonical mapping without scheduled indexing improves logic but still leaves too much live work

Combined, they create a local database that is both faster and more compatible with Sonarr and Radarr than the current request-driven approach.

Low-confidence or conflicting mappings do not need to be surfaced to operators in version one, but the persistence model should not prevent a later web-UI override layer.

Provider-specific alias tables should be captured during provider crawl whenever the provider exposes usable alias data directly. This keeps provider-specific naming close to the source and reduces later enrichment work.

## Selected Decisions

- canonical TV mapping should prioritize Sonarr-friendly orderings and remain extensible beyond only TVDB ordering
- canonical movie mapping should prioritize TMDb and may omit or null secondary IDs when they do not materially help
- secondary TV identifiers such as `tvmaze_id`, `anilist_id`, and `mal_id` should be persisted when they are cheap to obtain and do not add significant engineering complexity
- ambiguous anime sequel, remake, split-cour, and similar cases should use best-effort automatic mapping in version one
- low-confidence mappings may still be used best-effort
- if one provider episode has multiple plausible canonical matches, AniBridge should return all plausible matches
- content clearly represented as films should stay in the movie domain rather than being forced into TV specials
- operator review flows for low-confidence mappings can be deferred
- the persistence model should leave room for future manual override support through the planned web UI
- automatic re-mapping should occur on later refreshes when canonical metadata changes
- stale mapped data may continue to be served if refresh is temporarily blocked upstream
- provider titles may still be returned for generic search even when canonical enrichment is incomplete
- provider-specific alias tables should be captured during provider crawl when feasible
