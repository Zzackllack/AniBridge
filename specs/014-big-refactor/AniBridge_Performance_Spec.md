# AniBridge Performance Spec

Date: 2026-03-17  
Status: Draft  
Scope: Torznab search path, live probing, provider fallback, metadata extraction, season search, caching strategy

---

## 1. Purpose

This document captures the key performance findings and optimization directions identified during a deep review of AniBridge's current search/probing architecture.

Primary goal:

- reduce end-to-end latency for Torznab search requests
- reduce timeout risk for Sonarr / Prowlarr
- preserve high-quality release titles (including quality info such as resolution / codec)
- improve scalability as more providers and features are added

This spec is intentionally performance-focused. It does **not** attempt to redesign the whole product.

---

## 2. Executive Summary

### Main conclusion

AniBridge is currently limited far more by **external I/O and live probing strategy** than by Python or FastAPI themselves.

The dominant latency drivers are:

1. live provider / hoster resolution
2. repeated provider fallback chains
3. `yt-dlp` metadata probing for quality extraction
4. strict season-search fallback probing on cold cache
5. serial execution of many external steps inside a single request

### Most important architectural insight

The current search path is too close to:

> "prove everything live during the request"

It should move toward:

> "use cache / metadata / history first, then confirm only the minimum necessary live"

### Core principle going forward

Do **not** remove quality extraction.  
Instead:

- invoke it less often
- invoke it later
- invoke it only for top candidates
- cache and reuse its results aggressively

---

## 3. Key Findings

### 3.1 Python / FastAPI are not the primary bottleneck

Python and FastAPI are not currently the main reason requests get slow.

The biggest latency costs come from:

- blocking external HTTP requests
- provider / hoster probing
- redirects / failures / retries
- `yt-dlp` metadata extraction
- serial fallback traversal across multiple providers

Implication:

- a rewrite to Rust / Zig / C++ would likely have a poor ROI right now
- architecture and request planning matter much more than raw language speed
- a better Python architecture will outperform a worse native-language rewrite

### 3.2 The most expensive step is live probing + metadata extraction

The heaviest runtime step is:

- provider / hoster live resolution
- followed by `yt-dlp extract_info(download=False)` quality probing

This is expensive because it depends on:

- remote sites
- hoster responsiveness
- redirects
- anti-bot / rate limits
- unstable embeds / direct links

Implication:

- this work must be reduced, narrowed, cached, and scheduled more carefully

### 3.3 The current provider fallback path is too expensive

Current behavior effectively risks repeated provider traversal:

- the probing path iterates over candidate providers
- then nested fallback logic may iterate provider order again internally

This can produce a practical worst case closer to:

- provider count × provider count
- multiplied by languages
- multiplied again by episodes in season search

Implication:

- adding more providers without refactoring the probe path will increase latency disproportionately
- current scaling risk is architectural, not just operational

### 3.4 Strict season search is the most dangerous timeout path

The most timeout-prone request shape is:

- `tvsearch`
- season-search mode
- cold cache
- fallback probing enabled
- multiple episodes
- multiple candidate languages
- multiple providers

This can trigger a very large number of serial external operations before a response is returned.

Implication:

- normal online season-search should avoid deep synchronous fallback probing wherever possible

### 3.5 Local DB and XML generation are not the main problem

The following are comparatively cheap:

- SQLite reads / writes
- cached availability lookups
- cached language lookups
- RSS / XML building
- release title formatting
- magnet construction

Implication:

- optimizing DB micro-costs will not materially fix request latency
- the external live probe path is the true hotspot

### 3.6 Existing caching direction is good, but not yet strong enough

AniBridge already has useful caching concepts:

- title / slug index caching
- availability caching
- season metadata usage
- STRM mapping cache

These are the right direction.

However, the system still falls back into too much live work when caches miss.

Implication:

- caching must expand from "availability only" toward:
  - provider success memory
  - negative cache
  - quality cache
  - in-flight request coalescing

### 3.7 Quality extraction cannot be removed

Quality extraction is needed because AniBridge uses the extracted values to construct useful release titles for Sonarr / Prowlarr.

Therefore, quality extraction must remain part of the system.

However, the current problem is not that quality exists — it is that quality extraction is performed too broadly and too early.

Implication:

- keep quality extraction
- move it later in the decision pipeline
- cache it separately
- avoid running it for every candidate

### 3.8 More workers do not automatically solve request latency

More Uvicorn / FastAPI workers help with:

- throughput
- handling more simultaneous requests

They do **not** automatically make a single request much faster.

The current expensive path is still mostly synchronous and blocking inside each request.

Implication:

- infra-level parallelism alone is not enough
- request-internal planning matters more

### 3.9 Async alone is not the first fix

A full async rewrite of the probe path could help eventually, but it is probably not the first best move because:

- current HTTP/probe stack is largely blocking
- provider libs are not designed around async
- `yt-dlp` is not naturally a simple async drop-in
- a partial async conversion may add complexity without fixing the real issue

Implication:

- first optimize the execution strategy
- then consider async only if the whole I/O model is ready for it

---

## 4. Primary Risks

### 4.1 Request timeout risk

Timeouts can happen when one request accumulates too many serial external operations.

Risk increases with:

- more providers
- more languages
- season-search
- cold cache
- unstable hosters
- repeated probing of recently failed providers

### 4.2 Growth risk as provider count increases

Without refactoring:

- every additional provider increases the fallback search space
- more providers can harm tail latency even if most are rarely useful

### 4.3 Feature growth risk

Upcoming features like:

- Web UI
- more operational visibility
- more providers
- more metadata logic

will increase pressure on the same hot path if the architecture remains request-live-probe-centric.

---

## 5. Performance Design Principles

The following principles should guide future work:

1. **Cache-first, probe-second**
2. **Cheap evidence before expensive confirmation**
3. **Rank candidates before probing**
4. **Extract quality only for top candidates**
5. **Remember both successes and failures**
6. **Avoid duplicate work across concurrent requests**
7. **Move expensive refresh work into background jobs when possible**
8. **Bound concurrency carefully**
9. **Prefer predictable latency over maximum theoretical completeness**
10. **Do not sacrifice release title quality, but obtain it more selectively**

---

## 6. Recommended Target Model

The request path should gradually move toward this shape:

1. resolve title / slug
2. load cached availability / metadata
3. rank likely languages / providers
4. do cheap availability confirmation if needed
5. run expensive quality extraction only for the best candidate(s)
6. build final release title
7. write back results to cache
8. schedule background warmup if the request had to do expensive work

---

## 7. Optimization Recommendations

### 7.1 Split probing into cheap and expensive phases

Introduce two explicit phases:

#### Cheap Probe

Purpose:

- detect whether episode / language / provider is likely available

Should avoid:

- `yt-dlp`
- expensive full metadata extraction where possible

#### Expensive Probe

Purpose:

- obtain final `height`, `vcodec`, and any title-relevant details

Should run only:

- for the top-ranked candidate
- or, at most, the top 1–2 candidates

#### Benefit

- keeps quality extraction in the system
- reduces total number of expensive metadata calls

### 7.2 Add provider success memory

Track provider performance history per content shape.

Suggested dimensions:

- site
- slug
- language
- optional season
- optional episode range / recent pattern

Suggested metrics:

- last successful provider
- last success timestamp
- success count
- failure count
- average latency
- last known quality result

Use this to rank provider order dynamically instead of relying only on static `PROVIDER_ORDER`.

#### Benefit

- fewer failed probes
- faster convergence to likely-good providers

### 7.3 Add negative cache

When a provider fails for a specific content combination, cache that failure temporarily.

Suggested examples:

- timeout
- 429
- 403
- embed missing
- language unavailable

Suggested TTLs:

- short TTL for transient network failure
- medium TTL for repeated provider issues
- longer TTL for clearly unavailable language combinations

#### Benefit

- prevents repeated immediate re-probing of obviously bad paths

### 7.4 Cache quality results separately

Availability cache and quality cache should be conceptually separated.

Suggested quality cache fields:

- site
- slug
- season
- episode
- language
- provider
- height
- vcodec
- quality_checked_at
- source
- confidence

#### Benefit

- preserve high-quality release titles
- avoid repeatedly calling `yt-dlp` for the same successful candidate

### 7.5 Use stale-while-revalidate for quality

If a cached quality result exists and is still "good enough":

- use it immediately for the response
- refresh it in the background if needed

This is especially useful for search requests where a slightly older quality signal is much better than blocking on a fresh expensive probe.

