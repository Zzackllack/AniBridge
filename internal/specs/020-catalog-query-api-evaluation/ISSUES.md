# Private-pilot defects and production improvements

Updated 2026-10-20. Evidence: [pilot follow-up](evidence/linux-private-pilot-followup-2026-10-08.json)
and [EVIDENCE.md](EVIDENCE.md). The October 8 implementation and bounded measurements are recorded below.
Deployment is confined to the maintainer-authorized existing private pilot.

## October 18 canonical rejection follow-up

Read-only recheck finds 48 AniWorld and 902 Serienstream titles with retained
`source_failure` outcomes. These are title lookup outcomes, not counts of rate
limits or failed episode pages. Bounded canonical-only sampling reproduces a
parser defect: v2 descriptor envelopes can contain legacy `tvdbId`/`tvdbShowId`
episode fields. The old parser demands generic `metadataId`/`metadataShowId`
fields and rejects valid explicit parent associations.

Safe per-lookup `canonical_failure` events now classify the phase and typed
rejection reason. Compatibility accepts either complete positive TVDB identity
pair and rejects disagreeing or partial pairs. Translation joins still require
the same episode ID and coordinates; source name and parent verification remain
unchanged. No similarity/ordinal acceptance, matcher reset, failure clearing,
schema migration or live deployment is part of this local change.

The full lookup path distinguishes two further sampled causes: old series IDs
returning different canonical IDs/IMDb associations (still rejected), and
valid German responses with no language tag and no translated episode names.
The latter now preserves verified English evidence, records the missing optional
language privately and supplies no German aliases. Named untagged translations,
wrong namespaces/parents and conflicts remain rejected. The initial layout-only
full-copy replay added zero maps because these earlier/later gates still fired;
that result is retained separately rather than presented as a successful repair.

The full failure population is not yet classified. Missing names, conflicting
parents/cuts and genuine remote failures remain distinct open work. The expensive
publication export/validation phases are unchanged by this fix.

## Subsequent canonical budget tuning

The maintainer challenged the hardcoded 30/minute budget and authorized tuning.
It originated in the October 5 design/implementation, not an established Skyhook
quota. `limits.canonical_requests_per_minute` accepts 4–120, defaults to 30 and
stays outside matching fingerprints. Shared durable admission and retry deadlines
remain intact. Safe HTTP counters contain no terms, URLs or response bodies.

Same-frozen-ledger, sequential 130-second canonical-only windows at 2 CPU/2 GiB
yielded starts/new usable maps of 61/10 at 30, 124/20 at 60, 181/99 at 90 and
243/102 at 120. No 403/429; one HTTP 500 at 120. Series mix and eligibility clocks
vary; this is not independent accuracy or an upstream-ceiling measurement.
All old releases/first-seen, maps and work retry/lease fields survive each copy.
See [rate evidence](evidence/canonical-rate-tuning-2026-10-14.json).

Configurable admission, safe counters, copied-state comparisons and the approved
90/minute pilot rollout are **implemented+verified**. Live source `d85ed05` pins
manifest `sha256:9a0df2b03fd386142f36a5ba8704c17e2e1489bd2519d88959d62753d2157218`.
Both configs/all three worker images changed together; schema/resources/networks
did not. All 482,969 prior releases/first-seen and 246,689 old maps, including
parent identities, survive. Six same-revision SQL/API totals and the public route
pass. An initial uninstrumented query assertion failed, cause unestablished;
instrumented retries pass. A live sample has 1,016 canonical HTTP 200s.

