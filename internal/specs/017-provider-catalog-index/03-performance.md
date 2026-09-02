# AniBridge Provider Catalog Indexing: Memory-Bounded Local Bootstrap and Progressive Enrichment Specification

## 1. Purpose

This specification defines the required redesign of AniBridge's provider catalog indexing system so that:

- first startup is usable quickly;
- full provider catalog data is eventually persisted locally;
- memory stays bounded under realistic self-hosted deployments;
- no official prebuilt provider-derived database or JSON catalog is shipped by the project;
- request paths continue to read from the local database instead of doing uncontrolled live probing;
- SQLite remains viable as the default database backend;
- normal users do not need to manually tune concurrency, queue sizes, retry intervals, or caching settings.

The core design principle is:

> AniBridge must compute provider-derived catalog data locally, progressively, and with strict memory bounds. The app must never require loading provider-scale state into Python memory.

This document focuses only on performance, memory, startup behavior, indexing architecture, and SQLite-safety.

The following topics are explicitly out of scope for this task:

- import/export of catalog snapshots;
- official prebuilt provider catalog snapshots;
- Uvicorn reload behavior;
- legal policy text changes;
- UI polish beyond minimal progress/readiness information needed for correct behavior.

---

## 2. Background and Current Problem

The current `provider-catalog-index` branch already moved from a previous "crawl everything then persist everything" design toward a streaming persistence model.

However, during realistic first bootstrap runs the container can still grow to multiple gigabytes of RAM and may eventually stop or be killed by the container/runtime.

The observed and discussed problems are:

1. The catalog contains many titles:
   - AniWorld has thousands of titles.
   - `s.to` has more than ten thousand titles.
   - Each title may expand into many episodes, languages, host hints, aliases, and canonical metadata mappings.

2. Python object overhead is large:
   - HTML responses;
   - BeautifulSoup parse trees;
   - provider library objects;
   - `TitleRecord` dataclasses;
   - nested episode/language objects;
   - canonical metadata payloads;
   - dictionaries/lists/strings;
   - SQLAlchemy ORM identity map objects.

3. A bounded result queue does not automatically bound total process memory because memory can also be retained by:
   - active crawler workers;
   - `Future` objects;
   - global metadata caches;
   - still-running timed-out workers;
   - SQLAlchemy sessions;
   - retry storms after failures;
   - concurrent provider refreshes.

4. SQLite write contention can happen when multiple provider writer paths or failure/status updates write concurrently.

5. The first-run user experience is poor if a full crawl is required before the software can be used.

6. Setting all concurrency to `1` is not an acceptable product solution. It is only an emergency workaround.

7. Shipping a finished provider-derived database would improve UX but creates a worse legal/platform risk posture because the project would distribute a curated provider index as an official artifact.

Therefore, AniBridge needs a local progressive indexing architecture that is fast enough for normal use, memory-bounded by default, and safe for SQLite.

---

## 3. High-Level Product Goal

On a fresh install, AniBridge should behave like this:

1. Start the container.
2. Initialize the database.
3. Quickly build a lightweight provider title index:
   - slug;
   - title;
   - aliases;
   - provider-relative path;
   - media type hint when available.
4. Mark the provider as searchable once the title index exists.
5. Allow the application to respond using database-backed catalog data.
6. Continue crawling expensive details in the background:
   - seasons;
   - episodes;
   - available languages;
   - host hints;
   - canonical TVDB mappings;
   - other normalized mapping data.
7. Never hold the full provider catalog in Python memory.
8. Keep RAM usage bounded below a strict target.

Target resource goals:

- Normal idle runtime: below 512 MB RAM.
- During provider indexing: preferably below 1 GB RAM.
- Absolute design target: no normal first-run indexing path should exceed 1 GB RAM.
- The implementation must avoid any algorithm where memory grows approximately linearly with total provider size.

These targets are product requirements, not tuning suggestions.

