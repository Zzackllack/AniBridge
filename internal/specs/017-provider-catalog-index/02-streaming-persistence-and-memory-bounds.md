# 017 Provider Catalog Index - Streaming Persistence and Memory Bounds

## Goal

Redesign provider bootstrap and refresh execution so AniBridge can index large providers without unbounded memory growth, long silent stalls, or container restarts under realistic first-run load.

The preferred solution is to stream crawled provider results into SQLite continuously instead of buffering a full provider crawl in memory and only persisting at the end.

## Problem Statement

The current provider indexing architecture is correct in spirit but too memory-heavy in practice for large catalogs such as `s.to`.

Today the refresh flow for AniWorld and `s.to` is effectively:

1. load the provider title index
2. crawl many titles in parallel
3. accumulate all crawled `TitleRecord` results in memory
4. persist the full provider result set only after crawling is complete
5. mark the refreshed generation as current

This creates a large in-memory buffer whose size grows with:

- total title count
- total episode count across those titles
- alias and language metadata
- canonical mapping payloads and intermediate metadata
- number of in-flight worker results

Lowering concurrency only slows the rate of growth. It does not remove the underlying architectural pressure.

## Observed Failure Mode

During first bootstrap runs, memory usage can climb steadily into multiple gigabytes before the provider refresh finishes.

Typical characteristics:

- memory rises roughly with crawl progress instead of staying bounded
- the process may appear healthy for a long time and then die abruptly
- large providers such as `s.to` are the worst case because they have many titles and many episodes per title
- progress visibility degrades because the system is still "working" while holding more and more buffered state

This behavior is more consistent with whole-provider result buffering than with a classic steady-state memory leak.

## Root Cause

The main issue is architectural buffering.

AniBridge currently keeps too much expanded provider state alive at once:

- full crawled provider results
- per-title episode lists
- canonical enrichment results
- temporarily timed-out worker state that may still be finishing in background threads

The memory profile therefore scales with provider size instead of with a small bounded working set.

## Proposed Direction

Replace the current "crawl everything, then persist everything" flow with a streaming provider pipeline:

1. discover provider titles
2. crawl titles in parallel
3. emit each completed title result into a bounded queue
4. persist queued results continuously into a staging generation
5. keep serving the previous successful generation during the refresh
6. flip the provider's current successful generation only after the full staged refresh completes successfully

This preserves refresh consistency while bounding memory growth.

## Required Architecture Changes

### Provider crawl contract

Provider crawl code should stop returning one large `list[TitleRecord]` for the full provider refresh.

Instead, each provider crawler should expose a streaming-oriented contract that:

- yields or submits one completed title result at a time
- reports title discovery totals as soon as they are known
- reports per-title progress as results are completed
- allows the orchestrator to apply backpressure when the persistence side falls behind

The contract may be implemented as:

- a generator that yields title results
- a callback-based emitter
- a worker pool that pushes into a queue owned by the indexer

The specific API shape is less important than the bounded-memory behavior.

### Dedicated writer path

Use one dedicated persistence path per provider refresh.

Recommended structure:

- N crawler workers per provider
- 1 dedicated DB writer thread or task per provider refresh
- 1 bounded in-memory queue between crawl workers and the writer

The writer is responsible for:

- inserting or replacing provider title rows for the staging generation
- inserting aliases, episodes, language availability, and mappings for the staging generation
- updating per-provider progress counters
- committing in small batches

SQLite write contention should remain controlled by avoiding many concurrent writers for the same provider refresh.

### Staging generation semantics

Do not publish partially refreshed provider state to the request path.

Required behavior:

- write new rows into a staging generation while the previous successful generation remains active
- keep `latest_success_generation` unchanged until the staged refresh fully succeeds
- if the refresh fails midway, keep serving the previous successful generation
- if no successful generation exists yet, keep bootstrap gating behavior intact

This is the key consistency rule that allows streaming persistence without exposing partial catalogs as complete.

## Queue and Backpressure Requirements

The queue between crawlers and the writer must be bounded.

Required properties:

