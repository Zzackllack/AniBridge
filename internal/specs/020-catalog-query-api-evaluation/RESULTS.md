# Bounded metadata API evaluation

2026-10-05. **Recommendation: adopt the request API as the next architecture,
subject to the explicit decisions below. Keep the current implementation until
that decision and its replacement specification are accepted.** This evaluation
approves neither a hosted endpoint nor transmission of real user searches.

The measured API cost is small enough to justify changing distribution direction.
Snapshots retain the better offline/privacy properties and lower uncached query
latency. The API avoids each consumer downloading and validating an entire changed
catalog, at the cost of server query work and incomplete offline coverage.
Neither approach fixes collection freshness, unresolved mappings or provider access.

## Inputs and proof boundary

- Base `88b8796`, branch `zzackllack-aux/catalog-query-api-evaluation`; the brief
  and prior implementation history are preserved. Production routes/configuration,
  jobs, media resolution and extraction are unchanged.
- Read 019's architecture, collector/publication, consumer/search, identity/schema,
  local jobs contracts, evidence and review, plus both referenced chats. Current
  evidence records both 24-hour attempts as failed; the second timeout remains
  unexplained.
  C4/M0–M4 remain incomplete. No continuation of that experiment occurred here.
- Synthetic compact schema2, **50,000 titles, 50,000 aliases, 1,000,000 entities
  and canonical episodes, 2,000,091 → 2,000,092 observed language releases**.
  Source `synthetic-a`, AniWorld only at scale. Small contracts additionally
  exercise all three providers, movie records and both schema versions.
- Revisions 91/92 are copies of already-admitted artifacts from
  `/tmp/anibridge-sustained-24h-renewal-v2/consumer/catalog`. Verify the synthetic
  signatures and both copies' whole-file digests. Original DB/artifact bytes are
  never changed. Each SQLite is **1,050,587,136 bytes**; changed compressed size
  is **257,860,626 bytes**. Identities and first-seen dates come from these inputs.
- About 20 GiB host free disk before preparation; **17,366,085,632 bytes** free
  after the two owned copies. Host had about 373 MB free RAM and 3.48 GB inactive
  pages; the isolated Docker workload was capped at **1 GiB, 2 CPUs, no swap**.
  No networking outside container loopback and no parallel experiment.
- Existing installed API image
  `sha256:c3444c9aad028a90b3dab7998c325b401481e71f2b7a6c2236d70a7afd7d80fe`.
  Python 3.14.8, SQLite 3.46.1, FastAPI 0.135.1, Pydantic 2.12.5, HTTPX 0.28.1,
  Uvicorn 0.42.0. Installed query module hash equals checkout source exactly.
  No wheel, lockfile, runtime dependency or new app was added for this experiment.
- Eight concurrent clients, 16 repetitions of eight fixed cases: title, alias,
  external ID, canonical season, recent pages 0/100, unknown ID, missing title.
  Every architecture receives identical cases, counts and result limits.
  Synthetic query clock is `1800080000`; cache outage ages use explicit simulated
  times, while HTTP latency uses real monotonic elapsed time.
- Latest complete run **8.342 seconds**; external stop at 180 seconds. Three
  short complete diagnostic runs, sequentially, never endurance evidence. Initial
  harness shutdown failed because Uvicorn propagated SIGTERM; replacing that with
  an explicit shutdown event fixed the harness without changing query logic.
  Earlier runs varied (API p95 146.346/150.505 ms versus 119.972 ms in the final
  run). Host/cache variation is not a measured algorithmic speedup.

Raw final measurements, actual SQL plans, requests, identities of input artifacts
and source hashes are in [evidence/results.json](evidence/results.json).

## Measured comparison

Each row below covers 128 logical queries. API timings include HTTP, validation
and cache writes. Snapshot timings cover the unchanged current SQL against a
read adapter with an empty local overlay, excluding production HTTP/RSS encoding
and actual Store activation/lease overhead. Neither path includes provider access.

| Path | Remote requests | Response body bytes | p50 / p95 / p99 (ms) |
| --- | ---: | ---: | --- |
| Local snapshot SQL | 0 | 0 | 15.341 / 89.420 / 96.631 |
| API, cache bypass | 128 | 4,489,504 | 83.159 / 119.972 / 172.691 |
| API, 40-ms injected delay | 128 | 4,489,504 | 117.532 / 147.039 / 161.216 |
| API, cold then cached | 16 | 715,568 | 2.863 / 91.272 / 176.572 |