---

## 4. Legal/Risk-Driven Distribution Decision

AniBridge must not ship or automatically download an official prebuilt provider-derived catalog database or JSON file as part of this task.

Rationale:

- Source code distribution and provider-derived catalog data distribution have different risk profiles.
- A prebuilt catalog would likely be considered an official project artifact.
- A prebuilt catalog could be attacked more easily through takedown or platform complaint processes because it is a concrete curated index.
- The project should avoid becoming the distributor of provider-derived operational metadata.

Therefore:

- No official provider-derived catalog snapshot must be added.
- No GitHub Release catalog asset must be required for first startup.
- No automatic download of a project-hosted provider catalog must be implemented.
- No bundled provider-derived SQLite/JSON catalog must be included in the Docker image.
- Local self-hosted computation remains the default.

This does not prohibit normal database migrations, schema files, empty seed tables, or code-defined provider configuration.

---

## 5. Non-Goals

Do not implement the following in this task:

1. Import/export of provider catalogs.
2. Official provider-derived database snapshots.
3. External hosted catalog update service.
4. Uvicorn reload changes.
5. Replacing SQLite with PostgreSQL as a requirement.
6. Requiring Redis, Celery, or another distributed job system.
7. A complex UI redesign.
8. Live probing as the normal search/request path.
9. Large-scale user-configurable indexing strategy UI.
10. Any feature that requires the user to manually understand queue sizes, concurrency, or SQLite locks.

---

## 6. Core Architectural Decision

The selected architecture is:

```text
Local progressive indexing

Phase A: lightweight provider title index
  -> fast
  -> memory bounded
  -> enables basic catalog search/readiness

Phase B: provider detail enrichment
  -> background
  -> bounded concurrency
  -> writes episodes/languages/host hints

Phase C: canonical metadata enrichment
  -> background
  -> bounded concurrency
  -> DB-backed or bounded cache only
  -> writes TVDB/canonical mappings

Request path:
  -> database only
  -> no uncontrolled live provider crawl fallback
  -> may trigger explicit targeted warm-up only when designed as a DB-writing indexing job
```

Important:

* The system must not wait for Phase B and Phase C to finish before the app is considered basically usable.
* The request path must not directly perform expensive live crawling as a hidden fallback.
* Any targeted on-demand indexing must be explicit, bounded, persisted, and visible as an indexing job.

---

## 7. Definitions

### Provider

A catalog source such as:

* `aniworld.to`
* `s.to`
* `megakino`

### Title Index

The lightweight list of provider titles.

Contains only cheap title-level metadata:

* provider key;
* slug;
* display title;
* normalized title;
* aliases;
* normalized aliases;
* provider-relative path;
* media type hint if known;
* generation;
* indexed timestamp.

This phase must not crawl every title detail page.

### Detail Index

The expanded provider-level metadata for a title:

* seasons;
* episodes;
* episode-relative paths;
* episode titles when available;
* available languages;
* host hints;
* media type hints;
* detail crawl state.

### Canonical Index

Normalized mappings to external canonical metadata, for example:

* TVDB series ID;
* canonical episode mapping;
* confidence;
* source;
* rationale.

### Generation

A version identifier for a consistent indexing pass.

AniBridge may continue using the existing provider generation model, but the implementation must support partial/progressive stages without exposing inconsistent full-catalog state as complete.

### Bootstrap Readiness

There are multiple readiness levels:

1. `title_ready`

   * The provider title index exists.
   * Basic title search can work from DB.

2. `detail_ready`

   * A meaningful detail crawl has completed for the provider.

3. `canonical_ready`

   * Canonical mapping enrichment has completed or reached a configured baseline.

4. `full_ready`

   * Detail and canonical enrichment have completed for the current provider generation.

The app must not treat "title ready" and "full ready" as the same thing.

---

## 8. Required Startup Behavior

On application startup:

1. Apply database migrations.
2. Ensure provider indexing status rows/stage rows exist.
3. Detect interrupted indexing work.
4. Clean up abandoned staging generations if necessary.
5. Start the provider catalog scheduler.
6. Schedule title index bootstrap for any provider that is not `title_ready`.
7. Schedule detail enrichment for title-ready providers that are not detail-ready.
8. Schedule canonical enrichment for titles/details that are not canonical-ready.
9. Do not block the web server until full catalog indexing is complete.

The app must become reachable even if provider indexing is still running.

Health/readiness responses must clearly distinguish:

```text
app_ready: true
catalog_title_ready: true/false
catalog_detail_ready: true/false
catalog_canonical_ready: true/false
catalog_full_ready: true/false
provider phases...
```

---

## 9. Required Request Behavior

### 9.1 Search and Torznab-like Query Behavior

Request handlers must read from the database.

They must not perform uncontrolled live crawling of provider title pages or provider episode pages during normal search.

If the title index is not ready:

* Return a clear "catalog title index is still initializing" response.
* Do not trigger large live crawling inside the request.

If a title is found but details are not indexed yet:

* Return only DB-backed data that is available; or
* Return a clear "details are still being indexed" message; or
* Optionally enqueue a bounded targeted warm-up job if that endpoint behavior is explicitly implemented.

The request must not block for a full provider crawl.

### 9.2 Optional Targeted Warm-Up

A targeted warm-up feature may be implemented because it improves first-run usability without requiring a global prebuilt DB.

If implemented, it must follow these rules:

* It must be explicit.
* It must index one title or a small bounded set of titles.
* It must write results to the DB.
* It must use the same memory-bounded crawler pipeline as background indexing.
* It must not bypass persistence.
* It must not become an uncontrolled live-probing fallback for every request.
* It must expose job/progress state or at least clear pending/completed behavior.
* It must obey concurrency limits.

Example behavior:

```text
User searches title.
Title exists in DB title index.
Details missing.
System may enqueue targeted detail indexing for that title.
Request returns "details indexing queued/in progress" instead of doing full live work inline.
```

---

## 10. Indexing Pipeline

The provider indexing pipeline must be split into stages.

### 10.1 Stage A: Provider Title Index Bootstrap

Purpose:

* Quickly make provider titles searchable from DB.
* Avoid expensive per-title crawling.
* Avoid canonical metadata fetching.
* Avoid episode/detail expansion.

Input:

* Provider alphabet/index page.
* Local provider-specific title index source if configured.

Output:

* `ProviderCatalogTitle` rows.
* `ProviderCatalogAlias` rows.
* Stage status updated to `title_ready`.

Hard requirements:

* Must not construct one huge list of expanded `TitleRecord` objects.
* Must not crawl every episode page.
* Must not query SkyHook/TVDB/canonical metadata.
* Must write to SQLite in small batches.
* Must use direct SQL or short-lived SQLAlchemy sessions to avoid large identity maps.
* Must commit frequently.
* Must be safe to restart.

Recommended default:

* Title index bootstrap may run quickly and with low concurrency because it is not the bottleneck.
* It should complete in seconds to a few minutes, not hours.

### 10.2 Stage B: Provider Detail Enrichment

Purpose:

* Crawl title detail pages.
* Persist episode/language/host-hint data.

Input:

* Title rows from the DB that are missing detail enrichment or are stale.

Output:

* `ProviderCatalogEpisode` rows.
* `ProviderEpisodeLanguage` rows.
* `ProviderTitleIndexState` detail success/failure state.
* Updated detail stage progress.

Hard requirements:

* Must process titles incrementally.
* Must never hold the entire provider detail catalog in memory.
* Must never accumulate a provider-sized Python list of detail results.
* Must use bounded title crawl concurrency.
* Must use a bounded queue or direct row-command pipeline.
* Must write to SQLite continuously.
* Must drop HTML/Soup/provider objects as soon as the title is persisted.
* Must tolerate per-title failures.
* Must not fail the whole provider because one title fails unless failure rate exceeds a configured threshold.
* Must respect retry backoff.

