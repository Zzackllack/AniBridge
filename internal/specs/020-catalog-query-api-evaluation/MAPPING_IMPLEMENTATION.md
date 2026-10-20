# October 14 mapping implementation and verification

October 20 follow-up: [recheck evidence](EVIDENCE.md#october-20-cached-canonical-retries-could-stall-the-queue)
and CQ-24/CQ-25 in ISSUES.md reproduce an expired-failure/cache scheduling loop.
Due canonical retries now bypass local correspondence completion; shared evidence
must be newer than the failed attempt to establish recovery. This changes neither
parent/episode acceptance nor matcher fingerprints, and does not require a state
migration. Existing backoff, maps, release identities and collection queues remain.
The hosted worker remains `52065c7` until a separately approved rollout.

Initial local handoff on `zzackllack-aux/catalog-query-api-implementation`; draft
PR #170, protected `v3`, default `main`, registry and live services are unchanged.
For the subsequent authorized push, hosted tests, pinned preview images and
current deployment blocker, see [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).
The machine interruptions removed temporary Mac files. Frozen remote copies and
private metadata survived; the final full replay recreated candidates with
SQLite backup from the original frozen baseline, rather than using a partially
modified copy. No live volume was used by an experimental writer.

## Changes delivered

`correspondence.py` is the shared bounded decision path for applying maps and
reporting allowlisted rejection counts. It distinguishes unattempted/unresolved
parents, absent evidence, unverified/conflicting associations, missing/generic
names, duplicate source/canonical names, alias conflicts, unsupported context and
occupied coordinates. `mapping_diagnostics` also separates legacy, expired,
current and absent descriptors without exposing names, HTML or query terms.

Private state v5 stores compact descriptor/episode identities, input fingerprints,
local examination clocks, durable canonical admission and fair queue positions.
Recognized v4 upgrades keep a no-overwrite `.pre-v5.backup`; pre-v4 and `/state/backup`
remain untouched. Code rollback drops only the five new private tables after the
canonical admission window expires. The public read/wire schemas are unchanged.

Verified TVDB evidence is reusable between provider titles; source identities are
never shared. Unchanged source/descriptor/matcher inputs skip matching and dirty
publication churn. Stable descriptors use seven-day eligibility; recent meaningful
unresolved names use daily eligibility. Generic ordinal names do not get a daily
refresh. First, changed, retry and old due work have durable opportunities under
the existing shared 30/minute budget. Redirects count; admission deferral does not
become a source failure. Existing backoff/Retry-After deadlines survive source and
matcher changes. Idle ticks are reported as idle.

Optional `episode_languages: ["deu"]` uses maintained Sonarr/Skyhook v2 `eng`/`deu`
TVDB official-order endpoints. English and German episode names join only on the
same namespaced episode ID **and** the same canonical coordinates. An untranslated
English row retains its ID so a German name can contribute evidence. Parent
names/aliases, year and IMDb are checked independently, including edited-series
cut conflicts sharing an IMDb ID. Existing conflicting maps are retained for
review. Private provenance records v2; the existing public `skyhook-v1` authority
tag remains compatible with the current publication allowlist.

Bounded source annotation handling covers demonstrated `[Episode N]`, JP/DE
suffixes and Serienstream wrappers. Ordinals never establish correspondence.
Repeated names and unambiguous contraction candidates require three distinct,
globally unique episode anchors or reviewed season evidence; three aliases of
one episode are one anchor. Ambiguity/conflicts veto acceptance, and accepted
coordinates cannot be silently repointed. No series slug or hardcoded episode
map appears in production matching code.

The explicit Serienstream unavailable player template no longer requires an
absent episode heading. It supplies availability only and retains useful names,
releases and retry history. A sampled season had HTTP 200, heading and season
navigation but no episode rows: `parent_children_missing` remains a safe parse
gap, not an empty enumeration or deletion. Stable parse gaps back off to 24 hours;
transport policy remains separate. A sampled title still returned HTTP 500 after
547 retained attempts. Three language-gap metadata probes found one 404 and two
`Ger-Sub` pages: subtitle evidence establishes German subtitles, never guessed
audio language or a release date. No removal quarantine was approved.

## Frozen data and accuracy limits

The deterministic seed is `mapping-2026-10-14-v1`: ten large unresolved and twenty
ordinary titles per provider, stratified by size, language and mapping outcome.
Alternating titles define development/held-out splits. Episode selection uses
`episode-label-v1`, five large/three ordinary cases where available: 105 AniWorld
and 110 Serienstream cases. The committed label fixture includes literal metadata
names, verified canonical episode IDs and expected coordinates, plus six real
ambiguous source entities. Native numbering and the old matcher are not labels.

**Chronology limitation:** title/episode selections and splits froze before tuning,
but metadata labels were reviewed after initial implementation. This does not
meet a strictly prospective pre-labelled trial. Review errata explicitly records
one normalized full-source collision and subsequently acquired development-only
parent evidence. These are fixed regression/coverage labels, not a blind precision
estimate. The initial label digest and final fixture digest are retained in JSON.

| Provider/split | Cases | Independently resolvable positives | Before correct | After correct | New wrong |
| --- | ---: | ---: | ---: | ---: | ---: |
| AniWorld development | 50 | 26 | 20 | 26 | 0 |
| AniWorld held-out | 55 | 26 | 23 | 26 | 0 |
| Serienstream development | 55 | 31 | 20 | 31 | 0 |
| Serienstream held-out | 55 | 35 | 17 | 35 | 0 |

All 118 labelled positives resolve; 38 new labelled acceptances have no observed
errors. All six supplementary ambiguous entities remain unmapped. Seven maps
outside positive labels already existed (three conflicting-parent AniWorld and
four generic-name Serienstream cases); all seven are retained, without new such
acceptances. This is not population-wide zero-error evidence.

Two recurring mismatch families improve on held-out series: meaningful German
source aliases absent from English descriptors (including One Piece, Naruto and
Boruto), and valid canonical episode IDs whose English title is missing but whose
German title exists (Rosenheim-Cops and In aller Freundschaft – Die jungen Ärzte;
five held-out labelled cases). Development cases include Conan's annotations and
Großstadtrevier/Behind Bars' untranslated rows. The full title replays add 3,227
held-out translated maps plus two fresh-primary maps; this counts maps, not
individually reviewed positives. Newly verified Pretty Rhythm parent aliases/year
add 69 development-series maps through the actual Enricher path with four recorded
requests. Its five selected cases contain three resolvable names and two gaps.

One Piece S01E01 is accepted from a unique German source alias joined to verified
canonical metadata/ID; S01E06 and S21E14 retain their old maps. Each targeted query
returns three releases. Equal native numbering and English similarity did not
provide the acceptance evidence.

## Full copied ledger and measured work

The fresh snapshot was taken sequentially around October 14 10:09 UTC, so it
slightly differs from earlier historical JSON. All before/after comparisons below
use that same frozen copy. No provider-wide new metadata crawl occurred.

| Provider | Episodes | Usable episodes | Releases | Usable maps before → after | Usable coverage |
| --- | ---: | ---: | ---: | ---: | --- |
| AniWorld | 63,601 | 63,585 | 116,409 | 41,530 → 42,871 | 65.3141% → 67.4231% |
| Serienstream | 306,899 | 285,665 | 357,637 | 184,641 → 188,232 | 64.6355% → 65.8926% |

Total gain: **4,932 usable maps**, 4,969 maps including 37 episodes without retained
releases. All 474,046 copied release IDs/first-seen times and 239,688 existing maps
survive. Work retries/deadlines/leases, pending signals, title schedules, omissions,
season checkpoints and four quarantines have zero differences. All 439,035 original
`/state/backup` releases and its 221,475 maps also survive. No release was removed
or added by rematching.

The recorded cohort uses 49 unique descriptors × English/German = 98 language
requests, plus four parent-repair requests: **102 logical requests / 4,932 useful
maps = 0.020681 requests/map**. Actual network requests during replay are zero.
This ratio excludes separate diagnostic/legacy endpoint probes, and is not a
provider-wide acquisition forecast. No HTTP validator support was assumed.

Cached-only replays added zero maps without new verified parent/name evidence.
The unchanged second pass skips 12,568/12,569 cached titles; one shared-descriptor
fingerprint genuinely changed. AniWorld replay took 39.9138s, with 1.8096s for the
unchanged pass; Serienstream took 256.4463s, with 15.6757s unchanged. Full replay:
296.4803s wall, 106.9739s CPU, 90,488 KiB process peak RSS. Cgroup anonymous memory
at completion was 74,498,048 bytes, file cache 2,028,478,464 bytes; the 2-GiB limit
was reached with reclaim (`max=3999`), zero OOM/kill events and no extra swap.
Measured mapping-phase I/O deltas were 1,942,679,552 bytes read and 1,456,508,928
written, including migration backups/WAL. The container had run tests beforehand;
peak is a container-wide high-water value, not anonymous process memory. No 4-CPU
comparison was justified by this result.

Applied refresh eligibility on all 12,570 associated TVDB parents yields 6,948
daily and 5,622 weekly candidates. Charging two language requests each gives a
snapshot average bound of **645.929 requests/hour**, below 1,800/hour and leaving
room for searches/retries. These counts include unverified associations, exclude
unmatched parents, and are cadence arithmetic, not a service trace or freshness
promise. Initial verification/backlog and future growth still require admission.
Existing eligible ages remain 3,613s/29,158s, with 612/7,969 due titles, zero first
attempts and one/five due canonical source failures. We did not reset those queues
to create better age results.

A separate finite controlled-clock fixture examines both providers for 180
simulated seconds, restarts the Enricher at 90s, and admits 81 requests, max 27 in
any rolling 60s window. Both providers receive first/changed/retry/old work:
12/12/10/8 and 12/12/8/7. Deferred ticks remain local; remaining fixture work age is
7,379s. This verifies admission/fair opportunities, not live queue throughput.

A finite installed-legacy/current comparison on the same 51 cached cohort titles
shows second-pass time **4.1050s → 0.5299s**, CPU **3.8552s → 0.4062s**, and SQLite
row mutations **2,823 → 0**, with zero new maps in either replay. Both phases are
separate 2-CPU/2-GiB/no-swap/network-disabled containers. Whole-wrapper wall time
is 45.6488s/103.6032s and includes different copy/preflight/cold-read costs; it is
not an overall startup-speed claim. Process peaks are 81,864/72,712 KiB, cgroup
peaks 1,676,816,384/1,023,102,976 bytes, with no OOM. Whole-wrapper I/O is retained
in JSON, including the legacy backup copy; the current replay writes zero bytes.
`unchanged_compare.py` reproduces this bounded common-title comparison.

## Serving, client, packaging and rollback

The pinned old worker's same-copy publications take 21.2972s/71.6461s versus
20.0487s/72.3104s after the change. All 96 old/new overlap queries return 200;
median is 44.55ms→45.10ms, p95 250.5ms→270.1ms and max 609.6ms→1,021.4ms. There is
no serving-speed improvement claim: timing/cache variation and the enlarged
map ledger remain visible. Cgroup peaks belong to different preceding workloads
(old seed/publication versus new tests/migration/replay), so they are not a
controlled before/after memory regression measurement. Both have zero OOM kills.
Full copied publications complete in 20.0487s/72.3104s. During publication, all 96
finite queries returned 200: median 45.1ms, max 1.0214s. Follow-up SQL-checked recent
queries return exactly 116,409/357,637 releases with 100 rows; targeted One Piece
queries take 6.0–6.8ms and ordinary Breaking Bad S01E01 returns two releases in
7.0ms. Controlled failed exports retain both last-good pointers and remove staging.
An absent AniWorld copy returns 503 while Serienstream continues returning 200.

Local correction precedence, cache/outage, provider isolation, late canonical
arrivals, parser recovery, changed names, canonical retry/rate exhaustion and
restart are covered by worker/core/API regressions. Linux worker passes 182 tests
against actual installed wheels, including read-only descriptor freshness checks. Linux core passes 310; Mac API passes 265 with 18 platform skips. ARM64 installed API/core metadata tests pass 90 at 1 CPU/512 MiB/no swap:
11.905s wall, 7.5087s CPU, 433,700,864-byte cgroup peak, no OOM, 2,727,936 bytes read
and 125,267,968 written. The stopped disposable client is still `71988fc`; its
consistent DB copy retains all 18 tables exactly after current migrations, with
zero jobs/corrections. This verifies fixtures/copy, not a live client cutover.

Both full ledgers downgrade to v4 with zero changes across all 32 v4 tables,
open using the original pinned image's installed code, then reupgrade and reopen
twice with the retained pre-v5 backup. Downgrade/verification takes 6.659s/31.019s.
A focused test additionally proves code rollback refuses an active admission
window. [SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md#october-14-mapping-follow-up-prepared-upgrade-and-code-rollback)
contains reviewed preparation, upgrade and exact worker/client rollback commands.
The registry staging helper passes six guard/invariant tests. Native ARM64 API
and worker builds import actual installed wheels and record real source SHAs;
no image was pushed or loaded onto the live host.

`tests.yml` now adds frozen core/worker jobs, wheel builds/installed imports and an
always-running final gate beside API tests, for both `main`/`v3` PR bases without
path filters. Actionlint and success/failure/skipped/cancelled gate cases pass
locally. Hosted CI, native AMD64 manifests and required-check enforcement are
unverified; no GitHub policy change was made.

## Honest work-item status

| Work item | Status | Remaining boundary/blocker |
| --- | --- | --- |
| Bounded shared rejection/freshness diagnostics and frozen cohort | implemented + verified | Prospective pre-tuning label timing was not achieved; chronology/errata explicit |
| Strict prospective pre-labelled blind trial | not implemented | Labels followed initial implementation; cannot retroactively change timing or claim blindness |
| Separate acquisition/rematch, fingerprints, safe shared descriptors | implemented + verified | Full live initial verification backlog not drained in this finite test |
| Shared budget, fairness, new-evidence/retry/old scheduling | implemented + verified | Cadence arithmetic and synthetic trace do not establish a live freshness SLA |
| Verified parent/episode aliases, multilingual IDs, conservative context | implemented + verified | Remaining missing names, absent parents, duplicate/conflicting evidence cannot safely resolve |
| Missing-heading unavailable parser and safe stable-gap retry policy | implemented + verified | Live new code not deployed; absent season children/HTTP 500 still require provider evidence |
| Representative language-gap diagnosis and subtitle client behavior | implemented + verified | Live client stopped; missing audio evidence remains unknown |
| Frozen CI projects, wheel smoke, unconditional gate | implemented + verified locally; environment-blocked hosted | Unpushed branch; no authorized publication or protection-policy change |
| Copied full-ledger publication/query/retention and rollback/resume | implemented + verified | No live cutover/import/playback claim |
| Upgrade/rollback helper and commands | implemented + verified; environment-blocked live | Fresh raw Coolify record and matching approved published manifests required; deployment/client restart unapproved |
| Megakino | not implemented in this follow-up | Optional; unresolved live language evidence, excluded from these measurements |

Remaining gaps are evidence failures, not a reason to accept numbering or weaken
uniqueness: absent verified parent associations, conflicting series-cut years,
unusable ordinal-only names, duplicate source/canonical names, missing English
and German canonical names, occupied coordinates, and provider pages lacking
children/players. More RAM or raising the canonical cap cannot supply those names.
Complete mapping, full bootstrap, long endurance, live media acquisition and
query-time scraping were neither implemented nor inferred from these results.

Machine-readable measurements and hashes:
[evidence/mapping-implementation-2026-10-14.json](evidence/mapping-implementation-2026-10-14.json).
Raw HTML, full canonical payloads, credentials and SQLite copies remain private
and are not committed. The final remote disposable tree is 7,642,062,369 bytes; live managed storage is
2,980,126,720 bytes plus the 1-GB reserve, for an 11,622,189,089-byte measured
subtotal. Local verification images/build scratch remain separate and did not
exhaust the 30-GB aggregate budget. Copies, migrations, backups, staging and SQL
scratch are retained and charged; no backup was cleared to improve these figures.

For reproducible serving comparisons, use `repair_benchmark.py` on an offline
legacy copy with the pinned installed image, and then on the v5 candidate using
the current installed image. Seed each read catalog once before the overlap run.
Retain the same providers/cohorts/resource caps, private config/source identity
and consistent frozen baseline. Do not run this against live volumes.