The upstream quota, full-provider precision and sustained capacity remain
unestablished. Absent/generic names, conflicting parents/cuts and unknown audio
still require positive evidence. Publication cost and prospective independent
labels remain the separate open items below. Exact v5 rollback is in SERVER.md.

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
| CQ-20 | Implemented; follow-up defect reproduced | Three October 11 HTTP-200 samples explicitly say no episode player is available. Retain positive metadata and previous releases using v4-compatible unavailable fingerprints; missing player evidence cannot delete releases. October 14 sample has a series heading and explicit unavailable player but no episode heading: `missing_video()` rejects it as `metadata_incomplete` before recognizing unavailable evidence. Handle this demonstrated case without guessing a name, release date or audio language. Missing/changed sections and challenge markers remain distinct. |
| CQ-21 | Implemented + verified | Bounded child phase/reason/exit reports and safe parser classifications replace discarded failure context. Status distinguishes sticky last fault from operational block state. No HTML, player URLs, credentials, query terms or IPs enter diagnostics. Unknown language counts and unapproved quarantines remain visible. |
| CQ-22 | Implemented + environment-blocked | Safe enrichment/export/validation/lock/publication diagnostics and signal/deadline exit reasons implemented and deployed in the authorized preview upgrade. Current-sized copied-state publications succeeded at 2 CPU/2 GiB, 4 CPU/4 GiB and 2 CPU/512 MiB; historical 48 ContractErrors/three timeouts were not reproduced. Original stderr was discarded, so historical cause cannot be established from retained logs; an actual classified live failure is still needed. Collector now uses the documented 2 CPU/2 GiB minimum; this is not evidence of the historical cause. |
| CQ-23 | Implemented + verified | Reproduced read-deadline failures from repeated public-ID view joins and a recent-index hint on targeted retrieval. Physical joins, validated exact recent summaries and target-specific access fix the demonstrated defects. 96/96 queries during current-sized publication pass at each of three profiles, including 100-row pages and native retrieval; large-series target returns three rows from 3,573-release history. Failed providers cannot produce empty success; corrections, explicit partial providers, outage cache and last-good retention regressions pass. |
| CQ-24 | Implemented + verified locally; rollout pending | A usable local cache could consume a due canonical failure retry while retaining its expired deadline, repeatedly selecting the same title. Due failures now reach the retry path; only verified descriptors acquired after the failed attempt may establish recovery without HTTP. Today's full-copy replay advances 30 distinct retries instead of zero, preserves all 497,949 releases and 289,152 maps, and retains backoff/admission across restart. No state or matcher reset. Hosted worker remains `52065c7`. |
| CQ-25 | Implemented + verified locally; rollout pending | Status previously exposed page retry age but hid overdue canonical retries behind aggregate outcomes. `progress.canonical_queue` adds bounded counts and oldest scheduled retry age, separately identifying cached failed work. Zero deadlines remain new-evidence eligibility, not epoch-old age. Counts do not promise admission or an SLA. |
| CQ-26 | Implemented + verified locally; API rebuild pending | Retain exact and explicitly estimated yt-dlp sizes, aggregate selected tracks and preserve unknown future totals. Exact/estimated 25-of-100 input now yields 25% instead of zero; real synthetic HTTP/HLS and both qBittorrent response paths cover intermediate progress. Final size is the verified published artifact and progress stays below 100% until durable completion. No fabricated byte denominator for genuinely unknown work. |
| CQ-27 | Implemented + verified locally; API rebuild pending | Recovery no longer rewrites completed jobs as failed when a consumer moves the output. Missing outputs project `missingFiles` with no stale path or automatic redownload; historical `missing_output` records remain intact and explicit retry remains available. Legacy sync shares info semantics without read-time history writes. Read-only Linux projection of all four copied local aliases retains ledger bytes and reports three missing-file warnings plus the available completed STRM. |

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

## October 14 read-only recheck and priorities

The pinned `36fbd51` worker and 2 CPU/2 GiB collector remain up with zero
OOM kills/restarts. Last 24 hours: 284 successful publications per provider,
no retained maintenance/child failures, 3,639 Serienstream HTTP-200 parse
failures (3,522 `metadata_incomplete`, 117 `contract_rejected`), and 288
Serienstream transport failures, mostly HTTP 500. No observed page 403/429.
The original CQ-22 failure cause remains unrecoverable from discarded stderr;
the current classified publication path is operationally healthy in this window.

At the 08:27 UTC snapshot, Serienstream has 141 pending / 143 failed pages,
25,135 unknown-language observations and 8,350 explicit unavailable observations.
Pending and failed sets overlap. Usable mapping is 65.31% AniWorld / 64.62%
Serienstream; recent gap-parent queues are 0 / 5, without a lossless-feed claim.
Four quarantines remain unapproved (three language, one entity removal).
All 439,035 backed-up release IDs/first-seen times remain unchanged. See
[current evidence](evidence/pilot-recheck-2026-10-14.json).