### 10.3 Stage C: Canonical Metadata Enrichment

Purpose:

* Resolve titles/episodes to canonical IDs/mappings.
* Write canonical series and episode mapping rows.

Input:

* Provider titles/details from DB.

Output:

* `CanonicalSeries` rows.
* `CanonicalEpisode` rows.
* `ProviderSeriesMapping` rows.
* `ProviderEpisodeMapping` rows.
* `ProviderMovieMapping` rows if applicable.

Hard requirements:

* Must not use unbounded in-memory caches.
* Must not keep thousands of full show payloads in process-global dictionaries.
* Must use either:

  * a DB-backed canonical metadata cache; or
  * a strict in-memory LRU/TTL cache with a hard max size.
* Must have low bounded concurrency by default.
* Must write results incrementally.
* Must tolerate failed canonical lookups.
* Must not block title readiness.
* Must not block detail indexing unless a specific mapping is required for that operation.

Recommended default:

* Canonical enrichment should be slower and safer than provider title/detail crawling.
* Use conservative concurrency because external metadata APIs can be slow and responses can be large.

---

## 11. Memory-Bounding Requirements

The implementation must satisfy all of the following.

### 11.1 No Provider-Sized In-Memory Results

Forbidden:

```python
all_titles = crawl_entire_provider()
persist(all_titles)
```

Forbidden:

```python
titles: list[TitleRecord] = []
for title in provider:
    titles.append(crawl_title(title))
```

Required:

```text
for each title:
  crawl title
  normalize to compact rows
  write rows to DB
  drop temporary objects
```

### 11.2 Bounded Queues

Any queue between crawler workers and persistence must have a fixed max size.

Default queue size should be small enough to keep RAM bounded.

Recommended defaults:

```env
PROVIDER_INDEX_QUEUE_SIZE=8
PROVIDER_INDEX_WRITER_BATCH_SIZE=32
```

If the queue is full:

* crawler workers must block;
* logs should indicate backpressure at a rate-limited interval;
* the system must not create an unbounded fallback list.

### 11.3 Compact Row Commands Preferred

The queue should not contain large fully expanded objects if avoidable.

Preferred queue item style:

```text
PersistTitleDetailCommand
  provider
  slug
  title fields
  aliases
  compact episode rows
  compact language rows
  compact mapping rows
```

Avoid queueing:

* BeautifulSoup objects;
* raw HTML;
* HTTP responses;
* provider library model objects;
* full external API payloads;
* unnecessary canonical raw payloads.

### 11.4 Drop Temporary Objects

After each title is persisted:

* raw HTML references must be released;
* BeautifulSoup references must be released;
* provider library objects must not be stored globally;
* large canonical payloads must be reduced to compact DB rows;
* SQLAlchemy sessions must be closed;
* batch lists must be cleared.

### 11.5 Bounded Metadata Cache

Process-global metadata caches must be bounded.

Forbidden:

```python
_search_cache = {}
_show_cache = {}
```

unless there is an enforced max size and eviction.

Acceptable:

```python
_search_cache = TTLCache(maxsize=512, ttl=3600)
_show_cache = TTLCache(maxsize=256, ttl=3600)
```

Better:

* DB-backed canonical cache table;
* tiny in-memory LRU hot cache;
* compact cached payloads only.

Cache requirements:

* hard max entry count;
* TTL;
* no full provider-sized retention;
* no full raw API response retention if only a subset is needed;
* clear unit tests for max-size behavior.

### 11.6 SQLAlchemy Session Discipline

Persistence code must avoid long-lived sessions that accumulate thousands of ORM objects.

Required:

* short sessions per batch;
* commit frequently;
* clear/close session after each batch;
* avoid unnecessary `select(...).all()` before deletes;
* prefer direct delete statements for replacing child rows;
* consider `session.expire_all()` or new session per batch if identity map growth is observed;
* avoid query-triggered autoflush surprises by structuring transactions carefully.

---

## 12. SQLite Safety Requirements

SQLite is the default database and must work safely.

### 12.1 WAL and Busy Timeout

The SQLite engine must enable:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=30000;
```

Also configure the DB connection timeout, for example:

```python
connect_args={
    "check_same_thread": False,
    "timeout": 30,
}
```

### 12.2 Single-Writer Discipline

Provider indexing writes must be serialized.

Acceptable implementation options:

1. A single global DB writer queue for catalog indexing.
2. A global provider-index DB write lock.
3. A write coordinator that ensures only one catalog-index write transaction runs at a time.

The implementation must ensure that these write paths do not run concurrently against SQLite:

* title index batch writes;
* detail enrichment batch writes;
* canonical enrichment writes;
* provider status writes;
* title failure-state writes;
* generation cleanup/promotion writes.

If using a global write lock, all catalog indexing writes must use it.

### 12.3 Provider-Level Concurrency Defaults

Default provider-level concurrency must be:

```env
PROVIDER_INDEX_GLOBAL_CONCURRENCY=1
```

This means:

* only one provider refresh/enrichment stage should run at a time by default;
* inside that provider, title-level concurrency may still be greater than one.

This default protects SQLite from cross-provider write contention while preserving useful crawl speed.

### 12.4 Title-Level Concurrency Defaults

Recommended defaults:

```env
PROVIDER_INDEX_CONCURRENCY_ANIWORLD=4
PROVIDER_INDEX_CONCURRENCY_STO=4
PROVIDER_INDEX_CONCURRENCY_MEGAKINO=2
```

These are product defaults, not emergency values.

The implementation must allow environment overrides, but the defaults must be safe for normal self-hosting.

### 12.5 Retry Backoff Must Be Respected

A failed provider or stage must not be retried immediately if `next_refresh_after` or equivalent retry timestamp is in the future.

Required due logic:

```python
if status is running:
    return False

if next_refresh_after exists and next_refresh_after > now:
    return False

otherwise:
    return due according to status/stage rules
```

Forbidden behavior:

```python
if latest_success_at is None:
    return True
