# Runtime audit and v3 readiness — October 25, 2026

**Review: NOT READY. Merge into v3: NOT READY. Public production: NOT READY.**

The remote draft still contains reproducible input-validation, logging and reload
defects. Their fixes are committed locally, without push or hosted verification.
The proposed build also deliberately refuses ineffective filesystem locks: the
retained developer client's current Docker Desktop Mac bind mount is affected.
The running Linux service was inspected, not upgraded. Independent mapping,
client-compatibility, enforcement and capacity acceptance criteria remain open.

Measurements: [sanitized JSON](evidence/runtime-audit-2026-10-25.json).
Selected contract: [IMPLEMENTATION.md](IMPLEMENTATION.md). This document accounts
for the requested audit scope; VERIFIED below always names a finite proof.
UNCHECKED means an explicit remaining gap, not a passing result.

## Provenance and authority

| Environment | Revision and result |
| --- | --- |
| Initial checkout and remote PR head | `ff126cc2375275e9a829e6c69107ebf13008d759`; clean and synchronized before edits |
| Live collector and metadata | `52065c76aa8bb75d3df4fa43e4ebcd2cded5779e`, ARM64; private v6/public schema2 |
| Live immutable image | `ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1cc57eae123d842af0cc9fc9003356da7e4da3af3dada3b95764f58db4513106` |
| Local runtime fixes | `0a4583b` storage, `325b9bd` canonical validation, `94117fe` qBittorrent/privacy, `ceb0ece` reload, `d2824a3` verified-alias bound |
| Local verification tooling | `b3992ea` generated real-client assertions; `29d568c` snapshot accounting |
| Hosted tests | Run `40147656170`, source **ff126cc**, successful API/core/worker and final gate |
| Hosted previews | Run `40147656209`, source **ff126cc**, successful native AMD64/ARM64 builds and both manifests |
| Published ff126cc worker index | `sha256:d81fb146254797aa80884b35610dc450816132b1e08d6d9c1c78c27289c4a8f2` |
| Published ff126cc API index | `sha256:3011117352291b8ae8d4b565d359a868707485d4da8df53492b48247643b9b44` |

The worker ARM64 manifest's actual OCI label reports ff126cc. These published
images **do not contain the new local fixes**. No candidate image digest exists.
All original commits remain ancestors. `main` remains default/stable; `v3` remains
at `e14a041`. PR #170 is open/draft into v3, with no submitted reviews or unresolved
inline threads and `REVIEW_REQUIRED`. The PR body still describes older code,
deployments and test gaps; it was not edited under this authorization.

The v3 ruleset requires one approval, CODEOWNERS and resolved conversations, plus
CodeQL. Its only required status is `Conventional Commit Title`. The successful
`Tests / Required Gate` is configured but **not enforced** by that status rule.
Legacy branch-protection REST returned 404 because this policy uses rulesets;
the effective rules endpoint, not that 404, establishes protection.

XPipe's current `oracle-oc1` connection was generated using the maintained
XPipe-to-SSH README; no old socket/address was assumed. Coolify read inspection
confirmed the existing service. Its connector omits raw Compose, so this audit
does not claim a fresh saved-source/draft comparison. No Zen edits were made.

## Confirmed defects and local fixes

These are controlled reproductions against code also present in the reviewed
head. They do not establish that malformed inputs caused an old live incident.