- configurable maximum queue size
- producer backpressure when the queue is full
- clear logs when crawlers are blocked on persistence backpressure
- no unbounded fallback list or hidden in-memory spillover

The queue size should be chosen so that:

- the writer has enough buffered work to stay busy
- memory remains predictably bounded even for the largest provider

The implementation should prefer slowing crawl throughput over allowing queue growth beyond the configured bound.

## Persistence Semantics

Per-title persistence should happen as soon as the title result is available.

Required behavior:

- persist each title independently into the staging generation
- commit frequently enough that long refreshes make visible forward progress
- make restarts and crash recovery able to resume or restart from a known staging state

Implementation guidance:

- use small batched transactions rather than one transaction per episode row
- clean up abandoned staging generations on the next startup or refresh attempt
- keep provider status and cursor state aligned with what has already been durably written

## Failure and Recovery Semantics

### Title-level failures

One bad title must not stall or invalidate the whole provider refresh by default.

Required behavior:

- timed-out or failed titles should be logged with provider, slug, and reason
- the refresh should continue unless the failure rate crosses a configured threshold
- skipped titles should remain absent from the new generation unless explicitly retried successfully later

### Refresh-level failures

If the full provider refresh cannot complete:

- do not promote the staging generation
- do not delete the currently served successful generation
- persist a clear provider-level error summary
- make the next run able to clean up or reuse stale staging rows safely

### Restart recovery

On startup, AniBridge should detect interrupted staging refreshes and handle them explicitly.

Required behavior:

- log that an interrupted staging generation was found
- mark the prior run as interrupted
- either delete the abandoned staging generation or restart it from a supported checkpoint

Version one may choose cleanup-and-restart over true mid-provider resume if that is simpler and more reliable.

## Progress and Observability

The new design must improve visibility, not reduce it.

Required progress signals:

- title discovery started
- title discovery completed with total count
- crawl progress as `completed/total` and percent when total is known
- queue depth and writer lag
- persistence progress as `persisted/total`
- generation promotion success
- explicit staging cleanup or abandonment messages

The health surface should remain able to report:

- provider phase
- processed titles
- total titles when known
- current slug or recently active slug
- last error summary
- whether the provider is serving an older successful generation while a new one is building

## Memory and Performance Requirements

The redesigned flow must keep memory bounded primarily by:

- worker concurrency
- queue size
- one-title working set
- writer batch size

It must not scale memory roughly linearly with full provider size.

Additional recommendations:

- drop intermediate canonical payloads as soon as they have been normalized and written
- avoid keeping large per-title objects alive after queue submission
- avoid background timeout wrappers that leave many unreachable or still-running worker threads alive for long periods

Concurrency should remain configurable, but the implementation must not depend on low concurrency to stay within safe memory limits.

## Implementation Guidance

### Suggested rollout order

1. introduce staging-generation streaming persistence behind the existing provider status model
2. convert AniWorld and `s.to` from full-list return values to streaming title emission
3. keep Megakino aligned with the same orchestration contract where practical
4. add queue depth, writer lag, and staging-generation logging
5. tighten cleanup of abandoned staging generations and interrupted runs

### Acceptable simplifications

The first implementation does not need:

- fully parallel SQLite writers for the same provider
- cross-provider shared queue infrastructure
- perfect mid-run resume at arbitrary title boundaries

What matters first is:

- bounded memory
- continuous persistence
- atomic generation promotion
- clear recovery behavior

## Non-Goals

- replacing SQLite
- exposing partial staging rows to the request path as if they were ready
- maximizing raw crawl speed at the expense of stability
- introducing a complicated distributed job system

## Selected Decisions

- streaming provider results into SQLite is the selected solution
- a bounded queue with backpressure is required
- one dedicated writer path per provider refresh is preferred over many parallel SQLite writers
- staging generations must remain invisible to the request path until refresh success
- old successful generations must remain served during replacement refreshes
- cleanup-and-restart is acceptable for interrupted staging generations in version one
- lowering crawl concurrency is not considered a real fix for the memory issue, only a temporary mitigation
- progress reporting must include real counts and writer-state visibility, not only long-running heartbeat messages