Next development priorities:

1. Prioritize the matcher and descriptor recheck mismatch in
   [MAPPING_REPAIR.md](MAPPING_REPAIR.md). Later read-only diagnosis found
   15,280/92,506 usable episodes unresolved with cached descriptors, and zero
   never-checked matching-input entries. Its 8,611 partial series cannot sustain
   30-minute remote rechecks under the existing 30/minute shared canonical cap.
   Add a fixed independently labelled baseline, avoid unchanged descriptor churn
   and improve demonstrated name/identity gaps; waiting or larger limits alone
   cannot supply missing evidence. Counts are later sequential samples.
2. Fix the demonstrated CQ-20 heading case with a sanitized fixture, then explain
   the remaining season contract rejection. Tune repeated parser/absence work
   separately from transient HTTP 500 retries; preserve retry history and avoid
   turning parser errors into provider bans. The sampled title has 525 retained
   attempts; a mere queue-count decrease does not prove efficient maintenance.
3. Audit representative remaining language gaps and unresolved ordinary matches
   with bounded metadata/descriptor cohorts. The anime source's One Piece S01E06
   now returns three releases, but S01E01 remains explicitly unresolved; the
   two local S01E01 results do not prove that source's mapping is repaired.
4. Prepare a separately approved disposable-client preview upgrade (still
   `71988fc`), then verify subtitle offers, local corrections, cache/outage and
   controlled acceptance using the matching implementation. Keep generated media
   acceptance distinct from live extraction/import/playback. Complete these
   gates before moving the draft toward integration; leave `main` default.

Add frozen worker/core pytest CI and an always-running gate for both supported
PR bases alongside the mapping fixes. Current tests CI covers only API; `v3`
requires only the title status plus review/CodeQL policy. Preview imports do
not run worker/core regressions. CI work is not the primary remedy for stalled
mapping coverage. The executable task handoff is
[NEXT_AGENT_PROMPT.md](NEXT_AGENT_PROMPT.md).

This recheck changed no live deployment, resources or collection schedule and
did not reset bootstrap, failures or state. No fresh full-crawl or crash campaign
was launched, so bootstrap-duration and whole-provider freshness gates remain.

## October 14 implemented mapping/maintenance follow-up

See [MAPPING_IMPLEMENTATION.md](MAPPING_IMPLEMENTATION.md) and its machine-readable
[evidence](evidence/mapping-implementation-2026-10-14.json). Historical recheck and
CQ-22 causes remain historical; nothing here identifies discarded stderr.

- CQ-06 correspondence: implemented/verified conservative parent checks,
  multilingual names/IDs, bounded annotations/context and conflict preservation.
  The same full copy improves usable maps 41,530→42,871 and 184,641→188,232.
  All labelled positive cases resolve, including both recurring held-out language
  mismatch families. Full coverage remains open: generic/missing/duplicate names,
  unverified parents, conflicting cuts and incomplete canonical data cannot be
  accepted from numbering or similarity. No removal/repointing was approved.
- CQ-17 unchanged work: implemented/verified separate descriptor/rematch clocks,
  fingerprints, safe cross-provider evidence reuse and durable shared admission.
  12,568 unchanged cached titles skip rematching; one genuine changed descriptor
  replays. Snapshot two-language refresh demand is 645.929 requests/hour, excluding
  unmatched-parent searches/retries. A finite synthetic restart/fairness trace stays
  below 30/min; this is not a live freshness or full-bootstrap capacity promise.
- CQ-20 missing-heading unavailable: implemented/verified availability-only parser
  acceptance retaining useful names, releases and failure history. A 200 season
  without episode rows remains `parent_children_missing` with stable-gap backoff;
  sampled title 500/unknown audio evidence remain provider gaps. Missing players
  and language evidence never create tombstones or guessed releases/dates.
