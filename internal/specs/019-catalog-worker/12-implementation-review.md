# Private implementation review

## Current verdict (2026-10-04, second endurance failure)

**M0–M4 remain incomplete. M5/C7/C8 stay closed.** Read10 for current executed
results and11 for dated failures; audit tables below are historical.

The second24h run failed after 92 updates at 79935.900 s in the 120 s semantic
validator. Exact 93/92/91 inputs, signed manifests, DB/receipts/tools/logs and
samples are preserved; automation paused and source stopped. Current same-byte
probes and four real HTTP admission replays pass under unchanged resource caps,
with validation 43.3–46.8 s. The second timeout's cause remains **unresolved**;
these short results do not explain or relabel it. Backoff now implements the
specified 5/15/60-minute retries; harness journals survive exception exits and
sampling includes CPU pressure/guest clock/scheduler counters. No deadline,
validation rule or distribution protocol was changed. The bounded shaped
regression is recorded in 10; no new actual24h run has been launched.

The original24h run failed after10 updates at9088.405s in the120s semantic
validator. Byte-identical failed input reproduces the deadline under8 readers
and evicted candidate cache. Changing only the validator's cache8→32 MiB
roughly halves logical page reads, passing the controlled repetition94.374s.
CPU/I/O/cache churn dominate; measured scheduling/throttle/reclaim are smaller.
The exact historical host contribution is unknown because per-child counters
were absent. Current installed repetition passes46.316s; host/cache/Python
variation prevents treating that result as a second controlled speedup. No
deadline/check/consumer resource cap was raised or weakened.

Identical-artifact renewal now verifies the new signed manifest and hashes the
retained file using a current source/origin/pin-bound validation receipt. Atomic
activation retains the previous distinct artifact. NULL/old receipts receive
full revalidation; trust/row-contract changes require full admission. Real local
HTTP tests prove zero artifact-body transfer across restart, with corrupt/missing
files, invalid manifests, cancellation and commit failure handling. Additive
private migration0008 preserves mainline state. Installed core289 and API catalog
plus migration249 checks pass in Linux arm64 images; native core289 is separate.

Actual fresh exports confirm ordinary listing/title/canonical timestamps dirty
full snapshots.60 new language releases in2m stored history still cost257.885 MB;
1-MiB fixed chunk reuse would transfer176.783 MB because compact join keys/indexes
shift during export. Unchanged collection produces identical bytes.48 distinct
daily changes across three measured-size providers derive37.136GB/client/day.
Recommend a stable-key/bounded-delta benchmark before a reviewed distribution
extension; no delta/shard, freshness relaxation or quota change is implemented.

The worker retains current plus previous per provider within30 GB **total**,
including state, staging, backups, open transfers/logs/runtime. The earlier
20,226,560,160-byte full footprint subset remains passing synthetic evidence.
The isolated six-export footprint6,107,614,272 bytes is not its replacement.
404/410 references get one manifest refresh/retry without losing last-good.
Earlier72h/576-GiB assumptions and failures remain historical.

Short full shaped regression passes900.881s/debug-passed:two distinct artifacts,
8900 error-free searches,p95≤.066s/p99≤.073s,12 durable histories,source switch/
503/stall recovery. Independent sampler finishes16 rows with explained warmup/
update steps and a final RSS plateau,noOOM/throttle. This cannot prove24h leak
freedom. Full-size HTTP renewal transfers zero bodies across restart in0.70–
0.77s,recovery0.61–0.66s. Failed harness launches remain in10/11. Shared
activation passes600 actual SIGKILL recoveries at six named boundaries. Final
repeated-poll trust/cancel guard has a reproduced pre-fix failure and current
54-pass focused suite. Current-image full-size HTTP renewal/repeated-poll/restart regression also
passes with zero bodies in0.61–0.80s. The second actual24h/100-update retry began2026-10-03T16:32:05UTC and failed
after92 updates; its final installed image713553… and frozen inputs remain
in10. The follow-up is paused to prevent conflicting cleanup. No pass is claimed.

