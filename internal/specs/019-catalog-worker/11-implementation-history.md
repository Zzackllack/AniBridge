# Dated implementation history

Historical measurements and earlier failures, preserved from the evidence ledger.
Statements marked current or pending below describe that point in the work; use
[10-implementation-evidence.md](10-implementation-evidence.md) for current status.

# Private implementation evidence

Work in progress; **no milestone is declared complete by this file's existence**.
M5/public defaults, publication and production access remain unauthorized.

## Current gate summary (2026-09-30)

| Milestone / gate | Current evidence and remaining boundary |
| --- | --- |
| M0 / C0 | Mainline baseline recorded; installed Linux arm64 proofs pass. Latest native/amd64 packaging and enforcement coverage remain separate/open. |
| M1 / C1 | Core wheel and 41 contract tests pass. Full adversarial mutation inventory still needs final audit. |
| M2 / C2 | AniWorld and s.to collector checkpoints, first-seen retention and private migrations implemented; generated installed worker tests pass. Full collection/failure/capacity matrix remains open. |
| M3 / C3 | Last-good activation, durable jobs and 600 real SIGKILL recoveries pass. Broader ENOSPC/source-switch/revocation matrix remains open. |
| M3 / C4 | **Failed** full-size artifact caps; schema-refinement decision pending. Smaller-profile measurements do not pass this gate. Shaping/endurance remain open. |
| M3 / C5 clients | Pinned real Prowlarr→Sonarr TV and Radarr movie query/grab/generated-media import and paused/blocked restart lifecycles passed. Broader RSS/estimate/503/partial profiles remain open. |
| C5b | Authorized AniWorld download/remux/probe passed; no provider import/playback claim. s.to DNS fails in Docker; megakino authorized page lacks usable metadata. |
| M4 / C6 | Recognized mainline backup/migration and legacy TV admission implemented. Local mapping corrections and targeted refresh-management are implemented and tested. Complete legacy/STRM, all-provider capacity and upgrade matrix remain incomplete. |
| M5 / C7 / C8 | Closed: no public deployment, redistribution clearance or hosted default enabled. |

Sections below retain dated measurements, including earlier failures later fixed.
An old “remaining” item is superseded only by a later explicit result, not by code
existence or a mocked test.

## Baseline (M0 / C0)

- Started 2026-09-27 on clean `zzackllack-aux/catalog-worker-spec`, SHA
  `00437b3` (specification), mainline parent `e14a041` (v2.6.0).
- Created `zzackllack-aux/catalog-worker-implementation` from that SHA;
  `git merge-base --is-ancestor 00437b3 HEAD` succeeded. No commits/pushes.
- `git ls-remote origin refs/heads/main refs/pull/119/head` still reports
  `e14a041c0a8ddeac71aab7b8f564ac4a9584603a` and
  `61351bbcbfc1295ab597f8385f063598c25f3191`. The 01 reuse matrix has no ref drift.
- Host: macOS arm64, uv 0.12.19, Python 3.14.7, SQLite 3.53.4; stdlib zstd
  import succeeds. Docker Desktop 4.49.0 / Engine 28.5.1, Linux aarch64,
  8,218,034,176 bytes VM RAM. Other containers/user data are not test fixtures.
- Existing `uv run --locked` fails before execution: lockfile needs update.
  `uv run --frozen` uses the existing recorded resolution successfully.
- Initial `uv run --frozen pytest --no-cov` with explicit disposable DATA_DIR:
  174 passed, 1 failed in 10.36s. Failure is the default-path assertion in
  `test_repo_root_defaults_anchor_local_data_paths`, caused by this isolation
  override; not counted as an application regression. Clean disposable archive
  rerun is recorded below when finished.
- Agent deployment/release guidance refers to `apps/api/anibridge.spec`, but
  that path is absent at baseline; verify actual release build mechanism before
  claiming PyInstaller coverage.

## Field/source inventory (C7 remains closed)

| Source | Private implementation fields | Redistribution state |
| --- | --- | --- |
| AniWorld | names/aliases, paths, native structure, positive language labels | unresolved; synthetic fixtures only so far |
| s.to | names/aliases, paths, native structure, positive language labels | unresolved; no collection performed |
| megakino | names/aliases, paths, kind/year/structure, positive languages | unresolved; no collection performed |
| Skyhook | compact validated IDs, names/year/type for matching, explicit episode correspondences | unresolved; no raw payload publication |
| TMDb | compact validated movie IDs/matches | credentials and rights unverified |

No catalog, media, cookie, private operational DB or signing secret belongs in
this report. Synthetic fixtures do not prove live provider extraction, client
import, playback, capacity, freshness, or redistribution permission.

- Baseline rerun in a disposable local Git clone (no user data or env file):
  `uv run --frozen pytest --no-cov` **175 passed**, 12.76s; Starlette
  deprecation and unclosed terminal-log ResourceWarning remain. An intermediate
  archive-only run lacked Git metadata required by release-script tests.
- Lock mismatch identified: project 2.6.0, lock root package 2.5.2.
- Context7 retrieved Python 3.14 zstd, cryptography Ed25519 and HTTPX pinned-IP
  SNI/streaming documentation. Installed httpcore confirms SNI hostname is
  passed to TLS verification independently of TCP address.

## Approved implementation refinement

2026-09-27: native macOS Python 3.14.7 rejected
`resource.setrlimit(RLIMIT_AS, (268435456, 268435456))` with
`ValueError: current limit exceeds maximum limit`. Maintainer selected
**Linux pilot; keep native enforcement gated**. Native package construction
is separate evidence and must not be described as native resource enforcement.
Equivalent native supervision remains an open packaging/runtime gate.

The maintainer supplied exact inputs for bounded C5b work: AniWorld
`rascal-does-not-dream-of-bunny-girl-senpai`, season 1 episode 1; s.to `9-1-1`,
season 1 episode 1; megakino21.com film 6444 (`spider-man-3`). This authorizes
those individual inputs, not a bulk crawl or production deployment. No live
execution is claimed until recorded below.

## Incremental checks

- Core: `uv run --project packages/catalog-core pytest -q` — 39 passed.
  Clean Python 3.14.7 environment installed the built wheel and ran the same
  39 tests successfully. No API import/state dependency. Tests cover synthetic
  artifacts for three provider identities, movies/specials, signatures, strict
  JSON, corrupt schema and zstd, identity and magnet round trips.
- Worker: `cd apps/catalog-worker && uv run pytest -q` — 10 passed.
  Direct state/parser/publication tests, including injected exceptions at five
  publication boundaries. This is not SIGKILL evidence or a complete C2 pass.
- Two Linux arm64 Docker builds completed. Initial builds exposed relative
  uv dependency path handling: build roots now preserve `apps/*` and
  `packages/catalog-core`, while runtime virtualenvs remain `/app/.venv`.
  API lock root version corrected from stale 2.5.2 to 2.6.0; existing dependency
  versions retained. Both images install a deterministically built core wheel.

### Linux service integration (2026-09-27)

`bash scripts/catalog/validate-private.sh` builds and installs both images,
creates an isolated Docker internal network, serves a generated signed catalog
from the worker container, and runs the consumer against that HTTP source.
Only temporary container filesystems are used; the script removes its own
container/network on exit.

- Latest completed run: worker 17 tests, core 40 tests, API catalog 26 tests;
  all passed. Python 3.14.7 / Linux arm64 / SQLite 3.46.1.
- API image ID: `sha256:683fb37de6126082796e29086b6bbfa0f7fd97b77d5a8bd78742757e67d56adc`.
- Worker image ID: `sha256:93d85fc53215178bd642751c4dda4822426a80f832609f5ed249c71e18ab99e3`.
- Service scenario: signed HTTP install 0.2486 s; two language releases;
  unknown size remains zero with no invented quality; paused admission,
  idempotent duplicate, explicit resume and persisted blocked outcome; saved
  snapshot recovery and local RSS pass.
- cgroup memory.peak: consumer 150,233,088 bytes (1-GiB/2-CPU container),
  worker 43,573,248 bytes (2-GiB/2-CPU container). This tiny synthetic catalog is
  not the required C4 cardinality/24-hour measurement.
- This scenario calls catalog/job services directly. Application route wiring,
  real *arr grab/import and generated-media playback are not proved by it.
- Subsequent host worker changes: `cd apps/catalog-worker && uv run pytest -q`
  passes 22 tests. Added paged-listing restart/atomic acceptance, historical
  cadence, persistent language gaps, rejected-observation preservation,
  conservative queued Skyhook enrichment, and 72-hour/two-artifact retention
  with transfer leases. These newer worker changes require an image rerun.
- Context7 Sonarr documentation did not document Skyhook's internal response;
  repository Skyhook client and installed aniworld 5.0.6 parser source were
  inspected for endpoint/field shapes. Generated fixtures test the new parser
  and enrichment; no live canonical match is claimed.

### Bounded live metadata observations (C5b remains unverified)

One metadata GET per user-supplied URL, using the verified provider transport:
AniWorld returned 100,999 bytes and positive de-dub/de-sub/en-sub offers;
s.to returned transport_failure; megakino returned 250 bytes (not validated
catalog structure). No HTML, media URLs or catalogs were retained in the repo.
No extraction, media download, client import or playback was executed. The
s.to transport outcome did not retain an HTTP status, so its cause is unknown.

### Historical remaining gates (2026-09-27)

C0 lacks amd64/native package proof (native execution remains explicitly
gated). C1 has executable coverage but still needs the full mutation matrix.
C2 lacks the complete large HTTP/kill/failure matrix and real provider mapping
proof. C3 SIGKILL repetitions are in progress; exception tests are not a
substitute. C4 realistic cardinalities/shaping/100 updates/24-hour stability
remain unexecuted. C5/C5a/C5b have no real *arr/import/playback pass. C6 has
initial backup/rejection tests but not the complete released-state matrix.
M2–M4 are incomplete, including application routes, operative durable runner,
management, sampling, bounded ID fallback and the remaining provider adapters.
C7/C8 and M5 remain closed. No public default is enabled.

## Subsequent measurements and corrections (2026-09-27–28)

These supersede the narrower counts above; they do not close entire milestones.

- `scripts/catalog/crash_activation.py`: 100 real SIGKILL repetitions at each
  of decompress/validate/rename/before-commit/commit/registry, with eight reader
  threads. All 600 recovered the committed old/new snapshot and revision floor.
  Linux arm64, installed API image `683fb37…` above. This does not cover every
  inner fsync, ENOSPC, key compromise or concurrent management transition.
- `scripts/catalog/collector_capacity.py`: generated 100,000-title listing
  (5,300,000 bytes), 22.17s parse/accept, peak 332,783,616 bytes in a 2-GiB/2-CPU
  Linux container. A 40-season title resumed after its thirtieth checkpoint.
  Generated parser/DB evidence, not a live crawl or full HTTP capacity test.
- Core: 41 host tests passed; 41 also passed under Linux amd64 emulation using
  API image `sha256:e6c779307421e07b180b42c1d8728599a93bccf44ccff580ea0fab842958281e`.
  Later core edits (saved-file digest recovery) still need a rebuilt image check.
- Current Linux source-overlay checks: worker 27 passed (including actual CLI
  publication and SIGTERM/lock release); API catalog 31 passed before the later
  resolver tests. Source overlays are explicitly not newly built wheel evidence.
  Host worker: 25 passed, 2 Linux-only checks skipped. Host resolver: 8 passed.
- Migration suite: 8 passed on macOS/Python 3.14.7. Includes each released
  revision, unchanged unrelated DATABASE_URL target, and actual SIGKILL after
  three different migration CREATE statements. Every killed transaction kept
  revision 0003, rolled back the new tables, retained its backup, and upgraded
  successfully on restart. This is not the entire C6 rollback/legacy matrix.
- PyInstaller 6.19.0 / hooks 2026.3 / macOS arm64: clean onefile build passed;
  packaged startup migrated a disposable DB and returned HTTP 200 `/health`
  on loopback port 18573, then stopped. Added the missing dynamic migration
  import to the hook. Native snapshot resource enforcement remains gated.
- Job tests: 9 passed on host, including cancellation precedence, retained
  partial bytes, missing-output behavior and duplicate admission at disk cap.
- A disposable full-suite run found 11 legacy feed regressions caused by new
  process-global ElementTree namespace registration. Registration was removed;
  snapshot RSS now declares prefixes on its own document. Rerun pending below.

### C4 capacity: measured failure and narrower pass

`capacity.py generate --titles 10000`: 10k titles/200k entities/400k releases,
433,373,184-byte SQLite and 127,880,202-byte zstd. Generation 115.622s;
2-GiB/2-CPU container peak 692,137,984 bytes.

`capacity.py generate --titles 50000`: 50k titles/1m entities/2m releases,
2,169,835,520-byte SQLite and 646,634,545-byte zstd, 940.559s; generator peak
2,147,483,648 bytes (at its cgroup limit, no headroom claim). Both artifact
sizes exceed the maximum configurable 2-GiB/512-MiB caps. **C4 is failed.**
No cap was raised. Maintainer question 3 remains pending: benchmark compact
internal join keys while preserving external identities, then review the
specific contract change before adoption, or keep the exact schema/caps and
leave capacity blocked. No normative schema change has been made.

For the smaller fixture, initial query execution exceeded 2s; subsequent
query p95 was 542ms and saved recovery 30.474s. Profiling found unnecessary
whole-catalog joins and full semantic revalidation of already admitted bytes.
Queries now avoid unnecessary count joins and use the verified signed count
when an indexed minimum proves the entire catalog falls within the RSS window.
Recovery re-verifies the saved signature, stored digest, exact byte length and
whole-file SHA-256 in a bounded child. Only a committed, previously validated
version uses that path; new artifacts still receive full validation.

Latest `capacity.py consume` with current API/core source overlays, Linux arm64,
1-GiB/2-CPU: activation 21.370s, saved recovery 0.355s; eight readers/100 mixed
recent-feed and canonical episode queries, p50 19.7ms / p95 43.0ms / p99 67.7ms;
peak 691,380,224 bytes. An intervening run concurrent with native packaging
hit the memory ceiling and p95 653ms; it is not treated as a pass. The latest
run is a narrower local-file check, without transfer shaping, 100 updates,
filter-diverse queries or 24-hour steady state. C4 overall remains failed/open.

### C5b permitted AniWorld extraction only

`scripts/catalog/resolve-permitted-aniworld.py`, Linux arm64, installed aniworld
5.0.6 plus current resolver source overlay, 256-MiB child/60s/16-request/16-MiB
budget: the authorized season 1 episode 1 resolved through VOE. Latest attempt:
4 requests, 227,825 metadata bytes, 2.377s. No media downloaded; resolved URL
stayed in memory. Initial diagnostic logging exposed redirect paths; harness
logging was suppressed and its retained output reduced to the result counters.
No scraped HTML or URLs are retained in this evidence file. Other hosts are
not yet adapted to the bounded resolver, which is not wired to API grabs.
This is extraction proof for this one input, not download/import/playback or
C5b completion. s.to and megakino extraction remain unverified.

### Resumed local lifecycle and HTTP integration (2026-09-28)

- Full disposable current-checkout API suite before the latest runtime additions:
  207 passed, 13 skipped, 12.52s; the namespace regression above is fixed.
  Skips include the deliberately gated native snapshot execution tests.
- `scripts/catalog/validate-private.sh`, installed Linux arm64 images: core 41,
  worker 27 and API catalog 52 passed. Synthetic HTTP activation 0.242s;
  consumer peak 148,430,848 bytes, worker 43,024,384 bytes. API image
  `sha256:92cb67905daf9fc2db9553b9c9e051a74d0b6b8be9a39af4af9f553a538a2b0d`;
  worker `sha256:39481a19a3401904aede8a30f62c2727f1e6cf2086af5800394a0d1c42d4541e`.
  These image results precede the runtime/HTTP wiring below.
- Added a shared two-child consumer admission budget (each child <=256 MiB),
  cancellation ownership, sequential transfer/remux/probe phases, and local-only
  FFmpeg 7.1.5-0+deb13u1. Synthetic progressive/HLS transports are distinct from
  generated-video remux/probe/null-decode checks.
- A live durable AniWorld/VOE attempt exposed upstream parser-import thread
  address reservations. Offline reproduction failed under RLIMIT_AS=256 MiB;
  setting the child-only glibc `MALLOC_ARENA_MAX=1` succeeded (147,672-KiB virtual,
  91,384-KiB RSS at import). No memory cap was raised. Context7 lacked the glibc
  detail; verified its startup environment semantics in upstream
  `bminor/glibc/manual/memory.texi` (M_ARENA_MAX).
- Transfer progress initially carried fractional speed incompatible with strict
  child JSON. Counters are now integral, finite and range-bounded; a regression
  test checks serialization. Failed executor/setup paths now release their slot
  and mark only their own job failed.
- Authorized episode transfer subsequently fetched 209,518,496 bytes through
  the controlled transport, but local remux failed with `memory_limit` after
  124.658s. Container peak 425,664,512 bytes. It remained failed, not completed;
  no *arr/import/playback claim and disposable media removed with the container.
  This is transfer evidence, **not C5b completion**.
- Generated 720p/1080p inputs reproduced FFmpeg trailer allocation failure at
  ~261,700 KiB virtual/~53,768 KiB RSS. Bounding exec-time native stacks to 1 MiB
  and the muxer packet queue to one preserves the 256-MiB cap. Generated 180p,
  720p, 1080p remux/probe/decode and generated native-HLS transfer/remux pass.
  These observations describe generated inputs, not catalog quality estimates.
- Linux source-overlay HTTP/runtime + generated-media tests: 8 passed in 3.66s.
  Explicit `CATALOG_CONFIG_FILE` snapshot mode now connects lifecycle, local
  Torznab, durable qBittorrent admission/projection/actions and minimal `/ready`.
  Fixture flow proves signed update -> local canonical query -> paused add ->
  resume -> blocked -> restart -> explicit removal, with no provider requests.
  An unchanged poll verifies its manifest but skips artifact transfer. Bad update
  retains readiness/last-good bytes. This is mocked HTTP/client proof only.
- Runtime wiring is still incomplete M3/M4: canonical fallback, optional samples,
  management, STRM/legacy execution, all provider/host adapters, conditional GET,
  complete removal/upgrade matrix and actual *arr clients remain open. New source
  edits require rebuilt image/full-suite checks. Public/native gates stay closed.

### AniWorld output proof and first real client findings