| Priority / issue | Trigger → observed → expected; fix and regression |
| --- | --- |
| P1 / CQ-28, wrong parent proof | A descriptor with actual year 2022 plus a field named `parent` claiming 2020 was accepted for a 2020 source. `canonical.Enricher.tick` trusted a remote field used internally for compact proof. It now derives fresh proof from actual descriptor fields. Wrong-year evidence conflicts; valid same-year metadata still works. Four cases cover a forged object and a malformed list. |
| P1 / CQ-29, worker interruption | A legacy episode ID supplied as a list raises uncaught `TypeError`; a season/episode of `2**63` reaches SQLite and raises uncaught `OverflowError`. Both escape ordinary retry persistence. `descriptors.episodes` now validates IDs and contract coordinate bounds before writes. Three cases retain source state and a future retry instead of stopping the tick. |
| P1 / CQ-28 follow-up, retained proof | Missing/list/incomplete cached parent proof could fail before remote recovery. CodeRabbit raised one major issue on this boundary. `parent_evidence.status` treats invalid proof as unverified and `descriptors.cached` makes it a miss. Three regressions reacquire valid metadata without deleting history; the bounded descriptor-plus-search alias case also stays valid. |
| P1 / CQ-30, ineffective ownership | On this Mac bind mount, two independent `flock(LOCK_EX|LOCK_NB)` calls both succeeded. The migration exclusion regression failed there and passed on Linux-local scratch. `ProcessLock` now verifies exclusion through a second handle before granting ownership, closing handles on refusal. Its unsupported-filesystem regression fails against the old implementation. **Breaking safety change:** a writable state directory on such a filesystem is refused. |
| P2 / CQ-31, false torrent filtering | `filter=completed` returned incomplete legacy aliases in query mode; the legacy route ignored the filter entirely. A shared completion predicate now filters the complete legacy/durable stream in both modes. Six request tests include completed/active/missing-job history and a paused durable alias, consume JSON fully, and verify unchanged database bytes. |
| P2 / CQ-32, private input logging | Rejected `urls` and magnet-helper diagnostics exposed submitted private strings. The route and helper now use constant messages and safe hashes, including parse errors. A captured-log HTTP rejection failed before the fix; full magnet behavior regressions still pass. This is a bounded repair, not a promise that all older downloader/proxy logs are private. |
| P2 / CQ-33, broken reload selection | `reload_env = ..., CATALOG_CONFIG` created a tuple, so `true` and `1` never enabled reload. The accidental tuple is removed. Four tests intercept actual `uvicorn.run`, check true/false/1/0, and retain disabled query access logging. |

A depth-only JSON suspicion did **not** reproduce the proposed crash on this
Python runtime. The confirmed failures above use actual malformed fields. No
historical discarded stderr was reconstructed or assigned a speculative cause.
There is no schema, matcher-version, provider-rate or environment-variable change.

## Live facts and exact denominators

Both containers retained their October 19 start times and zero restarts/OOM kills.
Collector: 2 CPU/2 GiB/no extra swap; metadata: 2 CPU/512 MiB/no extra swap.
Canonical admission remains the operator's shared 90/minute budget, not a known
upstream quota. Backend `172.16.27.0/24`, the existing `172.28.0.0/16` project
network and Docker's `10.254.0.0/16` pool split into /24s remain unchanged.

Each provider backup pinned a read transaction before SQLite backup. Committed
WAL data is included; transferred hashes matched. The providers were captured
four seconds apart, so this is one consistent snapshot **per provider**, not a
cross-provider transaction. Every before/after comparison uses those same inputs.

“Usable episode” below means an observed episode with at least one retained
positive language release. It does not count unsupported/unavailable content as
successful mapping. All retained releases are observed variants; none are media
availability measurements. There are no effective tombstones or unsupported
titles in this snapshot, so the published counts equal these raw release totals.

| Provider | Observed episodes | Usable | Usable mapped | Usable unresolved | All map rows | Releases | Mapped releases | Unresolved releases |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AniWorld | 63,724 | 63,709 | 46,771 | 16,938 | 46,774 | 116,727 | 91,954 | 24,773 |
| Serienstream | 307,605 | 299,126 | 237,704 | 61,422 | 242,715 | 381,676 | 312,257 | 69,419 |

The 15/8,479 episodes without a retained release are outside the usable
denominator. Serienstream separately retains 8,478 unavailable observations and
one unknown-language observation. Those observations are not additive mapping
categories. Detail failure/pending sets can overlap and are not summed.

The following primary buckets partition unresolved usable episodes exactly.
Canonical retry state takes precedence over correspondence rejection; the other
reasons come from the actual matcher decision path. No overlapping totals follow.

| Primary reason | AniWorld | Serienstream |
| --- | ---: | ---: |
| Retrying canonical failure, including future deadlines | 99 | 2,599 |
| Unresolved parent | 5,525 | 8,977 |
| Conflicting/unverified parent facts | 1,267 | 7,315 |
| Missing name | 0 | 6 |
| Generic name | 1,371 | 13,369 |
| No name candidate | 8,426 | 27,536 |
| Duplicate source name | 215 | 1,279 |
| Duplicate canonical candidate | 4 | 41 |
| Unproved season context | 25 | 117 |
| Coordinate conflict | 6 | 172 |
| Alias conflict | 0 | 11 |
| **Total** | **16,938** | **61,422** |

