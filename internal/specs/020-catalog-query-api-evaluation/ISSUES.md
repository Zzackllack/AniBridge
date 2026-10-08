# Private-pilot defects and production improvements

Updated 2026-10-08. Evidence: [pilot follow-up](evidence/linux-private-pilot-followup-2026-10-08.json)
and [EVIDENCE.md](EVIDENCE.md). This records outstanding work; it does not claim
that the deployed worker has these fixes or authorize another deployment.

## Production requirement

The maintainer rejects approximately week-long full-provider bootstrap as a
production outcome. Aim for collection measured in hours, using fewer requests,
efficient bounded concurrency and provider-aware scheduling. The 1,200/hour
pilot cap and current retry delays are tuning choices, not accepted production
defaults. Establish an actual complete-bootstrap benchmark; partial publication,
title enumeration and extrapolation from a growing queue are not that benchmark.

Keep the 30,000,000,000-byte total collector/service budget, existing container
resource limits, durable resume, useful partial publication and query availability.
Improve work efficiency before raising rates; select higher per-provider rates
and concurrency from bounded measurements of real responses and resource usage.

## Finite backlog

| ID | State / priority | Issue and required outcome |
| --- | --- | --- |
| CQ-01 | Confirmed open / P0 | Local budget waits occur inside the HTTP deadline. Reproduced `transport_failure` with zero HTTP calls; both providers reached 1,200 starts at their latest cooldowns. Defer work until budget is available, outside network deadlines, without recording provider failures or occupying scarce fetch slots while waiting. |
| CQ-02 | Confirmed open / P0 | Three transport failures in five minutes pause the whole provider for 30 minutes. Ordinary page failures retry after 5/30/120/360 minutes; challenge delays start at six hours. Replace blanket pauses with classified, bounded page retries and provider circuits for sustained actual failures. Success resets escalation. |
| CQ-03 | Confirmed open / P0 | HTTP 429 handling forces at least one hour even for a shorter `Retry-After`; HTTP-date values are not parsed. Respect valid seconds/date instructions with bounded handling. Local throttling is never a remote 429. Explicit 401/403/challenges remain distinct from transient errors. |
| CQ-04 | Confirmed open / P1 | Transport discards HTTP status/error class; normal event logs only say `settled` and lack timestamps. Emit timestamped sanitized outcomes, request/budget/retry counts and durations. Do not log response bodies, tokens, URLs with query strings or user query/IP histories. |
| CQ-05 | Confirmed open / P1 | Serienstream requires a parenthesized English episode title. Live German-only heading `S01E01: Leichtfertige Versprechen` is discarded. Retain source-language names/aliases and use unique canonical evidence; generic `Folge 1`, duplicate titles and unproved numbering remain unresolved. |
| CQ-06 | Measured gap / P1 | Only about 68% AniWorld / 48% Serienstream episodes with releases are mapped. Investigate unmapped cohorts, missing canonical titles, translations, split seasons and ambiguity; remeasure coverage after fixes. Ordinary series must not require manual review, and source coordinates must remain separate from canonical coordinates. |
| CQ-07 | Optimization to measure / P1 | Episode-by-episode metadata fetches dominate the growing backlog. Investigate provider season/listing rows as batch sources of episode names and positively observed languages. Fetch detail pages only for missing/changed evidence. Validate row completeness and absence semantics before replacing existing observations. |
| CQ-08 | Confirmed overhead / P1 | A new `httpx.AsyncClient` is created for each fetch, preventing cross-fetch connection reuse. Introduce scoped bounded pooling while preserving DNS validation/pinning, Host/TLS identity, verified HTTPS, redirect restrictions and `trust_env=False`. Bound cached DNS/session state; separate provider cookies and canonical credentials. |
| CQ-09 | Optimization to measure / P1 | Async already exists: four total fetch slots, two per provider, 2-second spacing. Measure useful entities/request, budget stalls, network latency, parser startup, SQLite checkpoints and publication before selecting higher bounded concurrency. Profile per-page parser subprocess cost; preserve its memory/deadline/termination guarantees if reusing parser workers or batching. |
| CQ-10 | Requested improvement / P1 | Evaluate stable configurable browser-compatible User-Agent/Accept/Accept-Language/Referer profiles against current provider responses. A/B measure success, actual 429/403 rates and latency. Advertise only supported encodings and retain bounded decoding. Header strings alone do not provide browser TLS/JavaScript behavior or prove an IP-reputation fix; preserve the existing no-browser/CAPTCHA-solver scope. |
| CQ-11 | Confirmed reporting gap / P1 | `complete` is always false; discovered, checked, usable and mapped counts differ, queues grow as seasons are discovered, and recent gaps latch. Expose first-pass coverage, retry/blocked work, available releases, mapping coverage, freshness, throughput and a qualified ETA. Avoid calling title-list completion or a drained recent queue a complete scrape. |
| CQ-12 | Optional environment blocker | Megakino remains disabled: unresolved live language observations and unstable origins/challenge behavior. Keep AniWorld/Serienstream completion independent of it. Live extraction/import/playback and a copied real-state upgrade rehearsal remain separate, unverified gates. |
| CQ-13 | Fixed + verified | Coolify allocated `192.168.0.0/20`, shadowing NetBird. Pilot backend is now `172.16.27.0/24`; fra-node-01's automatic Docker pool is `10.254.0.0/16` split into `/24`s. Existing conflicting bridge was replaced, Docker restarted, and host/probe-network pings passed. Keep overlap checks in deployment instructions. |
| CQ-14 | Fixed + verified | Canonical enrichment previously treated its own 30/minute budget exhaustion as source failure. Deployed `3bf551e` defers the lookup without failure/backoff; 17 focused checks passed. CQ-01 is a separate provider-fetch budget defect. |