#### Benefit

- lower latency
- still keeps cache fresh over time

### 7.6 Introduce in-flight request coalescing (single-flight)

If multiple requests are probing the same target simultaneously, they should share the same in-flight work.

Suggested coalescing key:

- site
- slug
- season
- episode
- language
- request mode

#### Benefit

- prevents duplicated expensive work
- flattens latency spikes under bursty Sonarr / Prowlarr activity

### 7.7 Use bounded parallelism for final candidate confirmation

Parallelism can help, but it must be tightly bounded.

Suggested model:

- only 2 provider confirmations in parallel
- winner takes all
- ignore / cancel remaining work once success is confirmed

Avoid:

- broad unbounded parallel probing across providers × languages × episodes

#### Benefit

- reduces tail latency without overwhelming upstream hosters or local resources

### 7.8 Make normal season-search much more metadata/cache first

Season search should prefer:

- metadata-derived episode numbers
- cached known episode numbers
- cached language information

Strict fallback probing should be minimized on the synchronous online path.

If deeper discovery is needed:

- return partial results quickly
- schedule background warmup / refresh

#### Benefit

- reduces the highest-timeout search mode

### 7.9 Move expensive warming into background jobs

Use background infrastructure to warm likely-needed data.

Good warmup targets:

- newly requested titles
- currently airing series
- recently failed titles
- next episode guesses
- titles with stale but frequently used quality cache

#### Benefit

- shifts cost out of the request path
- improves future request latency

### 7.10 Remove nested provider fallback duplication

Refactor the probing pipeline so provider iteration happens in exactly one clearly controlled layer.

Desired separation:

- resolve direct URL for exactly one provider
- probe exactly one resolved URL
- ranking / fallback policy handled by the caller

This avoids repeated nested traversal of the same provider list.

#### Benefit

- better predictability
- easier reasoning
- easier future parallelization

---

## 8. Recommended Refactor Direction

### 8.1 Short-term priority

1. remove nested provider fallback duplication
2. separate cheap probe from expensive quality probe
3. add provider success memory
4. add negative cache
5. cache quality results independently

### 8.2 Mid-term priority

1. add single-flight request coalescing
2. add bounded parallel provider confirmation
3. make normal season-search metadata/cache-first by default
4. add stale-while-revalidate quality behavior

### 8.3 Later priority

1. background warming pipeline
2. confidence-based result model
3. richer provider ranking heuristics
4. possible async modernization if still justified after architectural cleanup

---

## 9. What should NOT be done

The following would likely be bad directions:

- removing quality extraction entirely
- returning generic low-information release titles
- solving the problem by only adding more Uvicorn workers
- rewriting the whole project to Rust / C++ before fixing architecture
- introducing unbounded per-request concurrency
- expanding provider count without first fixing probe-path scaling

---

## 10. Suggested Implementation Concepts

This section is intentionally lightweight and non-binding.

Potential new internal concepts:

- `cheap_probe(...)`
- `quality_probe(...)`
- `rank_candidate_providers(...)`
- `get_last_success_provider(...)`
- `cache_negative_probe(...)`
- `get_cached_quality(...)`
- `refresh_quality_in_background(...)`
- `singleflight_probe(key, fn)`
- `confirm_top_candidates_parallel(...)`

Potential new persistence concepts:

- provider stats table
- negative probe cache table
- quality cache table
- background warmup queue entries

---

## 11. Success Criteria

The work should be considered successful if it produces the following outcomes:

### Functional

- release titles remain high quality for Sonarr / Prowlarr
- no regression in compatibility

### Performance

- fewer `yt-dlp` calls per request
- fewer provider attempts per request
- lower timeout frequency
- lower tail latency on season-search
- improved warm-cache hit rates

### Operational

- easier reasoning about probe behavior
- easier debugging of why a provider was chosen or skipped
- scalable path for future provider additions

---

## 12. Final Summary

AniBridge does **not** primarily need a language rewrite.  
It primarily needs a more selective, cache-aware, and history-aware probing architecture.

The key move is:

- keep quality extraction
- stop treating it as mandatory for every intermediate candidate
- compute it later
- reuse it aggressively
- reduce repeated provider failures
- reduce duplicate in-flight work
- keep the online request path fast and predictable

That is the highest-leverage performance path forward.