- The corrected single authorized AniWorld/VOE job completed in 125.256s, one
  attempt, with a verified 203,921,375-byte Matroska output. ffprobe observed
  1280x720 H.264 video and AAC audio for **this output only**. Cgroup peak
  566,071,296 bytes in the 1-GiB/2-CPU container. Media stayed in its disposable
  filesystem and was removed; no client import or playback was performed.
  Command: `download-permitted-aniworld.py` with current source overlay on the
  previously recorded API image. This closes the observed local transfer/remux
  defect, not all C5b stages or other providers/hosts.
- Installed image rerun (`validate-private.sh`): worker 27, core 41, API catalog
  60 passed; synthetic update 0.2382s, consumer peak 148,815,872 bytes, worker
  42,643,456 bytes. Images: API
  `sha256:39734f03c3cf5ce6503c03ad3250c7681113011055e61c1db7110f5c94d0321a`,
  worker `sha256:96558eb800ada4d7f807e4c056d5d4b087fe32ba1d3842ac303150fd9f1131ef`.
  Later client compatibility edits require fresh image evidence.
- Source-overlay API catalog suite after durable alias-removal tests: 62 passed
  in 10.14s. Full disposable Git-copy API suite after runtime wiring: 217 passed,
  25 Linux-gated skips; existing Starlette deprecation/terminal-log warning.
- `validate-arr-tv.sh` starts fresh named volumes, separate worker/API/Sonarr
  containers, generated video, no host ports, and removes its own resources on
  exit. Sonarr stable 4.0.20.3014-ls326, pinned image
  `lscr.io/linuxserver/sonarr@sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`.
  Primary release tag and v3 OpenAPI/source inspected (Context7 returned v5
  development material, so it was not used as the v4 API contract).
- Actual Sonarr registered both indexer and qBittorrent endpoints and returned
  the generated mapped episode with size 0 and quality Unknown. An explicit
  Unknown-allowed profile approved it; normal HD-1080p rejected it with
  `Unknown is not wanted in profile`. No invented quality was introduced.
- Actual grab exposed percent-encoded xt URN incompatibility with Sonarr's
  MonoTorrent parser. The encoder now emits literal `xt=urn:btih:` separators;
  identity/hash/payload rules are unchanged and core's 41 tests pass. Added
  explicit Torznab magneturl/infohash attributes and regression assertions.
  Subsequent admission exposed .NET `True`/`False` form spelling; boolean form
  validation now accepts case variants. Grab/import rerun is still pending;
  registration/search/profile evidence alone does not pass C5.

### Real Sonarr TV lifecycle and local management (2026-09-28)

- `bash scripts/catalog/validate-arr-tv.sh`, disposable Linux arm64 containers,
  Sonarr 4.0.20.3014-ls326 at the digest above: **passed** generated-media
  query/grab/import, explicit Unknown-allowed profile, normal HD-1080p rejection,
  actual Sonarr paused admission, API restart with zero extraction attempts,
  resume to blocked, two Sonarr polls, second API restart preserving blocked
  without automatic extraction, explicit management retry, cancel and removal
  preserving history. Exactly two injected extractor calls (initial + retry).
  The imported generated file was 7,862,192 bytes, 601 seconds; a shorter
  20-second fixture was correctly rejected by Sonarr's normal sample detection.
- Sonarr maps stalledDL to queue `status=warning`, with `errorMessage` saying
  stalled with no connections. Its separate `trackedDownloadStatus` remains
  `ok`; primary v4 QueueService/QBittorrent source confirms these are distinct.
  The harness now checks the actual warning field and uses the maintained
  `RefreshMonitoredDownloads` command, not its deprecated alias.
- API image for this experiment:
  `sha256:c5f82df678b71763b12d7554ca679e5a046384a2b6fdfb41b20f7b3357ce0d02`;
  worker `sha256:96558eb800ada4d7f807e4c056d5d4b087fe32ba1d3842ac303150fd9f1131ef`.
  Final cgroup memory peaks: API 123,244,544 bytes (after restart, **not** the
  whole run maximum), worker 36,687,872, Sonarr 311,775,232. Named resources were
  removed by the harness. No live provider media entered this *arr experiment.
- New authenticated catalog status/rollback endpoints use status ETag/CAS,
  durable admission, 24-hour idempotency, task history/queue/storage bounds and
  one local executor. Rollback pointer, replay hold and task success commit in
  one transaction. Cancellation reaps validation and leaves a recoverable task.
  Additive private migration 0005 introduces status version/update state;
  migration 0004 retains its original schema subset. Host migration + management
  tests: 15 passed. Rebuilt installed Linux API catalog suite: **79 passed**.
- Source-overlay follow-up: durable unfinished/cancelled output directories are
  excluded from legacy TTL deletion. A bounded child records a SHA-256 receipt
  after local media verification; resume after publication but before completion
  can reuse matching bytes without a second transfer. Changed output fails
  closed. Jobs/generated-media tests: **26 passed** in 11.35s. These later edits
  still need an installed-image rerun.
- These results advance the AniWorld TV slice; they do not pass all M3/C4/C5.
  Prowlarr/Radarr, other providers, fallback/sampling/STRM, full management,
  large-profile capacity, endurance and the remaining failure/migration matrix
  remain open. Native enforcement, C7/C8 and M5 remain gated.


### Worker preflight, page completeness and bounded ID fallback

- Worker private state now validates the exact recognized schema/provider before
  mutation, retains a v1 backup, and upgrades transactionally to v2 (persistent
  listing traversal tables). Three real SIGKILL boundaries (tables/version/commit)
  resumed with the original revision intact. Foreign columns, triggers and
  provider mismatches reject unchanged. Host worker suite: 34 passed, two
  Linux-parser skips; installed Linux worker: **36 passed**.
- AniWorld parsing now requires a complete HTML document and recognizes an empty
  episode offer container separately from malformed/truncated detail. Unknown
  paging controls reject rather than count a partial listing. Unrelated title
  links cannot complete the current title. One permitted AniWorld episode page
  was fetched for structural inspection only: 100,999 bytes, hosterSiteVideo and
  closed body/html confirmed. No host redirect/media was requested or retained.
- Repeated generated 100,000-title/40-season checkpoint experiment after these
  changes: 5,300,026-byte document, 13.116s listing parse/import, 332,783,616-byte
  container peak; restart after season 30 preserved 40 release discoveries.
  This remains generated parser/DB evidence, not live listing throughput.
- `validate-private.sh` installed-image rerun: worker 36, core 41, API catalog
  **80 passed**; synthetic HTTP install 0.717s, consumer peak 148,455,424 bytes,
  worker peak 42,524,672. API image
  `sha256:c95af430a18dd84465b7ac9d1b2f16bf26728674538557115e83c24fb9cacaf6`;
  worker `sha256:1a00065d022e27dbfc258f12e1dbe1ebd8e0c3b36114434086e0d3aab23c64a9`.
  A prior Docker layer-unpack failure recovered on rebuild; no global prune or
  unrelated container/volume deletion was used.
- ID-miss fallback now has fixed Skyhook/TMDb adapters, exact supplied-ID
  validation, compact durable positive/negative/transient cache, singleflight,
  two inflight / 30-per-minute admission and a two-second lookup deadline.
  Movie IMDb lookup validates its unique result with movie details; no TV guess.
  Candidate matching uses exact local name/alias/type/year and existing episode
  maps only. Missing episode maps and conflicting local IDs never trigger
  correspondence inference. Search and RSS stay local; only ID-bearing misses
  can contact the configured canonical source.
- Added dnspython **2.8.0** for cancellable bounded DNS (0.5s lifetime), avoiding
  an abandoned blocking system-resolver thread after lookup timeout. HTTPX
  retains verified original TLS/Host identity while connecting to validated
  public IPs; no redirects, ambient proxy or compression expansion. Context7
  HTTPX/dnspython/TMDb primary docs and Sonarr v4.0.20.3014 ShowResource inspected.
  Canonical tests use synthetic responses; **no live TMDb credential or fallback
  latency claim**. Authenticated management CORS is separated from legacy wildcard
  CORS; explicit origins only, no cookie credentials.
- Installed Linux API catalog suite after fallback/CORS: **95 passed** in 18.88s.
  Full disposable Git-copy host suite passed with Linux-only cases skipped;
  exact count and final packaging/resource reruns remain to be recorded.
  A later small edit freezes host preference at durable admission; it still
  requires its targeted and rebuilt-image regression checks.

### Sampling, latest crash recovery, and s.to increment (2026-09-29)

- Previous full disposable-copy host suite: **245 passed, 30 Linux-gated skips**
  (`pytest`, Python 3.14.7/macOS arm64). This predates scoped sampling and s.to.
  Frozen host-policy targeted tests: **21 passed**. Baseline warnings unchanged.
- Latest `crash_activation.py` run used installed API
  `sha256:2b11381c7f8ce5e2470086ba7955e03bd4ad778f539b23c1ec7ca2d33e45b2d8`
  with migration 0005: **600 real SIGKILL recoveries passed**, 100 each at
  decompress/validate/rename/before_commit/commit/registry with eight readers.
  Stage durations 47.555/82.780/82.971/89.392/90.880/64.473s. Complete old/new
  views and accepted revision floors remained intact. This does not cover every
  ENOSPC/key-revocation/source-switch failure gate.
- Explicit searches now enqueue bounded optional quality work; RSS/caps do not.
  One active sample shares child admission with downloads/validation and is
  cancelled/reaped before required work proceeds. Starts (six/hour), success,
  unknown and challenge cooldowns persist; scope includes provider/title/native
  season/language/origin/host policy/extractor version and observed structure.
  Actual completed downloads take precedence. Exact files retain observed codec;
  sibling estimates inherit resolution only. Artifact updates require a scope
  recheck; unchanged scopes retain original expiry. No sample changes size,
  release ID, infohash, first_seen or feed GUID.
- Sampling fetch is capped by a shared deadline/request/byte budget; a server
  ignoring Range cannot make the prefix unbounded. HLS is currently unknown,
  not expanded into downloads. Local ffprobe only reads a bounded prefix under
  supervision. stdout/stderr each have a 64-KiB cap; overflow kills the process
  group. Generated-prefix test proves real ffprobe extraction, not live sampling.
- Linux source-overlay catalog suite before the global-cache guards: **107
  passed**. Added free-disk/private-metadata refusal and damaged-evidence checks;
  focused fallback/quality suite **23 passed**. Four intermediate test failures
  were obsolete minimal Store doubles missing the storage fields; corrected
  doubles preserve the production storage guard. Rebuilt-image checks follow.
- s.to metadata/VOE resolution now has explicit native path and language-label
  dispatch; AniWorld numeric language semantics are not reused. Shared worker
  collection persists listing pages and release history independently per
  provider. Synthetic Linux worker suite before coverage/operator-review changes:
  **40 passed** (source overlay, Python 3.14.7). Latest host worker suite after
  those changes: **39 passed, three Linux skips**.
- Publication coverage is measured from the rights-filtered artifact instead of
  hardcoded partial values; oldest active page check is unknown when any active
  page has never succeeded. The local `--review-season` command records reviewed
  correspondence with expected-old CAS, requires an existing validated title map
  and observed native season, and re-enriches episodes by exact title. It never
  maps episodes solely by ordinal equality.
- Context7 AniBridge s.to docs and installed AniWorld **5.0.6** s_to models
  inspected. Separate permitted-page diagnostics: s.to failed before HTTP;
  direct container DNS confirmed `socket.gaierror: Name or service not known`.
  megakino21.com returned HTTP 200, **250 bytes**, without a complete HTML document
  or observed title/language metadata. No host/media fetch occurred for either.
  **C5b s.to and megakino remain blocked/unverified**, not passed by fixtures.
- Remaining: megakino adapter/TMDb worker enrichment, overrides/targeted refresh,
  STRM/legacy execution, full client/provider matrix, large-profile C4 decision,
  endurance, broader migration/failure matrix and final packaging/platform gates.
  Public defaults, C7/C8 and M5 remain closed. Native enforcement remains gated.
- Rebuilt installed Linux private harness: **worker 42 / core 41 / API catalog
  111 passed**, synthetic HTTP install 0.2177s, consumer peak 151,027,712 bytes,
  worker peak 42,479,616 bytes. Worker image
  `sha256:a42422c396f1ce0055f567d121e34446e0c202795a1df266f8f1d19e122502b3`;
  API `sha256:9510379224aa766e9f7b92d1aa771193cc9cfbd4346d0d58b75151b27d217769`.
- Subsequent source-overlay changes admit complete legacy TV native paths and
  retain configured/preferred host order across retry. No v2 identity or canonical
  map is invented. Jobs/supervisor subset **28 passed**. Migrated incomplete jobs
  remain failed explicitly; legacy megakino resolution remains unimplemented.
- Conditional metadata polling keeps at most six small ETag/body records; real
  local HTTP integration proved 200/304 reuse with no repeated artifact transfer.
  Cached envelopes still reject expiry and revoked keys. Two targeted conditional
  tests passed; preceding whole Linux source-overlay catalog suite **113 passed**.
- Source Ruff checks passed. Disposable Compose configuration validates with
  `docker compose ... config --quiet`; no Compose services were launched. The
  worker image now provisions writable UID-1000 state/public mountpoints; that
  later Dockerfile change still needs its own installed-image rerun. Deployment
  docs explicitly keep this separate from production migration/public hosting.
- Broader disposable Git-copy API run after conditional polling/legacy TV changes:
  **252 passed, 42 Linux-gated skips** (294 collected), existing Starlette warning
  only. `pnpm --prefix docs run build` passed in 5.16s; existing chunk-size and
  missing m3u8 highlighter warnings remain. Later durable quality-observation
  changes require a subsequent regression run.
- Actual-download quality observations now commit in the job completion transaction,
  bounded to 32 compact pending records, then feed the persistent scoped cache.
  Restart and stale-generation tests passed; URLs are absent from pending records.
  Linux source-overlay catalog suite: **115 passed** in 18.22s.
- Worker TMDb enrichment now uses movie search/find/detail endpoints and the shared
  canonical request budget. Missing year, multiple candidates, incomplete paging,
  and mismatched detail IDs stay unresolved; no TV fallback. Only compact accepted
  mappings persist. Context7 TMDb primary API docs inspected; tests use a synthetic
  token and responses. Latest host worker suite **44 passed, three Linux skips**.
  No live TMDb credential/access or megakino collection proof is claimed.

### 2026-09-29 installed and real-client rerun (before local overrides)

- `bash scripts/catalog/validate-private.sh`: worker **47**, core **41**, API
  catalog **115** passed. Synthetic HTTP install **0.2471s**; consumer cgroup
  peak **151,539,712 bytes**, worker **43,130,880 bytes**. Linux arm64, Python
  3.14.7, Docker Engine 28.5.1. API image
  `sha256:88bdc6bce5832c6c6492b524a7ad67950f7904b12642626826d7d4da6aa509bd`,
  worker `sha256:0000b5afba5d41641c49ff76f5e934e78777927ed83ff71325329886e8c9f45b`.
- `bash scripts/catalog/validate-arr-tv.sh`: pinned Sonarr **4.0.20.3014-ls326**
  (`sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`)
  passed unknown-size/quality profile checks and imported **7,862,192 bytes** of
  locally generated H264/AAC media. Actual client polling observed paused and
  blocked states across two API restarts; explicit retry made the second attempt,
  then cancellation/removal preserved history. This uses synthetic catalog rows
  and an injected challenge; it is not live-provider import or playback proof.
  End-of-run cgroup peaks: API **128,532,480** (after restart, not full-run max),
  worker **26,722,304**, Sonarr **314,269,696 bytes**. Disposable named containers,
  volume and network removed by the harness. API/worker image identities above.
- Later local override changes and Alembic 0006 require new package regression
  evidence; these successful runs do not validate those later edits.


### 2026-09-29 local mapping corrections

- Authenticated override CRUD, strict identity/namespace checks, idempotency and
  atomic If-Match updates now feed snapshot search/RSS and ID-miss detection.
  Episode/title conflicts and changed/missing input fingerprints suspend local
  application; status transitions advance versions in the same transaction as
  a title edit or catalog activation/rollback. Disable/delete remain possible
  after disappearance. Queued jobs freeze verified local-operator provenance.
- Added private Alembic **0006** lookup/expiry indexes; frozen 0004/0005 table
  contracts remain unchanged. Disposable mainline migration matrix and explicit
  0005 correction-row preservation checks passed. No user installation touched.
- Linux source-overlay suite: **123 passed** in 21.89s, including eight override
  tests (concurrent PATCH/create, storage rejection, restart, held read snapshot,
  activation conflict, movie RSS identities and durable job provenance). One
  initial new assertion used the wrong test accessor; corrected and rerun.
- `bash scripts/catalog/validate-private.sh`: installed worker **47**, core **41**,
  API catalog **123** passed. HTTP install **0.2383s**; consumer peak **151,539,712**,
  worker **42,848,256 bytes**. Python 3.14.7/Linux arm64/Docker 28.5.1; API image
  `sha256:5964391a6a15968151e98c8a36bec272773200d6f57ff2a0fae30ca68fdd660d`, worker
  `sha256:a2a806ef376427ed15bb662ba77d6145fc8356183492199c84014fd13d3fd119`.
- Full disposable-copy host API suite: **254 passed, 50 Linux-gated skips**
  (304 collected); existing Starlette deprecation warning. Ruff checks passed.
- Context7 SQLite lookup supplemented by upstream URI/progress-handler docs:
  https://www.sqlite.org/uri.html and https://www.sqlite.org/c3ref/progress_handler.html.
  Overlay readers retain the private read snapshot, transfer provider handles to
  read-only immutable attachments, and retain existing query/cache limits.
  Large-profile override cost is still unmeasured; C4 is not passed.


### 2026-09-30 megakino metadata and legacy movie paths

- Strict same-origin sitemap/index traversal uses **defusedxml 0.7.1**, explicit
  DTD/entity/external-reference rejection, bounded parser children and persisted
  complete-listing checkpoints. Movie ingestion retains native paths and observed
  title/year/IMDb metadata. Unlabelled players and Movie.inLanguage do not create
  guessed releases. Serial discovery stays unknown pending episode structure.
- Context7 defusedxml docs and mainline megakino sitemap/host code inspected.
  Explicit player language attributes are a conservative fixture-supported
  surface, **not confirmed live-site selectors**.
- `bash scripts/catalog/validate-private.sh`: installed worker **57**, core **41**,
  API catalog **127** passed. HTTP tests cover all three dispatches, restart,
  blocking and first-seen retention. The initial movie test compared unordered
  rows; corrected to check the same release ID. HTTP install **0.2531s**; consumer
  peak **151,425,024**, worker **42,651,648 bytes**. API image
  `sha256:0c997ab5ca15d845c3dfe8ca40137c6fde82aaee939f0e87d29491b661f24edb`, worker
  `sha256:42ed8bd00059341104fb1920e67aed08ffe47d1dc14ac51f171482e33c71fd7d`.
  Python **3.14.7**, SQLite **3.46.1**, Linux arm64, Docker Engine **28.5.1**.