Backoff must follow evidence: honor explicit 429 instructions; briefly retry
isolated network/5xx failures per page with bounded exponential delay and jitter;
escalate a provider circuit only for sustained actual failures. Parse errors mark
coverage gaps instead of proving an IP ban. Explicit authentication/challenge
responses must not be hammered. Preserve successful provider data throughout.

## PR #119 reference inspection

Inspected [PR #119](https://github.com/Zzackllack/AniBridge/pull/119) at head
`61351bbcbfc1295ab597f8385f063598c25f3191`, without copying code:

- `apps/api/app/catalog/providers.py` reads AniWorld episode titles and language
  flags from season rows. This is a concrete request-reduction approach to verify
  against today's provider HTML. Its Serienstream season rows have empty title
  and language fields, so the same savings are not established for that provider.
- `apps/api/app/catalog/indexer.py` uses a bounded `ThreadPoolExecutor`;
  `config.py` defaults to four AniWorld/Serienstream workers per provider.
  It has concurrency already; switching labels to “async” is not a benchmark.
- Its canonical matcher labels matching source/canonical numbers as confirmed
  `direct_numbering`. Do **not** reuse that assumption: faster collection cannot
  sacrifice identity correctness or resolve movies as fake TV episodes.
- The inspected performance document is a specification, not a measured full
  crawl. No verified full-bootstrap duration was found in the inspected source
  or PR description. Do not advertise a measured speed advantage without one.

HTTPX's maintained [async documentation](https://www.python-httpx.org/async/)
explicitly recommends client reuse outside hot loops for connection pooling.
Pooling with our DNS-pinned transport needs implementation and verification;
simply replacing the client with ordinary URL fetching would weaken that boundary.

## Validation needed to close the performance work

1. Regression: exhausting local budgets sends no request and adds no failure;
   actual 429/date handling, transient retries, escalation/reset and restart pass.
2. Bounded metadata comparison: baseline versus batch/pool/header/concurrency
   candidates on identical sources; report useful rows/request, latency, errors,
   memory, CPU, disk and publication/query availability. No full crawl on the Mac.
3. Linux bootstrap: measure durable first-pass coverage and elapsed time on the
   selected VPS, including explicit failed/unsupported/ambiguous cases. Count
   outstanding failures separately; do not silently relabel them as complete.
4. Verify unchanged language observations, canonical/source coordinates, frozen
   identities, local correction precedence and last-good serving during failures.
   Rerun job/import checks only if those paths change or a new defect warrants it.

Implement CQ-01–04 first, then request reduction/pooling and measured throughput
tuning alongside CQ-05–06. Retain the existing pilot volumes and checkpoints.
