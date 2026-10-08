# Private-pilot defects and production improvements

Updated 2026-10-08. Evidence: [pilot follow-up](evidence/linux-private-pilot-followup-2026-10-08.json)
and [EVIDENCE.md](EVIDENCE.md). The October 8 implementation and bounded measurements are recorded below.
Deployment is confined to the maintainer-authorized existing private pilot.

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
| CQ-01 | Fixed + verified | Nonblocking durable admission defers outside network deadlines and before fetch slots. Exhausted-budget regression sends zero HTTP calls, records no failure and survives reopen. Short redirect spacing releases its slot and resumes the same chain; pool exhaustion also defers locally. Redirect/cancellation/pool regressions pass. |
| CQ-02 | Fixed + verified | Short jittered page retries (5s exponential base, 300s base ceiling), sustained-real-failure circuits, success reset and single half-open probes. Parser/local waits never establish bans; explicit blocks start at 15m, capped at 6h. |
| CQ-03 | Fixed + verified | Valid Retry-After seconds and HTTP dates are respected with a 1s–24h bound; malformed values default to 60s. 12-second/date regressions pass. Local exhaustion is admission_deferred, never remote 429. |
| CQ-04 | Fixed + verified | Bounded timestamped JSON outcomes retain HTTP status, error class, request count, network/parser durations, retries and budget waits. Live 200 page/batch events verified without sensitive values. |
| CQ-05 | Fixed + verified | German-only headings and bilingual source aliases are retained. Generic numbered headings, duplicate/conflicting evidence and source numbering remain insufficient. German/alias regression and six formerly null live Arthur headings pass. |
| CQ-06 | Implemented + bounded measurement | Unique non-generic canonical names can prove coordinates without a numbering assumption. Copied-ledger 50-title cohorts add 11 AniWorld/7 Serienstream maps; season cohorts map 13/13, 7/7 and 33/51. Whole-provider coverage remains partial; current live counts are in evidence. |
| CQ-07 | Implemented + verified | Validated AniWorld microdata and current Serienstream rows batch positive names/flags. Missing/unknown/changed evidence retains detail fallback; omitted flags never delete releases. One-time checkpointed season refresh accelerates retained backlogs. 18 sampled row/detail language sets agree. |
| CQ-08 | Fixed + verified | One bounded pool per provider/canonical origin, closed with collector lifetime. Explicit requests have no ordinary cookie jar. Per-hop DNS validation/pinning, Host/TLS, verified HTTPS and trust_env=False remain enforced; regressions and live pools pass. |
| CQ-09 | Implemented + bounded measurement | 21 baseline requests yielded 18 detail rows; three candidate season requests supplied 71 rows. Offline checkpoint/publication replay: 14.77s to 3.51s, peaks 67.9MB to 59.9MB. Parser imports reduced, fresh supervised children retained; no SQLite/publication rewrite justified. Keep 2/provider slots and 2s spacing; 1800/hour matches existing spacing. Full-bootstrap duration remains unmeasured. |
| CQ-10 | Implemented + bounded measurement | Strict per-provider stable UA/Accept/Accept-Language/root Referer configuration. Identity encoding only. 16-request collector/Chrome A/B returned 200 throughout, no demonstrated browser-header benefit; default identifies AniBridge. No browser or solver added. |
| CQ-11 | Fixed + verified | Status exposes discovery/check phases, first-pass/detail coverage, failures/unsupported work, usable releases/mappings, rates and qualified current-queue ETA. Growing discovery suppresses ETA. Completion can truthfully become true for supported first-pass detail evidence; mapping and recent-feed gaps stay separate. |
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
Origin-scoped pooling is now implemented and verified while retaining per-hop
DNS pinning; ordinary unpinned URL fetching would weaken that boundary.

## Validation outcome and remaining measurement

1. Admission, Retry-After/date, transient retries, circuits/reset and restart
   regressions pass. Final installed Linux checks cover the changed boundaries.
2. Bounded real metadata, offline checkpoint/publication, headers/pools and live
   resumed throughput comparisons are in `evidence/collector-repair-2026-10-08`.
3. Complete supported-provider bootstrap and sustained capacity remain unmeasured.
   First-pass phases, failures, unsupported work and mappings remain separate.
4. Stable language/source coordinates and sampled first-seen identities survived
   cutover. Local API compatibility checks pass; unchanged generated job/import
   evidence was retained without acquiring new media.

CQ-01–11 implementation is committed. The existing private pilot retains its
volumes, checkpoints, failures and pre-v4 backups. Remaining measurement limits:
a complete supported-provider bootstrap and sustained production-capacity run;
short cohorts and queue projections do not close those gates. CQ-12 remains
optional. CQ-13/CQ-14 fixes and historical endurance failures are preserved.