```

when a retry timestamp exists.

This is critical to prevent first-bootstrap retry storms.

---

## 13. Worker Timeout and Cancellation Requirements

The current behavior of marking a title as timed out while leaving the underlying worker running is dangerous if the provider is retried quickly.

Required behavior:

1. All HTTP calls used by provider indexing must have hard timeouts.
2. A title timeout must prevent new work from piling up.
3. If a provider/stage fails, the scheduler must not immediately start another run while old workers may still be active.
4. The system must track active provider/stage workers and avoid duplicate runs.
5. `executor.shutdown(wait=False)` must not be used in a way that allows repeated retries while old threads continue consuming memory.
6. If Python threads cannot be safely stopped, the retry/backoff logic must account for that and wait long enough before another run.
7. Timed-out title work must not retain large result objects.

Recommended implementation:

* Prefer bounded waits and clean draining.
* Do not submit new futures after writer failure.
* Cancel pending futures.
* Let running futures finish within timeout.
* Mark provider/stage as failed with retry backoff if shutdown is incomplete.
* Do not reschedule until retry backoff has elapsed.

---

## 14. Scheduler Requirements

The scheduler must support staged indexing.

### 14.1 Stage Ordering

For each provider:

1. Ensure title index exists.
2. Then schedule detail enrichment.
3. Then schedule canonical enrichment.

Do not run expensive detail/canonical enrichment for a provider whose title index is missing.

### 14.2 Fairness

Default behavior should avoid one provider starving all others forever.

Recommended:

* Run one provider/stage at a time by default.
* Choose due work by priority:

  1. missing title index;
  2. targeted warm-up jobs;
  3. missing detail enrichment;
  4. missing canonical enrichment;
  5. scheduled refreshes.

### 14.3 Retry Backoff

Each stage must have a retry timestamp after failure.

Failures must not cause immediate retry loops.

### 14.4 Progress State

The scheduler must expose progress per provider and stage:

* provider;
* stage;
* status;
* total titles when known;
* queued titles;
* active workers;
* completed titles;
* failed titles;
* persisted rows or persisted titles;
* current/recent slug;
* queue depth;
* writer lag;
* last error;
* next retry time;
* whether title index is ready;
* whether details are complete;
* whether canonical mappings are complete.

---

## 15. Database Schema Requirements

The exact schema may reuse existing models where appropriate, but the final system must be able to represent the following states clearly.

### 15.1 Provider Stage Status

There must be durable state for each provider and indexing stage.

Required logical fields:

```text
provider
stage
status
generation
latest_success_generation
started_at
completed_at
latest_success_at
next_retry_after
total_items
completed_items
failed_items
cursor_slug
last_error_summary
updated_at
```

Stages should include at least:

```text
title_index
detail_enrichment
canonical_enrichment
```

This may be implemented as:

* a new `ProviderIndexStageStatus` table; or
* carefully extended existing provider status tables.

The implementation must avoid ambiguous status fields where `bootstrap_completed` means different things in different contexts.

### 15.2 Title Detail State

There must be durable state per provider title for detail indexing.

Required logical fields:

```text
provider
slug
detail_status
detail_attempted_at
detail_success_at
detail_failure_count
detail_last_error_summary
canonical_status
canonical_attempted_at
canonical_success_at
canonical_failure_count
canonical_last_error_summary
updated_at
```

This may extend the existing `ProviderTitleIndexState` table.

### 15.3 Canonical Metadata Cache

If canonical metadata is cached in DB, use tables with compact payloads.

Required logical fields:

```text
cache_key
source
payload_compact_json
created_at
expires_at
last_used_at
```

The payload must be compact and contain only fields required by AniBridge mapping.

Do not store unnecessarily large raw responses.

### 15.4 Generation Visibility

The request path must only serve rows from a generation considered visible/active for the relevant data type.

If title index generation is ready but details are not complete:

* title search may use title rows;
* detail-dependent endpoints must know details may be incomplete.

Do not mark a provider as fully ready just because title rows exist.

---

## 16. Persistence Requirements

### 16.1 Replace Rows Efficiently

For per-title child rows such as aliases, episodes, languages, and mappings:

* delete old rows for that provider/title/stage;
* insert new rows;
* do not first load all old rows into Python unless needed.

Avoid:

```python
session.exec(select(Child).where(...)).all()
session.exec(delete(Child).where(...))
```

Prefer:

```python
session.exec(delete(Child).where(...))
```

### 16.2 Batch Size

Default writer batch size:

```env
PROVIDER_INDEX_WRITER_BATCH_SIZE=32
```

Rules:

* batch size must be configurable;
* batch must be small enough to avoid large memory spikes;
* batch must be large enough to avoid one transaction per tiny row;
* writer must flush by size and by time.

### 16.3 Failure Recording

Title failures must be recorded durably.

However, failure recording must not bypass SQLite write serialization.

All failure-state writes must go through the same write coordinator or lock.

### 16.4 Promotion

For stages that use generations:

* write into staging generation;
* mark stage generation successful only after successful completion;
* do not expose partial full-stage state as complete;
* if refresh fails, keep previous successful generation visible;
* clean up abandoned staging generation on restart or next run.

For progressive detail enrichment, per-title successful writes may become visible if the API clearly treats detail completeness as per-title/progressive. This must not falsely report provider-wide `detail_ready`.

---

## 17. Configuration Defaults

The following default values must be safe for normal users.

```env
PROVIDER_INDEX_GLOBAL_CONCURRENCY=1