- CQ-21 local corrections/subtitles: current installed API/core fixture tests pass
  at 1 CPU/512 MiB; copied stopped-client migration preserves all 18 tables. The
  old disposable client remains stopped at `71988fc`, with zero corrections;
  new live client behavior/extraction/import/playback are not claimed.
- CI: frozen API/core/worker jobs, installed-wheel imports and unconditional gate
  for main/v3 are implemented and checked locally. Hosted execution/native AMD64
  manifests/protection enforcement remain environment-blocked: no push/publication
  or policy authorization. The draft PR and default branch are unchanged.

The strict prospective pre-labelled evaluation timing was **not achieved**:
selection/splits froze before tuning, metadata labels followed initial
implementation. This limitation and review errata are explicit; the held-out
numbers are fixed regression evidence, not blind precision. Do not silently tick
that acceptance requirement as met. All 474,046 full-copy release IDs/first-seen,
239,688 old maps, retry/checkpoint/lease/quarantine state and the 439,035 historical
backup releases survive. Worker/client upgrade preparation is tested; live cutover
remains blocked on fresh raw service/config review, approved matching pinned
manifests and new deployment/client approval. No allocations, routes or live
volumes changed. Megakino is optional and outside these results.

## October 14 subsequent authorized production follow-up

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) and its separate profiling
evidence for current status. Earlier no-push/publication statements above describe
the initial local handoff. The user later authorized pushing and Coolify work.

- Hosted CI/package verification: **implemented + verified** on pushed `2240b91`.
  API/core/worker, final gate, lint and both native image architectures passed.
  Ruff now checks instead of rewriting reviewed branches. Published registry
  worker passes full-copy offline publication, exact totals, last-good retention
  and isolation without a source overlay.
- Pilot/client cutover: **implemented + environment-blocked** preparation and
  copied rollback. Matching pinned images exist; the Mac lock blocks required
  authenticated Zen interaction. Old unused form is authorized to discard, but
  untouched. Live service/client upgrades have not occurred.
- Publication optimization: **not implemented**. Cold copied-state preflight
  costs 19.6629s/74.7822s; the run uses 18.111 CPU seconds over 98.824 wall seconds.
  Warm quick/FK checks take 4.374s combined. Phase profiling, trustworthy snapshot
  reuse and retention of integrity rejection are required before changing this.
  Existing work-title/FK indexes do not justify adding duplicate indexes.
- Larger correspondence repair: **not implemented beyond the measured repair**.
  The fixed cohort still has 4,460 absent candidates and 1,176 generic names,
  plus unresolved/unverified parents and conflicts. New verified metadata and a
  prospective pre-labelled evaluation are required, not a DB/cache/cap increase.
- v3 required-check enforcement: **not implemented**. Read-only rules inspection
  still finds only the title status required. Final tests and safe unconditional
  image smoke gates must actually prevent failing merges; path-filtered privileged
  preview build jobs cannot simply become universally required statuses.
- Live freshness/full-bootstrap capacity, new client subtitles and live media
  acceptance: **not verified**. Finite copied-state tests do not close these gates.
  No new crawl, competing writer, ledger reset, allocation or policy change was made.

### Subsequent approved live cutover

The Mac was unlocked and the blocker cleared. Worker `2240b91` is deployed through
native Zen; the local client runs the subsequent tested `6818115` privacy fix.
Both use immutable native manifests. Resources/networks/volumes remain unchanged,
and no OOM/restart loop was observed. Both initializer-source and volume configs
were updated, preventing startup from overwriting the German metadata setting.
Before resuming, all retained v4 columns compared against pre-v5 backups, except
the expected publication dirty/time fields: 481,435 releases/first-seen and
239,690 maps survive. Live SQL totals, targeted metadata, proxy route, installed
subtitle/privacy fixtures and client metadata queries pass; jobs/corrections stay
zero. This supersedes the environment-blocked deployment item above.

The short live sample adds 144/32 maps, not the whole copied-ledger gain. The
bounded live cohort still has 19/30 AniWorld and 30/30 Serienstream unverified
legacy descriptors; eligible-work ages are 6,045s/34,788s with 1,186/8,660 due.
These sequential reads are not a fairness/capacity SLA. Exact AniWorld One Piece
S01E01 stays explicitly unresolved live until fresh verified evidence arrives;
do not misattribute the client's Serienstream results to AniWorld. Four removal
quarantines remain unapproved. Live media acceptance, full capacity, prospective
labels, publication optimization and required-check enforcement remain open.