Selected collection remains AniWorld/Serienstream recent hints, targeted metadata
and private canonical cache, plus reserved bounded historical reconciliation.
The prior full50k/1m/2m sparse synthetic scheduler passes240 targeted/4 signal/
59 historical starts,148–150s simulated drain, no starvation and retained gaps.
Original875h full-active stress remains failed. Real observation→publication→
installation freshness, historical removal/outages under concurrency, provider
association/special/client disagreement and finite constraint/inner-fsync cases
remain open. New shared activation has600 real SIGKILL cases; every inner fsync is not proved.

Megakino's bounded HTTPS cookie bootstrap reaches metadata in Docker; one private
TMDb association is established. Selectable language/usable labelled offers and
live media/import are unverified; the maintainer keeps the live-media gate blocked.
AniWorld earlier extraction is separate from canonical→client import/playback.
Native amd64/Windows environments remain missing. No new TMDb credential is
needed. Generated import suites were not unnecessarily repeated.

No push, PR, production migration, deployment or public launch occurred.

Reviewed 2026-09-30 against the ordered handoff and final uncommitted diff on
`zzackllack-aux/catalog-worker-implementation`. Exact commands, versions, source
fingerprint and results are in [10-implementation-evidence.md](10-implementation-evidence.md).
This is a dated requirement audit, not permission to launch or a completed gate register.

Continuation authorization (2026-09-30) supersedes the historical lack of commit
permission below: local commits are now authorized. Compact internal keys and
normal-client RSS workflows may be investigated and implemented with measured
comparisons and explicit schema/criterion changes. Named HTTPS provider
alternatives and one movie metadata page are supplied. Existing failures are
not relabelled; results and remaining gaps are recorded in 10. Pushes, PRs,
publication, production changes and M5 remain unauthorized.

## Requirement checks