There are zero never-checked canonical title records and zero currently overdue
canonical retries at the pinned clock. This supersedes October 20's *current*
stall population, not its reproduced bug. Descriptor rows: 2,216/10,160;
144/650 are expired. Another 13/204 legacy cached parents lack a compact descriptor.
Descriptor expiry and parent retry deadlines are separate clocks; neither means
that an HTTP attempt is currently admitted. Input hashes, versions, negative
results, shared descriptors, late arrivals and changed evidence have regressions.

AniWorld has no retained page failures or expired work leases. Serienstream has
90 failures, one scheduled due three seconds before the snapshot clock, no
expired leases, and a maximum 3,554 retained attempts. Attempt buckets are
1/86/2/1 for 1–9 / 10–99 / 100–999 / 1000+. The oldest retained successful-check
timestamp is **not** a first-failure age. The ledger cannot associate each current
failure with a persisted last HTTP status/reason; logs deliberately omit paths.
CQ-34 therefore remains unchecked instead of guessing those facts.

Retained logs cover the last 24 hours: 285 Serienstream HTTP 500 page failures,
96 page 404s, seven HTTP-200 `parent_children_missing` cases, and smaller bounded
transport-error classes. There are no retained page/canonical 403/429 records in
this window. That is no evidence of current Cloudflare throttling, and no proof
that throttling never happens. Successful publication child records: 123/93;
there are no retained child/maintenance failures in this window. Both recent
feeds still latch gaps; pending gap parents are 0/5. Eight Serienstream quarantine
decisions remain unapproved and untouched.

## State, query, client and resource proofs

All **498,403 release rows, including first-seen values**, and **289,489 map rows**
survive. This preserves even maps that still need accuracy review. The full Linux
rehearsal hashes every row/column of 38 retained tables per provider in stable
order. Only `worker_meta.dirty/published_at` and v6 publication bookkeeping are
allowed to change. Source observations, parent IDs, descriptors, schedules,
failures, leases, omissions, quarantines and matching history compare exactly.
All live pre-v4/pre-v5/pre-v6 backups and `/state/backup` remained untouched.

| Experiment | Result and boundary |
| --- | --- |
| Same frozen ledger, old 52065c7 vs local scheduler, 30 ticks/provider | Both idle; zero network requests, attempts or maps. Scheduler wall/CPU is in JSON. No request-efficiency improvement follows from idle work. |
| Existing 215-case labels | All 118 positives still resolve; six supplementary ambiguous entities stay unmapped. Seven pre-existing maps outside positive labels remain. Labels followed the original tuning, so this is regression evidence, not a blind population precision trial. |
| Mac Docker copied full publication, 2 CPU/2 GiB | 4.401 s / 30.284 s, excluding source startup. Sequential, uncontrolled cache conditions. Eight copied queries match SQL; failed export retains last-good pointers and absent-provider serving yields 503 while the sibling yields 200. This run predates the new Mac-bind refusal and makes no lock-exclusion claim there. |
| fra-node-01 full-size installed-wheel rehearsal, 2 CPU/2 GiB, no network | Same frozen ledger on Linux storage; supported lock probe passes. Source reopen + publication + after-row-hash work takes 15.502/77.334 s per provider; this is **not publication-only latency**. Whole wrapper CPU 128.921 s; peak memory 1,895,440,384 bytes; no OOM/max events or throttling. Block I/O: 1,978,306,560 read / 330,211,328 written bytes. |
| Compatible worker rollback rehearsal | Actual installed 52065c7 reopens both resulting v6 ledgers, retaining exact release/map/work/parent counts. No v5 downgrade or ledger restore is needed. |
| Nine live metadata requests | Shared read lease pins each provider's published pointer through SQL and HTTP. Revisions 3839/4156; exact totals 116,727/381,676. First/second recent pages have no duplicate IDs. Native required targets return three/three/two releases; large season returns 500+10 unique rows. Complete bodies pass; latency 5.1–191.3 ms; unauthenticated POST 401. |
| Required live mapping rechecks | AniWorld Classroom S04E16 and One Piece S01E01 each return three releases. One Piece season 21 returns 510 unique releases. This verifies current published maps, not their independent accuracy or media acquisition. |
| Retained developer client | Still stopped on 428b5d8, with its original bind mounts. A consistent copied DB streams all four aliases through both endpoints at 1 CPU/512 MiB: three missingFiles warnings and one available completed STRM. Copied bytes stay identical; 5 jobs, 4 aliases, 2 durable requests, 0 corrections. No scheduler started on retained data. |
| Real generated acceptance, both providers | Digest-pinned Sonarr 4.0.20.3014 and Prowlarr 2.6.5.5623; current source overlay using unchanged locked dependency images. Real search, sole grab, production job/transfer/remux/receipt, intermediate torrent and Sonarr remaining bytes, completion and generated-file import pass. One attempt. API restart and six-second history/library check pass. Stacks stopped; acceptance volumes retained. |

