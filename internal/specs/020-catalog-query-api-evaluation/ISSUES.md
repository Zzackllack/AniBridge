# Private-pilot defects and production improvements

Updated 2026-10-11. Evidence: [pilot follow-up](evidence/linux-private-pilot-followup-2026-10-08.json)
and [EVIDENCE.md](EVIDENCE.md). The October 8 implementation and bounded measurements are recorded below.
Deployment is confined to the maintainer-authorized existing private pilot.

## Production requirement

The maintainer rejects approximately week-long full-provider bootstrap as a
production outcome. Aim for collection measured in hours, using fewer requests,
efficient bounded concurrency and provider-aware scheduling. The 1,200/hour
pilot cap and current retry delays are tuning choices, not accepted production
defaults. Establish an actual complete-bootstrap benchmark; partial publication,
title enumeration and extrapolation from a growing queue are not that benchmark.

Keep the 30,000,000,000-byte total collector/service budget, durable resume,
useful partial publication and query availability. Production collector sizing
is minimum 2 vCPU/2 GiB, recommended 4 vCPU/4 GiB; 6 GiB is a measured-headroom
option. The earlier 2-vCPU/512-MiB pilot was a constrained test. The authorized
October 11 preview upgrade now uses the 2-vCPU/2-GiB minimum for the collector.
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
| CQ-06 | Implemented + verified | Conservative unique names now handle native seasons spanning canonical seasons; AniWorld-only trailing `[Final Episode]`/`[Episode NNN]` fallbacks retain source coordinates. Exact IMDb title-search fallback verifies descriptor identity. Selected copied-ledger 50-title cohorts add 3,816 AniWorld/823 Serienstream maps with zero conflicts and all release identities retained. Whole-provider coverage and copied AniWorld One Piece S01E01 remain unresolved. |
| CQ-07 | Implemented + verified | Validated AniWorld microdata and current Serienstream rows batch positive names/flags. Missing/unknown/changed evidence retains detail fallback; omitted flags never delete releases. One-time checkpointed season refresh accelerates retained backlogs. 18 sampled row/detail language sets agree. |
| CQ-08 | Fixed + verified | One bounded pool per provider/canonical origin, closed with collector lifetime. Explicit requests have no ordinary cookie jar. Per-hop DNS validation/pinning, Host/TLS, verified HTTPS and trust_env=False remain enforced; regressions and live pools pass. |
| CQ-09 | Implemented + bounded measurement | 21 baseline requests yielded 18 detail rows; three candidate season requests supplied 71 rows. Offline checkpoint/publication replay: 14.77s to 3.51s, peaks 67.9MB to 59.9MB. Parser imports reduced, fresh supervised children retained; no SQLite/publication rewrite justified. Keep 2/provider slots and 2s spacing; 1800/hour matches existing spacing. Full-bootstrap duration remains unmeasured. |
| CQ-10 | Implemented + bounded measurement | Strict per-provider stable UA/Accept/Accept-Language/root Referer configuration. Identity encoding only. 16-request collector/Chrome A/B returned 200 throughout, no demonstrated browser-header benefit; default identifies AniBridge. No browser or solver added. |
| CQ-11 | Fixed + verified | Status exposes discovery/check phases, first-pass/detail coverage, failures/unsupported work, usable releases/mappings, rates and qualified current-queue ETA. Growing discovery suppresses ETA. Completion can truthfully become true for supported first-pass detail evidence; mapping and recent-feed gaps stay separate. |
| CQ-12 | Optional environment blocker | Megakino remains disabled: unresolved live language observations and unstable origins/challenge behavior. Keep AniWorld/Serienstream completion independent of it. Live extraction/import/playback and a copied real-state upgrade rehearsal remain separate, unverified gates. |
| CQ-13 | Fixed + verified | Coolify allocated `192.168.0.0/20`, shadowing NetBird. Pilot backend is now `172.16.27.0/24`; fra-node-01's automatic Docker pool is `10.254.0.0/16` split into `/24`s. Existing conflicting bridge was replaced, Docker restarted, and host/probe-network pings passed. Keep overlap checks in deployment instructions. |
| CQ-14 | Fixed + verified | Canonical enrichment previously treated its own 30/minute budget exhaustion as source failure. Deployed `3bf551e` defers the lookup without failure/backoff; 17 focused checks passed. CQ-01 is a separate provider-fetch budget defect. |
| CQ-15 | Fixed + deployed + verified | Direct pooled canonical requests lost AsyncClient's identifying default headers. Skyhook control returned 400 without User-Agent and 200 with it; identifying defaults restored without changing provider overrides, pinning or cookies. |
| CQ-16 | Fixed + deployed + verified | Recent-hint descendants were deferred a week even when bootstrap would otherwise idle: 704 AniWorld pages remained. Idle bootstrap now admits never-checked, nonfailed, non-targeted descendants after all due work; actual retry deadlines and recent hints remain protected. Status distinguishes due/deferred/leased first-pass work and due failures. |
| CQ-17 | Implemented + verified; SLA unmeasured | Four-hour active title/season eligibility and parents older than a latched feed gap share the existing 20% reconciliation budget; weekly episode fallback remains. Copied-state claims preserve ten future failed-work deadlines. Gap-parent counts are visible; capped feeds do not establish lossless coverage or a four-hour SLA. No query scraping, daily episode recrawl or demand-refresh system. |
| CQ-18 | Fixed + deployed + verified | The last failed AniWorld title returned HTTP 200 but contained an invalid optional IMDb hint. Ignore malformed optional hints while retaining native metadata; reject conflicting valid IDs and never coerce/publish malformed values. |
| CQ-19 | Implemented + verified | Ten bounded live metadata requests establish Ger-Sub detail labels, 25 combined season flags and four recent-feed labels. Shared parser/local resolver recognize de-sub without inferring audio. Eight saved-response replays add 25 releases, preserving all prior identities/first-seen times. Unknown cases remain explicit; both removal quarantines remain unapproved. |
| CQ-20 | Implemented + verified | Three current HTTP-200 samples explicitly say no episode player is available. Retain positive metadata and previous releases using v4-compatible unavailable fingerprints; missing player evidence cannot delete releases. Missing/changed sections and challenge markers have separate safe reasons. Unavailable does not imply an observed release date or cause. |
| CQ-21 | Implemented + verified | Bounded child phase/reason/exit reports and safe parser classifications replace discarded failure context. Status distinguishes sticky last fault from operational block state. No HTML, player URLs, credentials, query terms or IPs enter diagnostics. Unknown language counts and unapproved quarantines remain visible. |
| CQ-22 | Implemented + environment-blocked | Safe enrichment/export/validation/lock/publication diagnostics and signal/deadline exit reasons implemented and deployed in the authorized preview upgrade. Current-sized copied-state publications succeeded at 2 CPU/2 GiB, 4 CPU/4 GiB and 2 CPU/512 MiB; historical 48 ContractErrors/three timeouts were not reproduced. Original stderr was discarded, so historical cause cannot be established from retained logs; an actual classified live failure is still needed. Collector now uses the documented 2 CPU/2 GiB minimum; this is not evidence of the historical cause. |
| CQ-23 | Implemented + verified | Reproduced read-deadline failures from repeated public-ID view joins and a recent-index hint on targeted retrieval. Physical joins, validated exact recent summaries and target-specific access fix the demonstrated defects. 96/96 queries during current-sized publication pass at each of three profiles, including 100-row pages and native retrieval; large-series target returns three rows from 3,573-release history. Failed providers cannot produce empty success; corrections, explicit partial providers, outage cache and last-good retention regressions pass. |

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
3. Fresh complete supported-provider bootstrap and sustained capacity remain unmeasured.
   First-pass phases, failures, unsupported work and mappings remain separate.