- Complete legacy movie magnets freeze a unique indexed local movie path without
  canonical inference/v2 equivalence. Hash/path survive duplicates and restart.
  Local movie host selection recognizes labelled VOE players; unknown original
  language stays unavailable. No live host/media request proves this adapter.
- Permitted megakino diagnostics still saw **250 bytes**, only meta/script tags,
  no title or offers. No script/browser execution or host/media fetch. A current
  authorized direct URL was requested; **C5b megakino stays blocked**.
- Later source-overlay STRM/overrides/jobs subset: **38 passed**. Synthetic URLs
  prove durable file creation, receipt reuse, ownership/racing-file rejection,
  challenge/restart persistence, pause winning completion and proxy-mode refusal.
  No real STRM import/playback. Output publication now requires hard-link support
  within the owned job directory; final creation cannot overwrite another file.
  These edits postdate installed images above and need installed regression.

## 2026-09-30 — Installed STRM increment and real Radarr movie contract

- `bash scripts/catalog/validate-private.sh` (`/tmp/anibridge-private-v31.log`):
  installed Linux arm64 worker **57**, core **41**, API catalog **131 tests pass**.
  HTTP fixture activation took **0.2372s**; blocked job persisted. API cgroup
  peak **151,183,360**, worker **43,192,320 bytes**. API image
  `sha256:b5cdcb29df41c61066b12fd3c9fb1d70286fcbd4becc57ebbae414615aa9f0cb`;
  worker `sha256:c3caa291a79b507e8551b109ca49796d82b953b3a19c0d5974be56c0dd99e16b`.
  This includes direct STRM receipt/publication and the no-overwrite hard-link
  publication fix; no real STRM import or playback claim.
- Stable disposable-copy full API run (`/tmp/anibridge-full-api-v32.log`)
  exits **0**, all collected tests pass or Linux-gated skip. Existing Starlette
  deprecation remains; unclosed SQLite fixture warnings need cleanup. The earlier
  v31 host run overlapped a source-copy synchronization and is excluded as current
  proof. `pnpm --prefix docs run build` passes in **6.26s**, with existing chunk-size
  and m3u8 highlighting warnings.
- `bash scripts/catalog/validate-arr-movie.sh`
  (`/tmp/anibridge-arr-movie-v6.log`) passes against Radarr **6.4.4.10685**,
  `lscr.io/linuxserver/radarr@sha256:adb6c09d6b729ea5e642c99cea35af72702ef476bf4763f153299ac5db9f0b4f`.
  API image `sha256:a16d82e76b75d64f5fea06d453eb21f5e79e88767ffdbc6fb6763589a866cc90`;
  worker remains the v31 image with a mounted synthetic publisher fixture.
  Real-client Torznab/qBittorrent registration, conjunctive TMDb/IMDb search,
  Unknown quality/size=0 approval under explicit **German + Unknown** policy,
  HD-1080p rejection, and generated movie import pass. Imported file is
  **7,862,192 bytes**; generated source is 601s, 320x180, H264/AAC. Radarr labels
  its imported quality WEBDL-480p; that is client interpretation, not invented
  catalog evidence. API/worker/Radarr peaks after final API restart:
  **128,851,968 / 28,291,072 / 220,176,384 bytes** (API is not full-lifetime max).
- Actual Radarr paused admission has **0 attempts**; restart preserves pause.
  Resume encounters the injected challenge and remains stalled/warning for two
  actual client polls; another API restart preserves blocked state and makes no
  automatic attempt. Explicit retry makes attempt 2; cancel/remove retain history.
  Only the extractor is replaced by the disposable generated fixture; real job
  acceptance, subprocess remux/probe, receipts, publication and client import run.
  No live provider, canonical-source mapping or playback evidence is implied.
- Initial Radarr experiments exposed numeric IMDb wire IDs and missing observed
  movie year. HTTP parsing now normalizes digit IMDb IDs to canonical `tt` form;
  movie labels include observed years. Shared identity/magnet/schema stay unchanged.
  The fixture now supplies both synthetic authoritative IDs, preserving strict
  conjunctive ID matching. Default Original/English language policy correctly
  rejects German; the successful profile explicitly selects German. No criterion
  was weakened to accept a conflicting language or unknown quality in HD-1080p.
- Worker canonical enrichment now retains validated secondary IMDb/TMDb-TV IDs
  from the same primary canonical detail response, with the original source-rights
  filter; conflicting prior IDs prevent partial replacement. Source-overlay
  canonical tests **12 pass**; RSS/fallback tests **17 pass**. Installed worker
  proof of this newest refinement is still pending. Context7 and primary Radarr
  parser/language source informed the experiment. Failed runs v1–v5 are diagnostic
  history, not passing evidence.
- Disposable volumes, networks, client profiles and generated media were removed
  by the harness. Public launch, C4 full-size caps, targeted refresh, STRM proxy,
  megakino series structure, C5a and remaining C5b/C6 matrix remain open.

## 2026-09-30 — Real Prowlarr → Sonarr generated-TV flow

- `WITH_PROWLARR=1 bash scripts/catalog/validate-arr-tv.sh`
  (`/tmp/anibridge-arr-prowlarr-v1.log`) passes. Prowlarr **2.6.5.5623**,
  `lscr.io/linuxserver/prowlarr@sha256:f2b26429893d4c4cb71941b7ee50b1bdecd9d5f9f9e02d5410615e9f4f7c8d95`;
  Sonarr **4.0.20.3014**, pinned digest recorded above. Same API/worker images
  as Radarr v6. Fresh volumes and network; no host ports or installation access.
- Real Generic Torznab registration and full application sync creates the Sonarr
  indexer pointing at Prowlarr. Sonarr queries through that proxy, accepts honest
  size 0/Unknown under the explicit profile, rejects HD-1080p, grabs through the
  durable qBittorrent API and imports **7,862,192 bytes** of generated media.
  Paused admission/restart has zero extraction attempts. Challenge-blocked job
  stays visible for two polls before and after another restart; explicit retry,
  cancel and removal preserve history. No live extraction/import/playback claim.
- Prowlarr/Sonarr/worker peaks **151,506,944 / 194,629,632 / 27,602,944 bytes**;
  API peak after its final restart **128,790,528 bytes**. All own disposable
  containers, generated media, volumes and network cleaned by the harness.
  Context7 Prowlarr application/Generic Torznab schema and actual image schemas
  informed configuration. C5a burst/estimate/503/partial matrix remains open.

## 2026-09-30 — Explicit targeted refresh increment (resource gate pending)

- Shared metadata parsers/transport moved into `catalog_core.providers`; worker
  facades preserve its imports. Core now declares HTTPX 0.28.1 and defusedxml
  0.7.1. No worker media extraction, user-query endpoint or telemetry was added.
- Authenticated refresh creation/read routes, UUID idempotency and equivalent-set
  deduplication accept 1–10 existing local title IDs, never URLs. Shared durable
  refresh/rollback queue remains 32/concurrency 1. Each title uses a supervised
  256-MiB child with 120s/30 requests, including admission wait. Completed-title
  checkpoints resume after restart. Provider start spacing/hourly cap, challenge
  and 429 cooldowns persist locally; clock rollback stops requests.
- Successful observations override older central data for the same identity for
  24h; central observations at least as recent supersede them. Invalid/failed
  pages preserve central data. Unknown language labels cannot remove known offers.
  New native episodes remain canonically unresolved unless a validated published
  or local operator mapping exists. A private persistent discovery ledger carries
  min(local,central) first_seen through expiry, reappearance and central arrival.
  No canonical-source enrichment or media extraction occurs during refresh.
- Source-overlay tests: refresh/override/snapshot/runtime/task subset **43 pass**
  (`/tmp/anibridge-refresh-v5.log`); native local-entity operator correction,
  expiry/CAS transition **6 refresh tests pass** (v6). Parser/rate and refreshed
  lifecycle tests **13 pass** (`/tmp/anibridge-refresh-child-v3.log`), including
  actual supervised installed parser with asserted 256-MiB limit, persisted starts,
  and a hung child killed/reaped within 2.5s for a 0.5s supervisor deadline.
  These are generated-page contracts, not live provider refresh proof.
- Installed v37 run: worker **59**, core **41**, API catalog **146 pass**;
  HTTP activation **0.2379s**, API peak **150,319,104**, worker **42,700,800 bytes**.
  Images: API `sha256:930cd1b5508c28f78a1a67ffd408492d14a341d68bc9ba030036942faf5f0c2f`,
  worker `sha256:c510ca3a5dd7ac9ee7259faec1b0bc3deab58baa577890478db37cba6d513820`.
  This predates the latest query optimization and is not full-scale refresh proof.
- `bash scripts/catalog/validate-capacity-refresh.sh` v1 and v2 **fail** the
  two-second query deadline on the generated smaller profile: 10k titles,
  200k entities, 400k releases, SQLite **433,373,184 bytes**, zstd
  **127,880,202 bytes**, one private observation, eight readers. Query-plan
  inspection shows compound entity/canonical views materializing large tables.
  Limits and public schema remain unchanged. Indexed central/ledger/local branches
  and a small-overlay count delta are being validated; v8 small-fixture regression
  suite **38 pass**. No overlay resource gate is marked passed by those tests.


## 2026-09-30 — Indexed refresh overlay and correction validation

- `validate-capacity-refresh.sh` v3 existing-entity overlay and v4 new-entity
  overlay meet the small-profile latency target: respectively p95 **101.662 /
  102.249 ms**, p99 **106.908 / 106.038 ms**, consumer peaks **605,044,736 /
  605,413,376 bytes**. Same generated 10k-title/200k-entity/400k-release fixture
  and eight readers/100 mixed RSS and exact-ID requests, 1 GiB/two-CPU consumer.
- v4 mapped local episode **fails** the selected 500-ms p95 target (**1.186 s**),
  despite completing within the two-second query deadline. A NOT MATERIALIZED
  experiment v5 worsens it to **1.574 s** and was reverted. The harness originally
  only reported percentiles; it now asserts p95 <=500ms, p99 <=2s, recovery <=10s
  and cgroup peak <=1GiB after reporting measurements. Earlier zero exits do not
  override those measured failures.
- Query-plan inspection identified full canonical-title materialization on RSS
  polls. Indexed per-title primary selection now preserves local/published
  precedence and retains published episode correspondence only for the same
  canonical assignment. No artifact schema, memory cap or query deadline changed.
- Source-overlay v6 mapped measurement meets targets: p95 **198.225 ms**, p99
  **203.153 ms**, recovery **0.217 s**, consumer peak **605,634,560 bytes**.
  Repeated v7 with executable assertions passes: activation **15.383 s**, recovery
  **0.298 s**, p95 **222.928 ms**, p99 **260.021 ms**, peak **604,872,704 bytes**.
  API source over installed v37 image; local-file activation, no shaping, 100
  updates, large correction inventory or 24-hour endurance. This does **not** pass
  full C4; the 50k-title artifact-cap failure still requires the pending decision.
- Generated three-provider query comparisons exercise all three release branches,
  primary title corrections, disabled corrections, language/year/category/ID
  filters, counts and mode-aware pagination against the small relational view.
  New checks reject boolean native coordinates/control labels before writes, and
  storage refusal prevents new deduplication receipts while existing receipts
  remain readable. Overlay/override/snapshot subset **44 pass** (v2); expanded
  query regression suite **7 pass** (v3). No live provider claim.
- Consistent disposable-copy full API run: `uv run pytest --no-cov -o addopts='' -q
  --junitxml=/tmp/anibridge-full-api-v39.xml` — **263 passed, 71 skipped**, 16.06s.
  Native Linux-only skips are explicit; baseline Starlette deprecation remains.


## 2026-09-30 — Migration and actual disk-exhaustion increment

- Consistent disposable-copy migration suite v41 **13 pass**, including every
  interrupted state, retained bytes/files/STRM rows/historical hashes, cross-site
  collision rejection, three SIGKILL migration boundaries, original-backup
  restore, exclusive startup ownership and a racing backup publisher. Corrupt
  retained backups block without replacement. Startup now holds a process lock;
  backup publication uses no-overwrite linking and requires hard-link support.
  Mainline/private backups remain separate from any user's installed database.
- Actual ENOSPC experiment: `bash scripts/catalog/validate-storage-failure.sh`
  v4 passes on fresh Linux container tmpfs **640 MiB**, consumer **1 GiB/two CPUs**,
  source overlay over installed v38. Exhaustion before activation commit yields
  SQLite OperationalError, retains **revision/floor 1**, and last-good searches
  succeed. A subsequent update is refused as storage_full. Fresh Store reconstruction
  and saved validation succeed with pressure retained and **81,920 free bytes**.
  Pressure writes **670,605,312 / 670,609,408 bytes**; cgroup peak **762,662,912**.
  This is actual local disk pressure, not a mocked free-space result or arbitrary
  cap increase; it is not every possible ENOSPC boundary or a process-kill test.
- v1 exposed SQLite sidecar recreation after closing the last connection; initial
  v2 also found an incorrect column name during the fix. Retaining one idle WAL
  handle, read-only query handles, closing failed constructor resources and checking
  private storage before clock writes resolves the observed failure. Context7
  retrieved upstream SQLite WAL/SHM teardown source. Snapshot/refresh/override/
  runtime/update regression subset **49 pass** (v2); failed-constructor/read-only
  test subsequently added. Full latest installed suite still needs rerun.
- Installed v38 before these newest changes: worker **59**, core **41**, catalog
  **153 pass**, HTTP installation **0.235s**, API peak **152,911,872**, worker
  **43,520,000 bytes**. API `sha256:28132758cfeba17d70d048377de205a2785d5ccc8e2ab82cfadc80b2884970c0`,
  worker `sha256:8f7abb481a4c0b2e537fda584b5f5be8d2a90e8e43e8851091fa406a3fa2580a`.
  Docs build v4 passes in **5.41s**; newest STRM/recovery documentation not yet rebuilt.

## 2026-09-30 — Stable snapshot STRM proxy increment

- Proxy `.strm` creation uses the supervised local resolver after durable
  acceptance and verified no-overwrite publication. Direct/proxy delivery freezes
  at acceptance; completion registers a digest of the frozen request in the same
  private transaction. Registration persists independently of client aliases and
  original output, matching mainline stream-map lifetime. Public release identity,
  magnets, first_seen and worker behavior are unchanged.
- `/strm/catalog` supports signed stable job URLs and scoped expiring nested HLS
  URLs. Provider disabling still applies. Playback resolves locally with the
  existing 60s/16-request/16-MiB child; transport pins every public DNS/TLS hop,
  disables ambient proxies/cookies, caps two streams, 120s inactivity and playlist
  input/output/URI inventories. HEAD fallback closes without buffering an ignored
  Range. DASH returns an explicit unsupported error. HTTPX media URL logging is
  suppressed in the streaming task; HLS logging no longer prints URLs/key tags.
- Source-overlay catalog/legacy STRM/migration suite v5 **180 pass**. Tests cover
  Range/TLS identity, private redirects, mixed DNS answers, nested HLS key/part
  signatures, resource refusal, source-close cleanup, alias/output removal and
  preserved completion. Earlier v4 had **165 pass/two harness path errors** because
  the tests mount lacked enough parents for integration conftest; corrected test
  location, no application acceptance change. Latest log-suppression refinement
  still needs installed-suite rerun.
- `bash scripts/catalog/validate-strm-playback.sh` v1 passes with generated
  two-second **320x180 H.264/AAC**, **76,496-byte MP4** and locally remuxed HLS.
  Actual HTTPX/TLS (disposable CA/SNI), Range and FFmpeg **7.1.5-0+deb13u1** decode
  pass for MP4 and HLS, then after original output/alias removal and reconstructed
  Jobs reader. Five media requests, cgroup peak **282,222,592 bytes**. API source
  overlay over v38; resolver and DNS destination are explicit harness injections.
  This is generated playback proof, not live provider resolution, actual *arr STRM
  import, remote-public DNS behavior or public launch readiness. All media/key/DB
  state resides in the removed disposable container.

## 2026-09-30 — Installed verification and real RSS selection finding

- `bash scripts/catalog/validate-private.sh` v42 passes: worker **59**, core **41**,
  catalog **159 tests**; synthetic HTTP installation **0.2263s**, API cgroup peak
  **152,670,208**, worker **43,003,904 bytes**. Linux arm64 API image
  `sha256:eb58bd6f804de3ee8e938d3bab80c566d451b08cdf18e3084dbb5d6c5ff6634c`,
  worker `sha256:3661a2a9bba421714527d12e46e9b35eb8059a3e91fb8a6ba1bee35531edd5f9`.
  Includes latest migration/ENOSPC/refresh/proxy changes and URL-log suppression;
  predates subsequent runtime startup cleanup/recovery refinements.
- Disposable-copy full native API v43 initially had **4 failed /268 passed /72
  skipped**: newly added playback tests lacked their Linux platform marker and
  correctly hit the closed native runtime gate. Adding that marker, without
  changing enforcement, yields v44 **267 passed /77 skipped**, **13.87s**. Existing
  Starlette deprecation and legacy terminal ResourceWarning remain separate.
- Generated TLS/Range/MP4/HLS playback v2 passes after log suppression, five media
  requests and cgroup peak **196,153,344 bytes**. Same fixture resolver/DNS and
  FFmpeg **7.1.5-0+deb13u1**; no provider/client-import claim. Docs build v5 passes
  in **5.64s**, including STRM and recovery documentation.
- `bash scripts/catalog/validate-arr-rss.sh` v2 uses the above installed images
  and pinned Sonarr **4.0.20.3014**, digest
  `sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`.
  Fresh profiles and generated native coordinates, **no monitored series, profile,
  download client, media or canonical mapping**. This isolates feed selection;
  it does not prove all 1,000 eligible releases or import/redownload behavior.
- Bootstrap **fails**: cycles 1/2 each request offset 0 and observe the same
  **100 /1,000** tied-second GUIDs. After activating a new 1,000-entry burst, cycle
  1 requests offsets **0–1000 in steps of 100**, sees all **1,000 new entries** and
  one old page; cycle 2 returns the first 100. Partial provider injection returns
  HTTP **200/X-AniBridge-Catalog-Partial: true** and is read by Sonarr. Empty
  registry injection returns **503**, no feed items; Sonarr's command still marks
  completed, so command success cannot be treated as feed success.