Both real Sonarr imports retained source files. Actual post-move behavior is
covered by import-move unit tests and read-only historical missing-output
projections, **not a newly observed Sonarr move**. No browser check was made, so
there is no visible progress-bar claim. The generated hook supplies HTTP input
only and is mounted only by the acceptance overlay; normal Dockerfiles do not
copy it. No provider media was acquired or played. Sonarr's two selected public
descriptor/artwork lookups worked; an external metadata outage remains a
dependency, with no new fallback. Issue #175 remains an idea beyond these two
strengthened finite scenarios.

The live collector's sampled CPU/memory changed from 6.13%/399.6 MiB to
37.44%/415.6 MiB, metadata about 0.14%/67 MiB. Collector cumulative block writes
were 273→274 GB since container start: this is cumulative I/O, **not disk space**
or patch-attributed traffic. Live publication phase medians: preflight 0.847/4.173 s,
export 0.638/3.872 s, validation 1.673/8.923 s, pointer commit 0.011/0.023 s.
The snapshot, metadata, source waits and publication phases are different work.
No writer occupancy, fully classified eligible-age trace, sustained rate, fresh
bootstrap duration, upstream ceiling or 4 CPU/4 GiB benefit was measured here.
Nothing supports a database-engine migration or a rate/resource increase.

## Complete audit matrix

Common environments: live **52065c7**, hosted **ff126cc**, local commits above;
Linux means ARM64 2 CPU/2 GiB unless the table says otherwise. Test filenames are
under worker/core/API tests as named; JSON contains the finite measurements.