The injected 40 ms is a fixed application response delay, not a real WAN or
10-Mbit/s bandwidth shaper. No TLS handshake, Internet loss or cold host-page-cache
measurement is claimed. Headers/TLS and compressed response traffic are excluded.

The title/alias/ID cases and the **whole 20-episode/two-language season** each
return 40 records in **one HTTP request, 31,217 bytes**. A recent page of 100
records is 77,546 bytes (page two 77,520); a true missing match is 329–331 bytes.
Larger seasons use bounded 100-record pages, never one request per episode.
The average measured response is 35,074.25 bytes; average JSON request is 94.125.

The cache phase achieved **112/128 hits (87.5%)**. Hits alone: p50 **2.763 ms**,
p95 **5.860 ms**, p99 **6.284 ms**. Cold misses dominate the combined tail.
Eight distinct requests produced sixteen fetches because concurrent first misses
are not coalesced. This is recorded overhead, not hidden behind an assumed hit
rate; `client.py` has a TODO for bounded same-key coalescing before adoption.
Raw request bodies were 1,510 bytes in this phase, 12,048 without caching.

Server CPU for the isolated delayed phase: **1,018 ms /128 responses**, peak
RSS **117,239,808 bytes**. The other server lifetime includes the cached and update
phases: **3,524 ms /401 responses**, peak RSS **120,590,336 bytes**. These are
whole-process CPU including startup/shutdown, not per-SQL timings. Consumer
process peak RSS was **135,852,032 bytes**; entire container high-water usage
**185,876,480 bytes**. Snapshot SQL used 777 ms CPU for 128 queries (see raw
result for its exact value if reproducing). Short throughput is approximately
128 / measured wall time; it is not a sustained capacity promise or a 10k-user
load test. Collector CPU contention is unmeasured.

Observed local cache files: **299,008 bytes** after the repeated cached workload;
307,200 after cache-bypass refreshes. Fixed limits: 128 entries, 2 MiB payload,
16 MiB SQLite pages. A byte-pressure test inserts 100 values and preserves only
the two newest values allowed by its smaller test cap. Cache hits revalidate
stored records; corruption cannot become last-good output.

Actual `EXPLAIN QUERY PLAN` from the reused candidate/count/result SQL shows
`title_search`, `alias_search`, `canonical_lookup`, `entity_title`,
`canonical_episode_entity`, and `release_recent`. There is no provider-sized
Python scan or a complete parallel search engine. The supplied recent workload's
oldest release falls inside its window, so the existing validated row-count
shortcut applies. A heavily filtered window requiring a large SQL count has not
been characterized here.

## Updates, parity and failures

Both paths execute 256 concurrent queries while an atomic pointer switches from
91 to 92. Snapshot p95 **95.117 ms**, API p95 **103.385 ms**. **Zero query errors
and zero mixed-version responses**; snapshot observed 50 old/206 new responses,
API 23 old/233 new. Every response equals the appropriate complete version,
including total, ordering, source/canonical coordinates, language and digest.
Pointer replacement took 1.345 ms for snapshots and 0.682 ms for the API.

This is replacement of prebuilt immutable catalogs, not collection/export under
query load, crash admission or shared retention cleanup. Each request holds its
selected version until completion; this prototype never deletes either input.
Production must connect existing reader leases to worker quota/cleanup rather
than assume Linux unlink semantics work everywhere. Cross-page requests can
straddle updates, like existing offset RSS; overlap and GUID deduplication remain
necessary. No multi-page snapshot transaction or cursor framework was invented.

The service runs the actual `app.catalog.search.query` SQL. The allowlisted wire
projection excludes magnets, modes/categories, media URLs, job tokens, credentials,
private worker/user tables and quality observations. Local `rss()` reconstructed
from metadata is byte-equal on the small provider/movie/schema contract cases.
Unmapped canonical requests and duplicate external-ID associations remain empty
and unresolved; ordinary source searches keep unmapped records marked partial.
Known source ordinals never become guessed canonical numbering. Positively
observed subtitle tokens do not imply an audio language. Stable GUID/infohash and
native coordinates survive a post-fetch local mapping correction.

**Important incomplete boundary:** the prototype does not implement correction-
aware remote candidate discovery, targeted observation merging or full local
policy filtering/totals. A correction can change the ID/season needed to discover
records that an already-filtered remote result omits. The consumer needs a bounded
stable-title/native-entity metadata lookup and must apply its existing correction
precedence **before** canonical filtering/pagination. Simply formatting remote
results cannot preserve that contract. Full implementation must add this to the
same narrow read model, not upload local overrides to the service. Cached stale
records preserve the mappings/languages observed in that response; they do not
claim knowledge of subsequent mapping corrections or newly observed languages.