- Measured peaks: API **203,567,104**, worker **39,034,880**, Sonarr
  **143,138,816 bytes**, 1-GiB API/client and 2-GiB worker/two-CPU envelopes.
  Script exits nonzero on the missed bootstrap target. v1 never reached feeds:
  the non-root worker lacked ownership of the fresh harness volume; preparing
  only its subtree as uid/gid 1000 fixed the harness, no application change.
- Context7 Sonarr retrieval did not cover RSS internals; pinned primary sources
  [HttpIndexerBase.cs](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/NzbDrone.Core/Indexers/HttpIndexerBase.cs)
  and [Torznab.cs](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/NzbDrone.Core/Indexers/Torznab/Torznab.cs)
  corroborate initial first-page exit and a hard maximum page size of 100.
  Raising advertised caps cannot solve initial pagination. **Decision question 4
  is pending**: validate/document explicit initial search/backfill, or retain
  blocked bootstrap behavior pending a client change. No criterion, feed ordering
  or page limit has been changed; full C5a remains open.

## 2026-09-30 — Startup recovery, host contracts and native packaging

- Runtime constructor now releases its owner/SQLite anchor if later component
  validation fails. Management startup retries failed recovery before claiming
  work. Frozen Linux executables are explicitly gated too: a onefile executable
  cannot launch the current Python `-m` child protocol. This applies the accepted
  Linux-container pilot/native-enforcement decision, without enabling a substitute.
- Linux source-overlay snapshot/legacy STRM subset v8 **25 pass**, including late constructor
  failure, transient startup disk error, frozen delivery after configuration
  changes, pause winning playback registration, exact-payload registration and
  token-purpose isolation for token/apikey/none. v6/v7 harness failures respectively
  used an absent test path and regenerated an already existing synthetic artifact;
  corrected harness/test fixture, no enforcement or ownership criterion changed.
- Bounded host resolution adds maintained AniWorld **5.0.6** pure Filemoon HTML/
  encrypted API and Vidoza parsing, with the same attempt byte/request/deadline/
  HTTPS/DNS limits and no quality claims from source labels. All network helpers
  stay excluded; inspected Doodstream networking disables TLS verification, and
  Streamtape/LoadX/Luluvdo are upstream stubs. Vidmoly requires delivery headers
  outside the current URL-only receipt. These remain explicit unsupported paths.
- Installed-source host/runtime/STRM/auth subset v3 **37 pass**, including actual
  parser imports in a fresh **256-MiB RLIMIT_AS** child, observed AES-GCM data,
  private decrypted URL refusal and malformed playback. Early v1/v2 selected
  absent test filenames and ran no tests. Generated contracts do not prove live
  Filemoon/Vidoza access, download or playback.
- Installed v45: worker **59**, core **41**, catalog **167 pass**; HTTP installation
  **0.220s**, API peak **152,735,744**, worker **43,298,816 bytes**.
  API `sha256:baeb9fc3b94664727174cc6fbd2f1b306a18b99cbc4e3de92525ee85e2574661`,
  worker `sha256:53da0f58b8ac9a37ac3a81601db7801dd79cafba09f0a4995b5a9d9cb6301b0f`.
  This includes the latest application changes; five later parser validation
  tests ran separately against the installed image in v3 above.
- Disposable-copy full native API v48 **274 passed /81 skipped**, **15.30s**.
  v46 failed before collection because pytest-cov metadata/entry points were
  absent; v47 **273 passed /81 skipped /one failure** showed missing installed
  AniWorld version metadata. Reinstalling only this disposable environment from
  the frozen lock restores **AniWorld 5.0.6 /pytest-cov 7.1.0** and passes v48.
  The cause of metadata loss is unestablished; no application test was weakened.
- PyInstaller **6.19.0 /hooks 2026.3 /macOS arm64** v3 clean onefile build and
  disposable loopback `/health` pass. This build predates the latest runtime/host
  refinement; latest v4 build is pending. Linux amd64/Windows/native enforcement
  remain unverified. Docs build v6 passes in **5.59s**.

## 2026-09-30 — Current-image crash and generated playback checks

- Current v45 API image rerun: `crash_activation.py` default **600 actual SIGKILL
  recoveries**, six boundaries ×100 and eight pinned readers, passes. Per-boundary
  elapsed **51.671 /58.621 /58.022 /58.547 /58.217 /60.136 seconds**. Atomic active
  revision/trust floor and saved reads recover at every case. This includes WAL
  anchor, refresh, override and current runtime source; it remains a small
  generated fixture, not 100 large updates or full C4 endurance.
- Generated MP4/HLS/Range/TLS playback v3 passes after factoring the disposable
  certificate helper, **five requests /198,127,616-byte cgroup peak**, current
  image with source overlay. Same 76,496-byte generated fixture and proof limits.
- Latest native v4 **PyInstaller 6.19.0/hooks 2026.3/macOS arm64** onefile build
  and disposable `/health` pass, including current runtime/host source. Native
  snapshot execution remains gated on every platform. No Windows or current
  Linux amd64 packaging proof.

## 2026-09-30 — Actual Sonarr STRM import and RSS rerun

- `validate-arr-strm.sh` v5 passes real Sonarr **4.0.20.3014** query/grab/durable
  **163-byte proxy STRM import**, with fixture resolver and actual disposable
  HTTPS media transport. It does **not** prove live extraction or imported-file
  decode. API/worker/Sonarr peaks **342,138,880 /39,350,272 /303,415,296 bytes**,
  using v45 application images and the previously pinned client digest.
- Unknown-only profile **rejects**: the literal `.STRM` suffix is parsed by Sonarr
  as **SDTV/480**, although the feed contains no height/codec/source assertion and
  size is 0. An explicitly named disposable profile allowing client labels
  Unknown and SDTV approves, then imports. This is client interpretation, not
  permission to assert SDTV in AniBridge. Pinned upstream
  [MediaFileExtensions.cs](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/NzbDrone.Core/MediaFiles/MediaFileExtensions.cs)
  maps `.strm` to that default. Keep this profile consequence explicit.
- v1/v2 stop at that restrictive profile; v3 completes but playback fixture used
  the normal resolver instead of its harness injection. v4 misnamed the runner's
  injected callable and never started. Correcting the fixture to `runner.execute`
  yields v5. v6 adds decode of the actual imported copy and **fails** that extra
  check; generated 601-second MP4 had tail metadata while the simple fixture HTTP
  server ignores Range. Fast-start fixture plus diagnostic rerun v7 is pending;
  imported decode is not marked passed by earlier transport/import success.
- RSS v3 repeats the measured bootstrap failure **100 /1,000** and successful
  subsequent **1,000-entry burst** with current images. Partial HTTP 200 and empty
  503 repeat, management without bearer returns **401**, queryless RSS enqueues
  **zero samples**. Peaks API **203,055,104**, worker **38,293,504**, Sonarr
  **140,779,520 bytes**. No monitored eligibility/import/deduplication proof.
  Decision 4 remains pending and the harness retains a nonzero failure exit.

- Actual imported-copy decode v7 **passes** after adding fast-start metadata to
  the STRM-only generated MP4; ordinary TV/movie fixture generation is unchanged.
  Sonarr imports the exact **163-byte** proxy file and FFmpeg decodes one second
  via its stable URL. API/worker/client peaks **216,305,664 /26,800,128 /187,695,104
  bytes**, v45 application images, same pinned Sonarr. This proves generated
  client import plus imported-copy playback, with fixture resolver/DNS/TLS; no
  live-provider, Radarr STRM or public launch claim. Earlier v6 decode failure
  remains recorded and does not become a successful experiment retroactively.

## 2026-09-30 — Current amd64 image and enforcement-environment failure

- Latest Linux amd64 API image build passes:
  `sha256:48e84d9f0cd85938ced6d8d177427d988ce280934fd52ae46805ce27def8bf27`.
  Installed core suite **41 pass**, **1.15s** under Docker Desktop Rosetta.
  Catalog suite **fails: 70 failed /102 passed**, **28.54s**, with child SIGTRAP
  failures; no resource cap was relaxed and this is not native amd64 runtime proof.
- Minimal Python-only reproduction (no AniBridge imports): initial VmSize
  **306,588 KiB**, VmRSS **23,796 KiB**; setting the unchanged **256-MiB RLIMIT_AS**
  results in exit **-5/SIGTRAP** and `rosetta error: mmap_anonymous_rw mmap failed,
  size=1000`. This identifies an emulation enforcement limitation independently
  of catalog input or application code. The exact remaining gate is **native
  Linux amd64 execution under the specified envelope**, with no such host
  available in this workspace. Windows/native enforcement also remains open.