## October 18 publication implementation

This supersedes the earlier **publication optimization: not implemented** item
for local code. [PUBLICATION_FOLLOWUP.md](PUBLICATION_FOLLOWUP.md) records the
four work items, measurements, exact proof boundaries and recovery commands.

- Precise change tracking: **implemented + verified**. V6 transactional title
  generations distinguish content from timestamp-only observations. Controlled
  copied-state checks defer timestamps at 300 seconds and admit them at 3600;
  real content keeps its normal cadence. No provider freshness SLA is implied.
- Validation cost: **implemented + verified**. Bounded subphase timings, physical
  counts and digest/metadata/policy/validator receipts allow unchanged row-proof
  reuse. Full schema/integrity/relationship/semantic/summary checks remain;
  default untrusted admission is complete. Independent full validation passes.
- Incremental publication: **implemented + verified**. Verified cloning and
  affected-title updates reuse indexes. Additions, late maps, removals, conflicts,
  tombstones, tampering, stale policy and broad-change fallback are tested.
  Existing global conflict checks remain. The controlled comparison improves 11.79→3.67 s / 56.25→12.83 s,
  retaining all releases, first-seen times, old maps and private work history.
- Collection pause: **implemented + verified**. The provider fence is removed;
  a WAL snapshot and captured-generation acknowledgement retain concurrent writes.
  Crash/restart, old-image rollback/open and full copied resume pass. Abandoned
  staging and SQLite sidecars are recovered under the owner lock before quota
  admission; a second publisher cannot clear an active owner's scratch.

Remaining costs: whole-file cloning/global scans, cold source preflight and the
full rebuild path for invalid bases or broad changes. Real eligible-work age
under sustained concurrent collection and long-run fragmentation/capacity remain
unmeasured. Raw due ages in this experiment use its retained controlled clock;
unchanged table contents establish preservation, not a live scheduling SLA.
No new mapping coverage/accuracy gain is claimed. Missing names, ambiguous or
unverified identities and canonical/provider gaps require their existing evidence
rules; publishing existing data faster cannot supply that missing evidence.

The new local changes have no matching published native manifests or hosted CI
run yet; live rollout was not attempted in this pass. The existing pilot remains
on `d85ed05` with its resources, volumes, routes and backup generations intact.
Required-check protection policy and live extraction/import/playback stay separate.
The historical CQ-22 cause is still unknown; successful new publications do not
recover discarded stderr. No local implementation item above is left blocked.

## October 19: Sonarr connection test fails on retained legacy history

Implemented + verified locally. On client source `d318637`, query-mode
`GET /api/v2/torrents/info` and `/sync/maindata` sent HTTP 200 then terminated
the chunked body: `ClientJobs.views(durable=False)` imported the nonexistent
`torrent_info_record` helper. Sonarr 4.0.16.2944 reported a download-client
connection failure although version/preferences/category requests succeeded.
This is an application compatibility defect, not evidence of DNS/auth failure.

Extract the released legacy record projection into a shared module and use it
in both modes. Preserve aliases, jobs, states, output paths, timestamps and
category filtering; no migration or history clearing. Mixed-history regressions
include completed/active/failed/cancelled, missing-job aliases, paused durable
jobs and public-path translation. New tests fail before the repair.

A read-only, scheduler-free Linux HTTP harness using a consistent copy of the
current dev ledger returned all three aliases in both complete JSON responses.
The real Sonarr download-client test returned HTTP 200 against that harness;
saved Sonarr settings and copied database bytes were unchanged. Full API suite:
272 passed, 18 existing skips, one existing TestClient deprecation warning.
This verifies the client connection test, not a new live grab/import/playback.
The operator's existing dev container still needs a rebuild to load the fix;
no hosted collector/service was changed.

## October 19: query search ignored configured torrent counts