Cache identity includes protocol, configured origin/source ID, token fingerprint,
provider, operation and complete request. Different sources/origins/credentials
cannot use each other's entries. Observation timestamps remain unchanged;
`Result` separately reports fetch age, hit/miss/stale state and the current error.
Cache TTL is 60 seconds; stale fallback at most 24 hours in this prototype. A
restart with the service stopped returns the previously fetched season as stale
at age 100 s and a transport error. An uncached title returns `Unavailable`.
Previously cached negative results are not offline success. Missing later pages,
expired/evicted queries, new titles and cross-source queries remain unsupported
until online. Valid self-contained grabs/jobs continue to use existing local
contracts independently of the metadata service.

**30 focused tests pass on native macOS and inside the installed Linux image.**
They cover the above fixtures, hit/expiry/restart/source change, finite eviction,
cache corruption, timeout, oversized/malformed JSON, duplicate keys, wrong
source/language/identity/season/query, revision regression and explicit outages.
A recursive SQLite query proves client timeout signals SQL cancellation and waits
for thread completion before releasing admission. A ninth concurrent request is
rejected. Limits: 2-KiB requests, 512-KiB responses, 100 results, offset <=10,000,
8 active operations, global 200 requests/s with burst 256, current 2-s SQL progress
budget and 3-s HTTP/client deadline. These are prototype defaults, not approved
hosted-service quotas. SQLite thread cancellation is cooperative; stalled kernel
I/O is not a hard-killed child process. Production deadline/enforcement is an
explicit contract gap. Current request/rate errors are 400/413/429, auth 401,
unavailable/deadline 503, all no-store. Transport failures never become a cached
successful empty response. Existing production routes are unaffected.

## Transfer and storage projections

These are **derived scenarios**, not real user traffic, provider update cadence,
quotes from a hosting supplier or measured multi-provider serving.

For one measured-size provider, assume 1,000 daily queries/client with the eight
cases equally weighted. API body traffic is
`queries × (1 - hit_rate) × (35,074.25 + 94.125)` bytes. At assumed 80% hits it is
**7,033,675 bytes/client/day**, or 35,168,375 without caching. Snapshot query traffic
is zero, but 48 distinct changed snapshots/day costs **12,377,310,048 bytes/client**;
unchanged signed renewals reuse validated artifacts with zero artifact-body bytes.
A once-daily changed snapshot costs 257,860,626 bytes. Pointer/manifest/header/TLS
traffic is additional. Do not assume the 87.5% short repeated-workload hit rate
will hold for fresh queries distributed over a whole day.

| Clients | API, assumed 80% hits | API, zero hits | Snapshots, 48 changed/day |
| ---: | ---: | ---: | ---: |
| 100 | 0.703 GB/day | 3.517 GB/day | 1.238 TB/day |
| 1,000 | 7.034 GB/day | 35.168 GB/day | 12.377 TB/day |
| 10,000 | 70.337 GB/day | 351.684 GB/day | 123.773 TB/day |

At 10k clients this scenario is 23.15 average API requests/s with 80% hits,
115.74 with none; burst/rate/CPU headroom and actual RSS polling mixtures require
measurement before operating a hosted service. Scaling all three providers to
this same dataset size triples relevant provider requests/storage/traffic; it is
not evidence that their actual catalogs are equal.

The query server needs the existing immutable allowlisted public database, not
another private ledger or materialized service database. Two measured uncompressed
versions cost **2,101,174,272 bytes/provider**. Three such providers plus one
construction SQLite derive **7,354,109,952 bytes** before logs/leases. This fits
inside the current 9-GB output allocation only with measured headroom and bounded
protected generations. Add the existing 20-GB state quota and 1-GB runtime reserve:
**28,354,109,952 bytes before other output costs**, under the 30,000,000,000 cap.
This is arithmetic, not a measured whole-worker capacity pass.

Keeping six compressed artifacts **and** six uncompressed read databases **and**
the existing 1.342-GB publication staging allowance derives approximately 9.193 GB
of output, exceeding that 9-GB subordinate quota. A perpetual parallel distribution
mode is therefore a bad default. Choose one production distribution contract;
reuse immutable export/identity validation and remove redundant compressed
publication once an explicit cutover contract is accepted. Active leases, backups,
WAL, staging, cache, logs and runtime files still count; publication must refuse
new work when protected bytes exhaust the budget. Never enlarge it implicitly.
The evaluation borrowed an existing 1.67-GB API image; this is not evidence that
that image fits the worker's 1-GB runtime allowance. Packaging the serving command
with the existing worker must be measured after query extraction.

