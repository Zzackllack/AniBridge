# Turn 2 implementation and readiness — 2026-10-25

**Storage update:** [subsequent authorized cleanup](CLEANUP_2026-10-25.md)
removed 8.75 GB of old experiment files and nine unused images. It supersedes
the 33.02-GB projection below with a 22.25-GB projection. Exact next-workload
admission and physical shared-cache attribution remain unchecked; all other
evidence below retains its original revision and environment.

**Review: NOT READY. Merge into v3: NOT READY. Public production: NOT READY.**

This supersedes the push/hosted/native-platform claims in the earlier
[implementation follow-up](IMPLEMENTATION_FOLLOWUP_2026-10-25.md), while retaining
its historical measurements and open criteria. The maintainer authorized push
in turn 2. The preserved 20 local commits and the new focused fixes are pushed
to the existing PR branch. No reset, force push, deployment, existing-service
restart/configuration/resource/network change, protection change, PR edit, draft
transition or merge occurred. `main` remains default/stable; PR #170 remains
draft/open into protected `v3`.

Tested code: `3064faf34c2ac29a0a246e5c6703c6d50ae94c18`.
Sanitized machine-readable evidence (`evidence/turn2-readiness-2026-10-25.json`, local-only)
contains the full matrix and bounded measurements. The final documentation
commit descends from that source; its hosted checks must be read separately.

## Confirmed defects, fixes and honest before/after evidence

| Priority / ID | Trigger and impact | Repair and reproduction |
| --- | --- | --- |
| P1 / CQ-41 | A failing recent feed rescheduled the independent inventory deadline. Repeated feed failures could starve new-title discovery. | `State.failure` schedules inventory only for listing work. HTTP 500 and HTTP-200 parse failures now leave inventory due and retain the feed gap. Two before-fix failures pass. A parse failure is not evidence of Cloudflare throttling. |
| P1 / CQ-42 | A failure could commit its work/receipt before a separate signal acknowledgement, leaving inconsistent retry state after interruption. | `Collector._apply` wraps failure and signal settlement in one transaction. Two injected rollback cases compare all five affected tables; both fail before and pass after. |
| P1 / CQ-43 | An unexpected writer exception left producers waiting forever for acknowledgements while the worker process stayed alive. | `Pipeline.run` watches writer and producers together, propagates the fatal error and cancels/joins all producers. Both continuous/one-shot regressions time out before and terminate correctly after. |
| P2 / CQ-44 | Configured qBittorrent login parsed oversized form bodies before credential checks. | A pre-parser guard bounds bytes (16 KiB), time (5 s) and ASGI receive frames (1024, including empty frames). Declared/chunked excess fail before the fix. Fragmented URL-encoded/multipart forms, timeout recovery and empty-frame bounds pass afterward. It uses the installed framework parser after bounded replay. |
| P1 / CQ-45 | An unreadable state/backup directory was silently omitted from quota accounting. | `storage.used` fails closed on walk errors, tolerating only concurrent disappearance. The unreadable regression fails before; both quota cases pass after. This does not certify host-wide physical storage. |
| P1 / CQ-46 | Real generated 1080p remux/probe failed in the native AMD64 image under the old 256-MiB virtual-address cap. | Measured mappings exceed 256 MiB despite about 64–68 MiB sampled RSS. Only remux/probe receive 320 MiB; parser/transfer limits remain 256 MiB. Existing generated-media regressions and paired native controls pass at 320/512 MiB. Exit 245 alone was not treated as a segmentation fault. |
| Test gap / CQ-47 | Image import smoke checks and a runner without FFmpeg hid behavioral/platform failures. | The gate now runs full native API/core/worker suites offline as UID1000 at 2 CPU/2 GiB. Ordinary API CI installs FFmpeg. Real CI exposed the remux defect plus fixture assumptions, rather than skipping them. |
| Hardening / CQ-48 | New CodeQL alert 9 flags fast password-bearing HMAC session-key derivation. | This was a session key, not a stored password verifier; no password disclosure is established. Standard-library PBKDF2-HMAC-SHA256 (600000 rounds) now derives the key once at startup, binding random secret and framed username. Real cookie rotation tests cover username/secret alongside existing password/restart/expiry cases. Older cookies require login again. |