| Requirement | Implementation and executed evidence | Assessment |
| --- | --- | --- |
| Committed handoff, baseline, mainline compatibility | HEAD 00437b3 retains the spec; native/Linux mainline baselines each pass 175 tests; no #119 migrations reused | Baseline established; implementation remains uncommitted |
| Separate installable contracts/worker/API | Independent uv projects, installed wheels, arm64 Docker tests; amd64 builds/emulated core; macOS onefile health | Platform matrix partial; native amd64 enforcement/Windows missing |
| Exact schema, signatures, identities, bounded artifact admission | Core schema/row/header/manifest/identity/magnet tests; hostile mutations expose and fix read-only CHECK/WAL blind spots | Passed tested cases; complete constraint-mutation inventory remains open |
| Selected snapshots and local search | Store/Updater/search; signed HTTP fixture, local ID/title/category/season/offset and concurrent reader tests | Implemented; no hosted search or fallback to provider search |
| Last-good snapshots, atomic trust floors, source provenance | Versioned receipts, retained rollback, source A/B and revoked-key tests; 600 real SIGKILL cases and ENOSPC recovery | Passed measured cases; not every inner fsync/disk failure |
| Independent metadata-only providers | AniWorld first, s.to language/pagination fixtures and megakino movie fixtures; private worker and allowlisted export | Three adapters implemented; observed megakino serial structure/live mapping absent |
| Canonical mapping in worker, conservative evidence | Canonical matchers, reviewed season correspondence, export-rights inventory and provenance rejection tests | No ordinal/guessed correspondence; real all-provider mapping proof open |
| Bounded canonical ID-miss fallback | Local ID-hit/conflict checks, exact title/year candidate matching, source deadlines/singleflight/cache tests | Local hit makes no canonical request; missing episode maps stay unresolved |
| Checkpoints, quarantine, discovery history | Listing/detail transactions, durable leases/rates, first-seen ledger, eight real publication/crawl SIGKILL cases and writer failure | Tested subset passes; full scheduler/freshness/checkpoint matrix open |
| Durable acceptance before local resolution | Frozen requests, aliases/CAS, supervised executor; actual Sonarr/Radarr generated imports | Implemented; temporary failures stay asynchronous |
| Explicit blocked/retry/pause/cancel after restart | Job tests and real clients: paused zero requests, blocked two polls/restart, explicit retry/cancel/remove | Generated-client slice passes; broader provider/state matrix open |
| No HTTP event-loop database stalls or abandoned background writers | Offloaded transactions; real SQLite writer locks, HTTP <500 ms, cancellation and startup ownership tests | Tested cases pass; full sustained HTTP load remains unmeasured |
| No blocking search quality probe, honest unknown evidence | Scoped optional queue, deadlines/child admission, cache/actual-probe tests; real restrictive/Unknown profiles | Unknown size0/height/codec preserved; disagreeing-quality client matrix open |
| Real RSS, stable IDs/first_seen | Persistent language discovery, feed ordering/pagination/identity tests, actual Sonarr experiment | Later burst passes; bootstrap **100/1000 after two cycles**, gate failed |
| Authenticated local management, no browser/WebUI | Independent bearer token, CORS/body/rate/CAS/idempotency tests; overrides/refresh/rollback/job endpoints | Implemented and fixture-tested; no WebUI/browser implementation |
| Bounded targeted local refresh | Existing local IDs only, off by default, private observations/checkpoints/expiry and smaller overlay capacity | Implemented; full-scale/endurance/large correction history open |
| Bounded resources without raising limits | Linux process limits, 10k fixture, child/publisher ownership and transfer leases; full 50k fixture | Full artifact exceeds **2-GiB/512-MiB maximum**; C4 failed, schema decision pending |
| Mainline migration preserves data and rejects foreign schemas | Alembic 0004–0007, preflight/no-overwrite verified backup, disposable known revisions/files/hashes and interrupted upgrades | Tested fixtures pass; complete released-state/interrupt matrix open; no user DB used |
| User-local media and proxy STRM | Bounded host resolution/TLS/DNS, generated MKV and copied STRM import/decode; scoped playback registration | Generated transport/import proof; live canonical→import/playback gate open |
| Authorized live provider evidence kept separate | Exact AniWorld extraction/download/probe; exact s.to DNS failure and megakino script stub | AniWorld extraction only; C5b not passed; no bulk or substitute-content testing |
| User/env/deployment/agent guidance | Opt-in JSON/env/Compose examples, recovery and profile implications, docs build/Ruff/diff checks | Updated; public defaults absent |
| M5/public launch closed | No official source, public provisioning, deployment, commit, push or PR | Boundary preserved; no C7/C8 readiness claim |

The worker currently collects a single persisted page per provider turn rather
than exercising the specified concurrent pipeline. Its finite request/child
limits are not a substitute for measured ready-queue/writer-batch/freshness
behavior. Large job-history recovery/retention and qBittorrent projections still
materialize history. These remain implementation/resource review work, not
passed requirements concealed by the smaller benchmark.

## Decisions and environments still required

1. Full C4 fixture produces **2,169,835,520 SQLite /646,634,545 zstd bytes**.
   Proposed next experiment: a compact internal-join schema preserving public
   identities, with a reviewed DDL change. No schema or cap change was made.
2. Sonarr bootstrap coverage fails despite subsequent burst pagination.
   Proposed product refinement: explicit bootstrap search/backfill, with an
   explicitly revised acceptance case. No criterion, ordering or limit changed.
3. Authorized megakino film6444 supplies only a script stub. A usable specifically
   authorized movie input is missing; TMDb credential/source permission is absent.
   s.to fails DNS in the disposable environment. No browser/DNS bypass was used.
4. Native Linux amd64 resource execution and Windows packaging environments are
   missing. Linux-container pilot is authorized; native/frozen snapshot execution
   remains gated. No larger child limit was substituted to satisfy emulation.

No pending decision is approved by silence. Shaping/100 updates/24-hour C4 and
the complete RSS/provider/client/migration/failure inventories remain open.
Private implementation progress does not establish release readiness.

## Suggested logical Conventional Commit boundaries

These are review boundaries, not staged changes or commits already made. Keep
required dependencies/tests with each increment and verify each resulting tree
before committing. No commit/push/PR action is authorized by this document.