Owned experiment disk peaked at about **2.103 GB** including query cache/report
files (raw file lengths, not a full producer accounting test). No server-side
result cache or new durable database was introduced. Consumer request caches
are local to users; a co-located cache still counts against that host's budget.
No large source fixture was regenerated; cleanup removes only the two owned
copies, retaining tiny inputs/manifests/results and all original preservation data.

## Reuse, migration and decisions

Reuse the collector, one-writer scheduling, conservative enrichment, stable
identities/first-seen ledger, fresh allowlisted export validation, local policy,
Torznab formatting, durable jobs, local extraction and STRM/mainline compatibility.
The prototype's strict metadata model, source/query-scoped cache, cancellation
adapter and workload harness are reusable. `ReadStore`'s two empty overlay tables
are a small experimental adapter, not a new production state schema. The SQL
module's import was verified not to load `app.main` or run API startup globals.

The smallest next implementation should extract only the current pure SQL/read
records into `catalog-core`, keep corrections/observations and formatting local,
and add one explicit read-serving command to the **existing collector service**.
Publish a fresh immutable allowlisted database and atomically activate it after
validation; do not serve private worker tables or mutate an active read file.
Use the existing Docker/self-host configuration pattern. Keep the evaluation
script outside normal startup. Do not design interchangeable backends or another
app/DB/broker/service framework.

Before implementation, approve these material changes:

1. **Privacy and availability:** requests disclose text/IDs and service-visible IPs;
   uncached metadata depends on that service. Self-host configuration must remain
   explicit. No new hosted endpoint/outbound default follows from this prototype.
2. **Trust and outage policy:** decide whether verified HTTPS plus source-scoped
   credentials replaces whole-artifact Ed25519 admission for remote metadata.
   Prototype validation proves record structure/identity, not publisher authenticity
   or a global replay floor. Recommend HTTPS/authentication initially, with exact
   source identity, source/provider revision rules and bounded freshness in the
   next spec. Approve stale TTL/negative-result behavior and how partial/offline
   status reaches users/*arr; cached metadata can be older than current corrections.
3. **Operation and product cost:** approve an initial workload/user/egress budget,
   authentication provisioning and fair quotas. The measured low short-run cost
   does not authorize public hosting or certify burst/SLA capacity.
4. **Compatibility/cutover:** approve replacing consumer snapshot distribution
   instead of sustaining both modes, with an explicit private-pilot config/state
   transition and restoration plan. Preserve jobs, legacy hashes, STRM and user
   data. No migration/removal occurs before that contract and tests exist.

Independent redistribution/rights, C7/C8 and deployment gates remain applicable
**to API responses**. No evaluation result grants public redistribution rights.
The collector freshness and live provider/client/media gaps remain as recorded
in 019. The post-fetch local correction test is not real Sonarr/Radarr proof.

The minimum production specification must additionally pin the allowlist/schema,
stable-title batch lookup, correction-before-filter precedence, pagination/update
semantics, source/revision/observation/stale handling, cancellation/resource bounds,
reader leases and whole-worker storage admission. It needs bounded same-key cache
miss coalescing, packaging/resource evidence, operator-safe metrics, and a small
correction-aware Torznab fixture test. These are required implementation work,
not reasons to ask an ordinary schema/deadline/package questionnaire now.

Default application logging is disabled in the prototype server (`access_log=False`)
and errors contain only fixed codes. It records aggregate request/byte counters,
not raw terms, credentials or client IPs. Production should expose auth-protected
aggregate latency/error/admission/catalog-age/storage metrics with bounded log
rotation. Reverse proxies/load balancers, TLS terminators, infrastructure logs
and operators can still observe IPs/metadata; POST body placement is not a privacy
guarantee. No anonymization claim or hosted ingress deployment is made here.

## Reproduction

See [scripts/catalog/query_api/README.md](../../../scripts/catalog/query_api/README.md)
for exact local Docker commands and the owned cleanup boundary. No automations,
new endurance run, scraping/media download, deployment, remote provisioning,
push or production route replacement occurred.

Documentation consulted through Context7:
[FastAPI async execution](https://fastapi.tiangolo.com/async/) for threadpool
behavior and [HTTPX timeout semantics](https://www.python-httpx.org/advanced/timeouts/)
for per-operation versus per-chunk deadlines. The experiment adds an outer
operation deadline rather than treating an inactivity timeout as a total budget.
