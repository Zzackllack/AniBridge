# Implementation follow-up — 2026-10-25

**Review: NOT READY. Merge into v3: NOT READY. Public production: NOT READY.**

Eleven focused implementation commits follow the preserved eight audit commits.
Tested source: `1397b3fac40d1dce55d20f17af758c54b4007e58`. They are local; PR #170 remains draft/open at `ff126cc`
into `v3`, with `main` still default/stable. Fresh GitHub inspection reports all
19 contexts successful for that remote source, REVIEW_REQUIRED, no reviews and
no inline review threads. Only Conventional Commit Title is an enforced status.
Those results do not cover these local changes.

This report updates the [original runtime audit](RUNTIME_AUDIT_2026-10-25.md).
Its live baseline remains the last inspected `52065c7`, private v6/public schema2;
no new live inspection or service mutation is claimed in this phase. The local
candidate now uses **private v7/public schema2**. The original report's v6→v6
code-only rollback instructions do not apply to this candidate.

[Machine-readable evidence](evidence/implementation-followup-2026-10-25.json)
contains revisions, test counts, paired fixture hashes, dependency results,
review dispositions and this entire matrix. Raw logs and ledgers stay private.

## Confirmed fixes and bounded hardening

| Priority / issue | Trigger, cause and impact | Implementation and evidence |
| --- | --- | --- |
| P1 / CQ-35, damaged cached evidence | Invalid JSON, malformed episode/language fields or a mismatched stored digest could consume retries, raise uncaught errors or supply unvalidated cached records. Parent-only SQL JSON extraction also bypassed the acquisition validator during local rematching. | `descriptor_codec.decode` validates bounded payload/hash, parent ID/proof, languages, secondary IDs and unique episode IDs/coordinates. Both reuse paths reject the whole entry and reacquire normally; all prior valid maps remain. Eight recovery cases fail before and pass after, alongside 71 existing canonical/retry/matching checks. A colocated hash detects accidental mutation, not hostile authenticity. No live corruption incident is asserted. |
| P1 / CQ-36, credential boundary | Existing login accepted every password and did not enforce a session on endpoints. The first new local middleware also missed mounted app paths; a mounted real-router request returned 200 without credentials. | Opt-in constant-time credentials and Starlette signed SID cookies protect both modes. Root-path-aware routing and mount-scoped cookies fix the introduced bypass (403 afterward). Sessions expire in one hour, survive restart, and invalidate on credential/secret rotation. Secure cookies default on; explicit false opts into trusted HTTP. Proxy-Origin and production-wiring tests pass. Thirteen focused checks include the two existing compatibility checks. No real credentialed Sonarr or public-ingress claim. |
| Operational / CQ-34, retained failure blind spot | Retained work had attempts/deadlines but no durable bounded class/status/first-failure clock; path-free aggregate logs could not reconstruct each failure. | Private v7 adds one transactional receipt per detail work row and disjoint operator groups. Real success clears it; admission waits, unavailable templates and positive season rows do not erase outstanding detail failures. Six receipt/migration/reserve tests plus the existing positive-batch regression pass. Old first-failure times remain unknown. Live attribution and listing/signal/full canonical attribution stay open. |
| Merge safety / CQ-37 | Final gate did not depend on unconditional native image builds; publishing is intentionally path/trust restricted. | Read-only API/worker AMD64/ARM64 smoke jobs now run for forks, Dependabot and docs-only changes without registry credentials/publication. Source labels, installed imports and absence of acceptance sitecustomize are checked offline. The real gate shell rejects 124 of 125 result combinations. actionlint passes. Hosted execution and policy enforcement remain blocked. |
| Dependency / CQ-38 | Selected locked versions were in affected advisory ranges. | Installed Werkzeug 3.1.9 and setuptools 84.2.1 clear the selected [Windows device-name](https://github.com/advisories/GHSA-g6x2-hccm-hh4m) and [macOS sdist exclusion](https://github.com/advisories/GHSA-h35f-9h28-mq5c) ranges. Docs Vite 8.3.5, source-map-js 1.2.2 and supported optional esbuild 0.28.2 yield zero registry advisories, down from eight; frozen build passes. Seven hosted alerts still describe remote manifests. No full Python/OS SBOM closure or destination-platform claim. |
| P2 / CQ-39, false copied-query failure | The independent SQL oracle expired targeted releases after 30 days while the actual native query intentionally retained them. This could misdiagnose old catalogs as broken. | Sixty-day-old fixture releases give old SQL expectation 0, corrected SQL/full HTTP 2 and recent-feed total 0. Production search behavior is unchanged. |
| Privilege separation / CQ-40 | Metadata inherited the private writer-state mount despite serving published catalogs only. | Local server template removes that mount. A populated serving command works when its configured state path is a file, proving it cannot use the writer directory. Published read-catalog remains writable for leases. Existing live Compose and its update plan are preserved; applying the mount change needs separate review. |

Authentication stays opt-in to preserve trusted-network compatibility. Partial
configuration or values below the length requirements refuse startup. Set an
independent random session secret;
cookie contents contain no credentials. Logout clears the client cookie; copied
cookies remain valid until expiry or credential/secret rotation. Login admission
is 60 attempts/minute per process, reserved before form parsing. Other application
routers are outside this authentication boundary. See `.env.example` and agent
configuration/security guidance for the exact settings.

CodeRabbit reviewed the implementation through `5310413` and raised **3 issues**:
one major (secure default) and two minor (proxy Origin, possible FK deletion).
The first two are fixed and tested. Foreign keys are enabled, but no application
path deletes durable `work` rows; cascading deletion would be inappropriate.
The mounted-path defect came from an independent manual regression. No second
CodeRabbit review of the subsequent repairs or metadata-template change is claimed.

## Complete finite audit matrix

VERIFIED means the finite evidence in that row, at the stated revision and
environment. It does not certify population accuracy or production capacity.
Unchanged rows retain the earlier audit's explicit live/fixture boundary.
Candidate-sensitive full-size/Linux/client rows are unchecked again where the
new source needs fresh execution. No open criterion has been waived.

| ID / area | Status | Evidence | Remaining uncertainty / exact blocker |
| --- | --- | --- | --- |
| A1 Inventory → title/season/episode → durable work | VERIFIED | `listing`, `Collector`, `State.detail`, `batch`, signals; collection/private-operation suites; exact snapshot totals | Observed inventories can grow; no complete-provider claim |
| A2 Capped feeds, pagination and new-child reconciliation | VERIFIED | `signals`, `State.claim`, signal/collection repair tests; live gap markers and 0/5 gap parents | Lossless provider feed coverage is UNCHECKED; feed caps and historical gaps cannot prove it |
| A3 Unknown language, subtitles, unavailable/missing/empty markup | VERIFIED | core episode-row/recent tests; sto/collection/finale cases; live 1 unknown and 8,478 unavailable observations | No inferred audio; stable upstream gaps remain |
| A4 Retry/admission/circuit/cached retry/lease fairness | VERIFIED | retry/transport/cached-retry/canonical-rate/circuit tests; snapshot zero overdue canonical retries and expired leases | Synthetic fairness is not live eligible-work throughput; cached retry repair remains undeployed |
| A5 Retained failure reason + HTTP status + first-failure age | UNCHECKED | `work_failures`, private v7, six migration/receipt regressions and the existing positive-batch regression | Detail receipts are implemented locally; live v6 has no receipts. Historical first failures stay unknown. Listing/signal and full per-title canonical attribution remain separate gaps. |
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
| C4 Migration/backup/idempotence/rollback/reopen | UNCHECKED | New populated v6→v7→v6 fixture, 39 retained tables, interruption/restart/WAL-backup reserve and code rollback | Full-size v7 upgrade/rollback and current Linux execution are blocked by aggregate disk admission. Prior full-size proof was v6. |
| C5 Entire release/map/history/correction preservation | UNCHECKED | New fixture preserves every retained table and observations added after upgrade; prior full-copy v6 proof remains recorded | Two fixture releases/one map are not the full ledger. Full-copy v7 preservation has not run. |
| C6 Query totals/isolation/pagination/corrections before policy | VERIFIED | Prior nine revision-paired live requests; new SQL/full-HTTP comparison for sixty-day-old releases | Targeted native requests retain old content while recent feeds exclude it. No new live queries or freshness SLA in this phase. |
| C7 Cache invalidation/coalescing/revision/outage/timeout | VERIFIED | query/client/provider tests, including cancellation and partial provider failures | Positive stale cache is bounded prior-page coverage, not general outage availability |
| C8 Strict aggregate disk peak and next-copy admission | UNCHECKED | Original conservative 30,902,859,428-byte projection; fresh read-only Docker inventory and Mac free-space sample | Shared physical layers, old experiment ownership and continuous aggregate peak remain uncertified. No new service copies/images/containers admitted. |
| D1 Torznab grab → frozen identity → durable job/output | UNCHECKED | Prior two real Sonarr/Prowlarr generated-media flows and current durable-job unit suite | Final candidate has no fresh real-client run; the new credentialed mode has only real-router tests. |
| D2 Mixed history, missing jobs, states/categories/paths/full streams | VERIFIED | legacy-history/filter/completion/batch tests; actual copied four aliases | No corruption-tolerant proof for every arbitrary private DB mutation |
| D3 Exact/estimated/unknown size, tracks, retries, STRM/counts | VERIFIED | synthetic HTTP/HLS and progress/receipt/STRM tests; configured fake peers retained | Size/quality/counts are not invented measurements; unknown totals remain unknown |
| D4 Real Sonarr intermediate progress/import/restart | UNCHECKED | Prior two generated flows showed intermediate queue progress/import and six-second restart checks | Those runs predate this implementation. Final-candidate/credentialed Sonarr acceptance is blocked by disk admission. |
| D5 Real Sonarr move plus longer duplicate-prevention recovery | UNCHECKED | unit move/explicit retry and historical copied history pass | Actual runs kept source; no new real move or long restart campaign |
| D6 Visible browser progress, provider import/playback | UNCHECKED | No UI/media proof claimed | Browser omitted; real provider acquisition outside authorization |
| D7 Metadata service/Sonarr external outage independence | VERIFIED | local cache/provider isolation and frozen-source job tests; selected descriptors fetched | Complete Sonarr metadata outage E2E is UNCHECKED; no substitute emulator |
| D8 Public qBittorrent authentication | UNCHECKED | Opt-in signed SID authentication in both modes; secure default, expiry, tampering, rotation, logout, login admission and production-wiring tests | Unconfigured mode still accepts trusted-network clients. Credentialed real Sonarr/proxy ingress has not run; other application routers are outside this auth boundary. |
| D9 Mounted/proxied authentication boundary | VERIFIED | Mounted real-router request returns 200 before repair and 403 after; complete mounted login/logout and simulated TLS proxy hop pass | ASGI protocol fixture, not deployed HTTPS ingress or real Sonarr proof. |
| E1 Outbound URL/redirect/DNS/TLS/session/decoding bounds | VERIFIED | Existing outbound transport fixtures; new populated CLI serve test with unusable writer-state path; server template removes private mount | Existing service retains its historical writable state mount; update tooling preserves it. A separate reviewed operational change is needed. |
| E2 Malformed canonical inputs and private proof recovery | VERIFIED | Original canonical input tests plus full stored-descriptor validation and eight cache recovery/rematching regressions | Stored hashes detect accidental mutation, not authenticity against a writer controlling both hash and payload. No exhaustive fuzzing. |
| E3 Secret/query logging boundaries | VERIFIED | worker allowlists, query access logs disabled, captured-log Torznab/grab tests | Complete legacy downloader/OS/proxy logging privacy UNCHECKED |
| E4 Child limits/cancellation/shutdown and async boundaries | UNCHECKED | Existing native macOS async/cancellation checks and earlier Linux child tests | Final candidate has 13 worker and 18 API Linux-only skips; current Linux resource enforcement and sustained FD/pool behavior have not run. |
| E5 Dependency exposure across supported platforms | UNCHECKED | Werkzeug 3.1.9/setuptools 84.2.1 installed on macOS; docs audit eight→zero after frozen build | Seven hosted alerts still describe remote manifests. Current Linux/native image behavior, full Python/OS SBOM and Windows behavior remain unchecked. |
| E6 Full-path profiling and short 2/2 resource samples | VERIFIED | phase medians, copied publication, Linux cgroup CPU/memory/I/O, query latency | Sustained capacity, lock/writer occupancy, exact physical Mac backing I/O and eligible-class age UNCHECKED |
| E7 Filesystem/platform support | FAILED | actual Mac-bind exclusion failure; fail-closed fix; native Linux/macOS tests | Developer state must move safely before candidate startup; Windows resource enforcement remains outside this Linux pilot |
| F1 Frozen project and installed-wheel checks | UNCHECKED | macOS Python 3.14: API 324/18 skips, core 322, worker 303/13 skips; installed core/worker wheels repeat 322 and 303/13 | No current native Linux/AMD64 candidate execution or published image. Previous Linux results cover the earlier source/dependencies. |
| F2 Lint/workflow/static gate behavior | VERIFIED | Full API Ruff/format, Pylint 8.44 >7.5, actionlint; actual final gate shell tested over 125 combinations | Only all-success passes. Current worker-wide pre-existing lint remains outside hosted lint scope; no mass cleanup. |
| F3 Hosted results for new final local source | UNCHECKED | PR metadata/checks re-queried: remote ff126cc is draft/open into v3; all 19 reported contexts succeed | Eleven new implementation commits remain local, as do the earlier eight audit commits. No push authorized; no final-source hosted checks/images. |
| F4 Enforced unconditional test/build merge gate | FAILED | Unconditional unprivileged API/worker AMD64/ARM64 smoke jobs now feed Tests / Required Gate locally | Effective v3 status policy still requires only Conventional Commit Title. Hosted validation and an approved protection change remain necessary. |
| F5 Review approval and current PR description | FAILED | Fresh GitHub metadata: REVIEW_REQUIRED; zero submitted reviews and zero inline review threads | Human/CODEOWNER approval and a current PR description remain missing; PR edits/draft transition were not authorized. |
| F6 Stable/default/prerelease release policy | UNCHECKED | all workflows and v3 transition checklist reviewed | main stays stable/default; prerelease/default/retention/external integrations remain separate release decisions |

## Verification and preservation

macOS ARM64 / Python 3.14.9: **API 324 passed, 18 Linux-only skips; core 322
passed; worker 303 passed, 13 Linux-only skips**. Built core/worker wheels were
reinstalled without dependencies and imports checked from site-packages; those
installed suites repeat 322 and 303/13. Editable project environments were then
restored through frozen sync. Full API Ruff/format passes; Pylint 8.44 clears
the configured 7.5 gate; actionlint passes. The existing TestClient deprecation
remains; coverage-enabled execution also retains previously observed resource
warnings. No production leak is established from those warnings.

API statement coverage is 6,235/10,032 (62.15%; 35 excluded lines). Branch,
core and worker code coverage were not measured. These figures are separate
from mapping coverage, scenario completeness and operational confidence.

Reproduce from the repository root:

```sh
(cd apps/api && uv run --python 3.14 --frozen pytest -q -rs --tb=short)
(cd packages/catalog-core && uv run --python 3.14 --frozen pytest -q)
(cd apps/catalog-worker && uv run --python 3.14 --frozen pytest -q)
(cd apps/api && uv run --python 3.14 --frozen ruff check app)
(cd apps/api && uv run --python 3.14 --frozen ruff format --check app)
(cd apps/api && uv run --python 3.14 --frozen pylint --fail-under=7.5 app)
actionlint
pnpm --prefix docs install --frozen-lockfile --ignore-scripts
pnpm --prefix docs audit
pnpm --prefix docs run build
```

The new populated migration fixture compares **all 39 non-version v6 tables**
(including publication bookkeeping), with two releases and one accepted map.
v6→v7 leaves every row equal. It then adds an observation after upgrade and
proves v7→v6 retains every resulting row and the original backup bytes. This is
small fixture proof. It does not replace the prior full copied-ledger v6 proof
for 498,403 releases/first-seen and 289,489 maps. Different table exclusions in
the two experiments explain their table counts; they are not coverage scores.

No new full-size or independently labelled mapping cohort ran. Matcher rules
were not tuned. The historical 215-case/118-positive result and its non-blind
label chronology remain exactly that. No new precision, provider completeness,
requests-per-map, eligible-age-by-class, CPU/memory/throttling/I/O, writer
occupancy, query/publication latency or sustainable rate is claimed. The
original JSON retains the older finite performance samples and their limits.
Issue [#175](https://github.com/Zzackllack/AniBridge/issues/175)'s broader E2E
suite remains unimplemented; focused ASGI regressions do not replace real clients.

New full-size experiments are blocked by aggregate disk admission. The earlier
conservative projection was 30,902,859,428 bytes versus the 30,000,000,000 cap,
including reserve. A fresh Docker inventory still cannot certify physical
shared-layer/cache attribution and ownership of older experiments. Mac free
space alone does not resolve that aggregate constraint. No additional service
copies, images or containers were created; no backups, retained acceptance
volumes or rollback images were deleted. Small native fixtures/build artifacts
use the existing diagnostic scratch allocation; continuous peak compliance is
not certified. All Mac Docker containers remain stopped.

## Version-specific upgrade and rollback preparation

**Prepared commands only. Candidate image digests do not exist.** First resolve
disk admission, run final-candidate Linux/full-copy v7 migration/preservation/
publication/rollback trials, obtain hosted checks/native manifests after an
authorized push, then review the actual images. Fresh raw Compose must come
from authenticated Zen; the read-only Coolify token remains read-only. Preserve
unrelated drafts, configuration bytes, budgets, networks, volumes and all backups.

```sh
REVISION=FUTURE_PUSHED_TESTED_FULL_SHA
OLD_WORKER=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1cc57eae123d842af0cc9fc9003356da7e4da3af3dada3b95764f58db4513106
uv run --project apps/api --python 3.14 --frozen python scripts/catalog/query_pilot/prepare_worker_update.py \
  --revision "$REVISION" --compose "$PLAN/current-compose.yaml" \
  --worker-config "$PLAN/worker.json" --expected-old-image "$OLD_WORKER" \
  --directory "$PLAN/reviewed"
```

The helper refuses missing/unfinished required checks or a manifest missing
either architecture. It pins the resulting immutable digest, preserves config
and allocations, and writes private candidate/rollback files. Its default
image-only update preserves the existing metadata mount; the mount isolation
change needs its own exact reviewed Compose diff.

Only after a separately approved live action: pull/inspect that candidate
digest, stop both services through Zen with Docker Cleanup off, then run these
guarded commands on fra-node-01 in the reviewed plan directory:

```sh
bash stopped-state.sh snapshot
bash stopped-state.sh publish
bash stopped-state.sh verify
```

They use the candidate image at 2 CPU/2 GiB with no network and logging disabled.
Existing v6 state gets a consistent, no-overwrite `.pre-v7.backup` before atomic
schema upgrade; admit its WAL-inclusive size and scratch beforehand. Public
schema2 is unchanged. Only after verification should the approved candidate be
started in the existing service, followed by revision-paired SQL/query, later
publication, required-title, resource and restart/OOM checks.

For rollback from v7 to the retained v6 image: stop both services, keep volumes,
and use the **new v7 candidate image** through the generated script:

```sh
bash stopped-state.sh rollback-v6
```

It checks the pinned baseline version, removes only v7 failure receipts and
restores the v6 schema contract. All current observations, work, retries,
accepted maps, corrections and backup generations remain. Then restore that
plan's `rollback.yaml` in Zen and start the pinned old image. **Do not restore
an old ledger over later observations or use rollback-v5 for a v6 baseline.**
Syntax and populated fixture rollback pass; a final full-size rollback has not.

The API changes have no database migration. A future client plan must pin its
new immutable API digest for all relevant services and preserve existing data,
downloads, aliases, configuration and jobs. The unsafe Mac bind must move via
an admitted consistent backup/storage plan before candidate startup. Do not
bypass the filesystem lock guard. For a credentialed rollout, an old image
without authentication is not an equivalent security rollback: select a tested
auth-capable digest or maintain an independently enforced ingress boundary.
No actual client storage move, cutover or ingress change is approved here.

## Remaining readiness gates

- **Draft → review:** local changes are concrete, committed and locally tested,
  but reviewers still see ff126cc. Approved push, hosted source checks/native
  builds, fresh final-source real-client/Linux acceptance and a current PR
  description remain missing. Review the new private migration and breaking
  filesystem guard. No draft transition was performed.
- **Merge into v3:** human/CODEOWNER approval; enforced aggregate gate after
  hosted validation; prospective independent mapping evidence or an explicit
  contract decision; full-size v7 preservation/rollback and overlap under admitted
  disk; real Sonarr differing scene numbering and actual move/restart behavior;
  safe retained-client storage. Keep the open acceptance criteria visible.
- **Public production:** public scope/auth/TLS/rights/default policy, all-router
  security boundaries, destination images/OS advisories, release/retention and
  rollback policy, external outage behavior and sustained freshness/capacity
  evidence remain unestablished. No resources/rates should be increased on the
  strength of these tests.
- **Limitations within this phase:** historical failure clocks cannot be
  reconstructed; unsupported/ambiguous provider content stays unresolved; old
  label splits are regression evidence; generated media is not provider-media
  acquisition/import/playback. Long endurance and real media remain outside the
  current authorization. These limits do not justify speculative mappings.

The local code defects above are repaired. Moving the PR into review, merging,
deploying the private candidate and releasing publicly remain separate decisions.