```text
feat(catalog-core): add signed artifact and stable identity contracts

Introduce exact SQLite records, bounded admission and shared provider parsers.
Keep quality, jobs, credentials and media URLs outside published artifacts.
```

```text
feat(catalog-worker): collect and publish independent provider snapshots

Persist crawl checkpoints, discovery history and conservative canonical maps.
Publish signed metadata with quarantine, retention and process ownership.
```

```text
feat(catalog): consume local snapshots and persist accepted grab jobs

Add atomic trust and recovery, local Torznab queries and frozen requests.
Resolve media locally after admission with durable blocked and retry states.
```

```text
feat(catalog): add scoped estimates and authenticated management

Expose corrections, refresh, rollback and job lifecycle endpoints.
Preserve honest unknown quality and stable RSS and proxy playback identities.
```

```text
feat(db): add guarded mainline catalog state migrations

Retain verified backups and original rows, hashes, paths and files.
Reject foreign schemas and revalidate older private admission receipts.
```

```text
test(catalog): add disposable client and crash experiments

Exercise pinned real clients with generated media and persistent failures.
Record resource measurements and keep live-provider evidence separate.
```

```text
ci(catalog): validate installed worker and consumer contracts

Build private Linux images and run installed contract suites on catalog changes.
Keep live access and all publication actions outside the workflow.
```

```text
docs(catalog): document the private pilot and unresolved gates

Update configuration, deployment, migration and internal agent guidance.
Record failed capacity and RSS gates without enabling public defaults.
```

## Subsequent compact storage review (2026-09-30)

The initial implementation is now locally committed in dependency order; see
10 and local Git history. The original review above remains dated evidence.
The approved schema2 refinement preserves every original fixture record and
fits default artifact caps at unchanged full cardinality. Exact v1/v2 layouts
and receipt revalidation are implemented. Installed contract/worker/consumer
suites pass; full correction-overlay p95 and a later cold validation run failed.
C4 remains open. Worker pipeline, large job history and the other original
functional/gate gaps are still required; byte-size improvement does not resolve
them or grant M5 authorization. TMDb connectivity is now proved; provider
mapping/media input and redistribution are separate requirements.

## Subsequent RSS workflow review (2026-09-30)

05's exhaustive bootstrap criterion is replaced under explicit maintainer
approval by pinned clients' existing historical search and new-release/catch-up
workflows. Both clients now pass the recorded explicit-search, unmonitored,
1,000-entry burst, controlled 23-hour cursor gap and restart/dedup subset. No
control service, stored *arr credentials or automatic library-wide search is
introduced. Original bootstrap failure remains historical evidence. Latest
full-size correction overlay passes narrowly; complete C4/C5a, worker pipeline,
large history and other M0–M4 gaps remain open. M5 remains unauthorized/closed.

## Subsequent implementation and capacity review (2026-10-01)

One-writer pipeline and bounded durable histories now have focused/installed
proof in10. Full compact SQL publication preserves logical identities/provenance;
full mapped queries and shaped cold install pass named subsets. Prior failures
remain visible. Exact schema compatibility is explicit.

Mainline tests now cover all states/revisions/exact unversioned layout, backup
sync boundaries, later-DDL interruption and actual pinned PR119 rejection.
The named C6 matrix passes without implying exhaustive SQLite/VFS coverage.
Worker backup safety is independent of this API migration evidence.

M0–M4 remain incomplete: full steady-backlog freshness,100 updates/24h, RSS
activation/estimate failures, complete adversarial inventory, usable live movie
metadata and authorized end-to-end media proof, native amd64/Windows execution.
Native CI is prepared, neither pushed nor run. M5 remains closed.

## Current requirement verdict and local commit inventory (2026-10-01)

The tables at the start of this file are historical. Current evidence is10;
all detailed prior measurements/failures now reside unchanged in11. Current
source at4a83571 passes full414-test API validation, installed106-worker/
247-core/217-catalog subsets, full bounded SQL publication/equality, full mapped
queries and10-Mbit/s cold install. The one-writer pipeline and bounded job/
TTL/qBittorrent history implementations supersede the old materialization review.
Named mainline and worker backup matrices pass; foreign experimental data remains
unsupported. RSS exact-GUID activation/catch-up and selected conflict/hung/hostile
estimate regressions pass separately from live-provider proof.