Turn-2 CodeRabbit reviews raised 0 issues, then 3 issues. The latter caught an
introduced duplicate `memory_bytes` override and a probe that exited successfully
despite failed phases, plus diagnostics ordering and shared config-test pollution.
All three were corrected. Invalid intermediate probe results are excluded.
Three regression cases require nonzero status for failed supported-limit controls.
The local path-default test now simulates only absence of the Docker marker in
its own subprocess; actual directory discovery remains real. Runtime Docker
defaults were not changed to appease the test. The focused authentication follow-up reviewed all three changed files and raised
0 issues. CodeQL now reports the earlier alert instance fixed; its automated
conversation is resolved/outdated. No alert dismissal or thread operation was
performed by this agent.

## Revision and environment evidence

The fresh read-only live container sample is **2026-10-25 15:15:58 UTC**:
collector/metadata still run `52065c76aa8bb75d3df4fa43e4ebcd2cded5779e`, image
`sha256:1cc57eae123d842af0cc9fc9003356da7e4da3af3dada3b95764f58db4513106`.
Both started October 19 at 20:19 UTC with zero restarts/OOMs. Collector remains
2 CPU/2 GiB and metadata 2 CPU/512 MiB. Existing private v6/public schema2 is
the prior directly inspected schema baseline; this turn did not rescan the full
live ledger or re-read the canonical admission setting. The prior 90/minute
setting is our budget, not an upstream quota. Candidate private state is v7;
public schema2 and API DB schema are unchanged. All repairs above are **pushed,
not deployed**. Live failures must not be attributed to fixes the host lacks.