- Context7 retrieved Docker's primary
  [known issues](https://github.com/docker/docs/blob/main/content/manuals/desktop/troubleshoot-and-support/troubleshoot/known-issues.md)
  and Rosetta settings: cross-architecture execution is best effort and consumes
  extra resources. Image construction and core test success do not override the
  observed catalog-suite failures. AMD64 worker image construction is pending.


## Evidence chronology retained on 2026-10-01

The following ledger is preserved verbatim from10 before its current-status
summary was refreshed. Current/pending statements apply to their dated point.

## Latest installed and source checks (2026-09-30)

| Gate / command or procedure | Environment | Result |
| --- | --- | --- |
| C0–C3: `bash scripts/catalog/validate-private.sh` (v60) | Installed Linux arm64 wheels/images; generated internal HTTP network | Worker **70 passed /26.91s**, core **183 /8.68s**, catalog **198 /116.02s**; installation **0.5027s**, consumer peak **152,858,624**, worker **42,303,488 bytes** |
| Full API: `uv run --frozen pytest --no-cov -o addopts='' -q` (v61) | Disposable native checkout, own DB/download paths | **284 passed /103 Linux-only skips /31.81s**; no native snapshot enforcement claim |
| Full API Linux source overlay | Disposable standalone Git copy; installed dependencies/core, validation-only image adds Git | v6 **387 passed /81.97s**; final source, installed core/dependencies; validation-only image `2929c301…` adds Git |
| Core hostile mutation investigation | SQLite 3.53.4 host and 3.46.1 installed image | Both exposed **16 rejection-test failures** before explicit row/header checks; corrected core suite passes. One later mutation needed a single-row WHERE to avoid a fixture UNIQUE failure |
| Worker process-death/writer tests | Installed Linux worker, synthetic state, 256-MiB publication children | Five publication and three crawl SIGKILL cases, transactional writer error, ownership/orphan cleanup; all included in the 70-test suite |
| Ruff and `git diff --check` | Current source/harness | Pass; final check repeated before report |
| `pnpm --prefix docs run build` | Local docs toolchain | v10 **pass /19.97s** |

Current installed image IDs (v60, including startup/shutdown writer ownership):

- API: `sha256:c423c3d5fdbaf56861bea2d181ee8d51dc7c8dfd30cec039a909e5a06e9d88c5`.
- Worker: `sha256:ae5038c6166ce4e906eb236f3747c1c8228c331bd8c0fc317d7bedfaac5ba01a`.

Dependency lock SHA-256:

- Core: `8a63698fc5bfd26d5c8575b011b84a2140efed67c5a4ae7ffece06727695d845`.
- Worker: `c3fc7c6857ac0ad4c53cd2467853b649e2388df6f76205bca498fe6f531e023e`.
- API: `b04051e9231fcfe43659331bf7e18f0d40e3b6970e581e528199afe83bb386bb`.

The initial full Linux run with network disabled failed six tests: Docker path
assumptions, a copied Git alternates path, two DNS-dependent legacy mocks and two
new STRM test isolation failures. The new tests now patch the route's actually
bound auth globals. A standalone Git copy, container-local path setup and DNS
access restore the legacy baseline and full run. No production check was used.
A root-cwd `uv --project` invocation mistakenly collected other projects and
failed collection; corrected project-cwd tests pass. Starlette deprecation and
an occasional unclosed legacy terminal-log ResourceWarning remain from baseline.

## Trust, crashes and resource experiments

- `crash_activation.py` v5, API `84096949…` / migration 0007: **600 real SIGKILL
  cases**, six boundaries ×100, eight readers; all passed. Elapsed per boundary:
  **67.644/72.523/63.076/61.957/62.363/62.559s**. These storage/receipt paths are
  unchanged by the later HTTP/scheduler offload. Tiny fixtures do not prove
  large-update endurance or every internal fsync.
- Source-switch tests retain independent floors (A rev5→B rev1→A rejects rev4),
  revoke keys with/without a trusted previous version, reject clock rollback and
  corrupt/truncated/trailing signed candidates, and preserve last-good reads.
- Read-only integrity checking missed CHECK violations; immutable PRAGMA mode
  missed actual WAL header versions. Explicit fixed row/type/range/enum/header
  checks close these admission gaps. Migration 0007 versions private receipts:
  an old invalid CHECK admission recovers previous without lowering its floor;
  a valid older receipt is fully checked once, then uses hash-verified recovery.
  Context7 SQLite retrieval and pinned upstream 3.46.1 source supplemented the
  host/container experiments. Wire schema, identity and golden bytes are unchanged.
- Transient local SQLite/OSError injection verifies poll/removal/recovery/outcome
  schedulers retry. Persisting an executor result does not run the extractor twice.
  Worker output ownership cleans only abandoned reserved build directories;
  process-shared transfer leases protect files from publisher-child cleanup.
- Actual ENOSPC v5, API `84096949…`: disposable **640-MiB tmpfs**, unchanged last-good/floor/pointer,
  update reports storage_full, fresh Store recovers with **86,016 free bytes**;
  cgroup peak **760,324,096 bytes**. Not zero-free cold boot/every disk-failure point.
- `bash scripts/catalog/validate-capacity-refresh.sh` v9, API `84096949…`: **10k titles /200k entities
  /400k releases /2 languages**, SQLite **433,373,184**, zstd **127,880,202 bytes**.
  Eight readers/100 queries; new/mapped overlay activation **17.804/26.483s**,
  saved recovery **0.249/0.449s**, p95 **168.414/372.520ms**, p99
  **171.992/393.494ms**, consumer peaks **602,914,816/602,980,352 bytes**;
  generator peak **706,654,208**. Local-file transfer only: no shaping/update-loop/
  24h proof. Receipt revalidation latency for an old large pilot is unmeasured.
- Full **50k/1m/2m** fixture: SQLite **2,169,835,520**, zstd **646,634,545 bytes**;
  exceeds **2-GiB/512-MiB maximum** caps. Limits/schema were not relaxed. Compact
  internal-join schema benchmark requires the pending material decision.
- Earlier collector capacity procedure: persisted **100k listings /40 season
  slices**, **13.116s**, DB **5,300,026 bytes**, peak **332,783,616**. This is
  synthetic checkpoint/memory evidence, not actual provider throughput/freshness.
- Final amd64 API image build (v3) passes: `sha256:58d1731e2db6ebc28f25aca5e33f0fa69959ef720542d823fce35cde6bdc6c91`. Worker v2 build
  passes: `sha256:a581972b7bfdc202b37c15d5da5696de2275ed29d06c801825b7eba1eeee24b1`.
  Emulated core v3 **183 passed /28.87s**. Earlier Rosetta catalog run **70 failed
  /102 passed**: Python alone uses **306,588-KiB VmSize** and SIGTRAPs under the
  fixed 256-MiB RLIMIT_AS. Native Linux amd64 execution is missing; emulation
  does not count as resource enforcement proof. Windows package checks are absent.
- Final native macOS arm64 onefile build (v6), PyInstaller **6.19.0**, hooks
  **2026.3**, Python **3.14.7**, macOS **27**: builds and loopback `/health` returns
  **200 / {"status":"ok"}** using disposable legacy-mode state. Snapshot/native
  enforcement remains gated. This build precedes the final three Linux recovery
  ownership joins; the legacy-mode package path is unchanged. Command: `uv run --with pyinstaller==6.19.0 --with
  pyinstaller-hooks-contrib==2026.3 pyinstaller --clean --noconfirm
  --additional-hooks-dir hooks --onefile app/main.py --name anibridge` with
  temporary dist/work/spec paths; no user installation or source artifact output.

## Real clients, generated media and live evidence

Pinned actual client versions/images used (experiments, not latest-version claims):

| Client | Version | Image digest |
| --- | --- | --- |
| Sonarr | 4.0.20.3014 | `lscr.io/linuxserver/sonarr@sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06` |
| Prowlarr | 2.6.5.5623 | `lscr.io/linuxserver/prowlarr@sha256:f2b26429893d4c4cb71941b7ee50b1bdecd9d5f9f9e02d5410615e9f4f7c8d95` |
| Radarr | 6.4.4.10685 | `lscr.io/linuxserver/radarr@sha256:adb6c09d6b729ea5e642c99cea35af72702ef476bf4763f153299ac5db9f0b4f` |

- `WITH_PROWLARR=1 bash scripts/catalog/validate-arr-tv.sh` v3 and
  `bash scripts/catalog/validate-arr-movie.sh` v8 **pass** on API `ec360023…`,
  worker `7d666dc5…`, with migration 0007 and async job/progress transactions
  (before the final startup-ownership join). Fresh registration→search→grab
  →generated **601s/320×180 H264/AAC/7,862,192-byte MKV** import; Unknown allowed
  accepts size0, HD-1080p rejects Unknown. Paused zero attempts, blocked >2 polls
  and restart, explicit retry/cancel/removal, history preservation pass. Client
  post-import SDTV/480p labels are client interpretations, not AniBridge claims.
  TV API/worker/Sonarr/Prowlarr peaks **129,683,456/27,611,136/313,970,688/
  238,706,688 bytes**; movie API/worker/Radarr **129,519,616/28,921,856/
  332,599,296 bytes**.
- `bash scripts/catalog/validate-arr-strm.sh` v9 **pass** on final API `c423c3d5…`,
  worker `ae5038c6…`: Sonarr imports the **163-byte proxy STRM**, FFmpeg decodes
  the imported copy from generated HTTPS/faststart media. Explicit test profile
  allows Unknown+Sonarr's SDTV interpretation of `.STRM`; Unknown-only rejects.
  Peaks API/worker/Sonarr **215,691,264/27,918,336/191,803,392 bytes**. Fixture proof with migration
  0007; no live provider or Radarr STRM claim.
- RSS v3 actual Sonarr: bootstrap cycles 1/2 repeat **100/1000**; later 1000-new
  burst paginates offsets0…1000 and observes all1000 new. Partial 200 header,
  empty 503 and zero RSS-triggered samples pass. No monitored-series/download
  client in that RSS experiment: eligible/no-redownload/import matrix is not
  proved. Harness retains a failure exit. Explicit bootstrap/backfill decision
  is pending; criterion/feed ordering remains unchanged.
- Earlier generated MP4/HLS/Range/TLS playback: five requests, consumer peak
  **198,127,616 bytes**, FFmpeg **7.1.5-0+deb13u1**; alias/output removal and job
  reconstruction covered. Separate from mocked transports and live playback.
- Only authorized AniWorld episode: bounded local extraction/download/remux/probe
  v8 **passed /125.256s**, output **203,921,375 bytes**, observed **1280×720 H264/AAC**,
  peak **566,071,296**. Media removed. No canonical alignment/client import/playback
  claim. Exact s.to episode fails Docker DNS before HTTP; authorized megakino
  film6444 returns a 250-byte script stub, no usable metadata/offers. Replacement
  authorized movie input and TMDb credential/source permissions are absent.

## Operational limits and remaining review

Use fresh pilot volumes. Mainline backup is `.pre-catalog-v3.backup`; worker
ledger backup `.pre-v2.backup`. Keep private DB and its WAL/SHM plus catalog volume
consistent. Rollback uses a stopped copy and matching binary, not destructive
in-place downgrade. Hard links and advisory locks are required. Secret rotation
controls imported proxy STRM access. Incomplete historical requests may protect
the entire download tree from TTL cleanup until deliberately reconciled.

Still unverified: complete mutation/inner-crash/ENOSPC inventories; large retained
job/correction histories (some recovery/retention projections still materialize
history); all-provider canonical/mapped series/special/live flows; scope-estimate
versus actual-quality disagreements in clients; legal real-provider freshness;
100 shaped updates/24h RSS/FD stability; native Linux amd64 and Windows packaging;
public redistribution/key custody/90-day overlap/quota/operating cost. Worker
collection currently runs one persisted page per turn serially across providers;
configured concurrency/ready-queue/batch ceilings are not a proven fixed-pool
pipeline or throughput/freshness result. Do not
present the passed subsets as complete C0–C6 or milestone exit gates.

Final HTTP concurrency audit: actual SQLite writer locks exposed synchronous
transactions in async routes/background work. Grab/management writes and job,
update-status, quality and progress transactions now run outside the event loop.
Seven lock/cancellation cases and a startup-owner test are included in the
catalog suite; unrelated
HTTP must complete within 500 ms. Cancelled background writers are joined before
shutdown recovery; startup retains its process lock until recovery exits.
The first startup test rerun **1 failed /15 passed** had already loaded an
incorrect expected exception type before its correction; the corrected installed
case passes. The initial focused scheduler rerun had **1 failed /61 passed** because
an existing test asserted in-memory cleanup at the instant a threaded commit
became visible; it now awaits both durable state and scheduler cleanup under
the unchanged four-second deadline, retaining no-reexecution/no-leak assertions.

QA workflow now includes an installed Linux contract job and worker/core/harness
path triggers. It was exercised locally; GitHub CI was not dispatched or proved.
User/deployment/env and agent guidance describe the opt-in Linux pilot and gaps.

Final requirement review and suggested Conventional Commit boundaries are in
[12-implementation-review.md](12-implementation-review.md). All experiments
removed their own containers/networks/volumes; local test images and private
temporary validation checkouts are retained. No unrelated Docker state was removed.

## Authorized continuation (2026-09-30)

The maintainer authorized local commits, a measured compact internal-key schema
with explicit compatibility, and an evidence-based RSS workflow revision. Caps,
cardinality, public identities and released-mainline state remain unchanged.
The original failed capacity/bootstrap measurements above remain failed.
HTTPS Serienstream alternatives and the supplied megakino Paddington page are
authorized for bounded metadata investigation; the latter is not media permission.
No *arr control service, stored client credentials, new backfill API or automatic
library-wide search is authorized. Native amd64/Windows and M5 remain gated.

Initial diff audit: 213 task-owned changed/new files, 1,558,688 bytes; all Python
files parsed, no binary/artifact paths or credential-shaped literals found.
Ignored virtual environments/build caches/data were excluded. Intermediate trees
are exported from the Git index into separate temporary directories; no stash,
history rewrite or real installation is used.

| Local commit / focused verification | Result |
| --- | --- |
| `f0aa2a4` shared contracts | Staged-tree wheel build, clean frozen sync and installed-wheel suite: **183 passed /1.33s**, macOS arm64. This is contract/package proof, not native resource enforcement. |
| `9b41c24` worker | Staged-tree Linux arm64 image build, installed worker tests under 2 GiB/2 CPUs: **70 passed /13.04s**. |
| `7dcbb64` consumer/lifecycle/management/migrations | Staged-tree Linux API image build, focused catalog/migration/STRM auth under 1 GiB/2 CPUs: **219 passed /45.71s**. Interdependent API components are kept together so the intermediate tree builds. |

`5d0f537` adds the disposable harnesses and QA entry point.
`bash scripts/catalog/validate-private.sh` on this unchanged source passed worker
**70 /15.45s**, core **183 /5.22s**, consumer **198 /46.68s**. Synthetic HTTP
installation took **0.2922s**, consumer/worker cgroup peaks **155,549,696 /42,524,672
bytes**. Images: API `sha256:ff8b75b89b501704e46c98fb25d3070be3e257fd8c459b42156c0beb267886f8`,
worker `sha256:80956f1364e68e7437d0f8bac0067178f851fe0269d058bc9adefd705b1ef29e`
(Linux arm64). Raw disposable log: `/tmp/anibridge-commit-installed.log`.
Documentation is recorded in the following local commit; see local Git history.
These commits record unfinished private work, not a completed milestone.

## Provider alternative investigation (2026-09-30)

C2/C5b bounded Docker procedure: resolve the named origin, require exclusively
global answers, pin the IP with original Host/TLS SNI, verified certificates,
`trust_env=False`, no redirects followed across origins, identity encoding,
2-MiB body ceiling and 15-second request timeout. GET only the supplied episode
path on each Serienstream alternative and supplied film5270 path on megakino;
no host requests or media download. API image `ff8b75b8…`, Linux arm64,
512-MiB/2-CPU disposable containers; private logs
`/tmp/anibridge-provider-alternatives-v1.log`.

- `https://serienstream.to` and `https://serienstream.cx`: DNS succeeds (one
  public answer each), verified TLS/HTTP200, **192,043 bytes**, no detected
  challenge. The initial parser rejected unrelated `/serienkalender` navigation
  as pagination. Its episode title also disappeared after help headings. Scope
  pagination to real path/query boundaries and preserve positively observed
  English episode headings; conflicting episode headings still reject.
- Targeted installed worker/parser overlay tests: **35 passed /2.12s**. A repeated
  bounded GET of the authorized s.to episode with corrected parser succeeds.
  This proves observed metadata parsing, not canonical episode correspondence,
  local host extraction, media rights, import or playback.
- `https://megakino21.com/films/5270-paddington-in-peru.html`: DNS succeeds
  (four global answers), verified TLS/HTTP200, **256-byte script stub**; metadata
  parser rejects and local offer count is zero. No HTTP/IP downgrade was tried.
- Supplied TMDb credential files are external to the repository, read-only in
  disposable containers, restricted to mode0600 and never printed. Two bounded
  verified-TLS TMDb requests confirm search/detail availability: movie516729,
  IMDb tt5822536, release2024-11-08. **No provider association was emitted**: the
  provider page lacks observed title/year/ID evidence. The first connectivity
  harness incorrectly used manifest integer-only JSON decoding on TMDb floats;
  its correction uses the same ordinary JSON decoding as the worker. This was a
  harness failure, not a product parser change. No redistribution is cleared.

Worker/API private examples now configure matching named HTTPS origins. Existing
legacy application defaults are preserved. Original s.to DNS and megakino6444
failures remain in the history; the new observations do not relabel them.

## Compact artifact schema2 (2026-09-30)

Authorization: compact internal storage only, unchanged public identities and
unchanged caps/cardinality. Schema2 has explicit signed/header/catalog version2;
exact schema1 remains readable. Worker private state2 retains the schema1 record
tables. Validator receipt version3 rechecks older receipts. Golden fixtures for
both layouts, hidden-row/view/index/type attacks, nonempty aliases and renamed
paths are executable. No released-mainline state is replaced or discarded.

Procedure: `scripts/catalog/compact_capacity.py --source <original generated
C4 directory> --destination <new disposable directory> --writer`, installed
Linux arm64 worker image with source overlay, 2 GiB/2 CPUs. Inputs are the
**identical** original 10k/200k/400k and 50k/1m/2m fixtures; two languages.
Read-only synthetic-key/hash/DDL preflight; every logical table is sorted,
stream-hashed and compared row-for-row. `dbstat` attributes table/index bytes.
These are generated records, not scraped catalogs or representative live data.

| Layout/design | 10k SQLite / zstd bytes | 50k SQLite / zstd bytes | Selection |
| --- | ---: | ---: | --- |
| Original schema1 | 433,373,184 /127,880,202 | 2,169,835,520 /646,634,545 | Historical maximum-cap failure remains failed |
| Integer keys, sparse identical paths, consolidated episode index | 215,093,248 /52,132,614 | 1,078,120,448 /263,905,522 | Misses default SQLite cap by 4,378,624 bytes |
| Release table WITHOUT ROWID | 210,726,912 /60,887,835 | 1,060,417,536 /308,713,586 | Rejected: worse compression exceeds default cap |
| Selected schema2: episode associations WITHOUT ROWID | 211,898,368 /50,332,426 | **1,061,736,448 /254,698,159** | Both default byte caps satisfied |

Original full release table/index group contributed about849 MB and episode
mapping group about596 MB. Integer relationships remove repeated digests; fixed
read views retain original records. Sparse current paths preserve renames;
unique expression indexes preserve path uniqueness. The episode compound PK
uses its own storage tree, and the unique entity/mapping index also serves
lookup. Public digest columns remain canonical hexadecimal TEXT.

Selected export/compress/total streaming comparison costs: 10k
**44.578 /1.408 /56.545s**, worker cgroup peak **640,634,880 bytes**;
50k **498.294 /19.334 /637.993s**, peak **2,147,483,648 bytes**. Full variants
ran in separate capped containers with overlapping disk activity: these times
are measured comparison costs, **not isolated production publisher throughput**.
No OOM observed; reaching the worker cap establishes no headroom. Actual full
publisher deadline/cost and update endurance remain unverified.

Regression investigations and results:

- Initial schema2 RSS joins materialized all canonical views; smaller capacity
  queries hit the fixed two-second budget. Indexed physical canonical LEFT JOINs
  fix this without changing records or limits.
- Attached observation wrappers initially read the private database's pragma
  instead of the leased artifact schema, failing two refresh tests. Carry the
  artifact version across attachment. `local_entities` uses an indexed physical
  lookup to avoid materializing the entire entity view.
- An ordered release index was incorrectly forced for targeted correction
  queries; restrict that hint to recent RSS. Do not scan every release for an ID.
- Redundant per-character digest checks dominated validation. Canonical digest
  validation already proves ASCII/length/controls; retain it once. Keep all
  other string, type, FK, identity and semantic checks. No deadline increased.
- `bash scripts/catalog/validate-private.sh`, installed-image run v3:
  worker **71 passed /18.89s**, core **210 /5.28s**, consumer **203 /76.86s**;
  synthetic HTTP install **0.351s**, consumer/worker peaks
  **152,428,544 /42,430,464 bytes**. API image
  `sha256:cfa4971408b576ee92131f1e14c1979654743b6f529694d06594290e666bfd1a`,
  worker `sha256:fdd00b102cec3369fa70ea10d19ffefa7ce53e19120cd2ebe90003acaee8e068`.
  This run precedes the final local-observation count optimization; targeted
  source-overlay checks cover subsequent changes. v2 had two refresh failures;
  do not relabel that earlier run as passing.
- `capacity.py consume` on selected10k, no overlay: activation **46.996s**,
  saved recovery **0.314s**, eight-reader query p95/p99 **146.61/160.04ms**,
  peak **427,732,992 bytes**. Corrected mapped overlay10k: activation **12.406s**,
  recovery **0.145s**, p95/p99 **213.65/270.04ms**, peak **425,504,768 bytes**.
- Selected50k, no overlay: activation **79.428s**, recovery **1.405s**,
  eight-reader p95/p99 **78.40/87.28ms**, peak **1,073,741,824 bytes**. This
  measured run meets those targets but leaves no measured memory headroom.
- Selected50k mapped overlay v5: activation **110.330s**, recovery **4.771s**,
  p95/p99 **610.42/621.34ms**, peak **1,073,741,824 bytes**: **failed p95**.
  Following v6 cold activation hit the unchanged120s validation deadline.
  Local-observation counting is being refined; these failures remain recorded.

Raw synthetic logs remain disposable under `/tmp/anibridge-compact-*`.
Byte-size success is not full C4: shaped transfer, concurrent activation/update,
100 updates, scheduler/freshness, FD/RSS endurance and representative legal
catalog cardinality still require evidence. M0–M4 remain incomplete.

Latest schema2 focused source-overlay refresh/correction/snapshot/query matrix:
**51 passed /64.60s** under 1 GiB/2 CPUs. Native core after anchor digest reuse:
**210 passed /2.04s**; a cold validator profile failed at120s after initial
integrity/storage/FK checks **57.048s**, title4.569s, alias0.858s, entity53.635s;
only370,214 release rows had been checked. The duplicate anchor parsing is now
removed only after canonical-path validation, using the unchanged v1 digest
recipe. Cold validation and full-overlay remeasurement remain required.

## 2026-09-30 — Full compact overlay remeasurement

`capacity_consumer.py` selected schema2 50k-title/1m-entity/2m-release mapped
fixture v7, Linux arm64 source overlay, 1 GiB/two CPUs/eight readers: activation
**115.074s**, saved recovery **2.138s**, local-query p95/p99 **0.375925/0.398347s**,
cgroup peak **1,073,741,824 bytes**. These checks pass after avoiding repeated
anchor parsing and full overlay count scans. Earlier latency/deadline failures
remain failed. Cold validation and memory have little headroom. Local-file input
is not shaped transfer, 100 updates, actual full publisher or 24-hour C4 proof.

## 2026-09-30 — Normal pinned-client RSS workflows

Procedure: `bash scripts/catalog/validate-arr-rss-workflow.sh`, v6; fresh owned
Docker volumes/network, Linux arm64, API/client 1 GiB, worker 2 GiB, two CPUs.
API image `sha256:cfa4971408b576ee92131f1e14c1979654743b6f529694d06594290e666bfd1a`,
worker `sha256:fdd00b102cec3369fa70ea10d19ffefa7ce53e19120cd2ebe90003acaee8e068`,
with current API/core source overlays. Sonarr **4.0.20.3014** digest
`sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`;
Radarr **6.4.4.10685** digest
`sha256:adb6c09d6b729ea5e642c99cea35af72702ef476bf4763f153299ac5db9f0b4f`.

Both clients pass: initial RSS sees 100 entries, creates **zero jobs**;
explicit normal `EpisodeSearch`/`MoviesSearch` finds monitored historical content
outside that page, unknown size 0 approved; a new 1,000-entry tied-second burst
pages through offset 1000 and accepts the eligible target. Empty-catalog 503
preserves cursor; catch-up after the client's actual **58.54/58.51s** backoff
covers the next 1,000 entries. Controlled first-seen timestamps create a
**23-hour cursor gap**, not 23 hours of wall-time/endurance. Repeated cycles and
actual API/client restart preserve the same **three paused jobs, zero attempts**.
RSS quality enqueues **zero**; unauthenticated management remains 401. Synthetic
reviewed canonical associations prove client behavior, not real provider mapping.
No extraction, import or playback occurs in this experiment.

Cgroup peaks printed after restart describe only that interval: Sonarr
API/worker/client **131584000/47214592/128323584**, Radarr
**131674112/53575680/123711488 bytes**; not whole-run peaks.
Earlier v1/v2 immediate catch-up/status-endpoint harness failures, v3 Radarr
fixture missing IMDb association and v4/v5 narrower successful experiments are
not relabelled as the v6 result. Original exhaustive bootstrap **100/1000**
remains failed in 11 and `validate-arr-rss.sh`. The approved criterion revision
uses pinned primary source plus this real-client workflow. Broader C5a still
requires activation/pagination and estimate disagreement/failure evidence.

## 2026-09-30 — Executable worker pipeline

Replaced serial CLI orchestration with fixed per-provider producers, global
fetch/parser and ready-result reservations, one acknowledged SQLite writer and
independent maintenance. One listing request/provider; other slots claim durable
details. Queue pressure blocks reservation, including parsed results awaiting put.
Page slices count redirect starts and cumulative HTTP/parser/queue/writer time;
large titles resume at durable page boundaries. Listing buffers are configured
100-row batches within atomic checkpoint transactions. One publication globally
fences its provider, preserving dirty observations while other providers progress.

Linux arm64 worker image `fdd00b1...` with current worker/core source overlays,
2 GiB/two CPUs: full worker suite **77 pass /40.48s** before final cumulative
writer-deadline refinement; focused pipeline/CLI/HTTP tests **11 pass /14.72s**
after that refinement. Final failure/deadline bookkeeping receives an additional
focused run below. Injected slow provider, writer failure, queue size 1/32,
redirect limit, cancellation and concurrent real parser children pass. A failed
writer leaves its unadmitted durable lease recoverable after expiry.

`pipeline_capacity.py` generated **100,000 titles for each of three providers**,
maximum-size supervised listing parsers concurrently: **13.697s**, max fetching
**3**, max ready **2**, cgroup peak **911,314,944 bytes** in the same envelope.
This run precedes the cumulative writer-deadline refinement. Generated transport
injection measures parsing/admission resources; no HTTP/provider/publication or
24-hour/freshness proof. Full freshness/backlog and concurrent artifact-building
resource measurements remain open; no caps or cardinality were raised/reduced.

Final pipeline-focused v3 **6 pass /2.99s**, same Linux overlay/envelope, includes
the cumulative deadline and failure bookkeeping. Full installed rebuild follows
with the next application increment; this source-overlay proof is not a new image.

## 2026-09-30 — Bounded durable history and current installed checks

Recovery reads 100-job keyset batches and checks completed files without loading
history; missing-output updates guard against racing cancellation. TTL ownership
streams into an automatically deleted SQLite spool (2-MiB cache) with indexed
ancestor checks, preserving conservative unprovable legacy ownership. qBittorrent
info/sync stream the existing JSON shapes through bounded alias/projection and
encoding buffers. Removal creates at most 100-alias durable intents; final-alias
checks use indexed existence queries, not full sets. Existing legacy projections
and all hashes/outputs remain visible; no history cap or destructive migration.

Linux arm64 API image/source-overlay focused history/job/runtime/STRM/concurrency
and legacy qBittorrent tests v4 **62 pass /15.06s**. v2 eight integration setup
errors came from mounting tests too shallowly for conftest's repository-root
lookup; v3 **61 pass/one failure** was an incorrect fixture expectation for the
cloned legacy alias's existing `paused` label. Correcting that expectation
preserves its released projection; no application assertion was removed.
`history_capacity.py`, 1 GiB/two CPUs, generated 10k/50k jobs and aliases:
recovery **0.365/1.257s**, guard **0.009/0.025s**, complete JSON encoding
**0.367/1.624s**, bytes **3893201/19466001**, max chunk **33150 bytes**,
cgroup peaks **148987904/202051584 bytes**. No history was omitted. This is
encoding/recovery proof, not HTTP-client memory or 24-hour stability.

`bash scripts/catalog/validate-private.sh` installed v4 passes worker/core/API
catalog suites and fixture HTTP install **0.4295s**, API peak **152133632**,
worker **42450944 bytes**. Images Linux arm64:
worker `sha256:c23b93ad818fc49810a651eb602d25a1287b698c48c7f5cc01568a40dd0a0ae7`,
API `sha256:8f8d632517cbe0b42892c85f6ea7d6f08a2ca69077feb50f6f2d33042dfb23c9`.
These include pipeline/history changes, not the subsequent bulk-export work.
Final counts and real-client streaming rerun follow below.

Installed v4 counts: worker **77 pass /20.17s**, core **210 pass /5.90s**,
API catalog **207 pass /65.00s**.

## 2026-09-30 — Prepared native CI and streaming client rerun

QA now prepares native `ubuntu-24.04` amd64 and `ubuntu-24.04-arm` container
checks with an architecture assertion, plus legacy frozen-package health on
Linux/macOS/Windows using **PyInstaller 6.19.0 /hooks 2026.3 /Python 3.14**.
Context7 primary GitHub runner documentation was consulted. YAML/job inventory,
Python syntax and Ruff checks pass locally. No workflow was dispatched or pushed;
no paid/remote resources were provisioned. Native Linux amd64/Windows execution
and native snapshot enforcement remain blocked by missing local environments.
`frozen_smoke.py` passes on the existing macOS arm64 v6 binary in **8.151s**,
with disposable loopback state. That binary predates the latest changes; this
checks the new harness and legacy packaging, not latest frozen feature coverage.

`validate-arr-rss-workflow.sh` v7 repeats both pinned clients after streamed
qBittorrent responses: historical search, burst, normal backoff (**58.50/55.35s**),
23-hour controlled cursor catch-up and actual client/API restart all pass with
three unchanged paused jobs/zero attempts/zero RSS sample enqueues. Same client
digests as v6; installed application images `c23b93a...` / `8f8d632...` plus API/core
overlays. No import/playback or long-outage/endurance proof is added.

## 2026-09-30 — Complete state selection and later migration interruptions

`test_migrations.py` now covers **seven interrupted states** (queued/resolving/
downloading/retry_wait/paused/blocked/cancelling) and **three terminal states**
(cancelled/failed/completed) across released 0001/0002/0003. Original bytes,
paths, aliases and retained backups remain preserved; interrupted state is
recorded as prior_state and becomes an explicit incomplete-request failure.
Legacy admission scans use 100-row keyset batches before mutating selections,
avoiding history-wide allocation and SQLite's undefined open-cursor mutation
visibility. Existing schema/backup/STRM/file/collision/rollback tests remain.

Linux arm64 API source overlay, 1 GiB/two CPUs, migration v2 **14 pass /27.35s**.
Actual SIGKILL boundaries now span 0004 catalog source/request/cache, 0005 control,
0006 override index and 0007 receipt ALTER. Each restores the original 0003
transaction and resumes; no real installation or PR #119 compatibility is used.
This closes that selected all-state/revision/later-DDL subset; full C6 still
requires the remaining exact unversioned/backup/fsync/interruption inventory.

## 2026-09-30 — Concurrent provider block preservation

An already-in-flight successful listing/detail response could overwrite a
concurrent challenge's provider-wide `blocked` label. Positive facts now retain
the active cooldown; details also preserve parser/clock/storage failures until
the appropriate recovery path. Discovery times and last-good facts remain intact.
Linux arm64 worker/core source overlays on installed image `c23b93a...`,
2 GiB/two CPUs: focused worker/pipeline/export v1 **35 pass /38.55s**, including
challenge → positive sibling → cooldown expiry. This is a regression check,
not complete scheduler/freshness or live-provider proof.

## 2026-10-01 — Mainline backup durability and exact unversioned data

The released-state matrix now includes the exact 0003 schema without its version
table, with all seven interrupted/three terminal states and retained aliases,
bytes and paths. Four actual SIGKILL tests cover verified backup copy, file
fsync, hard-link publication and directory fsync. Two injected sync failures
refuse migration; restart preserves an already-published backup. These augment
the six later-DDL interruptions, original file/STRM/hash/collision/restore,
foreign-schema rejection and exclusive ownership checks.

Linux arm64 API image `8f8d632...` plus source overlays, 1 GiB/two CPUs:
`pytest tests/unit/db/test_migrations.py tests/unit/db/test_migration_backups.py
-o addopts='' -q` **20 pass /25.98s**. Complete API tests on a disposable tracked
source copy with Git and matching source-tree DATA_DIR/DOWNLOAD_DIR: **402 pass,
exit 0** (v4; elapsed not recorded). Flat-image v3 **394 pass/two failures** was
an unsuitable environment for existing repository-path/Git tests, not an
application regression. v4 emits database-close warnings, including test
fixtures and core in-memory schema definitions; ownership is being audited.
No user database, production state or external release action was accessed.
The tested C6 matrix passes; untested inner SQLite/VFS crash boundaries remain
outside this named subset rather than a claim of exhaustive fault coverage.

## 2026-10-01 — Full shaped install and bounded validation

`validate-shaped-capacity.sh /tmp/anibridge-compact-50k-v5` v2 and v3 **failed**
the unchanged 120-second validation child deadline after completing transfer.
v3 had the ASCII path optimization alone. Profile v8 failed at120s: physical
checks11.404s, integrity through50.408s, foreign keys through62.086s,
entity rows16.938s, release rows27.849s; canonical episode checks were unfinished.
These were overlapping diagnostics, not isolated before/after benchmarks.

Core now proves canonical safe ASCII paths without repeated URL parsing and
checks every schema2 FK via its ordered covering index/primary-key parent.
Exact DDL inventory and SQLite-oracle hostile missing-parent tests pass;
integrity/storage/all logical/semantic checks remain required. In-memory schema
inspection connections now close explicitly. Native core **247 pass /6.59s**;
profile v9 completes full identical 50k validation in **114.641s** while other
small tests ran. No cap/deadline/schema/receipt version changed.

Shaped v4 **passes**: actual Linux TBF **10 Mbit/s**, generated signed unchanged
50k/1m/2m artifact **1061736448 SQLite /254698159 compressed bytes**, consumer
1 GiB/two CPUs, eight readers, fresh owned Docker network/volume, no host ports.
Install **281.548s**, saved recovery **1.984s**, query p95/p99
**0.052462/0.087246s**, cgroup peak **1073741824 bytes**, no OOM.
Source uses **iproute2 6.15.0 /libbpf1.5.0** with `NET_ADMIN` only for its private
egress qdisc; API image `8f8d632...` plus current API/core overlays. The actual
full cold-install subset passes; 100 updates/24h/freshness remain open. A source
overlay is not a rebuilt package. Context7 and primary SQLite FK/INDEXED BY
documentation informed profiling; the executable DDL/oracle, not docs alone,
proves the fixed relationship coverage.

Final Linux core overlay v2 **247 pass /5.55s** on SQLite3.46.1, 1 GiB/two CPUs.
Shaped source image `sha256:6d62fa622908d407eb8400691f5c6197bc75ecbb458e5fe570de1ccf2c252ce5`,
Linux arm64; source cgroup peak **293236736 bytes**, TBF sent **266310295 bytes**,
zero dropped packets. This source digest includes only the private shaper tools;
the fixture/catalog remains a read-only mount and is not baked into the image.

## 2026-10-01 — Active priority and single half-open probe

Two focused failures exposed scheduler behavior: older historical due work won
ordinary slots ahead of overdue active work, and both producers could probe a
cooled-down provider simultaneously. New/active/historical selections now follow
the specified priority; the persisted fifth-slot reservation survives restart.
Page leases use the configured cumulative slice deadline, preventing a second
claim at120s when a permitted 300s slice is still running. Half-open probes
reserve the durable provider cooldown deadline; only their exact positive
observation can clear it, never a later challenge. No schema change is needed.

Native scheduler/worker checks **25 pass /2.68s**, then circuit subset
**27 pass /2.32s**. Linux arm64 installed worker `c23b93a...` with current
worker/core overlays, 2 GiB/two CPUs: worker/scheduler/circuit/pipeline/HTTP
v3 **37 pass /12.91s**, including positive-probe/later-block CAS protection.
The before-change regression logs remain failed (**1 fail/1 pass** priority,
**1 fail/1 pass** half-open). These checks establish dispatch/circuit behavior;
full steady-backlog freshness and live-provider freshness remain open.

Circuit transport v4 **4 pass /1.69s**, same Linux overlay/envelope: the half-open
probe executes rate admission and a real supervised parser, while a sibling
cannot reserve another page. This supplements state/application checks; injected
generated transport still does not establish live provider access.

## 2026-10-01 — Pinned experimental schema rejection

Generated a **DDL-only** golden fixture by applying PR119's five experimental
revisions to a disposable released 0003 database. Source is local pinned
`61351bbcbfc1295ab597f8385f063598c25f3191`; final revision `20260625_0008`,
101 schema objects, no user/catalog/media rows. Those migrations are not copied
into the application or supported upgrade path. The isolated fixture proves
both versioned and unstamped actual experimental layouts reject before changes
or backup publication. Linux arm64 API source-tree image/overlay, 1 GiB/two CPUs:
`pytest tests/unit/db/test_foreign_migration_schema.py -o addopts='' -q`
v1 **2 pass /1.77s**. Existing unknown-schema checks
remain separate. PR119 database compatibility is explicitly unsupported.

## 2026-10-01 — Full-size bounded SQL publication and installed checks

`publisher_capacity.py --source <signed-generated-v1-dir> --root /tmp/run`
constructs a fresh synthetic ledger and invokes the actual supervised publisher,
worker 2 GiB/two CPUs, unchanged 256-MiB child address limit. Fixture construction
is not migration proof. All seven logical table counts and streamed hashes match
original signed rows, including public IDs, discovery times and provenance.
Full cardinality remains 50k/1m/2m; modest 10k/200k/400k. Only `synthetic-v1`
provenance is approved here; configured metadata credentials alone grant no rights.

Bulk INSERT/SELECT uses a read-only attached ledger and fixed pager budgets.
Secondary indexes rebuild before full independent validation; `release_recent`
stays live to interleave duplicate IDs inside the zstd window. Deferring it too
produced **323273813 compressed bytes**, failing the unchanged 256-MiB cap.
Selected full layout is **1050562560 SQLite /257838610 compressed bytes**,
within unchanged caps. `publication_sources` is a bounded explicit allowlist,
empty by default. No real source approval is inferred from these tests.

Failed diagnostics remain failed: v1/v3 timed out at180s; diagnostic v4 rejected
323-MB compression; v5 fit caps but validation interrupted at120s (total297.383s).
Runs overlapped other I/O and are not isolated before/after benchmarks. Diagnostic
v6 completed in213.709s with a360s supervisor. Measured full cost justified finite
production publication deadline180→360s, below1800s cadence; resource/artifact/
validator limits and cardinalities remain unchanged.

Production v7 **passes /195.564s**, separate logical comparison69.257s,
publisher RSS182968320/cgroup2147483648 bytes, no OOM. Repetition v10 to retain
verified synthetic publication for consumer tests **passes /138.280s**,
comparison/copy94.767s, RSS165593088, same artifact hashes. Modest instrumented
v9 **passes /14.078s**, comparison9.841s, SQLite209715200/zstd50691633 bytes,
RSS194936832/cgroup1389490176, stage FDs9–10. These are individual runs, not
24h trends. Another modest attempt never started because Docker was unavailable;
restarting local Docker restored execution, cause not attributed to application.

Actual bulk artifact consumer v11: `capacity.py consume --root /fixture
--local-refresh --refresh-case mapped`, 1 GiB/two CPUs/eight readers, full mapped
overlay **passes** activation56.185s, saved recovery1.020s, p50/p95/p99
**0.206757/0.271314/0.282084s**, cgroup1073741824 bytes. Local-file installation
is separate from the shaped Writer-fixture experiment above. No update/endurance
or live-provider proof is inferred.

CLI captures wall time after publication admission, preventing false rollback
refusal during another provider's build. Regression advances time400s during
admission; CLI/export v12 **11 pass /1.74s**. Renewal/export v6 **8 pass /0.49s**:
blocked renewal keeps bytes/facts/discovery times/block state, advancing only
signed revision/publication/expiry. Synthetic artifacts and raw logs stay outside Git.

`bash scripts/catalog/validate-private.sh` installed v5 Linux arm64 **passes**:
worker **94 /16.07s**, core **247 /4.56s**, API catalog **207 /46.57s**;
synthetic HTTP install0.3208s, consumer152354816/worker42295296 peak bytes.
Worker `sha256:1fb34e7e0890c001f8b89293aacde475c1a0b91c46e3bfee27970a5c32704311`;
API `sha256:7a5d20c0301adddf1280c27eb13fda5ad4598c28b0077d4cbef5bbc8e5a7ed4f`.
No real client/provider/import/playback claim. C4 steady-backlog freshness,
100 updates/24h remain open; native amd64/Windows and live C5b remain blocked.

Focused native export/CLI checks **10 pass/one Linux-only skip /0.35s**;
the corresponding real CLI case passes in installed Linux v5 above. Docs build
`pnpm --prefix docs run build` v13 **passes /5.22s**; Ruff/diff checks pass.

## 2026-10-01 — Worker backup refusal and no-overwrite recovery

The worker previously skipped validation of any existing `.pre-v2.backup` and
published with replacing rename. Six new refusal/race regressions initially
**failed /0.48s** (seven older checks passed). It now requires a regular,
non-symlink recognized version1/provider backup, validates a new SQLite backup
before sync, and atomically hard-links without replacing a competing copy.
A competing invalid backup refuses upgrade unchanged. No API/private artifact
schema or released-mainline compatibility changed.

`uv run --frozen pytest tests/test_state_migrations.py -q`: native **19 pass
/0.91s**, including four actual SIGKILL backup boundaries and two sync failures.
Linux installed worker v6,2 GiB/two CPUs: complete worker **106 pass /15.98s**;
image `sha256:b700df2bb3e2025ce0ef601396cce97b94fc392188d7f91414df1f6914e55de9`.
Earlier Linux focused before backup crash additions **13 pass /1.38s**.
Only disposable worker state was used; no user installation or live requests.

## 2026-10-01 — Full checked backlog and request-capacity contradiction

`scheduler_capacity.py --source <signed-generated-50k-v1-dir> --root /tmp/run
--claims 5`, installed worker `b700df2...`, Linux arm64/2 GiB/two CPUs,
generated already-checked active state after bootstrap: 50k titles/1m entities,
**1050000 work pages**. Actual `State.claim` selections measured
**0.714/0.684/0.691/0.668/1.119s**, cgroup peak2147483648 bytes. Actual durable
rate admission over a controlled four-hour clock window accepts **4800** starts
and refuses9600 intervening starts. No listings/retries/parsing/mapping cost is
charged, making this an optimistic necessary bound, not an end-to-end simulation.

Even that bound leaves **1045200 pages unvisited**; one sweep needs at least
**875 hours** at1200/hour. The full-active six-hour freshness target therefore
fails this permitted workload independently of parser speed. No cardinality,
rate cap or criterion was weakened. A maintainer question offers bounded
recent-change-signal investigation (recommended) versus a capacity-qualified
product promise. Until answered/validated, C4 freshness stays failed. This
harness performs no HTTP and proves neither live source signals nor24h stability.

## 2026-10-01 — RSS activation and estimate failure regressions

`validate-arr-rss-workflow.sh` v8 **failed in the harness**: the activation
trigger compared `new-burst` with actual cycle labels `new-burst-0`; no snapshot
change occurred and the1050 assertion failed. Corrected v9 passes both clients,
but its count lower bound could include older Radarr entries. v10 strengthens
coverage to the exact1050 expected new GUIDs during activation and exact1000
catch-up GUIDs. This is a meaningful assertion change, warranting the rerun.
Final client results follow below; v8 is not relabelled as application success.

Controlled publication inserts50 releases and edits metadata after the first
RSS page. Existing public IDs/discovery times stay fixed. The first response
uses the prior snapshot; later pages/cycles use the activated one. No API or
client production backfill/control service is introduced; orchestration lives
only in the disposable harness. Original exhaustive-bootstrap failure remains.

Linux arm64 API image `7a5d20c...`/source overlay,1 GiB/two CPUs:
`pytest tests/unit/catalog/test_sampling.py tests/unit/catalog/test_quality.py
tests/unit/catalog/test_local_media.py::test_local_probe_rejects_playlist_references
-o addopts='' -q` v8 **17 pass /9.69s**. Actual downloaded1080p/HEVC evidence
replaces inherited720p; codecs remain exact-entity only, size0/GUID unchanged.
Real supervised hung process/group stops within5s+2s, budget/temp directory
released and unknown evidence cached. Private/HTTP resolved URLs are rejected
before transport; hostile HLS key/segment references never reach ffprobe. These
network bodies/resolvers are generated/injected contracts, not live host proof.
Earlier quality-only v7 **11 pass /12.44s** includes actual hung-child cleanup.

Final v10 **passes** for Sonarr4.0.20.3014 (`f247545...`) and Radarr6.4.4.10685
(`adb6c09...`): exact1050 new GUIDs during activation, **zero missing**; exact1000
catch-up GUIDs; historical target approved at size0, unmonitored bootstrap0 jobs,
three monitored paused jobs, zero attempts/RSS sample enqueues, unchanged hashes
after actual API/client restart. Normal indexer backoff **58.11/58.26s** remains.
API/worker/client cgroup peaks Sonarr **131674112/61407232/133500928**,
Radarr **131678208/59576320/131018752 bytes**. Application images7a5d20c/b700df2
plus current API/core overlays; generated associations, no media/import/playback.
The named RSS activation/client subset passes; no universal C5a/24h/live claim.

Context7 could not establish provider update-signal contracts; its AniBridge
reference describes historical search routes, not recent-change completeness.
Read-only installed upstream **aniworld5.0.6**, `aniworld/search.py:363` offers
`fetch_new_episodes` for `/neue-episoden`; its global-session transport is not
suitable for worker reuse. This is a candidate source signal only, not a live
probe, language/completeness guarantee or implemented solution. Freshness decision
remains pending; rates/target unchanged.

## 2026-10-01 — Conservative conflicting quality evidence

The preceding passing disagreement test established overwrite behavior, but review
found that it still inherited the replacement height to unmeasured siblings,
even when host/variant observations conflicted. Three stronger tests **failed
/1.27s**: conflicting inheritance, malformed optional JSON failing offer, and
foreign-host evidence admitted under the selected policy. These are application
regressions/gaps, not harness environment failures.

Quality now suppresses inheritance durably after conflicting height/host/variant
observations in a retained scope; the latest exact entity retains height/codec.
Subsequent matching evidence/restart cannot silently restore inheritance for
that cache lifetime. Other-host records, malformed cache JSON and malformed
pending observations are ignored/discarded; queued estimates continue. The
private JSON `inherit` flag is additive, old valid rows remain readable, and
neither SQL schema, public identities, artifacts, TTLs nor sampling budgets change.
This tightens08's existing host/evidence boundary rather than inventing quality.

Linux API/source overlay focused quality/sampling/jobs/runtime **54 pass /16.79s**
(before the final damaged-pending regression). Rebuilt installed API catalog v7
**217 pass /49.80s**,1 GiB/two CPUs;
image `sha256:9344fbc37aae91183b6d9ad70769dc15effe113898a9a6de2cbb2c05ceb04df1`.
Full API v6 before this refinement **411 pass /63.19s** with current core/API
source and disposable repository/DB; validation-only image adds Git. v5 with an
older installed core also411pass63.68s is supplementary, not latest-core proof.
Final full API refinement results follow; real clients were last run before
this quality change. No new live extraction/download/import claim is added.

Final full API v7 **414 pass /63.37s**, current API/core source on a fresh
standalone disposable repository/DB, Linux arm641 GiB/two CPUs, Git-enabled
validation image; includes damaged-pending queue continuation and persistent
conflict suppression. No user data is mounted. Ruff/diff checks pass.


## 2026-10-01 — Current native packaging and artifact overhead

Latest native macOS27.0 arm64 onefile build passes in31.789s, Python3.14.7,
PyInstaller6.19.0/hooks2026.3; `frozen_smoke.py` health8.160s on disposable
loopback state. Snapshot enforcement stays gated; native amd64/Windows absent.
Docs build v14 passes5.51s.

Full generated overhead diagnostic v1 failed disk I/O during release-table
rewrite under the unchanged1-GiB file limit. v2 constructs a fresh destination
first, preserving row count/retained fields and avoiding duplicate intermediate
tables. No production schema/cap/data changed. Full/no-RSS/no-index-or-first_seen
SQLite985956352/825245696/816758784, compressed401205698/323618791/323458523 bytes;
v3 no-canonical-index control970477568/393935067 versus repeated full985956352/
401205698. Explicit canonical indexes15478784 bytes. Both cgroup2-GiB peaks,
no OOM; child256 MiB/two CPUs/outer600s. v2 build+compare24.499/19.357/19.728s,
compression3.506/2.853/2.922s. v3 no-map/full24.891/20.420s, compression3.421/3.474s.
RSS indexed22–65us versus117ms; mapping title/entity indexed4–19/3–11us versus
2–3/25–26ms. Counterfactual VACUUM relocation produces more compressed bytes
than production257838610; no reduced diagnostic schema is signed or published.
Raw synthetic files/results remain outside Git; current summary is10.

## 2026-10-01 — Current real Sonarr and Radarr generated STRM imports

The existing STRM harness now supports `ARR_KIND=radarr`, retaining Sonarr as
the default. Logical megakino movie/aniworld.to TV fixtures, category selection,
normal lookup/add/search and actual library-file endpoints follow the selected
client. Each run creates and removes its own Docker network/volume/containers;
no provider requests, user data or supplied credentials are involved.

`ARR_KIND=radarr bash scripts/catalog/validate-arr-strm.sh` v1 and the default
Sonarr current v1 both **exit0**. Pinned clients are Radarr6.4.4.10685
`sha256:adb6c09d6b729ea5e642c99cea35af72702ef476bf4763f153299ac5db9f0b4f`
and Sonarr4.0.20.3014
`sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`.
Installed API9344fbc.../workerb700df2... on Linux arm64; API/client1 GiB,
worker2 GiB, each two CPUs. Current harness source is mounted read-only.

Both return search size0 and **reject Unknown-only** because their parser
interprets the `.STRM` suffix as SDTV/480. An explicit disposable Unknown+SDTV
profile permits grab. Both produce a durable163-byte proxy STRM, actually copy
it into the correct movie/TV library, preserve its stable URL and decode one
second with FFmpeg through the generated HTTPS media server. Queue diagnostics
are empty. Cgroup peaks API/worker/client: Radarr343158784/41525248/304775168,
Sonarr342114304/42291200/309207040 bytes. No OOM or leftover run containers.
Private logs: `/tmp/anibridge-radarr-strm-v1.log` and
`/tmp/anibridge-sonarr-strm-current-v1.log`; raw logs/media are not committed.

Context7 retrieved Radarr import/parser documentation; pinned primary
MediaFileExtensions source confirms `.strm` belongs to its SDTV/streaming
extensions.07 records that source. This is client interpretation, not a quality
assertion from AniBridge. Fixture resolver/DNS/TLS remain injected; no live
provider metadata→extraction→import/playback or rights clearance is established.
Focused Ruff/format/Python syntax, shell syntax and diff checks pass. Application
source is unchanged, so the existing current installed/full suites remain the
application regression evidence; they are not relabelled as rerun here.

Final STRM documentation build v15 **passes5.16s**, retaining existing bundle
size and m3u8-highlighter warnings. Source audit after165aae9:372files,
fingerprint`b897787e0058b861b91fe9ca964249d8a86e3d5f8687b9681b3684296a71d190`,
252 task-diff files; Python syntax valid, no actual supplied credential bytes,
binary/database/media/data artifacts or untracked files. Prior audit atc04d9b3
was`c97e48394ec89be77db024444adb609aea23e0909dfb86010114eedb0979357e`.
No application source changed in this continuation; two real generated-client
checks ran, full suites were not repeated. M0–M4 remain incomplete with the
freshness decision pending and other named gates open; public gates stay closed.

## 2026-10-01 transport diagnosis supersedes the Megakino stub obstacle

The prior three HTTPS stub observations remain failures of the original fetch
path. An explicitly authorized three-request cookie sequence now reaches real
homepage/movie HTML in Docker, with separately verified shared and local code
paths. See10 for bounded measurements. No selectable language was established,
no sitemap foreign origin was followed, and no media download occurred. C5b
remains blocked by maintainer decision; metadata success cannot pass that gate.

## Original full-active verdict before the accepted signal strategy

**C4 freshness fails** the full already-checked active workload.
`scheduler_capacity.py --claims 5`:1050000 pages; real SQL selections
0.714/0.684/0.691/0.668/1.119s. Actual persisted admission over a simulated4h
accepts4800/refuses9600 starts. Even ignoring listings/retries/parser/canonical
cost, a sweep needs**875h**, leaving1045200 pages unvisited at4h. This is a
necessary capacity bound, not live/end-to-end freshness evidence. The six-hour
criterion and1200/hour cap remain unchanged. A numbered maintainer question
offers recent-change-signal investigation (recommended) or an explicitly revised
capacity-qualified product promise; **no answer received, no change approved**.
Installed upstreamaniworld5.0.6 `search.py:363` exposes `/neue-episoden` as a
candidate only; global-session transport/completeness are not worker proof.

**100 shaped updates and24h memory/FD/freshness are unexecuted**, not passed or
mislabelled as missing-environment blocks. Large legal representative cardinality,
broader sustained HTTP/correction-history evidence
remain open. Full-size single install/query/publication passes do not close C4.

## 2026-10-01 sustained harness debug failures

The first full-size debug attempt failed before publication because the fixture
child called the read-only schema connector with an unsupported writable flag.
The second published successfully in61.154s but served a malformed signing call
(single key instead of key sequence), causing a protocol error. The third
installed the full artifact but its verification tried to acquire a ninth query
slot while eight readers were active; admission correctly returned search_busy
at324.244s. These are corrected harness failures, not application regressions
or completed updates/endurance. Only owned large disposable files/containers
were removed; concise private results/logs remain. The fourth debug run passes
two actual updates in675.784s. No short run is relabelled24h.

The original20-GiB100-distinct-artifact capacity model fails:25.8GB before
staging/grace. Authorized sizing now allows an opt-in576-GiB output/48-GiB
state profile, with actual physical capacity still unavailable. The earlier
448-GiB draft used256MiB for the current artifact; review corrected it to the
permitted512MiB cap before recording a profile commit. No retention period,
referenced artifact, consumer memory limit or distribution protocol was changed.

Final retention review identifies an earlier failure that ordinary committed
publication tests missed: a failed reservation could shorten a third artifact's
supersession grace. The exact new regression fails against the previous helper
and passes after filtering failures and bounding the successful-history scan.
The first storage model used145 generations; cleanup-before-publication plus
inclusive grace needs146. The corrected576-GiB profile still covers that bound;
no grace period or referenced data is shortened.

## 2026-10-02 retention decision and failed sustained run

The maintainer explicitly replaces72-hour full-snapshot grace with current plus
one previous artifact per provider and active-transfer protection, within30 GB
**total** worker footprint. The576-GiB option is rejected and removed; preceding
sizing/default-capacity failures remain historical evidence, not newly passing
experiments.404/410 obsolete references use a bounded current-pointer refresh
while preserving consumer last-good. No deltas/shards/remote search are added.

The frozen24h run from2026-10-01T20:17:47UTC exits1 at2026-10-01T22:49:19UTC:
10 completed updates,9088.404883641 elapsed seconds,`TimeoutError: bounded child
deadline`. Actual traceback locates the120s semantic-validator child after
transfer/decompression. No DockerOOM kill; the sampler finished normally.
112947 error-free searches,p95.086s/p99.111s are the **last completed update**,
not a successful sustained result. Exact frozen artifacts/images remain in
`/tmp/anibridge-sustained-24h-v1/run.json`; the failed result/exit log/final
container-state and original sampler segments are preserved. Do not attribute
it to the inherited HTTP healthcheck or raise validation limits to hide it.
Follow-up is paused, source stopped and only the owned keep-awake process ended.
The precise cause of this validator deadline remains unresolved; storage/retry
work continues independently.

The first footprint harness failed before constructing data because its assumed
fixture count dictionary named the alias table incorrectly; the second tried
SQLite WAL preflight directly on a read-only single-file bind. Corrected the
harness to copy into disposable writable state before preflight. The first
completed four-publication pressure run omitted synthetic canonical provenance
from the export allowlist, so its mapping rows were filtered; it is partial
retention evidence only, not the full-capacity gate. Subsequent full-mapping
runs assert all50k title/1m episode maps and unchanged full entity/release counts.
Final Linux accounting also includes unlinked-open SQLite sort files;20.227GB
accounted peak passes the measured30-GB footprint subset. None relabels the
failed24h run or proves all live providers/100 producer updates.

After preserving failed-run tools, sampler segments/results, small receipts,
job DB and large-file hashes, removed only its owned stopped containers/network
and source/consumer catalog files. The completed retention-pressure files were
likewise removed after preserving results and inventories. Consumer memory.max
pressure and validator deadline remain unresolved; FD recovery and modest
parent RSS growth in the short sampled interval cannot establish endurance.
The source fingerprint, local commits and final test scope are recorded in10.

## 2026-10-03 — Reproduce the failed validator and reduce pager churn

The original `/tmp/anibridge-sustained-24h-v1/consumer/result.json` is unchanged:
failed at9088.404883641s after10 updates. Reconstructed candidate11 from the
original frozen mutation script and saved manifest timestamps. SQLite SHA-256
`9b2058da82a809a362c1ce32d1c4293d0b41ce9b35201b52c01fa7600b2bd2ea`
is byte-identical to the preserved failed-run inventory. Cardinality stays
50k titles/1m entities/2,000,011 releases with all canonical mappings.

Procedure: `validator_probe.py prepare`, then `probe --name CASE --loaded
--cache-mib 8|32` in isolated Docker containers,1 GiB/two CPUs,256-MiB child,
120s deadline,8 original reader threads at0.5s. Proof directory:
`/tmp/anibridge-validator-diagnosis-v1`. The original API image is unavailable;
retained image `eda046f65f6e242c8938fa47e53a04b9a2fbae03a3b6a880e770275b3d10dd91`
has byte-identical pre-fix validator SHA
`54707951cba6c9fba70f3d4d8c79e4d72342eb864c5d6b27ca3d22ad04a3f7e4`,
Python3.14.7/SQLite3.46.1/Linux arm64. This is code/input reproduction,
not execution of the unavailable original image.

| Probe | Wall seconds | Logical bytes read / read syscalls | Actual child RSS peak | Searches / errors | Result |
| --- | --- | --- | --- | --- | --- |
| Isolated,8 MiB |46.167|52.801 GB/12,890,430|~46 MB|none|Pass|
| Warm loaded,8 MiB |51.326|52.216 GB/12,747,559|~46 MB|780/0|Pass|
| Cache-evicted loaded,8 MiB |120.983|49.090 GB/11,984,419 before interruption|45,662,208 bytes|1606/6 query timeouts|**Fail** at unchanged deadline|
| Cache-evicted loaded,32 MiB |94.374|23.530 GB/5,744,190|71,245,824 bytes|1384/0|Pass|
| Current installed validator,32 MiB |46.316|see archived counters|see archived counters|704/0|Pass; different Python patch/cache state|

Controlled cache-evicted comparison:8-MiB child spent~98.063 CPU seconds before
interruption,4.831s scheduler wait,3.594s cgroup CPU throttle,16.444s I/O
pressure and0.180s memory pressure.32-MiB run spent89.409 CPU seconds,2.033s
scheduler wait,1.406s throttle,5.158s I/O pressure and0.092s memory pressure.
Both cgroups hit the1-GiB page-cache envelope, without OOM; memory.max events
are reclaim observations, not process OOM proof. Header/integrity/FK stage
rose from12.66s warm to60.407s before the failed cold row scans.

This demonstrates pager churn plus concurrent I/O/CPU cost, with smaller
scheduling/reclaim contributions. Increasing only the validator connection
cache to32 MiB roughly halves logical reads and removes the reproduced timeout.
Search cache remains8 MiB; no deadline/resource/DDL/check is relaxed. Linux
`posix_fadvise(DONTNEED)` cannot guarantee a physically cold macOS/virtiofs
cache. `/proc` rchar measures logical traffic; read_bytes=0 here is not zero
physical I/O. Inherited ru_maxrss is unsuitable for fork-child peaks; use
sampled `/proc` RSS. Different-cache current-image timing is not a causal
94→46s improvement claim. Original per-child counters were absent, so the
exact contribution of other host activity to that historical failure remains
unknown. No parallel large experiment ran during these probes.

Validation: native core289pass1.80s (macOS arm64/Python3.14.8); installed
core289pass4.36s (Linux arm64/Python3.14.8/SQLite3.46.1,1 GiB/two CPUs).
The installed fixed API image is
`bfc069b2bf65bfe54ec4881ec6f9360ada2586451b603aefbbc9bb83d2a919cc`.
These are finite regression proofs; C4 real24h/100 updates remains failed/open.

## 2026-10-03 — Persist trust context and reuse identical signed content

New additive private migration0008 preserves existing receipts with NULL
context until full bounded revalidation. No released-mainline data is discarded
and no wire identity/schema changes. The receipt binds current source ID, origin
and pinned key set. A verified higher manifest can reuse identical validated
content after hashing its retained regular file; atomic activation updates the
manifest/floor while retaining previous distinct bytes. Changed trust/contracts
require full admission, missing local bytes are downloaded, and corrupt bytes
reject without a floor advance. Cancellation retains bounded child ownership.

Installed all-catalog plus migration command/result in10:249pass64.16s. An
initial67pass/1fail harness fixture used identical content for an intended
remote404 case; it now exports truly changed rows, preserving the recovery test.
Zero-body renewal is proved by real local HTTP artifact counts across restart.
This proves that specific synthetic contract, not real-provider freshness,
actual24h stability or client import. Short regression remains pending.

## 2026-10-03 — Fresh-export bandwidth comparison

Command: Docker run `bandwidth_probe.py /source.sqlite /proof`, installed worker
`daa7ce8fc4e75f78aaa40a41b25c3a2c7dee465f7d95c15d88a934149e913c1e`,
Linux arm64/Python3.14.8/SQLite3.46.1,2 GiB/two CPUs. Each actual fresh export/
compression/validation runs in a256-MiB single-thread child with360s supervision.
Input is the previously generated private ledger, SHA
`c6edbfedacc1b6a2680a64ef975aa3af1a83327ae952a24b4d4e2f793daa404c`.
Executed frozen tool `/tmp/anibridge-bandwidth-probe-v3.py` SHA
`5f40a0a0f3ec9fdb7fdced92ac4b0a017bfe6c940904c6a4d8fd07b2fa5a0ea3`;
repo copy has import ordering/doc wording changes only. Proof/results:
`/tmp/anibridge-bandwidth-v3/result.json`. All50k titles/1m entities/50k title
mappings/1m episode mappings retained; release count2,000,240→2,000,300.
Existing discovery sum stays intact plus exactly60 new first_seen values.

| Cumulative case versus original baseline | Full zstd bytes | Dirty4-KiB pages | Changed independently compressed1-MiB chunks |
| --- | ---: | ---: | ---: |
| Unchanged fresh export |257,890,952|0|0|
| Complete listing check |257,890,952|1|240,302|
| Plus one title observation |257,890,955|2|240,305|
| Plus60 canonical checks |257,891,154|4|498,752|
| Plus60 new language releases |257,884,580|177,309|176,783,325 (697 chunks)|

Unchanged export has identical SQLite/zstd digests; ordinary truthful timestamps
make bytes dirty. Complete fresh builds take47.845–65.516s export,3.072–4.772s
compression,40.025–55.311s semantic validation. Sampled accounted peak is
6,107,614,272 bytes including1-GB runtime allowance and open-deleted temps.
This isolated fixture does not measure the entire live three-provider deployment
or close endurance/producer gates; the prior20,226,560,160-byte full footprint
proof remains separate. No peak CPU/RSS sampler was attached to this bandwidth
subset; child/cgroup limits enforce bounds but are not a trend measurement.

Offline fixed chunk comparison includes indexes and their recompression.256-KiB
chunks bootstrap271,696,450 bytes, exceeding the unchanged256-MiB cap; sparse
change187,310,133 bytes.1-MiB chunks bootstrap256,231,259 bytes, but sparse
change still176,783,325 bytes (~68.6% of full). Fresh sorted compact key
assignment/index rebuild makes small insertions dirty many pages. In-place
SQLite edits would have understated this cost. Figures exclude descriptor/
signature overhead, reconstruction/validation CPU, patch client and network;
there is no implemented or approved delta/shard protocol.

At this measured size,48 distinct updates/provider/day yield12,378,765,696
bytes/provider/day; three providers37,136,297,088 bytes/client/day (~1.114 TB/
30 days).100/1000/10000 clients derive3.714/37.136/371.363 TB/day. This is a
reconciliation-churn scenario, not observed live cadence or billing. Daily
identical signed renewal now has zero artifact transfer instead of the former
0.774-GB/day three-provider model. Changed snapshots still cost the full body.

Options: hourly publication coalescing halves this scenario to18.568GB/client/
day, still~557GB/month, and needs remeasured publication latency; it does not
solve sparse bandwidth. Fixed byte chunks help timestamp-only rechecks but
perform poorly on new release insertion. Logical stable-identity shards or
record deltas may reduce churn, but shard size/count/changes and reconstruction
cost are not measured. Recommended next experiment before a protocol decision:
preserve internal join-key assignments across exports, then benchmark a
maintained bounded binary-delta tool against immediate current/previous files.
If worthwhile, propose a separately versioned signed patch descriptor with exact
base/target digests, atomic reconstruction/full admission, ordinary full-snapshot
fallback on missing base, and patch retention charged to the same30-GB total.
Do not implement that distribution change without review. Existing full
snapshots/local search/after-grab local extraction remain the contract.

Harness failures remain recorded: v1 compared SQLite Rows to tuples and rejected
before export; v2 put the sampler thread inside the256-MiB process, inducing
MemoryError during index creation. v3 matches production's sampler-parent/
single-thread child separation without changing resource limits. No bulk/live
provider, credentials or media requests occurred.

## 2026-10-03 — Short shaped regression and full-size zero-body renewal

The original failed24h experiment remains unchanged. New short-v2 completes
900.881s/debug-passed with2 distinct full10-Mbit/s updates,8900 error-free
searches,12 job histories,source switching,503/stall recovery. Independent
minute sampler captures16 rows and finishes normally. Actual install261.402/
261.833s; recovery0.738s. RSS warms with8 readers then plateaus187.78 MB and
falls to155.10 MB after shutdown; steady19 FDs, temporary25,final20. NoOOM
or CPU throttling. Measured reclaim/I/O/CPU/disk trends and frozen hashes are
in10. Neither diagnostic plateau nor debug-passed closes C4 sustained evidence.

New full-size real HTTP renewal on copied generated state passes: manifests3/4,
zero artifact GETs/bytes across restart,local1.051-GB digest renewal0.774/0.697s
and recovery0.664/0.608s. Script/image/procedure recorded in10; synthetic origin/
pins remain unchanged. Failed harness launch/read-only WAL/pointer-path attempts
are preserved separately. No user installation/provider/media/client import
was touched. New shared-activation crash checks pass before the24h retry.

## 2026-10-03 — Guard repeated polls and recheck activation crashes

Final review added the exact-repeated-revision race to the existing renewal
trust-change test. Pre-fix installed image:1failed/1passed1.13s; repeated poll
returned after hashing without detecting a changed origin. It could similarly
miss cancellation after the hash. Require current trust context and uncancelled
ownership before either return or activation. Targeted installed renewal/update/
snapshot/trust suite **54pass22.07s**, image
`713553d06dae362af6ecbd461bef57273638d2db74c3ef0f5046094104fbb2d7`,
otherwise unchanged Python3.14.8/SQLite3.46.1/Linux arm64,1 GiB/two CPUs.
This does not change full-artifact admission/transfer/activation code or limits.

The shared activation introduced by b0996cc also passes actual
`crash_activation.py --repetitions 100`:600 SIGKILL cases,100 each at
decompress/validate/rename/before_commit/commit/registry with8 pinned readers.
Per-boundary52.173/59.012/60.134/59.466/59.598/59.665s. Executed installed
APIbfc069… at1 GiB/two CPUs; log`/tmp/anibridge-crash-renewal-v1.log`, tool SHA
`d822e070a4b869e71303fb66987555641934e09139f4b4772c8817635e54f071`.
Atomic committed revision/floor and previous reads recover correctly. Later
renewal-only return guards do not alter this install path. Small generated
crash fixtures are not large-update/endurance or every inner-fsync evidence.

Docs build`pnpm --prefix docs run build` passes5.79s,VitePress2.0.0-alpha.17;
existing bundle-size/m3u8 highlighting warnings remain. Ruff/diff checks pass.

Current-image full-size real HTTP renewal-v4 passes after the final guard,
including exact repeated polls and restart.4 pointers/4 manifests,zero artifact
GETs/body bytes; recovery0.799/0.638s,renewal0.796/0.662s,repeated poll0.614/
0.637s,86.761-MB parent peak/noOOM. Fixture,script SHA and image remain
explicit in10; the preceding shaped debug result is not silently reassigned
to the later image. No admission/transfer/install path changed in this guard.

## 2026-10-03 — Launch the separately validated actual24h retry

After the900.881s shaped debug regression,600 current shared-activation crashes
and final guard/current-image full-size renewal checks,the owned100-update/
86400s run starts16:32:05UTC at `/tmp/anibridge-sustained-24h-renewal-v2`.
Initial process state healthy; result pending,not passed. Final images,frozen
source/consumer versus sampler hashes,command,host capacity and keep-awake are
in10/run.json. No overlapping large experiment. The existing hourly follow-up
is resumed and stays quiet unless actionable failure or validated completion.
Preserved original failure remains9088.405s/10 updates; this new launch cannot
relabel it. The fixture source does not prove real collector retention/providers/
client/platform gates or release readiness. Full30-GB policy and M5 closure persist.

## 2026-10-04 — Preserve and investigate the second endurance failure

**C4 failed again: 92 updates/79935.900179509 s**, `TimeoutError: bounded child
deadline` in the 120 s semantic validator after transfer/decompression. Consumer
exit 1/no OOM; source was running/no OOM. Follow-up `catalog-endurance-follow-up`
is now PAUSED (verified saved status); the source was stopped after preservation.
The recorded keep-awake/monitor processes had already exited. No original
containers/network or large failing inputs were removed. No new 24h run started.

Proof `/tmp/anibridge-sustained-24h-renewal-v2`: Docker logs/inspect, original
result/progress/private DB/receipts/frozen tools, source artifact 93, accepted 92/91,
served A/B signed 93 envelopes and all 92 committed envelopes are retained.
`preservation-inventory.json` rehashes 31 original files unchanged; the additional
94 envelopes have a separate inventory. The failed temporary admission inode
was already removed by TemporaryDirectory cleanup. Preserved source bytes match
its signed digest exactly; original inode/cache/physical allocation state is
unrecoverable, rather than silently treated as reproduced. Do not restart the
retained fixture source: its initializer rewrites base.sqlite. Replay through
a separate static server with original inputs mounted read-only.

| Input | Exact SHA-256 |
| --- | --- |
| Candidate 93 SQLite, 1,050,587,136 bytes | db0fe27e010d886c4cbf02b8a1a70b2dcf31db17fdcc6216485e2b5995069887 |
| Candidate 93 zstd,257,860,710 bytes | 03689d3fd6ef2f104addc9ed681b300d932a6dba25868c9def2b2935dc8808b6 |
| Accepted 92 SQLite | 2198babeb93f4492a9cd1c2dc9b13169a49430def523b8517f76392e4d5c0342 |
| Accepted 91 SQLite | 80dbff27bdc32d1faac4207d2410ec74f373d993f79672b626ecbfca3cb2d6da |

Original active/floor A remain 92, B floor 79; no 93 receipt exists. All 1,822 jobs
are cancelled, generation 6/attempts 0/lease 0/no pending retry. The original
sampler has 1,329 minute rows and no monitor-failed file. Three gaps 954.219/
958.003/1189.770 s correspond to earlier macOS clamshell/maintenance sleep
records. No matching sleep appears at the final failure window; early gaps
**do not explain the final timeout**. Keep the post-warmup/prelaunch coverage
limit. Monitor-finished wall elapsed 82895.149 s is not consumer monotonic elapsed.

Idle RSS for revisions 1–5:165.384–190.820 MB;40–50:200.106 MB;85–92:
200.696–200.827 MB. FD baseline 20, transient samples up to 36 with readers;
source RSS 42.7→44.0 MB. Private footprint 645,384→7,270,624 bytes with 1,822
histories; catalog disk settles near 2.101 GB, staging reaches 3.417 GB. These
observations do not show late linear RSS/FD growth or OOM. Consumer cumulative
CPU 19237.442 s, quota throttle 16.194 s, memory PSI 7.514 s, I/O PSI 1983.764 s
(some)/1643.050 s (full); last I/O avg10 is 15.28%. Source CPU 4273.293 s, throttle
.004 s, memory PSI .026 s, I/O PSI 125.222 s. The original run has neither per-child
stages/CPU nor guest CPU-pressure/host-memory counters. Per-update install
journals were not persisted before failure, so a 92-install cost trend cannot
be reconstructed honestly from the last progress row.

### Bounded same-byte tests

Image 713553… from the failed run; Linux arm64/Python3.14.8/SQLite3.46.1,
consumer 1 GiB/two CPUs, child 256 MiB/120 s, production 32-MiB pager. No cap/check
changed. Proof `/tmp/anibridge-validator-second-failure-v1` uses read-only mounts
of preserved inputs; `validator_probe.py probe --name <name> --cache-mib 32`,
with `--loaded` for the frozen eight readers.

| Test | Validator wall/CPU | Result |
| --- | --- | --- |
| isolated93 |44.618/41.526 s |pass; process peak 73.093 MB |
| loaded93 |45.913/42.258 s |pass; 714 searches, p95.035/p99.043 s, no errors |
| stage93 |41.577/40.070 s |pass; per-SQL logical reads retained |
| preserved older candidate 11, current image/cache |45.231/42.484 s |pass; no substantial content-dependent growth seen in this comparison |

Stage 93: physical entity/release scans .436/.950 s; full integrity 8.745 s and
13.297 GB logical reads; entity rows 7.521 s/.158 GB; release rows 13.553 s/6.787 GB;
canonical episode rows 4.331 s/1.273 GB. Total logical reads about 23.6 GB for a
1.05 GB file. These are SQLite read-call bytes; bind-mount read_bytes=0 is not
proof of zero physical host I/O. Advisory fadvise cannot establish a cold macOS
cache. Original/stage probe scripts are separately retained and hashed:
15126f74f76576cac321ffdba9fac4b7057371fc9788232b3f6f96dd70ba04d7 /
536b2164b6109a02172967bdb83bdbb512252252aaee9d4fad92574316515ef8.

Bounded join-only comparisons on identical 93, 32-MiB cache/256-MiB child:
original release view 5.367 s/6.790 GB logical reads; entity-index order 4.508 s/
6.999 GB; explicit entity-table order 5.739 s/7.085 GB. Forced sorting 8.851 s/
17.674 GB reads/12.062 GB logical writes (1.998 GB kernel write_bytes cumulative,
not peak scratch size). **Rejected**: no demonstrated reduction; no DDL/index,
ordering or sort change implemented. SQLite primary query-plan/cache docs were
retrieved with Context7; execution plans are retained in the disposable proof.

### Admission and actual background retry

Four real local HTTP replays from copied original 92 state, same source/origin/
pins and signed 93 bytes: validator 46.789/44.852/45.953/43.310 s, child CPU 44.465/
41.955/42.519/41.096 s. The first three have 754/745/756 error-free searches;
complete admission 49.809/48.137/49.421 s. Fourth has explicit per-stage cgroup
samples: no OOM/throttle, peak 1 GiB, memory PSI .077 s/I/O PSI 2.626 s. Proof
`/tmp/anibridge-second-recovery-v1`; driver SHA 660816ee8b2026f72cdad07182dbe85eda55c6f16ca9e938b13ae90c3fff4c7f;
sampled variant b0ccb1d57a89bbbc89beb9d15449edfde6673639f19c9eb13e3755d76e8b9591.
The earlier 17-row external sample only covers a draft replay that later failed
serialization; it is not reassigned to all final replays. Draft failures
(base64 envelope treated as dict, then SQLite Row serialization) remain in logs.

Demonstrated implementation defect: Runtime.poll caught errors but returned to
the normal phase, missing specified 5/15/60-minute retries. Fixed in 34249b9;
success resets each provider's sequence, repeated failures return to normal
polling. Retry schedule is process-local; jobs/receipts/floors remain durable.

Current installed image c3444c9aad028a90b3dab7998c325b401481e71f2b7a6c2236d70a7afd7d80fe,
built with `docker build -f apps/api/Dockerfile -t anibridge-api:catalog-second-retry .`.
Outside working tree (`--workdir /tmp`), API/core import their installed wheels;
runtime module SHA f822ee0aaea7cde2c26f3e5c936f5e873fbcf8e3b761fbb7d08b8daa9c71e871,
core wheel fe62be0bec4e853a11cfd57354c8385fe2bbead00d25e045bc7d88dde37e0213.

Proof `/tmp/anibridge-second-background-retry-v1`: one **injected** TimeoutError,
then Runtime.poll waits **300.012 s actual time** and performs real signed 93
HTTP admission automatically. Completed 349.071 s; validation 45.931 s/42.438 CPU,
23.649 GB logical reads, 1.132 s child scheduler wait, no OOM, 1 GiB peak. Fixed
anonymous padding 76,636,160 bytes targets the failed run's 200.827-MB steady
parent RSS; no resource limit was increased. 5,082 searches, no errors, p95.067/
p99.070 s. Last-good/floor 92 remains protected during error; activation advances
A93/B79. Job/request/alias row digest remains exactly
7c4fece60cdbeb2713389e554f350fa4f29f6a84c0c074af0ec18e8a3808c011.
Driver SHA 146a8db85930911894805f7cce73df8a22133740b7a172e2115dc091556359a9;
frozen admission helper fa3afe14e3798fe5ed64c20c7f4b890dd3cb192c57d4abe94b296a2d067e0ee9,
validator probe b2642a1a3598b324aaa82745539ecffc0a434701fd4f1753c4e048a7a98010db.
Executed Docker 1 GiB/two CPUs, loopback alias worker, read-only `/failure` mount,
`PYTHONPATH=/proof/tools`, fixture-only driver; no API web server/media access.
This proves background recovery from an injected fault plus real original
candidate admission, **not a reproduced historical timeout**.

Future sustained harnesses persist journals after each acceptance/on exception,
freeze fixture-only per-admission tracing, and sample guest CPU pressure/
scheduler/monotonic time plus aggregate host memory/swap/load/free disk. Preserve
original exceptions if diagnostic writes fail; missing diagnostics cannot pass.
Installed-image QA mounts tools separately from tests and imports API/core wheels.
Focused 18 installed runtime/update/diagnostic tests pass, 1 GiB/two CPUs; command
`python -m pytest /tests/unit/catalog/{test_runtime,test_updates,test_admission_measurements}.py -q -p no:cacheprovider --no-cov`
with `/tests` and `/catalog-tools` read-only mounts. Earlier new-test drafts
failed fixture uniqueness setup/error-message expectations; corrected without
changing validator checks. Ruff/shell syntax/diff checks pass. Cumulative child
high-water RSS is labelled separately from resident/cgroup measurements.

### Bounded shaped regression

`DURATION_S=900 UPDATES=2 SWITCH_EVERY=2 INTERRUPT_EVERY=2 bash
scripts/catalog/start-sustained-validation.sh /tmp/anibridge-bulk-fixtures-50k/fixture
/tmp/anibridge-second-failure-short-v1 anibridge-api:catalog-second-retry
sha256:daa7ce8fc4e75f78aaa40a41b25c3a2c7dee465f7d95c15d88a934149e913c1e`.
Same 50k/1m/2m/two-language fixture, 10-Mbit tc shaping, no cardinality reduction.
**debug-passed 900.587 s/two distinct artifacts**, 8,666 error-free searches,
segment p95≤.072/p99≤.078 s; installs 260.267/264.929 s; source switch/recovery
.902 s,503 preserves last-good, hung response times out 15.029 s; 11 durable job
histories. Two artifact bodies total 515,680,232 bytes. This is not 100 updates,
24h, actual producer retention/footprint, provider, *arr or playback proof.

Source image 942905208d02fe7ad5aad75c7b3f609790798c10f68cb8cf22b5ff17cbc7997b;
API c3444c9…; Linux arm64/Python3.14.8/SQLite3.46.1. Frozen consumer
f8cc87af66a1d7d54d33ac3c6ec6e0d7f466e1318d05701b64c7fc4f5b1ea9b0;
sampler separately aa6587692b9510d4cab4aa3117101ec561be2a0edf887b09e1e9df44e9828bf8;
source/fixture hashes match the original second run. This run froze the journal/
guest-counter changes before the later per-admission helper/host-counter addition;
those are separately proven above, not silently attributed to this run.

Independent sampler 16 rows/max gap 60.163 s, finishes normally; no monitor failure.
Source RSS 42.598–43.254 MB, FD 4–6, plateau; consumer startup 29.880→187.339 MB,
last five samples 187.208–187.339 MB, final 154.907 MB, FD baseline/final 20,
transient 31. Peak sampled consumer disk 2.359 GB/source 1.566 GB. No OOM;
consumer quota throttle .036 s/source 0, final consumer CPU 238.935 s including
children, memory PSI about .137 s/I/O PSI 20.605 s, CPU PSI 13.214 s some/7.026 s full.
Warmup/installation steps explain the short increase; this does not prove 24h
leak freedom. Consumer exit 0; source intentionally stopped after result capture
(137 after stop timeout, no OOM), which is cleanup rather than an in-test failure.
Logs/private DB/manifests/tool hashes/resource/results are retained. Original
failed-run inputs stay untouched; owned short disposable large files alone
were removed after a 31-file inventory: five large files/two stopped containers/
network. An initial cleanup draft used the wrong column/Blob serialization and
aborted before deletion; corrected to retain exact envelope bytes. Final docs
build passes 5.84 s; source/AST/Ruff/shell/diff checks pass.

**Verdict:** second timeout root cause remains unresolved, and C4/M0–M4 remain
incomplete. No deadline/check/cache/consumer/worker cap changed. Native amd64/
Windows, real end-to-end provider freshness/all-provider canonical-to-client
flows and live Megakino media remain open separately. No new credential/input
or product decision is needed for the current diagnosis; M5 stays closed.