| ID | Status | Path / evidence | Remaining scope or exact blocker |
| --- | --- | --- | --- |
| A1 Inventory → title/season/episode → durable work | VERIFIED | `listing`, `Collector`, `State.detail`, `batch`, signals; collection/private-operation suites; exact snapshot totals | Observed inventories can grow; no complete-provider claim |
| A2 Capped feeds, pagination and new-child reconciliation | VERIFIED | `signals`, `State.claim`, signal/collection repair tests; live gap markers and 0/5 gap parents | Lossless provider feed coverage is UNCHECKED; feed caps and historical gaps cannot prove it |
| A3 Unknown language, subtitles, unavailable/missing/empty markup | VERIFIED | core episode-row/recent tests; sto/collection/finale cases; live 1 unknown and 8,478 unavailable observations | No inferred audio; stable upstream gaps remain |
| A4 Retry/admission/circuit/cached retry/lease fairness | VERIFIED | retry/transport/cached-retry/canonical-rate/circuit tests; snapshot zero overdue canonical retries and expired leases | Synthetic fairness is not live eligible-work throughput; cached retry repair remains undeployed |
| A5 Retained failure reason + HTTP status + first-failure age | UNCHECKED | `work` has attempts/deadlines/checks; bounded logs have aggregate classes | CQ-34: no durable per-path last class/status/first-failure clock; cannot join path-free logs |
| A6 Hours-scale full bootstrap and sustainable maintenance | UNCHECKED | Status separates first-pass from mapping and feed gaps | No fresh full bootstrap/endurance campaign authorized or measured |
| B1 Exact denominators/disjoint unresolved partition | VERIFIED | `audit_snapshot.py`, actual `correspondence.decisions`; tables above | Retained observations, not provider population completeness |
| B2 Parent/episode IDs, provenance, no numbering/similarity acceptance | VERIFIED | canonical/ID/matching/finale tests; new malformed proof/ID cases | Existing uncertain maps retained; no historical wrong-map cause inferred |
| B3 Descriptor acquisition vs local rematching, reuse and freshness | VERIFIED | fingerprints, `descriptors`, cache/retry/rate/late-arrival tests; 2,216/10,160 descriptors | Current live requests per useful new map and full eligible-age classes UNCHECKED |
| B4 Prospective independently labelled trial | FAILED | 215 fixed cases, 118 positives, development/held-out chronology in MAPPING_IMPLEMENTATION | Labels followed original tuning; a new prospective independent trial or explicit contract decision is required |
| B5 Multilingual/annotations/specials/split seasons/cuts | VERIFIED | finite matching/identity/finale fixtures and retained label evaluation | Population precision and newly labelled broad unresolved cohorts UNCHECKED; no matcher tuning in this audit |
| B6 Required current named targets | VERIFIED | live SQL/revision-paired native checks, including large pagination | Published-map existence is not independent provider-order ground truth |
| B7 Anime-Lists/TheXEM/provider-order and Sonarr conversion | UNCHECKED | research reviewed; no adapter integrated | Source order binding and a real differing scene→canonical Sonarr case remain untested; do not adopt research as a map |
| C1 Observation → journal → export/proof → pointer → reader | VERIFIED | v6 triggers, export/snapshot/clone/ack code; publication tests and full-size retention | Generation acknowledgement retains later fixture WAL writes; no distribution system added |
| C2 Corruption/tampering/receipts/partitions/cancel/crash | VERIFIED | publication follow-up/migration/validation-scope tests installed on Linux | Finite injected failures, not long crash/endurance proof |
| C3 Fresh full-size concurrent publication/query workload | UNCHECKED | Historical overlap evidence retained; current fixture overlap passes | Today's full-size runs are sequential; no new final-candidate full-size overlap/stress claim |
| C4 Migration/backup/idempotence/rollback/reopen | VERIFIED | Linux migration/private-operation suites; full v6 old-code reopen | Actual installation migration and long storage recovery not performed |
| C5 Entire release/map/history/correction preservation | VERIFIED | 38 retained tables/provider, both directions/hash equality; copied client unchanged | No nonempty live corrections; correction precedence is fixture proof |
| C6 Query totals/isolation/pagination/corrections before policy | VERIFIED | nine live pinned SQL/HTTP checks; copied last-good/isolation; query/correction tests | Current targets are within the retained recent cohort; no population/freshness SLA |
| C7 Cache invalidation/coalescing/revision/outage/timeout | VERIFIED | query/client/provider tests, including cancellation and partial provider failures | Positive stale cache is bounded prior-page coverage, not general outage availability |
| C8 Strict aggregate disk peak and next-copy admission | UNCHECKED | sequential server/Mac/archive/image inventories, reserve; own scratch retired | No certified continuous peak or exact shared-layer attribution; conservative aggregate accounting blocks another full-copy/upgrade admission |
| D1 Torznab grab → frozen identity → durable job/output | VERIFIED | two generated real-client flows; jobs/runner/executor/magnet tests | Separate from live provider acquisition |
| D2 Mixed history, missing jobs, states/categories/paths/full streams | VERIFIED | legacy-history/filter/completion/batch tests; actual copied four aliases | No corruption-tolerant proof for every arbitrary private DB mutation |
| D3 Exact/estimated/unknown size, tracks, retries, STRM/counts | VERIFIED | synthetic HTTP/HLS and progress/receipt/STRM tests; configured fake peers retained | Size/quality/counts are not invented measurements; unknown totals remain unknown |
| D4 Real Sonarr intermediate progress/import/restart | VERIFIED | two finite digest-pinned Sonarr/Prowlarr runs; generated byte hashes and attempts | Six-second post-restart window; source-retaining imports |
| D5 Real Sonarr move plus longer duplicate-prevention recovery | UNCHECKED | unit move/explicit retry and historical copied history pass | Actual runs kept source; no new real move or long restart campaign |
| D6 Visible browser progress, provider import/playback | UNCHECKED | No UI/media proof claimed | Browser omitted; real provider acquisition outside authorization |
| D7 Metadata service/Sonarr external outage independence | VERIFIED | local cache/provider isolation and frozen-source job tests; selected descriptors fetched | Complete Sonarr metadata outage E2E is UNCHECKED; no substitute emulator |
| D8 Public qBittorrent authentication | FAILED | Existing auth route accepts login; deployment guidance requires private/local exposure | Product hardening decision remains open; no new authentication system introduced |
| E1 Outbound URL/redirect/DNS/TLS/session/decoding bounds | VERIFIED | maintained transport/pinning code, core/provider tests and actual installed AniWorld tests | Fixture/mocked transport proofs do not prove live TLS against every host; metadata still has a writable worker-state mount, so filesystem privilege separation is not hardened |
| E2 Malformed canonical inputs and private proof recovery | VERIFIED | new wrong-year/list/overflow/cache/alias regressions | No exhaustive adversarial fuzzing or audit of every unused JSON field |
| E3 Secret/query logging boundaries | VERIFIED | worker allowlists, query access logs disabled, captured-log Torznab/grab tests | Complete legacy downloader/OS/proxy logging privacy UNCHECKED |
| E4 Child limits/cancellation/shutdown and async boundaries | VERIFIED | Linux supervisor/executor/runner/resource tests; finite production job children | Sustained event-loop blocking, pool saturation and FD growth UNCHECKED |
| E5 Dependency exposure across supported platforms | UNCHECKED | branch locks, installed Linux/macOS behavior, current advisory inventory | Werkzeug Windows and setuptools macOS-sdist advisories remain locked; docs advisories also open; no full OS patch/SBOM closure |
| E6 Full-path profiling and short 2/2 resource samples | VERIFIED | phase medians, copied publication, Linux cgroup CPU/memory/I/O, query latency | Sustained capacity, lock/writer occupancy, exact physical Mac backing I/O and eligible-class age UNCHECKED |
| E7 Filesystem/platform support | FAILED | actual Mac-bind exclusion failure; fail-closed fix; native Linux/macOS tests | Developer state must move safely before candidate startup; Windows resource enforcement remains outside this Linux pilot |
| F1 Frozen project and installed-wheel checks | VERIFIED | Mac API 313/18, core 322, worker 287/13; Linux core 322/worker 300; API 148 | Linux API uses explicit current-source overlay and unchanged locked dependency image; no candidate native AMD64 hosted run |
| F2 Lint/workflow/static gate behavior | VERIFIED | changed-file Ruff, full API Ruff, Pylint 8.43, actionlint, gate tests | Worker-wide lint has existing findings outside hosted lint scope; warnings accounted below |
| F3 Hosted results for new final local source | UNCHECKED | ff126cc results and manifests are final/successful | No push authorized; local fixes have no hosted source-SHA proof or published image |
| F4 Enforced unconditional test/build merge gate | FAILED | effective v3 rules require title only; tests final gate exists | Policy change unauthorized; safe unconditional package/image build gate still absent |
| F5 Review approval and current PR description | FAILED | REVIEW_REQUIRED, no reviews; historical body drift | Maintainer must update the concrete PR after approved push; no PR edit/draft transition performed |
| F6 Stable/default/prerelease release policy | UNCHECKED | all workflows and v3 transition checklist reviewed | main stays stable/default; prerelease/default/retention/external integrations remain separate release decisions |

