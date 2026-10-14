# Current code and PR #119 evidence

This inventory is pinned to local `main` `e14a041` and local
`provider-catalog-index` `61351bb` as inspected on 2026-09-26. The GitHub PR API and remote refs confirmed these heads during this review.
Refresh the refs before implementation. PR status and provider behavior can change.

## Mainline 2.6.0

| Area | Current behavior | Consequence for worker design |
| --- | --- | --- |
| `apps/api/app/utils/title_resolver.py` | Caches provider slug/title/alias dictionaries; `slug_from_query` scans candidates and can fall back to s.to suggest/Megakino search. | Replace the ordinary catalog search path with bounded local DB queries; preserve explicit fallback semantics where chosen. Do not keep a second full Python dictionary copy after installing a snapshot. |
| `apps/api/app/providers/base.py` and site adapters | `CatalogProvider` fetches/parses title lists; megakino uses a sitemap-specific client. | Extract or wrap pure parsing and provider transport behind injected configuration; importing `app.providers` also imports API config, so it is not a clean worker package yet. |
| `apps/api/app/api/torznab/api.py`, `tvsearch.py`, `search_handlers.py` | `search`, `movie`, and `tvsearch` use title resolution, Skyhook lookups, availability cache, and optional live probes. | Catalog integration requires contract tests for all query types, IDs, season/episode searches, specials, language filters, result caps, magnet identities, and STRM naming. |
| `apps/api/app/api/torznab/skyhook.py` | Request-time TVDB-style title and episode lookup through Sonarr Skyhook. | Keep external lookup behavior separate until redistribution rights and mapping fidelity are established. Record when local catalog answers instead of Skyhook. |
| `apps/api/app/db/models.py` | SQLite `anibridge_jobs.db` stores jobs, availability, STRM URL mapping, and qBittorrent client tasks; Alembic has three mainline revisions. | Do not ship or replace this DB. Add a separate read-only catalog DB and a small local state/override table through normal migrations. |
| `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/api/Dockerfile` | API is one Python 3.14 uv project and the Dockerfile copies API project/lock from repo root. Docs have their own pnpm workspace; there is no root Python workspace. | A uv workspace or package extraction changes lock and Docker build contexts. Stage and verify it independently. Worker gets its own image and writable state. |

The existing provider code includes cache/fallback behavior that can return an
empty map after a failed fetch. A worker must attach typed fetch outcomes and
validate suspicious cardinality changes; an empty parse cannot be published as
an authoritative deletion merely because HTTP returned 200.

## PR #119: useful parts and constraints

PR #119 adds `app/catalog/indexer.py` (~1,900 lines), provider crawling,
Skyhook-based canonical matching, generation-scoped SQLModel tables, scheduler
integration, and tests. Its catalog database lives with the API's operational
models. The indexer imports global `app.config`, `app.db.engine`, CRUD helpers,
and terminal progress reporting. It cannot become a standalone worker through
a file move or a Docker command change.

Specific behavior to revisit: a title-index refresh creates a new generation;
`_finish_title_index_success` sets detail and canonical enrichment back to
`pending`. Thus unchanged titles are eligible for repeat detail/canonical work.
Its bounded result queue does not bound BeautifulSoup trees, upstream objects,
active futures, caches, and SQLAlchemy sessions. The PR performance spec
records multi-gigabyte first-bootstrap observations, but no fresh benchmark
was run for this document.

PR #119's canonical matcher calls
`https://skyhook.sonarr.tv/v1/tvdb/search/en/` and
`https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}`. Do not publish raw
Skyhook payloads or assume its public reachability grants redistribution.

## Reuse assessment for implementation

- **Good references:** provider parsing patterns, normalized title/episode
  records, matching confidence ideas, search regression cases, generation
  failure cases, torrent resume tests, and special mapping tests.
- **Needs extraction:** provider fetch/parse adapters, title normalization,
  canonical matching rules, HTTP policy, and typed challenge outcomes. Give
  these functions explicit dependencies and no `app.config` import side effects.
- **Reimplement:** worker scheduling, persistent crawl state, publication,
  artifact validation, client update manager, and separation of private DB
  from public catalog. The PR's generation table layout is not the wire format.
- **Do not copy blindly:** broad Skyhook cache/payload storage, shared ORM
  engine, stale thread timeout pattern, large catalog objects held per future,
  and title-index refreshes that reset enrichment eligibility.

The implementation agent should refresh the path-by-path matrix below against
then-current PR/main heads and record any changed reuse decision. This spec does not direct a merge or closure
of PR #119.

## Concrete reuse matrix from this review

| Reference at inspected head | Reuse / replacement contract | Validation |
| --- | --- | --- |
| main `app/utils/magnet.py`, `tests/unit/utils/test_magnet.py` | Preserve aw/sto parsing and exact legacy hash bytes; replace new hash generation with provider-scoped v2 (09). Existing tests do not cover cross-provider collisions. | C1, C6 |
| main `app/core/downloader/provider_policy.py` | Preserve origin checks, DNS validation/pinning, TLS identity and typed challenge outcomes; inject dependencies and add total deadlines/body caps. Existing max redirect count 8 is reduced for new catalog operations. | C2, C3 |
| main `app/providers/sto/v2.py`, provider adapters | Reuse pure positive-language parsing with site-specific fixtures; reject default-language inference. | C2, C5 |
| main `app/api/qbittorrent/torrents.py`, `app/core/scheduler.py` | Replace schedule-before-persist and paused-add behavior with one durable service transition. Keep external hashes, categories and paths. | C5, C6 |
| main `app/db/models.py`, `tests/unit/db/test_migrations.py` | Additive mainline migration; current cleanup marks queued/downloading failed and must not run on new leased jobs. Job lacks slug/mode/full request. | C6 |
| main `app/utils/naming.py`, `app/api/torznab/utils.py` | Keep sanitization/RSS structure; replace guessed quality/codec/size and subtitle-audio inference. | C5 |
| #119 `app/catalog/indexer.py` `_finish_title_index_success` | Reference checkpoint/error tests; replace generation reset of detail/canonical pending work. Do not copy global engine/config/scheduler. | C2 |
| #119 `app/catalog/metadata.py`, `tests/unit/catalog/test_metadata.py` | Reuse bounded-cache test ideas; replace permissive fuzzy winner with explicit/unique validated mappings. | C1, C5 |
| #119 `tests/integration/api/torznab/test_indexed_catalog.py`, `test_specials_mapping.py` | Port useful assertions to new fixture DB; none proves live client import. | C5 |

Paths in this table are relative to `apps/api/`, including PR-only paths.
The implementation agent refreshes this matrix for drift, rather than treating
all selection work as an open design task. No application code was changed.