PROVIDER_INDEX_CONCURRENCY_ANIWORLD=4
PROVIDER_INDEX_CONCURRENCY_STO=4
PROVIDER_INDEX_CONCURRENCY_MEGAKINO=2

PROVIDER_INDEX_QUEUE_SIZE=8
PROVIDER_INDEX_WRITER_BATCH_SIZE=32
PROVIDER_INDEX_WRITER_FLUSH_SECONDS=1.0

PROVIDER_INDEX_TITLE_TIMEOUT_SECONDS=45
PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT=20.0
PROVIDER_INDEX_BACKPRESSURE_LOG_SECONDS=15.0

CANONICAL_INDEX_CONCURRENCY=2
CANONICAL_CACHE_MEMORY_MAX_SEARCH=512
CANONICAL_CACHE_MEMORY_MAX_SHOW=256
CANONICAL_CACHE_TTL_SECONDS=3600
```

If exact variable names differ, implement equivalent settings and document them.

Invalid environment values must be sanitized.

For example:

* concurrency less than 1 becomes 1;
* queue size less than 1 becomes 1;
* negative timeout uses default;
* invalid float/int logs warning and uses default.

---

## 18. Observability Requirements

Logs must make indexing behavior understandable without being spammy.

Required log events:

1. Scheduler startup with effective safe defaults.
2. Provider title index start.
3. Provider title index total loaded.
4. Title index batch persisted.
5. Title index ready.
6. Detail enrichment start.
7. Detail enrichment progress heartbeat.
8. Detail enrichment batch persisted.
9. Queue backpressure warning, rate-limited.
10. Per-title failure warning, rate-limited or summarized if noisy.
11. Canonical enrichment start.
12. Canonical enrichment progress.
13. Canonical cache hit/miss summary, not every request at info level.
14. Stage completed.
15. Stage failed with retry timestamp.
16. Stale staging generation cleanup.
17. SQLite lock retry/busy warning if encountered.
18. Memory budget warning if optional memory instrumentation is implemented.

Health endpoint should expose provider/stage progress.

---

## 19. Acceptance Criteria

The implementation is complete only if all criteria below are satisfied.

### 19.1 Functional

* Fresh install starts without a provider-derived snapshot.
* DB schema migrates successfully.
* Title index stage runs before detail/canonical enrichment.
* Title index stage writes searchable provider titles.
* App can report partial catalog readiness.
* Detail enrichment runs in background.
* Canonical enrichment runs in background or as a bounded follow-up stage.
* Request handlers read from DB.
* No normal request triggers a full provider crawl.
* Failed stages respect retry backoff.
* Interrupted staging generations are cleaned up or handled explicitly.

### 19.2 Memory

* No provider-scale list of expanded title records exists.
* Global canonical metadata caches are bounded or DB-backed.
* Queue sizes are bounded.
* SQLAlchemy sessions do not retain provider-scale identity maps.
* Large parse objects are not stored beyond a single title's processing.
* Default indexing should be designed to stay below 1 GB RAM.

### 19.3 SQLite

* WAL mode is enabled.
* Busy timeout is configured.
* Provider indexing writes are serialized.
* Cross-provider writer contention is avoided by default.
* `database is locked` should not be normal during first bootstrap.
* If SQLite lock contention still occurs, it must retry or fail gracefully with backoff, not start a retry storm.

### 19.4 User Experience

* Normal users do not need to tune concurrency.
* First startup does not require waiting for full provider detail/canonical enrichment.
* Basic title catalog readiness happens quickly.
* Progress is visible.
* Full enrichment continues automatically.

### 19.5 Legal/Risk Boundary

* No official provider-derived catalog DB/JSON is shipped.
* No automatic download of project-hosted provider-derived catalog data exists.
* Local computation remains the default.

---

## 20. Suggested Implementation Plan

### Step 1: Fix scheduler retry logic

* Ensure retry timestamps are respected even during first bootstrap.
* Remove logic where `latest_success_at is None` forces immediate due status despite retry backoff.

### Step 2: Add SQLite write safety

* Add WAL, synchronous NORMAL, busy timeout.
* Add a global catalog-index write coordinator or lock.
* Ensure all catalog indexing writes use it.

### Step 3: Introduce explicit stage status

* Add or extend DB models to represent:

  * title index status;
  * detail enrichment status;
  * canonical enrichment status.
* Add migrations.
* Update health endpoint.

### Step 4: Split title indexing from detail crawling

* Implement fast provider title index stage.
* Persist titles/aliases only.
* Mark title-ready separately from full-ready.

### Step 5: Rework detail enrichment to operate from DB rows

* Query due title rows in small chunks.
* Crawl only those titles.
* Persist each result or small batch.
* Drop temporary objects.

### Step 6: Bound or persist canonical caches

* Replace unbounded dict caches.
* Prefer DB-backed compact canonical cache.
* If DB-backed cache is too large for this task, use strict TTL LRU cache with hard max sizes.

### Step 7: Split canonical enrichment from provider detail crawl

* Avoid canonical API calls during initial title bootstrap.
* Prefer canonical enrichment after details are persisted.
* Make it independently bounded and retryable.

### Step 8: Add progress and tests

* Add unit tests for:

  * scheduler due/backoff logic;
  * bounded cache max size;
  * no immediate retry after failure;
  * title stage does not call detail crawler;
  * SQLite write coordinator is used.
* Add integration tests for:

  * fresh DB startup state;
  * title-ready before full-ready;
  * failed provider retry backoff;
  * detail enrichment persists incrementally.

---

## 21. Explicit Implementation Constraints

The implementation must not:

* add official provider-derived catalog assets;
* require users to configure low concurrency manually;
* block startup until all provider details are indexed;
* use unbounded global caches;
* use unbounded queues;
* store raw HTML or BeautifulSoup objects in queues;
* allow multiple provider writers to fight over SQLite by default;
* retry failed bootstrap stages immediately;
* perform full provider live crawling inside request handlers;
* mark full catalog readiness when only title index readiness exists.

---

## 22. Desired Final Behavior Example

Fresh install:

```text
Application startup.
Database migrations complete.
Provider catalog scheduler started.
aniworld.to title_index: running
s.to title_index: pending
megakino title_index: pending
Application HTTP server ready.
```

After title index for one provider:

```text
aniworld.to title_index: ready, 2421 titles
aniworld.to detail_enrichment: running, 37/2421 titles
catalog_title_ready=true
catalog_full_ready=false
```

User searches:

```text
Search query reads title DB.
Matching title is found.
If detail rows exist, return detail-backed result.
If detail rows do not exist, return clear "details indexing" state or enqueue explicit targeted warm-up.
```

Background continues:

```text
aniworld.to detail_enrichment: running
queue_depth=3
writer_lag=2
memory remains bounded
```

Failure:

```text
s.to detail_enrichment failed: network/provider issue
next_retry_after=...
scheduler does not retry before next_retry_after
previous visible data remains available
```

Completion:

```text
aniworld.to title_index: ready
aniworld.to detail_enrichment: ready
aniworld.to canonical_enrichment: ready
aniworld.to full_ready=true
```

---

## 23. Summary

The correct solution is not to lower all concurrency to one and not to ship a prebuilt provider catalog.

The correct solution is:

```text
local progressive indexing
+ fast title index bootstrap
+ background detail enrichment
+ background canonical enrichment
+ strict memory bounds
+ bounded caches
+ SQLite single-writer discipline
+ WAL/busy timeout
+ retry backoff
+ DB-only request path
```

This preserves the self-hosted legal/risk boundary while making AniBridge practical for normal users.