## Tests, warnings and reproduction

Use Python 3.14 explicitly; `uv --project` alone does not change pytest's working
directory and can select the host's Python 3.15. The first such invocation was
discarded as a harness error. Final commands run inside each frozen project:

```sh
(cd packages/catalog-core && uv run --python 3.14 --frozen pytest -q)
(cd apps/catalog-worker && uv run --python 3.14 --frozen pytest -q)
(cd apps/api && uv run --python 3.14 --frozen pytest -o addopts='--cov=app --cov-report=term-missing' -q -rs)
actionlint
git diff --check
```

API coverage is **62% of 9,943 measured app statements** on the final run; it is
line coverage, not mapping/scenario/operational confidence. Core/worker coverage
was not measured. Do not infer a scenario percentage without a defined universe.
Mac skips are Linux child enforcement; the targeted Linux suites exercise them.
Coverage mode emits 79 warnings (TestClient deprecation and resource warnings),
plus an exit-time terminal-log warning. Several allocation sites are test/SQLModel
paths; a production leak is not established and a leak audit remains unchecked.
The non-coverage focused Linux run emits one deprecation warning.

Changed files pass Ruff; full API app lint/format passes; Pylint is 8.43/10.
Worker-wide Ruff reports existing discrepancies (including test import grouping)
outside the configured hosted API-app lint scope. They were not mass-reformatted.
CodeRabbit reviewed 11 changed files and raised one major issue, addressed with
the cache-parent regressions; this is not a review of all 73k added PR lines.