Native hosted run [40213832650](https://github.com/Zzackllack/AniBridge/actions/runs/40213832650)
passes on `048f16f` before the final key hardening: each native API image runs
350 tests; each native worker image runs 322 core and 324 worker tests. No Linux
platform skips remain in those jobs. Final code [3064faf](https://github.com/Zzackllack/AniBridge/commit/3064faf34c2ac29a0a246e5c6703c6d50ae94c18)
passes [tests run 40214183582](https://github.com/Zzackllack/AniBridge/actions/runs/40214183582):
each native API image **352 passed**, each native worker image **322 core and
324 worker passed**, no skips. Ordinary Linux API also passes **352** (84
reported warnings). All 23 reported PR contexts succeed, including the aggregate
gate, Ruff, Pylint, CodeQL and both preview manifests. Manifest publication
[40214183699](https://github.com/Zzackllack/AniBridge/actions/runs/40214183699) succeeds;
registry metadata independently confirms the source SHA on both architectures:

| Component | Immutable manifest for tested code |
| --- | --- |
| API | `ghcr.io/zzackllack/anibridge-api-preview@sha256:3a4371c29cffaaf7cd5fd99a219718469eb87cc686151bc38bd1819c809d60c0` |
| Worker | `ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:fef55ddb46a22827346112e5f5996f19e5613a44d05e70f6458d92ba85875239` |

These are available candidate identities, not a deployment. No image was pulled
locally for this metadata verification.

macOS ARM64/Python 3.14 final API: **334 passed, 18 Linux-only skips**. Core 322;
worker 311 passed/13 Linux-only skips. Full API Ruff/format, configured Pylint
and actionlint pass. Final hosted counts supersede these platform-limited Mac
results. Existing TestClient deprecation remains visible; prior resource warnings
are not proof of a production leak. Final API statement coverage is **6286/10087 (62.32%) on macOS**, 35 excluded
lines, and **6444/10087 (63.88%) on ordinary Linux**. Branch/core/worker coverage
was not measured. Mapping coverage, labelled precision, scenario coverage and
operational confidence remain separate.

The first expanded runs failed: `d484f05` showed the remux failure; subsequent
fixture work exposed a missing tmpfs mountpoint and a local-path/Docker default
assumption. At `6e59813`, all 349 other API cases passed on each architecture;
only that default test still failed. These red runs remain evidence, not waived
checks. Final source is accepted only after its complete native matrix passes.

## Paired resource measurements and disk admission

Native generated-input probe source `6e59813`, same generated two-second 1080p
input per architecture, UID1000, no network, 2 CPU/2 GiB:

| Architecture / cap | Remux / probe exit | Peak virtual KiB (remux / probe) | Sampled RSS KiB (remux / probe) | Wall seconds (remux / probe) |
| --- | --- | --- | --- | --- |
| AMD64 / 256 MiB | 245 / 1 | 262088 / 262044 | 67224 / 65192 | 0.5063 / 0.5005 |
| AMD64 / 320 MiB | 0 / 0 | 262828 / 262944 | 67392 / 65800 | 0.4997 / 0.4994 |
| AMD64 / 512 MiB | 0 / 0 | 262828 / 262944 | 67820 / 65488 | 0.4968 / 0.4943 |
| ARM64 / 256 MiB | 0 / 0 | 250244 / 250364 | 58200 / 57976 | 0.4279 / 0.4196 |
| ARM64 / 320 MiB | 0 / 0 | 250244 / 250364 | 58604 / 57956 | 0.4256 / 0.4196 |
| ARM64 / 512 MiB | 0 / 0 | 250244 / 249468 | 60316 / 57952 | 0.4181 / 0.4219 |

CPU times are in JSON. `/proc` RSS/threads are sampled, not exact peaks; no
cold/warm control or repetition establishes throughput. These samples justify
the bounded native mapping allowance, not container capacity or supported-media
completeness. PBKDF2 startup has three warm Mac wall samples of
0.0454/0.0460/0.0465 seconds; no per-login KDF work is added. Native startup is
exercised by the image suites, without a separately isolated timing claim.

The two old server experiment roots previously reported permission errors.
A zero-copy, read-only `stat` helper using the already present image completed
their inventory. It used no network, no writable volume, no Docker logs,
1 CPU/128 MiB/pids16, then auto-removed. It was not a collector or trial stack.

| Retained scope | Allocated/accounted bytes |
| --- | ---: |
| Server mapping follow-up experiment | 7,643,955,200 |
| Server recorded-failure experiment | 4,856,303,616 |
| Live state including backups | 5,477,781,504 |
| Live published read catalog | 325,304,320 |
| Other enumerated server audit/update files | 1,434,619,904 |
| Retained Mac audit/update directories | 4,429,750,272 |
| Known Mac image layer-chain union (virtual accounting) | 7,854,235,648 |
| Required reserve | 1,000,000,000 |
| **Accounting projection** | **33,021,950,464** |

This exceeds **30,000,000,000** before attributing remaining caches/server images.
Image virtual sizes, compressed inspect sizes, shared cache and physical storage
are different measurements; the projection is not a certified physical peak.
All-Mac raw cache size 14,916,515,457 includes unrelated/shared content and is not
silently added or treated as zero. Fresh sampled free space is about 86.98 GB
server and 13.71 GB Mac; free space alone does not admit the aggregate workload.
**Next full-copy/real-client stack admission fails.** No copy/image pull or
retirement of old state, backup, image or acceptance volume was performed.
Ownership/retirement and shared-layer attribution need a reviewed storage plan.

No new full-copy or independently labelled mapping cohort ran. The prior v6
full-ledger comparisons remain valid only for their revisions. They do not prove
v7 full-ledger preservation/rollback. Requests per useful new map, eligible ages
by class, new publication/query latency, writer occupancy, physical I/O and
sustained freshness/capacity were **not measured** this turn. Ordinary/large live
query and Classroom/One Piece results remain the earlier dated runtime evidence.

## Complete finite audit matrix

The original 43 areas plus seven dependency paths are accounted below. VERIFIED
means the bounded code/fixture/runtime evidence stated, not a global guarantee.
Inherited rows retain [the prior report](IMPLEMENTATION_FOLLOWUP_2026-10-25.md)'s
revision/environment boundaries; rerunning fixtures on native images does not
refresh live denominators, independently label mappings or execute real clients.

| ID / area | Status | Evidence | Remaining uncertainty / exact blocker |
| --- | --- | --- | --- |
| A1 Inventory → title/season/episode → durable work | VERIFIED | `listing`, `Collector`, `State.detail`, `batch`, signals; collection/private-operation suites; exact snapshot totals | Observed inventories can grow; no complete-provider claim |
| A2 Capped feeds, pagination and new-child reconciliation | VERIFIED | Full native core/worker suites plus test_feed_failure_isolation: HTTP 500 and HTTP-200 parse failures no longer postpone independent inventory. | Historical feed gaps remain; capped feeds cannot establish lossless provider discovery. |
| A3 Unknown language, subtitles, unavailable/missing/empty markup | VERIFIED | core episode-row/recent tests; sto/collection/finale cases; live 1 unknown and 8,478 unavailable observations | No inferred audio; stable upstream gaps remain |
| A4 Retry/admission/circuit/cached retry/lease fairness | VERIFIED | Final-source Linux AMD64/ARM64 installed worker suites rerun retries, leases, admission, cached recovery and fairness fixtures. | Deployed 52065c7 lacks these fixes. Live eligible-work throughput and freshness SLA remain unmeasured. |
| A5 Retained failure reason + HTTP status + first-failure age | UNCHECKED | Private v7 transactional detail receipts, migration and interrupted failure checkpoints pass in both native worker images. | Live v6 has no detail receipts; historical first-failure clocks, listing/signal attribution and complete per-title canonical attribution remain unavailable. |
| A6 Hours-scale full bootstrap and sustainable maintenance | UNCHECKED | Status separates first-pass from mapping and feed gaps | No fresh full bootstrap/endurance campaign authorized or measured |
| B1 Exact denominators/disjoint unresolved partition | VERIFIED | `audit_snapshot.py`, actual `correspondence.decisions`; tables above | Retained observations, not provider population completeness |
| B2 Parent/episode IDs, provenance, no numbering/similarity acceptance | VERIFIED | Original finite identity/matching regressions plus eight damaged-cache recovery cases; current worker suite | No numbering/similarity acceptance added. Existing uncertain maps are retained; no population precision claim. |
| B3 Descriptor acquisition vs local rematching, reuse and freshness | VERIFIED | Digest/parent/language/episode codec validation in acquisition and local rematching; cross-provider and due-retry regressions | Eight corruption cases reacquire normally and retain maps. Current live requests per useful map and eligible age by class remain unmeasured. |
| B4 Prospective independently labelled trial | FAILED | 215 fixed cases, 118 positives, development/held-out chronology in MAPPING_IMPLEMENTATION | Labels followed original tuning; a new prospective independent trial or explicit contract decision is required |
| B5 Multilingual/annotations/specials/split seasons/cuts | VERIFIED | finite matching/identity/finale fixtures and retained label evaluation | Population precision and newly labelled broad unresolved cohorts UNCHECKED; no matcher tuning in this audit |
| B6 Required current named targets | VERIFIED | live SQL/revision-paired native checks, including large pagination | Published-map existence is not independent provider-order ground truth |
| B7 Anime-Lists/TheXEM/provider-order and Sonarr conversion | UNCHECKED | research reviewed; no adapter integrated | Source order binding and a real differing scene→canonical Sonarr case remain untested; do not adopt research as a map |
| C1 Observation → journal → export/proof → pointer → reader | VERIFIED | v6 triggers, export/snapshot/clone/ack code; publication tests and full-size retention | Generation acknowledgement retains later fixture WAL writes; no distribution system added |
| C2 Corruption/tampering/receipts/partitions/cancel/crash | VERIFIED | publication follow-up/migration/validation-scope tests installed on Linux | Finite injected failures, not long crash/endurance proof |
| C3 Fresh full-size concurrent publication/query workload | UNCHECKED | Historical overlap evidence retained; current fixture overlap passes | Today's full-size runs are sequential; no new final-candidate full-size overlap/stress claim |
| C4 Migration/backup/idempotence/rollback/reopen | UNCHECKED | Populated v6-to-v7-to-v6 fixtures now pass in both native installed worker images, including interruption/reopen and WAL-inclusive backup admission. | Final full-ledger v7 upgrade/rollback remains blocked by aggregate disk admission. Native fixture execution closes the former Linux-only gap. |
| C5 Entire release/map/history/correction preservation | UNCHECKED | All 39 non-version retained v6 tables and post-upgrade observations survive the populated migration fixtures on both Linux architectures. | Two fixture releases and one map do not replace full-ledger preservation. Historical 498403-release/289489-map v6 proof remains historical. |
| C6 Query totals/isolation/pagination/corrections before policy | VERIFIED | Prior nine revision-paired live requests; new SQL/full-HTTP comparison for sixty-day-old releases | Targeted native requests retain old content while recent feeds exclude it. No new live queries or freshness SLA in this phase. |
| C7 Cache invalidation/coalescing/revision/outage/timeout | VERIFIED | query/client/provider tests, including cancellation and partial provider failures | Positive stale cache is bounded prior-page coverage, not general outage availability |
| C8 Strict aggregate disk peak and next-copy admission | FAILED | Read-only stat inventory completes both previously unreadable server experiment roots. Sanitized byte accounting is in this report and JSON. | 33,021,950,464-byte accounting projection exceeds 30,000,000,000; physical image/cache attribution and continuous peak remain uncertified. No next full-copy/acceptance stack admitted. |
| D1 Torznab grab → frozen identity → durable job/output | UNCHECKED | Prior two real Sonarr/Prowlarr generated-media flows and current durable-job unit suite | Final candidate has no fresh real-client run; the new credentialed mode has only real-router tests. |
| D2 Mixed history, missing jobs, states/categories/paths/full streams | VERIFIED | legacy-history/filter/completion/batch tests; actual copied four aliases | No corruption-tolerant proof for every arbitrary private DB mutation |
| D3 Exact/estimated/unknown size, tracks, retries, STRM/counts | VERIFIED | synthetic HTTP/HLS and progress/receipt/STRM tests; configured fake peers retained | Size/quality/counts are not invented measurements; unknown totals remain unknown |
| D4 Real Sonarr intermediate progress/import/restart | UNCHECKED | Prior two generated flows showed intermediate queue progress/import and six-second restart checks | Those runs predate this implementation. Final-candidate/credentialed Sonarr acceptance is blocked by disk admission. |
| D5 Real Sonarr move plus longer duplicate-prevention recovery | UNCHECKED | unit move/explicit retry and historical copied history pass | Actual runs kept source; no new real move or long restart campaign |
| D6 Visible browser progress, provider import/playback | UNCHECKED | No UI/media proof claimed | Browser omitted; real provider acquisition outside authorization |
| D7 Metadata service/Sonarr external outage independence | VERIFIED | local cache/provider isolation and frozen-source job tests; selected descriptors fetched | Complete Sonarr metadata outage E2E is UNCHECKED; no substitute emulator |
| D8 Public qBittorrent authentication | UNCHECKED | Both native API suites exercise credentialed routers, bounded login bodies, rotation and PBKDF2-derived session keys. | Real credentialed Sonarr/proxy ingress acceptance remains blocked by disk admission. Auth is optional and covers /api/v2 only. |
| D9 Mounted/proxied authentication boundary | VERIFIED | Mounted real-router request returns 200 before repair and 403 after; complete mounted login/logout and simulated TLS proxy hop pass | ASGI protocol fixture, not deployed HTTPS ingress or real Sonarr proof. |
| E1 Outbound URL/redirect/DNS/TLS/session/decoding bounds | VERIFIED | Existing outbound transport fixtures; new populated CLI serve test with unusable writer-state path; server template removes private mount | Existing service retains its historical writable state mount; update tooling preserves it. A separate reviewed operational change is needed. |
| E2 Malformed canonical inputs and private proof recovery | VERIFIED | Original canonical input tests plus full stored-descriptor validation and eight cache recovery/rematching regressions | Stored hashes detect accidental mutation, not authenticity against a writer controlling both hash and payload. No exhaustive fuzzing. |
| E3 Secret/query logging boundaries | VERIFIED | worker allowlists, query access logs disabled, captured-log Torznab/grab tests | Complete legacy downloader/OS/proxy logging privacy UNCHECKED |
| E4 Child limits/cancellation/shutdown and async boundaries | VERIFIED | Both native API and installed worker suites execute the formerly skipped Linux resource, parser, cancellation, remux and probe checks at 2 CPU/2 GiB. | Finite generated workloads only; sustained FD/pool behavior and resource capacity remain unmeasured. Native FFmpeg address-space limit is now separately 320 MiB. |
| E5 Dependency exposure across supported platforms | UNCHECKED | Patched locked dependencies execute inside native AMD64/ARM64 API and worker images; macOS frozen suites and prior docs audit retained. | This closes native execution, not a complete Python/OS SBOM audit or Windows behavior. Default-branch advisory count is not candidate exposure. |
| E6 Full-path profiling and short 2/2 resource samples | VERIFIED | phase medians, copied publication, Linux cgroup CPU/memory/I/O, query latency | Sustained capacity, lock/writer occupancy, exact physical Mac backing I/O and eligible-class age UNCHECKED |
| E7 Filesystem/platform support | FAILED | actual Mac-bind exclusion failure; fail-closed fix; native Linux/macOS tests | Developer state must move safely before candidate startup; Windows resource enforcement remains outside this Linux pilot |
| F1 Frozen project and installed-wheel checks | VERIFIED | Frozen native Linux API/core/worker suites and installed worker wheel suites pass on AMD64 and ARM64; macOS API retains explicit Linux-only skips. | Counts, revision, run and conditions below; no full real-client E2E or code-coverage inference. |
| F2 Lint/workflow/static gate behavior | VERIFIED | Full API Ruff/format, Pylint 8.44 >7.5, actionlint; actual final gate shell tested over 125 combinations | Only all-success passes. Current worker-wide pre-existing lint remains outside hosted lint scope; no mass cleanup. |
| F3 Hosted results for new final local source | VERIFIED | All preserved local audit commits and new fixes are pushed. Final code revision, hosted tests, checks and preview manifests are recorded below. | Documentation-only descendants require their own hosted verification; hosted checks do not imply deployment. |
| F4 Enforced unconditional test/build merge gate | FAILED | Unconditional native behavioral jobs feed the hosted Tests / Required Gate, which rejects skipped/cancelled/failed dependencies. | Effective v3 rules still require only Conventional Commit Title as a status check. Protection was not changed. |
| F5 Review approval and current PR description | FAILED | Fresh connector query: prior CodeQL thread resolved/outdated; all 23 reported contexts pass on 3064faf. Local prepared PR description follows the repository template. | No human/CODEOWNER approval and PR body remains historical. CodeQL thread resolved/outdated automatically; no PR body, thread or draft edits made. |
| F6 Stable/default/prerelease release policy | UNCHECKED | all workflows and v3 transition checklist reviewed | main stays stable/default; prerelease/default/retention/external integrations remain separate release decisions |
| A7 Fatal writer failure and producer cleanup | VERIFIED | test_pipeline_fatal_writer: both continuous and one-shot modes timed out before the fix; now propagate RuntimeError and leave no pending tasks. | Injected fatal exception, not a long crash campaign. |
| A8 Failed observation and signal retry atomicity | VERIFIED | test_feed_failure_isolation compares worker_meta/work/work_failure/signal_meta/signal_pending around interrupted recent and targeted checkpoints. | Finite transaction rollback injection; no live failure was induced. |
| C9 Unreadable quota inventory | VERIFIED | test_storage_inventory_errors rejects unreadable subdirectories and tolerates concurrent FileNotFoundError. | Local fail-closed traversal cannot certify whole-host/shared-image physical storage. |
| E8 Credentialed login body admission | VERIFIED | Declared/chunked excess, fragmented normal forms, slow body and empty-ASGI-frame cases pass on both native API images. | 16 KiB/5 seconds/1024 frames; upstream proxy connection limits and auth-off compatibility remain separate. |
| E9 Native FFmpeg virtual memory admission | VERIFIED | Paired 256/320/512 MiB trials on generated two-second 1080p bytes; actual remux/probe and full native API regressions. | One fixture and cold/warm uncontrolled samples do not establish general format/capacity safety. |
| F7 Diagnostic control failures and test isolation | VERIFIED | Probe 320/512 failures now exit nonzero; three helper tests. Diagnostics follow tests. Local config contract runs in an isolated subprocess; image fixture mountpoint exists. | The introduced duplicate-keyword/false-green probe results were invalidated, not counted as success. |
| E10 Session key derivation and rotation | VERIFIED | PBKDF2-HMAC-SHA256 with 600000 rounds runs once at startup, random configured secret and length-framed username; real cookie username/secret rotation tests. | CodeQL prompted hardening, not evidence of leaked credentials. Existing authenticated cookies expire on this key-format change; real-client reconnect remains unchecked. |

## Reproduction and proposed upgrade/rollback

From repository root, use the existing projects/helpers:

```sh
(cd apps/api && uv run --python 3.14 --frozen pytest -q -rs --tb=short)
(cd packages/catalog-core && uv run --python 3.14 --frozen pytest -q)
(cd apps/catalog-worker && uv run --python 3.14 --frozen pytest -q)
(cd apps/api && uv run --frozen ruff check app && uv run --frozen ruff format --check app)
(cd apps/api && uv run --frozen pylint --fail-under=7.5 app)
actionlint
```

Native runs use `.github/workflows/tests.yml`'s four image jobs and ordinary
Linux project jobs. The media probe is generated-input-only and is run from the
API environment on Linux:

```sh
uv run --project apps/api --frozen python scripts/catalog/query_pilot/media_limit_probe.py
```

No proposed live upgrade is approved or fully tested. The v7 populated fixture
and exact generated rollback command pass in both native worker images, but
full-ledger upgrade/preservation/rollback still requires admitted disk. After
that gate, obtain fresh saved Compose through authenticated Zen and fresh worker
configuration via XPipe. Preserve unrelated drafts and all limits/mounts/networks.
Prepare, review and retain both private candidate and exact rollback files:

```sh
REVISION=3064faf34c2ac29a0a246e5c6703c6d50ae94c18
OLD_WORKER=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1cc57eae123d842af0cc9fc9003356da7e4da3af3dada3b95764f58db4513106
uv run --project apps/api --frozen python scripts/catalog/query_pilot/prepare_worker_update.py \
  --revision "$REVISION" --compose "$PLAN/current-compose.yaml" \
  --worker-config "$PLAN/worker.json" --expected-old-image "$OLD_WORKER" \
  --directory "$PLAN/reviewed"
```

`PLAN` is the future admitted private plan directory, not a ready live plan.
The helper refuses missing checks/architectures and resolves the immutable worker
manifest. Candidate/rollback Compose must retain all three worker image references,
volumes, configuration and allocations. Metadata mount removal needs its own
reviewed Compose diff; the default image-only helper preserves the live mount.
Only after separate operational approval: pull that exact digest, verify the
source label, stop both existing services through Zen with cleanup off, then:

```sh
cd "$PLAN/reviewed"
bash stopped-state.sh snapshot
bash stopped-state.sh publish
bash stopped-state.sh verify
```

The scripts use consistent SQLite backups, include committed WAL, create a
no-overwrite `.pre-v7.backup`, and preserve backup generations and `/state/backup`.
After approved startup, verify later publications and revision-paired SQL/query
totals plus retained identities and resource/restart/OOM counters.

Exact schema rollback command, **while both services are stopped**, using the
**new v7 image** selected in the plan:

```sh
bash stopped-state.sh rollback-v6
```

Then restore that plan's `rollback.yaml` through Zen and start the pinned old v6
image. This removes only v7 diagnostics and retains newer observations/retries/
maps/corrections. Never restore an old ledger over later data or run rollback-v5
against this v6 baseline. Full-size proof remains absent; these are prepared
commands, not a successful live upgrade claim.

Client DB schema does not change. Select its immutable API manifest only after
source checks/native builds; preserve jobs, aliases and downloads. The developer's
unsafe Mac bind must move through a consistent admitted storage plan before
candidate startup. Old unauthenticated images are not an equivalent security
rollback: retain independently enforced ingress or select a tested auth-capable
digest. The PBKDF2 key-format change expires existing authenticated cookies.

## Remaining decisions and verdict

- **Draft → review blockers:** final-code hosted checks and CodeQL now pass; the complete updated PR body is prepared locally in
  `PR_170_DESCRIPTION_TURN2.md`, not applied. Fresh final-source credentialed
  real-client acceptance remains open under the existing review criteria and is
  blocked by disk admission. No criterion was waived to call the draft ready.
- **Merge blockers:** enforced aggregate test gate; human/CODEOWNER approval; prospective independently labelled mapping
  trial or explicit contract decision; full-size v7 preservation/rollback and
  overlap; real Sonarr scene-order/file-move/restart cases; safe client storage.
- **Public-production blockers:** all applicable merge gates plus declared
  public scope, all-router auth/TLS/privacy/rights/default policy, full destination
  dependency/OS audit, release/retention/rollback policy, external-outage behavior
  and sustained freshness/capacity evidence. A green suite supplies none of those.
- **Nonblocking limitations within this authorized phase:** missing historical
  logs/first-failure clocks cannot be reconstructed; unsupported/ambiguous
  content stays unresolved. Generated media is not real provider acquisition,
  import or playback. Long endurance and real provider-media work remain outside
  scope. No guessed map, failure clearing or rate/resource increase is proposed.

All confirmed code defects in this turn are fixed and pushed. Operational,
full-size accuracy/preservation and real-client acceptance remain explicit
blockers; review, merge and public production are separately **NOT READY**.
