# Catalog metadata API evaluation

Date: 2026-10-05. Status: **evaluation brief, not an approved architecture
replacement or production implementation specification**.

## Purpose and decision boundary

Evaluate whether serving requested catalog metadata through a small HTTP API
is a better fit than distributing whole provider databases. The maintainer has
raised this alternative after substantial snapshot implementation work. Existing
code and evidence are assets to reuse, not a reason to preserve an unsuitable
design. Adoption still requires an explicit decision after the comparison.

The existing implementation and its normative contracts are documented in
[019](../019-catalog-worker/README.md). Read its current
[evidence](../019-catalog-worker/10-implementation-evidence.md),
[review](../019-catalog-worker/12-implementation-review.md), and identity/job
contracts before prototyping. This brief does not supersede those contracts.

Recorded evidence motivates this evaluation: a large synthetic catalog costs
roughly 258 MB per changed full download; 60 added language releases still
require about 177 MB with naive fixed-chunk reuse. Unchanged signed renewals
now reuse validated bytes. Two long consumer tests failed at validation
deadlines; isolated replay does not explain the second failure. These are
particular experiments, not measurements of real provider change rates or
proof that every deployment is impractical.

## Proposed flow

1. The collector continues building metadata centrally and incrementally.
2. Local AniBridge receives a Torznab request from Sonarr/Radarr/Prowlarr.
3. Local AniBridge requests the required metadata from a configurable catalog
   API, which queries already-collected data. No request-triggered provider crawl.
4. AniBridge formats results, applies local policy/corrections, and creates
   local magnets/jobs. On grab, provider/video-host resolution remains local.

Prototype three operations: title/external-ID matching, a bounded batch of
episode/language metadata for a title/season, and paginated recent releases.
Return metadata records rather than job tokens, media URLs or private state.
Do not make a separate HTTP request for each episode in a season.

The same service must be self-hostable through Docker. Users can configure
their own instance. Choose the smallest separation of collector and read-only
query serving that provides consistent reads; do not introduce another app,
database or infrastructure dependency merely to complete this experiment.

## Boundaries to preserve

- Existing public provider/entity/release identities and first-seen semantics.
- Conservative canonical mapping and positively observed languages.
- Durable user-local jobs, pause/block/retry behavior, STRM and mainline data.
- User-local provider access, extraction and quality observations; no worker
  browser, CAPTCHA solver, video proxy or search-time media probing.
- Roughly 1-GiB/2-vCPU local consumer target and 30,000,000,000-byte total
  worker storage budget. Include any query cache/server storage in accounting.
- Last-good data and explicit errors, rather than fabricated results or
  successful empty responses on transport failure.
- Independent public redistribution and deployment gates. No hosted launch.

Remote metadata requests would change two accepted properties: the service can
receive query terms/IDs and IPs, and uncached searches depend on service
availability. Local caching can cover prior requests, not the entire catalog.
Explain these changes explicitly; a prototype is not approval to transmit
real user queries to a hosted endpoint or to enable a new outbound default.

## Bounded prototype and comparison

Use a fresh evaluation agent and a separate branch based on the committed
implementation plus this brief. Preserve the current implementation/history.
Start with synthetic small fixtures and copies of existing query logic;
inspect its SQL, local overrides and Torznab formatting coupling before reuse.
Do not copy a complete parallel search engine or import API startup globals
into the collector. Extract only what the prototype actually needs.

Use local disposable HTTP/client tests. Include explicit ID/title searches,
one season batch, unknown/ambiguous mapping, recent releases and pagination.
Prove parity of returned source/canonical coordinates, languages and stable
identities on those cases. If needed, one small existing real-client fixture
may verify the prototype boundary; do not repeat the entire release matrix.

Measure response bytes, request fan-out, local latency, server CPU/peak memory,
cache growth, and consistent reads during catalog updates. Use identical
query workloads when comparing with local snapshot search. Record dataset,
concurrency, network delay and cache hit rate. Project daily transfer at explicit
workloads/user counts; never substitute those projections for measured traffic.
Verify indexed queries rather than provider-sized Python scans.

Include bounded deadlines/cancellation, response validation, request/result
limits, pagination, rate admission and error semantics. Exercise concurrent
clients and catalog replacement. Serve an allowlisted read model, not an
unrestricted SQL endpoint or the worker's private tables.

Prototype a finite local cache with source/provider/query identity and observation
age. Test a hit, expiry, changed source, startup with source unavailable,
timeouts and corrupt/malformed responses. Distinguish stale cache results from
current observations; do not cache upstream failure as authoritative emptiness.
Cached stale results must preserve language and canonical matching correctness.
Document which offline requests remain unsupported.

Plan authentication, HTTPS and operator visibility proportionately. Do not log
raw queries, credentials or client IPs by default. Discuss incidental ingress
logs and data disclosure even if the application disables request logging.
Redistribution restrictions apply to API responses as well as database files.

Check actual free disk/memory before experiments. Prefer a short benchmark
lasting minutes, with a stated stop condition and only one active experiment.
Use existing large fixtures only if available and affordable, with cleanup
limited to owned copies. No new 24-hour run, scheduled follow-up, bulk scraping,
media download, remote provisioning, paid service, push or deployment.

## Output and adoption gate

Produce a concise evidence-backed recommendation: retain snapshots, adopt the
request API, or explain the missing evidence. Include benefits, failure behavior,
server/consumer cost, privacy, reusable code, and migration/removal boundaries.
Do not claim that an API solves collector freshness or provider access problems.

If recommending the API, list the product decisions still requiring approval
and the smallest production contract required next. Do not silently support
multiple distribution modes or implement a general framework for future ones.
Full implementation is a separate task after the decision and updated spec.
Prototype code must remain opt-in and must not replace working default routes.

No ordinary schema/deadline/package choice requires a maintainer questionnaire.
Ask only when a material product, privacy, compatibility, cost or scope decision
blocks the evaluation. Treat unresolved measurements as unknowns.

Commit policy for the eventual prototype task: coherent local Conventional
Commits with multiline bodies; mark actual breaking changes with `!` and a
`BREAKING CHANGE` footer. Preserve original commits; no history rewriting or
public actions. This document creation itself makes no commit.