For Linux wheel checks, build both wheels with `uv build --wheel`, install them
without dependencies into the retained matching worker dependency image, and run
the actual installed imports/tests with network disabled, 2 CPU/2 GiB/no extra
swap. Keep writable scratch **inside Linux storage**, not a Mac bind mount.
Source overlays and installed wheels are identified separately in the JSON.

For a future admitted copy replay, use the same pinned baseline/clock and
`cached_retry_replay.py --phase before|after --now 1792889446 --ticks 30` under
old/new code. The current inputs are idle; do not reset deadlines to manufacture
an effect. `audit_snapshot.py --root COPY_ONLY_DIRECTORY --now 1792889446`
performs bounded read-only accounting and refuses a WAL sidecar. Existing
`evaluate_mapping_labels.py` consumes the committed label fixture. Full-copy
publication/query/preservation and Linux resource receipts are in JSON. Raw
ledgers, original metadata and private paths stay outside Git.

The initial Linux API bind-mount run has one failed migration-ownership test;
it is retained as a real filesystem failure, not erased by the 25 passing
Linux-local DB checks and final 148 passing local-filesystem tests. An early
restart verifier failed on expected connection refusal during startup; its ready
probe was fixed and both restart checks passed. An AppleDouble wheel sidecar
initially failed archive loading before touching copied state; it was excluded
and the full Linux rehearsal passed. These failures do not establish live causes.

## Disk and retained material

Initial free space was about 33.4 GB on the Mac and 87.9 GB on fra-node-01. The
worker's own status accounts about 6.8 GB including its runtime reserve; that
does **not** include research copies, every image or Mac archives. Sequential
inventory found about 19.7 GB of server files outside/inside managed roots,
plus the new audit material during experiments. Exact inventory/projections are
in JSON; image layer sums may double-count shared content.

The initial admission did not combine every historical Mac image/archive in one
inventory. Therefore this audit cannot certify a continuous aggregate peak below
30,000,000,000 bytes. After comparisons, only this audit's redundant Mac writer,
Linux writer/read scratch and test scratch were retired; the original frozen
baseline, query artifact/results, all historical archives, rollback images and
every live backup generation remain. A conservative combined projection still
does not admit another full snapshot plus maximum publication/scratch. **No more
full-copy work or rollout is admitted by this report.** Resolve physical shared
image attribution or explicitly review archival of owned disposable material
before new image/snapshot/migration admission. Do not prune backups or unrelated
images, or delete rows to make totals look better. Export containers used
`--log-driver none`; no binary archive was sent through Docker JSON logging.

## State-preserving operational plan — not executed

Worker state remains **v6** and public schema **2**. There is no matcher reset or
new migration. Full Linux publication/preservation and old-code reopen pass.
Future rollout must select the **new final tested source**, not ff126cc merely
because its image exists. Its new image and hosted checks are currently blocked
by the no-push boundary. This is an explicit placeholder, not a usable digest:

```sh
REVISION=FUTURE_HOSTED_TESTED_40_CHARACTER_SHA
WORKER=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:FUTURE_VERIFIED_DIGEST
OLD_WORKER=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1cc57eae123d842af0cc9fc9003356da7e4da3af3dada3b95764f58db4513106
uv run --project apps/api --python 3.14 --frozen python scripts/catalog/query_pilot/prepare_worker_update.py \
  --revision "$REVISION" --compose "$PLAN/current-compose.yaml" \
  --worker-config "$PLAN/worker.json" --expected-old-image "$OLD_WORKER" \
  --directory "$PLAN/reviewed"
```

Before that command, obtain fresh saved **raw** Compose through authenticated Zen,
preserve unrelated drafts, verify both initializer and active worker JSON, and
resolve total disk admission. The read-only Coolify token stays read-only. Review
the exact image-only diff/rollback; preserve all three references, configuration,
allocations, networks, volumes and backup generations.

Only after separate approval: pull/inspect the exact new digest, stop the existing
service in Zen with Docker Cleanup off, confirm collector and metadata stopped,
then run on fra-node-01 in the reviewed plan directory:

```sh
bash stopped-state.sh snapshot
bash stopped-state.sh publish
bash stopped-state.sh verify
```