Current installed API/worker generated STRM experiments additionally pass real
Sonarr/Radarr query/grab/completion/library import and copied-URL FFmpeg decode.
Unknown-only rejects both clients' SDTV suffix interpretation; explicitly allowing
that client label in disposable profiles proves import without inventing quality
in AniBridge. This closes the previously unexecuted Radarr fixture STRM subset;
live-provider metadata/extraction/import/playback remains unverified.

Historical C4 full-active freshness **failed**:1050000 checked pages versus4800
permitted starts/4h. The accepted signal strategy and current evidence above
supersede the previously pending decision; the old experiment remains failed.100 shaped updates/24h remain unexecuted, not blocked by a fabricated
environment limitation. Complete constraint/inner-crash/provider/special/client
matrix remains open. Native amd64/Windows environments and usable authorized
all-provider metadata→media→client import/playback remain blocked/unverified.
Latest native macOS frozen legacy health passes; it does not prove snapshot
resource enforcement. No milestone is declared complete from aggregate test counts.
M5/C7/C8 remain closed, with no push/PR/production/publication action.

Dependency-ordered local commits (subjects reflect their actual increments):

- f0aa2a4 feat(catalog-core): add signed artifact and stable identity contracts
- 9b41c24 feat(catalog-worker): collect and publish private provider snapshots
- 7dcbb64 feat(catalog): integrate local snapshots and durable job management
- 5d0f537 test(catalog): add disposable integration and failure experiments
- 007c0b1 docs(catalog): record private pilot operation and unresolved gates
- 3c77ba1 fix(providers): preserve Serienstream metadata on current HTTPS pages
- 692053e feat(catalog): add compact versioned snapshot storage
- cfba361 test(catalog): prove normal RSS and historical search workflows
- c160132 feat(catalog-worker): run bounded collection through one writer queue
- 8b96d7e perf(catalog): bound durable history recovery and client projections
- 3bed41d ci(catalog): prepare native container and frozen package checks
- f1cfdc3 fix(db): batch interrupted mainline requests during catalog upgrades
- c6246e6 fix(catalog-worker): preserve blocks across concurrent observations
- 55cb295 test(db): cover backup durability and unversioned mainline state
- 43491be perf(catalog-core): validate compact relationships in index order
- 20e6377 fix(catalog-worker): prioritize active work and serialize circuit probes
- 857f392 test(catalog): measure full cold installs over shaped transport
- 8334700 test(db): reject the pinned experimental catalog schema unchanged
- ec036d4 perf(catalog-worker): export full snapshots with bounded SQL joins
- cbdfa80 fix(catalog-worker): verify and preserve original migration backups
- 9da9983 test(catalog-worker): measure full active backlog and request capacity
- fe3f875 test(catalog): cover RSS activation and estimate failure cleanup
- 4a83571 fix(catalog): suppress inherited quality after conflicting observations
- ed1c645 test(catalog): measure full discovery and mapping index costs
- c04d9b3 docs(catalog): reconcile the private implementation requirement audit
- 165aae9 test(catalog): prove generated Radarr and Sonarr STRM imports

Final source audit:372 source files, fingerprint
`b897787e0058b861b91fe9ca964249d8a86e3d5f8687b9681b3684296a71d190`;
252 task-diff files versus handoff, all Python syntax valid, no actual supplied
credential bytes or binary/database/media/data artifacts, no untracked omissions.
Tracked source matches committed HEAD. Project-cwd worker/API Ruff passes; a
root-cwd worker-test import-order warning reflects different first-party discovery,
not changed code semantics. Final docs-only reconciliation does not change that
source fingerprint. The inventory above precedes this final docs-only audit
checkpoint; Git history contains that checkpoint too. All local history is
preserved; public actions stay closed.