4. Stable language/source coordinates and sampled first-seen identities survived
   cutover. Local API compatibility checks pass; unchanged generated job/import
   evidence was retained without acquiring new media.

CQ-01–11 implementation is committed. The existing private pilot retains its
volumes, checkpoints, failures and pre-v4 backups. Remaining measurement limits:
a complete supported-provider bootstrap and sustained production-capacity run;
short cohorts and queue projections do not close those gates. CQ-12 remains
optional. CQ-13/CQ-14 fixes and historical endurance failures are preserved.

The final follow-up `9afc52f` is deployed through the existing Coolify service.
Its 136-second restart/resume window added 674/673 episodes with zero new
failures; 200/200 sampled identities and unchanged limits/volumes were verified.
Latest phase/mapping/resource counts are in `final-deployment.json` and
[EVIDENCE.md](EVIDENCE.md). No deployment blocker remains.

October 9 recheck: AniWorld's discovered first-pass/detail work is complete,
with zero pending/failed pages and zero unknown-language observations. Canonical
mapping is 58.20% of usable episodes; feed-gap reconciliation remains CQ-17.
Serienstream collection continues, with 47,228 pending pages, 2,498 failed pages
and 61.10% usable-episode mapping. This is resumed collection from retained state,
not a fresh full-bootstrap benchmark. No runtime settings or deployments changed
during the recheck. See [October 9 evidence](evidence/pilot-recheck-2026-10-09.json).

October 11 recheck: AniWorld remains complete for discovered native first-pass
work (63,579 episodes / 116,359 releases, zero pending/failed pages). Serienstream
pending work falls to 20,061, but failures rise to 6,620 and unknown-language
observations to 50,933. Usable mapping stays near 58.17% / 61.13%. Both recent
feeds still report a coverage gap, with 11 / 24 pending hints. The old 512 MiB
collector is near its cgroup limit with heavy cumulative reclaim pressure but
zero OOM kills/restarts. No settings changed. CQ-22/CQ-23 prevent treating this
as merely a queue that needs more waiting. See [October 11 evidence](evidence/pilot-recheck-2026-10-11.json).

## October 11 implementation finish

The [sanitized repair evidence](evidence/catalog-pilot-repair-2026-10-11.json) and
[EVIDENCE.md](EVIDENCE.md#october-11-four-workstream-repair) record copied-state, live metadata
and fixture proofs separately. No pilot deployment, resource change, push or PR
was performed. Exact image-only upgrade and rollback instructions are in
[SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md#october-11-existing-coolify-upgrade-and-rollback).

That preparation-only result predates the subsequent explicit authorization.
Draft PR #170 is open against `v3`, with `main` still default. The existing
pilot now runs pinned preview revision `36fbd51` at 2 CPU/2 GiB for collection;
metadata remains 512 MiB. See [live deployment evidence](evidence/pilot-preview-upgrade-2026-10-11.json)
and [current upgrade/rollback](../../../scripts/catalog/query_pilot/SERVER.md#october-11-published-preview-deployment).
All 439,035 backup release identities/first-seen times were retained; 100-row
recent queries and ordinary/mapped large targets passed. Live One Piece S01E06
remains unresolved, and no provider-wide mapping/freshness completion is claimed.