Those guarded commands use 2 CPU/2 GiB/no network and a fresh stopped SQLite
snapshot. Save `candidate.yaml` in that same service and start it only after all
checks pass. Recheck actual digest/SHA, schema, limits, mounts, routes, same-revision
SQL/query totals, required targets, later publication and OOM/restart counters.
Do not run the preservation checker against moving live state.

Exact compatible worker rollback: stop in Zen, cleanup off, restore that **new
plan's** `rollback.yaml`, whose three image references must equal `$OLD_WORKER`,
then start the same service. **Do not run `rollback-v5`, restore SQLite backups,
clear failures or reset bootstrap for this v6→v6 rollback.** Live observations
made after upgrade stay in place. The current October 19 plan's older v5 rollback
is not the rollback plan for a new update.

Client changes are separate. The retained developer stack is still stopped and
uses a Mac bind mount; the new lock guard correctly refuses it. A state move
must be prepared against its actual saved Compose and consistent DB/STRM/files,
preserving hashes, aliases, corrections, ownership and path translation. Swapping
to an empty named volume would hide existing history. No such live move or client
restart is authorized or performed. This is a concrete client rollout blocker.

For a **separately prepared disposable named-volume client** using
`local-client.yaml`, the source-compatible tested rollback floor for completion
history is the published ff126cc API image below. It retains the earlier progress
and import-handoff repairs; older 428b5d8/6818115 images can reintroduce the old
missing-output recovery defect. Do not claim those are safe history rollbacks.

```yaml
# rollback-api.yaml; for that reviewed disposable client only
services:
  initialize:
    image: ghcr.io/zzackllack/anibridge-api-preview@sha256:3011117352291b8ae8d4b565d359a868707485d4da8df53492b48247643b9b44
  api:
    image: ghcr.io/zzackllack/anibridge-api-preview@sha256:3011117352291b8ae8d4b565d359a868707485d4da8df53492b48247643b9b44
```

```sh
# Only after that client's reviewed stop/backup and separate approval:
docker compose --env-file "$CLIENT_CONFIG/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml \
  -f "$PLAN/rollback-api.yaml" up -d --no-build
```

A future candidate override must pin a newly tested immutable API digest for both
services. No API schema changes are introduced here; use code replacement with
the same state, never restore an old DB over later jobs. The ff126cc fallback
still lacks this audit's filter/privacy/reload and lock fixes. No native candidate
image/AMD64 validation or actual client cutover is claimed. Mainline v2.6.0
downgrade still needs its retained pre-upgrade backup and matching files and can
lose later jobs; forward restoration is preferable.

## Remaining decisions by gate

**Draft → review blockers:** push is not authorized, so reviewers still see the
defective ff126cc source rather than the local repairs; hosted checks/native
images for the new source are missing; the PR description is stale. Review the
breaking filesystem restriction and supported client storage/migration plan.
This report supplies the concrete local changes; it does not request a live action.

**v3 merge blockers:** required human/CODEOWNER review, enforced test/build gates,
the prospective-label acceptance failure, differing scene-order Sonarr coverage,
real import-move/recovery acceptance, and explicit disposition of CQ-34/remaining
coverage criteria. A title check and code coverage cannot substitute for these.
Any relaxation must be an explicit contract decision, not an audit checkbox.

**Public-production blockers:** all applicable merge gates, sustainable hours-scale
bootstrap/freshness/capacity and recovery evidence, strict disk admission, supported
platform/auth/privacy/rights/hosting policy, dependency exposure closure, and
stable/prerelease/release/rollback policy. Current locks include Werkzeug 3.1.6
([Windows device-name advisory](https://github.com/advisories/GHSA-g6x2-hccm-hh4m),
fixed 3.1.9) and setuptools 82.0.1
([macOS sdist exclusion advisory](https://github.com/advisories/GHSA-h35f-9h28-mq5c),
fixed 83.0.0). Neither proves an exploited Linux pilot path. Current default-branch
docs alerts include Vite/source-map-js/esbuild; this audit does not close them.

**Nonblocking private-pilot limitations:** conservative abstentions and optional
Megakino absence, the untouched unapproved quarantines, fixture/copy proof where
live nonempty corrections do not exist, short source-retaining generated imports,
and historical failures whose original cause cannot be recovered. They remain
visible; none becomes a claim of full mapping, media proof or production capacity.

No image publication, push, deployment, existing-service restart/config/resource
change, PR edit/draft transition, protection/default change or merge occurred.