Implemented + verified locally. Catalog RSS hardcoded seeders/peers to one and
omitted leechers. It now uses the existing `TORZNAB_FAKE_SEEDERS` and
`TORZNAB_FAKE_LEECHERS` configuration for both download and STRM variants, with
negative counts clamped to zero and peers equal to their sum, matching legacy
behavior. Defaults remain 999/787. No size/quality or STRM naming change.
Four route-level regressions failed before the fix and pass afterward. Full
API suite: 276 passed, 18 existing skips, one existing deprecation warning.
The running local API needs a rebuild; no service was restarted for this fix.

## October 19: Classroom of the Elite S04E16 finale announcement

Implemented + verified on consistent copied state; live rollout remains pending.
Read-only XPipe/SSH inspection confirmed source `d85ed05`, v5 ledgers, zero
restarts/OOMs. AniWorld returned HTTP 200 and three observed languages for the
maintainer's exact episode URL. The private ledger and published revision 3327
already contain the episode and three releases; only its canonical map is absent.
`correspondence` reports `no_name_candidate`. Cached English and German canonical
names already identify TVDB 329822 S04E16, but both provider names append a finale
announcement. The old rule strips only the bare English `[Final Episode]`.
This is a correspondence defect, not a collection, pagination or publication lag.

The source-only fallback now recognizes the bounded English/German finale plus
confirmed-next-season/start grammar. It retains exact original keys and raw
metadata, requires the existing unique name/verified parent checks, and never
uses announcement/native numbers to choose canonical coordinates. Unrecognized
editorial suffixes and conflicting/duplicate aliases remain unresolved. Episode
matcher v7 makes old local receipts eligible once without invalidating canonical
descriptors or parent fingerprints.

A normal copied scheduler tick repaired this episode in 0.0137 s without network
requests, despite the old future eligibility deadline. After validated copied
publication: native request 0→3 releases, local Torznab 0→6 normal/STRM results.
Episode 15 retains its exact release set. Across six frozen cases, four new maps
were accepted; two remain unresolved. All 116,583 old release rows and 46,558 old
map rows survive; work/deadlines/failures, descriptors, names and quarantines are
unchanged. Linux worker: 280 tests passed. These results do not change the hosted
worker or prove a new live grab/import/playback. New rollout must use SERVER.md's
v6 upgrade/rollback procedure because the branch also contains the earlier
publication migration, rather than hot-patching the live v5 matcher.

## October 19: worker rollout closes the Classroom search gap

**Implemented + verified on the hosted metadata service and real Sonarr search.**
The subsequent approved Zen upgrade runs `52065c7` at the pinned manifest in
SERVER.md. S04E16 now yields three metadata releases and six normal/STRM Sonarr
results through Prowlarr; episode 15 is unchanged. The private v6 upgrade retains
all 497,850 prior release rows/first-seen values and 288,916 maps. Both providers
have completed later validated publications at their original limits/configuration.
This supersedes the earlier pending-rollout status, not the remaining accuracy,
freshness, live acquisition/import/playback or v3 release gates.

**Implemented + verified:** repeatable CI/image selection, immutable pinning,
private rollback files, stopped SQLite snapshots and preservation checks.
The normal targeted cached tick advances its fairness slot; the operator checker
now verifies that exact declared step without exempting retries or input hashes.
Eighteen focused operator tests pass. New tooling commits remain local; hosted
image CI evidence is specifically for the deployed application commit `52065c7`.

**Not implemented:** unattended Coolify writes, because the token remains
read-only and this deployment workflow requires authenticated Zen. Image builds
are already automated. `latest`/moving PR tags are not a stateful upgrade plan.
The initial archive transfer's transient log peak is also **unverified**; that
deleted transient output cannot retroactively establish disk-cap compliance.
Current conservative accounting including reserve is 21.83 GB. Later binary
exports and scripted one-off commands disable Docker logging.

The local client remains `428b5d8`; the separately implemented fake-swarm-count
fix `16bc0e1` still needs its own client rebuild. This worker upgrade installs no
client changes. See the dated evidence and repeatable operator guide for exact
receipts, resource/query samples, remaining limitations and state-preserving rollback.
