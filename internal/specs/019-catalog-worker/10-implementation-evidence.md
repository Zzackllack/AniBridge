# Private implementation evidence

Status: **M0–M4 implementation remains incomplete; required gates are open.**
Local implementation commits are authorized as of 2026-09-30. No public
deployment, redistribution, official hosted default, push or PR was performed. M5/C7/C8 remain closed. No user installation was migrated.
Dated measurements and earlier failures are preserved in
[11-implementation-history.md](11-implementation-history.md).

## Current failure verdict (2026-10-04)

The second actual endurance attempt **failed after 92 updates and 79935.900 s**
in the 120 s semantic-validator child. It did not reach 100 updates/24h. Exact
candidate 93, accepted 92/91, manifests, private DB/receipts, frozen tools/logs and
samples remain under `/tmp/anibridge-sustained-24h-renewal-v2`; the 31-file
preservation inventory was rehashed unchanged. The follow-up is **PAUSED**,
source stopped, consumer exited 1/no OOM; no original inputs were cleaned up.

Same-byte isolated and eight-reader reproductions currently pass. Four complete
HTTP admission replays from preserved revision 92 also pass. **The cause of the
historical second timeout is unresolved.** A separate demonstrated scheduler
defect is fixed: failed admissions retry after 5/15/60 minutes before normal
polling, instead of immediately returning to the normal phase. No validator
check/deadline/cache/resource cap changed in this continuation. The short
shaped regression below cannot close C4. No new 24h attempt was launched.

## Current retention decision (2026-10-02)

The maintainer replaces72-hour full-snapshot retention and rejects the oversized
576-GiB profile. Current contract is **30,000,000,000 bytes total worker disk**:
20-GB state/9-GB output subordinate quotas plus1-GB runtime allowance. Keep only
current/previous distinct artifacts and needed manifests per provider, including
across schema changes; active transfers remain leased.404/410 remote misses
trigger one uncached pointer refresh/retry, never loss of local last-good.
Compact identity/discovery/checkpoint records and revision floor persist;
obsolete intermediate publication rows/files are pruned. Existing verified
migration backups are counted and preserved; over-budget startup fails before
copying. No new full catalog-history backup series is added.

Earlier20-GiB capacity failure and576-GiB calculation below are **historical**,
not current operating requirements. Tests/entire-footprint measurements for the
new policy follow at the end. Full-snapshot bandwidth cost remains separate:
37.136GB/client/day for three measured-size providers with48 distinct changes
per day is a derived scenario, not measured live cadence or protocol approval.

The first real24-hour consumer run **failed**, not passed, at9088.404883641s
with10 completed updates and`TimeoutError: bounded child deadline`. The traceback
identifies the120s semantic-validator child, after transfer/decompression. Docker
reports exit1/noOOM; saved active/floor both remain revision10 (`synthetic-a`); the independent sampler finished normally. Latest completed
update had112947 error-free searches,p95.086s/p99.111s. This is a failed C4
sustained experiment, not a completed24h/100-update gate or explained platform
block. Preserve frozen hashes and monitor warmup limitations. The source was
stopped, owned keep-awake PID terminated and follow-up paused. The separately
validated replacement steps below do not raise the deadline or relabel that failure.

## First timeout refinement (2026-10-03; historical)

The original failed run stays failed. A byte-exact reconstruction reproduces
the120s interruption with8 readers and an evicted candidate cache. Increasing
only the semantic validator's SQLite cache8→32 MiB halves logical page reads
(49.090→23.530GB) and completes the controlled test in94.374s, with no search
errors or OOM. Deadline120s, child256 MiB, consumer1 GiB and search8-MiB cache
remain unchanged. Current installed repetition passes46.316s; host/cache/Python
variation prevents treating that timing as another controlled speedup.
Native/installed core289 checks pass. Detailed commands/counters/limitations
are preserved in11. Short regression now passes the bounded debug subset below; the second actual24h run subsequently failed after92 updates, with no pass claimed;
this fix does not pass the historical failed endurance experiment.

## Checkout and baseline

- Branch: `zzackllack-aux/catalog-worker-implementation`; handoff base `00437b3`
  includes the committed specification, parent `e14a041` (released v2.6.0).
  A dependency-ordered local commit series now records the private implementation. Tests use disposable copies/DBs.
- Initial commit-series source fingerprint: **364357b86451b80f3641c46836450908275084a9a0e870fa034a18a30a128e3e**
  over 339 git-listed tracked/untracked nonignored files under `apps/api`,
  `apps/catalog-worker`, `packages/catalog-core`, `scripts/catalog`, `docker`,
  plus `.dockerignore`, the test workflow and `VERSION`. Procedure: sort paths;
  SHA-256 of concatenated UTF-8 path + NUL + raw SHA-256(file) for each. Excludes
  documentation/evidence and ignored data. This identifies the input recorded
  by the initial five implementation commits, not subsequent refinements.
- Mainline baseline: native **175 passed /12.76s**; supplementary Linux baseline
  **175 passed /14.70s**, same recorded dependency environment. Initial explicit
  DATA_DIR override broke a default-path assertion; this was harness isolation,
  not an application regression. The stale lock root version (2.5.2 vs 2.6.0)
  was corrected without replacing existing dependency versions.
- Environment: macOS arm64, Python **3.14.7**, uv **0.12.19**, SQLite **3.53.4**;
  Docker Desktop **4.49.0**, Engine **28.5.1**, Linux arm64, SQLite **3.46.1**,
  VM RAM **8,218,034,176 bytes**. Consumer/worker envelopes remain **1/2 GiB,
  two CPUs**; child address limit remains **256 MiB**, two consumer children.
- Maintainer accepted **Linux pilot; native enforcement gated** after macOS
  rejected RLIMIT_AS. Frozen executable snapshot execution is gated too because
  its executable cannot launch Python `-m` children. Legacy packaging is separate.

## Milestones and gates

| Milestone / gate | Executed evidence | Remaining boundary |
| --- | --- | --- |
| M0 / C0 baseline | Mainline baseline and field inventory recorded | Source rights unresolved; package/platform gate is partial |
| M1 / C0–C1 contracts | Installed core wheel, exact DDL/data, signatures, identity/magnet goldens and hostile mutation tests pass | Complete per-constraint adversarial inventory and all supported package platforms are not closed |
| M2 / C2 worker | AniWorld first, then s.to and megakino movie fixtures; checkpoints, first_seen ledger, quarantine, independent publication, process death/writer-error tests pass | Signal/queue/cache scheduling now has full-history synthetic proof below; finite failure cases, real mapping/access and end-to-end freshness remain open |
| M3 / C3 consumer/jobs | Local signed activation, last-good recovery, source/key/clock tests, durable blocked/retry/pause/cancel, reader leases and repeated real SIGKILL tests pass | Crash coverage is six named boundaries, not every internal fsync; disk failure matrix is partial |
| M3–M4 / C4 capacity | Smaller profile meets measured query/readiness/memory targets | Original schema1 full fixture failed both maximum byte caps. Schema2 now fits default caps; full correction-overlay and shaped cold install subsets pass; actual publisher fits caps; the first100-update/24h run failed after10 updates; full-active freshness remains a recorded failure below |
| M3–M4 / C5 clients | Pinned actual Prowlarr→Sonarr TV and Radarr movie generated-media query/grab/import; paused/blocked restart/retry/removal pass | Full provider/special/dedup/estimate disagreement/eligible RSS matrix incomplete |
| M4 / C5a RSS/estimates | Pinned Sonarr/Radarr normal explicit historical search, unmonitored bootstrap, 1000-entry bursts, 23-hour controlled cursor catch-up and restart/deduplication pass | Original exhaustive bootstrap failed 100/1000; revised workflow evidence below. Activation during pagination and selected disagreement/hung/hostile regressions pass below; complete provider/client estimate matrix remains open |
| M4 / C5b live provider | Authorized AniWorld extraction/download/remux/probe passed on an earlier pilot image | No live canonical→client import/playback proof; Original s.to Docker DNS failure preserved; supplied HTTPS alternatives parse. Megakino HTTP bootstrap now reaches HTML, but language/mapping/offers remain unverified; supplied TMDb token works and one supplied movie association is established below, broader provider associations remain open |
| M4 / C6 migration | Disposable recognized 0001/0002/0003/unversioned fixtures, backup preservation, files/STRM/hash collisions, SIGKILL upgrade and rollback-copy tests pass | Named all-state/revision/unversioned/backup/interrupt/foreign-schema matrix passes below; inner SQLite/VFS coverage remains limited; no real installation was used |
| M5 / C7–C8 | No public endpoint/default enabled | Closed; no redistribution clearance, operations approval or deployment |

## Implemented private functionality

- Separate installed core/worker/API projects. Exact STRICT allowlisted artifacts,
  strict JSON, Ed25519 trust, bounded zstd, stable provider/language/mode identities.
  Worker publishes metadata only; canonical associations require validated
  evidence and approved provenance. No ordinal or guessed mapping.
- Durable per-provider collection/listing checkpoints, leases, rate/backoff,
  deletion quarantine, preserved discovery times, reviewed season correspondence,
  independent static publication. s.to uses its own positive language labels;
  megakino supports observed movie metadata. Unobserved serial structure stays
  unresolved. Static serving has no query/telemetry API and no media extraction.
- Consumer downloads selected snapshots and searches locally. Per-source floors,
  atomic activation/retained previous, source-switch provenance, local RSS,
  indexed title/ID/season/category/offset search and bounded canonical ID-miss
  fallback. Unknown size stays zero; no inferred resolution or codec. A >200
  title-candidate query returns HTTP 400/Torznab error 200.
- Durable frozen requests and hash aliases; local resolution only after grab
  acceptance; explicit blocked/retry/pause/cancel/restart behavior. Shared child
  admission bounds parsing, sampling and downloads. Pause/resume-all selects
  batches of at most 100 distinct jobs, tested with 205 jobs and duplicate aliases.
- Scoped, nonblocking quality queue and authenticated management status,
  corrections/CAS/idempotency/retained rollback/targeted refresh tasks. Refresh
  is off by default, accepts existing IDs rather than arbitrary URLs, preserves
  checkpoints and expires private observations.
- User-local bounded VOE/Filemoon/Vidoza parsing, generated MKV/STRM publication,
  stable scoped proxy playback registration, HTTPS/DNS/TLS pinning, bounded HLS
  rewriting/Range streaming. Unsupported stubs/header-dependent hosts and DASH
  proxy remain explicit. Generated parsing is not live host evidence.
- Private Alembic **0004–0008** preserves mainline rows/files/legacy hashes and
  retains a verified no-overwrite backup. Unknown/#119 schemas reject unchanged.
  Incomplete old requests fail visibly rather than guessing their resume input.

## Reference checks before the signal/storage increment (2026-10-01)

| Gate/subset and command/procedure | Environment/version | Result and limitation |
| --- | --- | --- |
| C0 installed core and worker/API integration: `bash scripts/catalog/validate-private.sh` v5 | Python3.14.7/SQLite3.46.1, Linux arm64; worker2 GiB/API1 GiB,two CPUs; fresh internal fixture HTTP network | Core247pass4.56s, worker94pass16.07s, catalog207pass46.57s; install0.3208s. Synthetic only; later changes below |
| C2 current installed worker: Docker build plus `pytest /tests -q` v6 | Worker imageb700df2...,2 GiB/two CPUs | **106pass15.98s**; includes pipeline/circuit/scheduler/export and backup regressions |
| Current installed API catalog: Docker build plus `pytest /tests/unit/catalog -q` v7 | API image9344fbc...,1 GiB/two CPUs | **217pass49.80s**; conservative conflicts/hung sample/hostile prefixes included |
| Full API: `pytest tests -q -o addopts=''` v7 | Fresh standalone tracked source copy/current API+core; own DB/downloads, Git-enabled validation image, Linux arm64,1 GiB/two CPUs | **414pass63.37s**; one baseline Starlette deprecation warning |
| Current legacy frozen package build and `frozen_smoke.py <binary>` | Native macOS27.0 arm64, Python3.14.7, PyInstaller6.19.0/hooks2026.3 | Build31.789s; loopback health**8.160s** on disposable state. Snapshot enforcement remains gated |
| Ruff, Python syntax, `git diff --check`; docs `pnpm --prefix docs run build` v15 | Current source/local toolchain, including revised STRM harness | Pass; docs**5.16s**. Existing bundle/highlighter warnings remain; no remote CI dispatched |

Prior installed image digests (superseded by the increment records below):

- Worker: `sha256:b700df2bb3e2025ce0ef601396cce97b94fc392188d7f91414df1f6914e55de9`.
- API: `sha256:9344fbc37aae91183b6d9ad70769dc15effe113898a9a6de2cbb2c05ceb04df1`.

Locks remain core`8a63698fc5bfd26d5c8575b011b84a2140efed67c5a4ae7ffece06727695d845`,
worker`c3fc7c6857ac0ad4c53cd2467853b649e2388df6f76205bca498fe6f531e023e`,
API`b04051e9231fcfe43659331bf7e18f0d40e3b6970e581e528199afe83bb386bb`.
Native amd64/Windows environments are missing. Prepared native CI has not run;
Rosetta's recorded256-MiB child SIGTRAP remains failed emulation evidence.

## Capacity and freshness verdict

Identical generated50k titles/1m entities/2m releases: original schema1
**2169835520 SQLite/646634545 zstd bytes** failed maximum caps. Selected
schema2 bulk publisher preserves all seven logical row hashes and public IDs,
first_seen/provenance: **1050562560 SQLite/257838610 zstd bytes**, within unchanged
default1-GiB/256-MiB caps. Physical schema versions are explicit; worker/API private
state is not overwritten by artifacts. Exact DDL/validators/goldens and oracle
relationship mutations accompany the change.

Actual supervised publication, worker2 GiB/two CPUs/child256 MiB:
full v7**195.564s**, RSS182968320/cgroup2147483648 bytes; modest v9**14.078s**,
RSS194936832/cgroup1389490176. Repetition v10**138.280s**, same bytes/hashes,
retains verified synthetic output for consumer checks. These are individual
runs, not isolated before/after or endurance measurements. SQL export keeps
recent index interleaved for compression; defer-all323-MB failure is retained.
Measured full build cost justified finite180→360s publisher deadline; validator
120s, all resource/artifact caps, rates and cardinalities remain unchanged.

Full actual bulk artifact + mapped private overlay,1 GiB/two CPUs/eight readers:
`capacity.py consume --local-refresh --refresh-case mapped` v11 **passes**
activation56.185s, saved readiness1.020s, p95/p99**271/282ms**. Full Writer fixture
`validate-shaped-capacity.sh <signed-50k-dir>` v4 **passes**, actual10-Mbit/s TBF:
install281.548s, saved1.984s, p95/p99**52/87ms**, cgroup1073741824,no OOM.
Source image6d62fa6...,iproute2 6.15.0/libbpf1.5.0; failed120s validators stay
failed in11. Consumer and publisher memory counts include child/file-cache cost.

The original full-active C4 freshness experiment **failed** and remains in11.
The maintainer now authorizes signal-driven targeted collection. The current
strategy is03's bounded recent-page hints with separately measured historical
reconciliation. No recent-window overlap establishes complete change coverage;
M0–M4 and sustained C4 remain open pending the measurements below.

## Full artifact overhead diagnostic

`artifact_overhead.py --source <signed-bulk-50k-dir> --root /tmp/run`, worker
b700df2..., Linux arm64/2 GiB/two CPUs,256-MiB child/1-GiB file limit/600s outer
deadline. Identical50k/1m/2m copies are rebuilt/vacuumed; retained release fields
are compared by SQL set equality. Reduced schemas are intentionally invalid,
never signed/published, and are not product alternatives or lower-cardinality
capacity passes. v1 failed disk I/O while rewriting a populated release table;
fresh construction avoids that intermediate duplication without raising limits.

| Diagnostic layout | SQLite bytes | Compressed bytes |
| --- | --- | --- |
| Full vacuumed control | 985956352 | 401205698 |
| Without RSS index | 825245696 | 323618791 |
| Without RSS index and first_seen column | 816758784 | 323458523 |
| Without explicit canonical lookup/entity indexes | 970477568 | 393935067 |

RSS index costs**160710656 bytes** SQLite; first_seen column adds**8486912**
without that index. Explicit canonical indexes cost**15478784**. RSS LIMIT100
three calls: indexed22–65 microseconds versus117ms without index; canonical
lookup/entity probes4–19/3–11 microseconds versus2–3/25–26ms without indexes.
These standalone queries are not HTTP p95 or isolated end-to-end comparisons.
Largest control objects: release_data190996480, RSS160710656, entity_data157941760,
public release-ID unique index149065728; canonical episode/title data29450240/
5873664 plus their indexes. v2/v3 cgroup peaks2147483648,no OOM. Build/copy/
vacuum/compare19.357–24.891s, compress2.853–3.506s. Diagnostic VACUUM expands
compressed transfer versus the257838610-byte production layout: page ordering
matters. Production export/schema/required indexes/discovery semantics stay intact.

## Clients, quality, recovery and migration

Real pinned Sonarr**4.0.20.3014** digestf247545d... and Radarr**6.4.4.10685**
digestadb6c09d...: `validate-arr-rss-workflow.sh` v10 **passes** historical missing
content via ordinary explicit search, no unmonitored bootstrap jobs, exact1050
new GUIDs across activation during pagination, exact1000 catch-up GUIDs after a
controlled23h cursor gap, normal58.11/58.26s backoff and actual client/API restart.
Three monitored jobs remain paused/zero attempts; GUIDs/hashes unchanged and
zero RSS quality enqueues. Original exhaustive-bootstrap100/1000 failure stays
failed in11. No client control service, stored credentials, remote search or
library-wide automatic backfill exists. Tests use generated associations; no
provider/import/playback proof from this RSS run.

Generated real Prowlarr2.6.5.5623→Sonarr TV and Radarr movie query/grab/import,
Unknown/size0 and restrictive profiles, blocked/pause/retry/cancel/restart passed
separately in11. Actual generated Sonarr/Radarr copied-STRM import/FFmpeg decode
passes with explicit client SDTV profiles; AniBridge does not assert SDTV.
`validate-arr-strm.sh` (Sonarr default) and `ARR_KIND=radarr` movie v1 both exit0
on current installed API9344fbc.../workerb700df2..., Linux arm64/two CPUs,
API/client1 GiB and worker2 GiB. Both Unknown-only profiles reject the client's
SDTV/480 interpretation at search size0. Explicit Unknown+SDTV permits grab,
durable163-byte completion, actual library import and one-second FFmpeg decode
through generated HTTPS media. Sonarr peak API/worker/client342114304/42291200/
309207040 bytes; Radarr343158784/41525248/304775168. Fixture resolver/DNS/TLS
remain injected. Live-provider import/playback remains unverified.

Selected estimate contracts pass actual hung-process cleanup5s+2s, private/HTTP
URL refusal, hostile HLS prefix isolation, codec/size unknown and scope/conflict
persistence. Review found three stronger failures before conservative repair:
conflicting height/host/variant now suppresses inheritance, exact latest evidence
remains, malformed optional/pending JSON cannot stop search/queue. The additive
private flag preserves valid old rows and changes no identity/SQL schema/budget.
Fixture network/resolution tests are separate from the real-client runs; complete
provider/client disagreement/host/special matrix is still open.

Named **C6 matrix passes**: released0001/0002/0003/exact unversioned003, all seven
interrupted/three terminal states, retained aliases/files/STRM/bytes/hashes,
four real backup SIGKILL boundaries/two sync failures, six later-DDL SIGKILL
boundaries/restart/restore, actual pinned PR119 schema61351bb... and unknown
schemas rejected unchanged. Focused backup matrix20pass25.98s; pinned rejection
2pass1.77s; current full API includes both. Worker backup independently rejects
corrupt/foreign/provider/symlink/racing-invalid copies and never overwrites;
19 focused native checks/four backup crash boundaries pass. This is not exhaustive
SQLite/VFS fault coverage or a migration of any real installation.

600 actual activation SIGKILL cases (six boundaries×100/eight readers) and real
640-MiB tmpfs ENOSPC last-good/floor/recovery pass named C3 subsets. Source/key/
clock/bomb/checkpoint/ownership tests supplement them. Some crash proof predates
schema2; every internal fsync/storage fault/per-constraint inventory remains open.
One-writer three-provider100k-title listing pipeline13.697s/911314944 peak bytes,
large10k/50k job recovery/encoding/TTL **passes** bounded batches/streams (50k
recovery1.257s, peak202051584); no sustained HTTP/24h or live-freshness inference.

## Live inputs, operations and final audit

HTTPS Serienstream alternatives parse the supplied exact episode in Docker;
logical provider key remains`s.to`. Original DNS failures remain historical.
Megakino21 film6444/approved metadata5270 return script stubs: canonical provider
association and usable offers are absent. Two bounded authorized TMDb token
requests succeeded; token/key remain in the supplied0600 local files, not Git.
An accessible TMDb record is not evidence of its association to an unusable
provider page or redistribution permission. Earlier exact AniWorld extraction/
203921375-byte remux/probe is separate historical proof, not latest mapping→client
import/playback or rights clearance. **C5b remains blocked**: usable Docker/provider
metadata/offers and specifically authorized complete media inputs/rights for
one path per provider are required. A page URL alone does not supply media rights.

Fresh pilot volumes, stopped verified backups and matching binary are required
for rollback; never discard user state/downloads. Mainline `.pre-catalog-v3.backup`
and worker `.pre-v2.backup` are distinct. Artifact schema2 is incompatible with
older schema1-only clients, which retain their compatible last-good snapshot;
valid v1 remains accepted by this client. Canonical export approval stays empty
by default independently of credential configuration. Official defaults absent.

Source audit including the overhead and Sonarr/Radarr STRM harnesses: **372files**, fingerprint
**b897787e0058b861b91fe9ca964249d8a86e3d5f8687b9681b3684296a71d190** using the
baseline procedure (documentation excluded).252changed files versus handoff:
all Python parses; no supplied credential bytes, binary/media/database artifacts
or data/ files in the task diff; no untracked task files. All task source matches
committed HEAD; no unrelated changes were staged. The current local commit
inventory is in12. One earlier continuation commit c6246e6 body contains literal
newline escapes; it is preserved under the no-history-rewrite instruction.
All subsequent bodies use real multiline files. No push/PR/publication/production
change occurred; C7/C8/M5 remain closed. **M0–M4 readiness remains incomplete**.

## Megakino bounded cookie bootstrap (2026-10-01)

The maintainer explicitly keeps C5b live Megakino media/import **blocked** and
authorizes transport investigation without downloading media. Actual Linux
arm64 Docker worker2-GiB/API1-GiB containers, httpx0.28.1, verified HTTPS and
public DNS pinning: original homepage200/222 bytes → exact same-origin token
204/0 bytes → one retry200/82849 bytes. Movie5270:200/256 →204/0 →200/47796.
No redirects. The token cookie is host-only, Path=/, Secure, HttpOnly and has
expiry; the retry also sets a host-only session cookie. No values were logged.
Procedures: `/tmp/anibridge-megakino-bootstrap.py`, then separate current-source
shared `megakino_session.fetch` and local `Budget.get_megakino` probes in Docker.
Each implementation probe consumes exactly3 requests; local48052 total body
bytes, shared47796 final bytes. No media-host requests or movie downloads.

Metadata reaches a real title and three iframe elements, but **no explicit
selectable language**, structured year or IMDb association accepted by the
adapter. Local offers returns zero supported explicitly labelled offers. The
site-wide phrase 'auf Deutsch' is not episode/player language evidence.
Transport is fixed; parser/canonical/live extraction support remains unverified.
The previously observed stub failure remains historical, not relabelled passed.

Shared and local paths recognise only the exact bounded stub, bridge the
maintained cookie jar to the logical origin, and retry once within existing
budgets. Ordinary transport cannot request the token query. Deterministic
shared tests12pass0.05s; Linux local-resolution/refresh-child tests28pass1.76s.
These used generated cookies/pages, current read-only source overlays on prior
installed images; they are not new installed-image or live media proof.
Context7 HTTPX documentation and its primary Cookies API/extensions were read;
HTTPX0.28.1 is pinned in the projects. No insecure HTTP alternative was used.

## Signal strategy and full-history scheduling (2026-10-01)

The maintainer selected recent-change signals and targeted collection. The old
full-active1050000-page/875h bound stays failed in11; no rates/cardinalities were
reduced. Worker private schema3 adds durable windows/pending generations/leases,
actual reconciliation-start accounting and validated canonical hint caches.
Atomic page facts/acknowledgements prevent a crash from discarding a new hint.
Public schema2, GUIDs/magnets/first_seen and API mainline migrations are unchanged.

Permitted Docker page inspection via verified pinned transport: AniWorld200/
205215 bytes,148 deduplicated episode/language hints (heading150); Serienstream
200/318696 bytes,177 hints. No unknown languages or usable recent pagination.
This establishes selectors, not complete change-log behavior or latency.
Megakino HTTPS sitemap200/886758 bytes,6073 URLs/lastmods,939 distinct unsorted
lastmods; every URL points at foreign `megakino3.com`. Strict adapter refuses it;
no foreign URL was fetched or treated as an update signal. Homepage cookie retry
reaches HTML but no reliable monotonic listing/update contract was established.

`incremental_capacity.py --source /fixture --root /proof/run-v1`, installed worker
image8f45b6c... with then-current core/worker read-only overlays, Linux arm64,
2 GiB/two CPUs. Known signed original fixture50k titles/1m entities/2m releases;
real stored queue**1100000 pages**, not a smaller active fixture. Four generated
60-release language-addition intervals use simulated15m provider clock and real
SQL checkpoint/admission: **240 targeted +4 signal +59 historical requests**;
**1 targeted request/new variant**; intervals drain**148/150/150/150s simulated**,
14/15/15/15 historical pages progress. Claim p95**0.000508s**,max**0.007979s**.
Restarted four times; first_seen preserved, final2000240 releases. Wall280.612s,
CPU67.438s,RSS85131264,cgroup2147483648 bytes,no OOM; private DB growth315392.
The simulated150-hint displaced window, reordering, day outage, unknown label
and provider failure leave a persistent gap/backlog151, no deletion/coverage lie.
No HTTP, canonical HTTP, publication/installation or24h is proved by this run.
At240 historical starts/hour1.1m pages require at least4583.33h (~191d)/sweep.

Cache regression: initial canonical title/series uses2 requests; new entity,
language and restart reuse validated hints with0 requests, TTL expiry uses1
series request. Source dates/provenance stay original; missing correspondence
and duplicate names stay unresolved. Four actual Linux signal SIGKILL boundaries
plus admission overflow/detail-ACK fault tests preserve whole checkpoints.

`bash scripts/catalog/validate-private.sh` current installed wheels/images:
**worker132pass24.75s, core273pass4.69s, API catalog218pass52.50s**;
synthetic HTTP install0.224s, blocked job persisted. Worker
`sha256:6384025c58bfc614362d9d7beb202d9ebd7cb860a81c192f86eb75d89c479df9`;
API`sha256:e3100712608fba4ebeafa2dd9d6fa264517de4a777ac05f820a6ee999730ef6b`.
Both arm64; inherited dependency locks unchanged. This supersedes older installed
suite counts, not prior client/media/platform evidence. Full API/frozen/docs
checks above remain prior-source checks until refreshed for this increment.

## Dirty artifacts, retention profile and transfer cost (2026-10-01)

`dirty_probe.py` in installed worker2GiB/two CPUs, with generated test seeds:
initial compressed2877 bytes/hash87b1e0...; no-collection24h renewal has the same
hash/bytes and original listing time. Unchanged episode positive check dirties
and yields hash69bbd5...; unchanged complete listing yields732474.../2879 bytes
and truthful new listing time. Identity/first_seen remain unchanged. These are
small real export/compression measurements, not full-size build-cost proof.

`storage_capacity.py` records the calculation in03.100 distinct measured full
artifacts require25783861000 bytes, exceeding21474836480 default output bytes
before staging. This is a **failed default capacity model**, not an executed
100-publication run. Three current streams/72h need112159795350 bytes; ordinary
rechecks can cause the same full-artifact churn as sparse or full content changes.
The authorized opt-in full-retention profile is576GiB public/48GiB state, finite
and derived with compatible allowance/transfers/staging/headroom. Modest stays
available. Consumer/memory/rate/retention/protocol boundaries do not change.
Full stored private ledger measured2702184448 bytes informs state sizing.

Profile tests8pass0.04s native; Linux storage/CLI/publication focused33pass3.89s.
Actual Docker startup with an empty8-GiB tmpfs refuses
`storage_profile_free_space`: free8589930496 bytes vs496GiB combinedquota;
376 bytes of own config/lock,0 provider starts. This proves refusal, not producer
capacity. An initial overlay-filesystem probe saw thin virtual capacity and then
failed on the absent generated key; it did **not** prove physical496GiB availability.
The host has only about15GiB free, so full-profile production-retention stress
is **environment blocked**; no additional storage was provisioned. Mocked free
space tests do not substitute for that gate. Monitoring reports bounded counters
and warnings; startup cannot reserve or infer thin-provisioned physical backing.

Derived egress:12.376GB/client/day/provider at48 distinct snapshots;37.129GB
for3 providers.100/1000/10000 clients imply3.713/37.129/371.288TB/day, before
protocol traffic. Actual prior10-Mbit full install281.548s ×144 =40542.912s/day
serial work. These costs are bounds, not observed live traffic/billing/endurance.
No new distribution protocol or public operating approval is inferred.

The reviewed final sizing uses both current and compatible512-MiB artifact
maxima:435GiB retained +10.5GiB leases/staging,25% headroom, rounded to576GiB
output. State48GiB gives624GiB combined. The earlier448/496-GiB draft
underestimated the permitted current cap and was corrected before committing.

Final profile Docker build and installed worker suite: **140 passed/24.62s**,
Linux arm64,2GiB/two CPUs; image
`sha256:d7d4973841ccc4a359a06f5732998f17c6236be7b249844a4eb623118e79eff8`.
The corrected624-GiB combined profile again refuses on8-GiB tmpfs with
free8589930496 bytes,376 bytes of own configuration/lock and zero provider
requests. Commands: Docker build, `pytest /tests -q -p no:cacheprovider`,
`storage_capacity.py`, and the actual CLI startup probe described above.
Current core273/API-catalog218 passes remain the unchanged relevant runtime
checks; they were not repeated for storage-only changes. Docs build12.27s passes
with existing bundle/highlighter warnings before the final sizing correction.

## Full shaped consumer endurance harness (2026-10-01)

`DURATION_S=600 UPDATES=2 SWITCH_EVERY=2 INTERRUPT_EVERY=2 bash
scripts/catalog/start-sustained-validation.sh
/tmp/anibridge-bulk-fixtures-50k/fixture /tmp/anibridge-sustained-debug-v4`
passes the short debug subset in675.784s: two distinct full artifacts,5,010
queries; segments p95.044/.081s, p99.171/.158s, no query failures.
Actual publications60.088/55.348s,10-Mbit installs270.993/279.065s.
Source switch/saved recovery<10s, actual503 rejection preserves last-good,
new variants and baseline first_seen verified, two durable blocked/retry/
pause/cancel jobs. Final parentRSS152428544 bytes/20 FDs; consumer1GiB
peak/no OOM, source2GiB/256MiB childRSS106225664. Source artifact one is
257838808 bytes; full SQLite cardinality remains50k/1m/2m plus genuine variants.
This is **debug-passed**, not100 updates/24h, production retention or live proof.

Final harness adds minute source CPU/RSS/FD/disk/request-byte counters and
actual one-request hung responses. A focused actual HTTP timeout regression
measures15.153s and then recovers; rerun of the final code is recorded below.
Eight query readers are quiesced only for verification/acquisition after install
and source reconfiguration; real searches remain concurrent throughout updates.
No ninth query slot or higher resource cap was introduced.

Earlier debug failures are retained in11. Final spec05 defines finite failure
criteria and commands. Tools/image hashes are frozen into each owned proof
folder before launching detached Docker containers; no continuous agent
reasoning is needed. The source keeps two fixture blobs only and is explicitly
not evidence that the real worker meets72-hour producer retention.

Final storage documentation build **passes6.18s**, with existing bundle size
and m3u8 syntax-highlighter warnings. No remote CI or platform run occurred.

Final hung-response/counter regression: **15.1405s timeout**, next request
recovers, metadata byte counters match, no OOM. Linux arm64 installed API
`e310071...`,1GiB/two CPUs; current frozen-tool candidate, no full update.

## Actual sustained run launched (2026-10-01)

`bash scripts/catalog/start-sustained-validation.sh
/tmp/anibridge-bulk-fixtures-50k/fixture /tmp/anibridge-sustained-24h-v1`
launched at20:17:47UTC on Git`5c776623fec4383e4636c2e770fd3c15a4574bc7`,
run`ab-sustained-1790885856-36393`, duration86400s/100 updates.
Source shaper image`sha256:3b38cec947793bb868bc727ad8087198c9656e3757a701e07b4aeb87bc85e6a7`;
API`sha256:e3100712608fba4ebeafa2dd9d6fa264517de4a777ac05f820a6ee999730ef6b`,
Linux arm64,2/1GiB,two CPUs. Frozen script hashes:
consumer`f2e06113599ce3c051b171ecb98f75e9af99b56319b54870d6a24105bc6b459e`;
child`d9ca48df75a2aa93ac1679e527e3b2db23c572aff5aa93d89967014aeb4049f5`;
source`b52134da6bd6b2b9c0b4dd8b155924061eb6fcd272cb937711b6f86ccb72ed74`.

First actual update completes at315.516s: publication49.2715s, shaped
install264.980s; source body bytes257840019, parentRSS43704320/no OOM.
The containers continue detached; **the100-update/24h gate is still pending**.
A quiet hourly thread follow-up checks actionable failure or completion, then
reviews results/resource trends and closes itself; no continuous reasoning or
repeat import/suite runs. A bounded local keep-awake process prevents idle sleep
for at most90000s. Manual Docker stop, host shutdown or unavailable desktop
execution remains an interruption, never fabricated endurance evidence.

Only owned debug large files/containers were cleaned after recording results.
No user data/credential or unrelated images were removed. Source fixture retains
two blobs and does not close real producer retention. Storage physical capacity
and native platforms remain blocked; provider-window end-to-end freshness and
all-provider canonical/media proof remain separate open cases.

Source audit after5c77662:392 files, fingerprint
`13839269e9eed911179a9bdff40f1bb201d038ef4b6929aaa94d9e70f1bd3d8b`,
272 task-diff files; Python syntax valid, no supplied credential bytes or
database/media/binary/data artifacts, no untracked task files. No push/PR or
public/production action occurred. Documentation-only records follow this SHA.

## Supplied movie metadata refinement (2026-10-01)

Inspected only the saved authorized movie5270 response: the `pmovie__year`
field contains countries, the year anchor, and runtime. Initial generated
pure-year tests passed but actual HTML failed the32-byte content limit twice.
This exposed an incorrect selector, not a reason to raise the limit. The final
parser captures only visible year text on the exact same-origin release-date
anchor within one bounded closed field;32-byte content/body limits remain.
Generated tests cover URL-only/generic years, unknown language, duplicate/foreign/
query/invalid/unclosed fields and structured metadata conflicts. Raw HTML is not
committed. No provider request or media request was added for this refinement.

A Docker source-assisted core probe plus installed worker uses the supplied
0600 credential file read-only (root in this disposable probe to read the bind;
service ownership/credential mode unchanged). Exactly2 actual verified HTTPS
TMDb requests, `/3/search/movie` then `/3/movie/516729`, take0.5582s.
Worker persists`tmdb-movie:516729`/`imdb:tt5822536`, `tmdb-v3` provenance,
exact-title-year/explicit-ID evidence, checked time and restart reuse with zero
extra requests. Observed provider year2024;0 selectable languages/1 unknown/
**zero releases**. This proves one supplied target's private metadata association,
not complete discovery, offers, publication, media, client import or redistribution.
The current supplied page therefore needs no additional TMDb input.

An adjacent canonical flaw is corrected: title/year search results previously
validated the detail ID but could accept a contradicted title/year. Independent
detail matching now rejects wrong/missing year or different title while retaining
explicit verified IMDb binding semantics. Targeted worker tests18pass0.73s and
API refresh/resolution43pass8.57s (one existing deprecation warning) on the
intermediate package. The first API test command used a nonexistent filename and
ran0 tests; the corrected named files are the stated43-test result. Final
installed-package checks and image identities are recorded below.
Context7 retrieves primary TMDb search/detail/Bearer documentation; no credential
values or response catalogs are retained in Git, and source rights remain closed.

Final metadata image checks: installed core **287pass8.51s**, worker
movie/adapter **18pass1.09s**, API refresh/resolution **43pass10.86s**
(one baseline deprecation warning); actual saved-response installed parser
returns2024/zero languages/one unknown without network. Worker
`sha256:244d8774958f0f4f58db0686b9d9a2402a91f5d94a9193ec7502a710851a7674`;
API`sha256:e3d820efde7ac27d20456b601a7bdc474dfb0f6c109e96e7bb5cacdcb322ae9e`.
These are installed Linux arm64/two-CPU2/1-GiB checks on the final selector,
not a repeated generated-media or whole-client integration suite. The sustained
run retains its original frozen image/tool hashes; its unchanged consumer
snapshot/lifecycle paths are separate from provider-parser evidence.

## Retention boundary and failed-history correction (2026-10-01)

Final source review found a concrete defect: failed reservations contributed
timestamps to supersession, allowing an older third artifact's grace to end
before its actual successful replacement+72h. The original helper fails the
new generated-filesystem regression; fixed code preserves the exact boundary
and removes only after it, with1 and100,000 failed reservations retained.
Existing actual process-shared lease tests still pass. Retention now streams
successful/private-current rows and holds at most two distinct candidates;
older irrelevant rows cannot grow a lifetime Python list or set. No private
history, referenced artifact or grace duration is discarded.

Sizing now includes cleanup-before-publication and the inclusive boundary:
146 generations,112933311180 bytes for three measured current streams; worst
current+compatible caps438GiB plus10.5GiB leases/staging,25% headroom560.625GiB,
round32GiB =576GiB. Thus the default full-retention quotas remain576/48GiB.
The3600s cadence requirement becomes320GiB rather than288GiB. Earlier145-slot
calculations remain historical models, not newly relabelled measurements.
Native generated storage/retention/publication tests **32pass1.05s**; this is
not native resource enforcement or full producer-retention capacity. Current
Linux installed results are recorded below.

Final installed worker regression **146pass23.83s**, Linux arm642GiB/two CPUs;
image`sha256:8a175ea0871460e67f834e7195f5c1589694966046caf7fc2c25bb332f80bc43`.
The current146-slot model executes and returns576/48GiB; this is arithmetic
plus functional failure/lease proof, not actual full-profile producer capacity.

## Sustained resource sampler refinement (2026-10-01)

The consumer's original resource loop samples during idle wait, leaving install
phase gaps. An independent detached sampler now reads only owned container
PID1 RSS/FD, cgroup CPU/peak/OOM and owned-state bytes every60s, without queries
or changing the frozen source/consumer tools. Initial warmup has idle-only
samples/cgroup peaks; do not describe it as continuous minute tracking.
The first companion mistakenly counted both source and consumer through the
source's parent mount; its small archivedv1 samples are labelled unusable for
per-source disk accounting. Correct scope samples show source1566242353 and
consumer2105562196 bytes, RSS44.2/188.2MB, FDs4/19, no OOM.
Archivedv2 samples remain valid; v3 adds normal-completion race handling.
Current sampler hash`a2246dddc389a2a73b5fcbe2f976e05eee89f336049729b890b11501a84f6fb4`.
An actual `--once` probe passes, and a separate already-completed-input command
terminates without probing or changing its result. New launchers freeze/start
this sampler from the beginning; no extra full-update run was performed.

At2068.232s the real run has3/100 distinct updates,25,516 concurrent queries
with no errors, p95.086s/p99.119s; third publication66.865s/install271.512s.
This is progress only, not24h/100-update completion. Source/consumer frozen
hashes remain unchanged after companion attachment and metadata fixes.
The quiet follow-up reviews all monitor segments, any sampling failures and
actual outcome before marking the consumer subset; producer retention remains
separate and blocked by physical capacity.

## Conservative publication-time grace (2026-10-01)

Review also confirms signed published_at is captured before construction.
Retention now adds365s for the unchanged360s supervised build budget plus
reaping/timestamp/admission rounding, preserving at least72h after replacement
visibility under the existing clock/deadline envelope. The finite margin does
not raise a resource deadline, discard timestamps or change the artifact/private
schema. Regression verifies the worst build-delay boundary as well as exact
effective grace and failed reservations.

Current sizing is147 generations:113706827010 bytes for three measured
current streams; capped current/compatible441GiB +10.5GiB working allowance,
25% headroom564.375GiB, round32GiB →576GiB. State48GiB and physical624GiB
startup requirement are unchanged; previous145/146 calculations are historical.
Focused storage/retention/publication tests32pass1.08s native. Final installed
focused check and image are recorded below; the full146-test installed worker
check above predates only this margin. Actual producer capacity remains blocked.

Final timing-margin installed focused worker checks **35pass5.73s**,
Linux arm642GiB/two CPUs, image
`sha256:a7105905c7d27b0c8ad9ea10fa804c0bb364306701474495c8f9258113d3ca1a`.
Includes storage/retention/publication/process-shared leases and CLI. Full
worker146pass23.83s remains the preceding full-suite check; core287 and
API-refresh-resolution43 checks are unchanged by worker-only timing constants.
Final documentation build **passes6.69s** with existing bundle/highlighter
warnings. No new native platform, live-media, production or public evidence.

Final continuation audit aftera27126f:396 source files, fingerprint
`ac872a48df69bfb504cf65375aa5aef40f9aa893dc0d6f507be076588b16255e`,
276 task-diff files; Python syntax valid, no supplied credential bytes or
forbidden database/media/data artifacts, no untracked omissions. The final
committed tree matches the intended task working tree; no history rewrite or
unrelated change occurred.

Latest real sustained progress: 6/100 updates at4666.641s,
63013 queries, p950.087s/p990.110s,
zero recorded query failures. No final result yet;100 updates/24h remain pending.
The current CLI consumer inherits an API web-server healthcheck and therefore
reports Docker unhealthy despite progressing normally (no web server is started
by this harness). Use process state/result/monitor failures, not that irrelevant
HTTP check; future launcher runs disable only this test-container healthcheck.

## Two-snapshot retention and total budget (2026-10-02)

| Gate/subset and command/procedure | Environment/version | Result and limit |
| --- | --- | --- |
| C2/C4 worker installed checks: Docker `pytest /tests -q -p no:cacheprovider` | Linux arm64/Python3.14.7/HTTPX0.28.1;2GiB/two CPUs; image08861a0... below | **154pass26.30s**; includes two-snapshot/schema transition,100,000 burned reservations, pointer-before-bookkeeping, process-shared transfers, inode race, cache/error headers, sparse quota exhaustion/startup GC without DB mutation, backup reservation/preservation, private scratch and deleted-open sort accounting |
| Final worker focused CLI/storage/retention/server/export | Same limits; reviewed image44ed9c... below | **29pass3.32s** after adding canonical-enrichment/operator admission; no additional full suite needed for this narrow CLI change |
| Consumer installed update/runtime/activation/trust | Linux arm64,1GiB/two CPUs, imageeda046... below | **47pass20.94s**, one baseline Starlette deprecation warning; real HTTP404/410 refreshes cached pointer unconditionally with no-cache, one retry, repeated miss preserves readable last-good/floor |
| Full producer footprint: frozen `retention_capacity.py ... --reuse-owned-pressure --updates 3` | Same worker envelope, image08861a0...; disposable known private ledger plus independent pressure copies; no provider/client/network requests | **556.889s**,3 full distinct actual publications163.720/162.319/184.184s.50k titles,1m entities,2,000,240 releases,50k canonical titles/1m episodes; no cardinality/filter reduction. Peak accounted**20,226,560,160 bytes** including1-GB runtime allowance; managed19,226,560,160; state16,335,749,696/public2,890,810,464. Includes staging and unlinked-open sort bytes. Final entire proof root17,901,876,960 before runtime allowance. NoOOM; cgroup peak2GiB including page cache/children. |
| Prior full-mapping repetition | Installed image98f604... (build log); same pressure root |4 actual full-mapped publications159.468/169.166/150.879/153.424s, total673.127s; accounted peak20,478,906,560. This earlier scan omitted deleted-open temp files and is supplementary; final scan above owns the current footprint claim. |
| Local static/config/documentation | Compose `config --quiet`, targeted Ruff/Python/shell syntax, `git diff --check`, docs build | Passed; final `pnpm --prefix docs run build`5.45s, baseline bundle/highlighter warnings. No deployment or native enforcement claim |

Full-pressure experiment uses six independent2.7-GB ledger/backup byte copies
(three live/one backup each), four other-provider-sized snapshot copies, actual
50-MiB log files, one real AniWorld publisher and a leased old artifact. The two
inactive replica datasets provide **storage pressure**, not valid collection or
publication proof for s.to/megakino. Final iterations retain two distinct real
artifacts/two needed manifests and two tiny publication rows, preserve discovery
identity/time checks and burned floor; the old third artifact survives its lease
and is removed after release. One active old blob is executed;16 distinct old
transfers remain a derived bounded allowance, not this measured workload.

Current model includes16 old transfers at256MiB plus six measured snapshots,
six measured private ledgers, one1.342-GB staging,52.4MB logs and1GB runtime:
about24.45GB. It does not guarantee arbitrary state growth or two full legacy
backups/provider (24.32GB state alone). Quota/free-space exhaustion stops safely,
verified backups remain intact. Startup can first collect obsolete prior-policy
output under read-only recognized-state preflight and transfer locks, plus owned
abandoned staging, without changing DBs or discarding compact checkpoints.
There is no retained catalog generation series or new periodic full backup.

Images: full/counter154-test
`sha256:08861a0ecbb8d6bc34a883623e0d79215ee902b97683a8abc1fee3da01b7878f`;
final CLI-focused
`sha256:44ed9cfafbf8bf1e7c7d0b1f0780566f640f4eacb5955e476fac250e74a41e37`;
consumer
`sha256:eda046f65f6e242c8938fa47e53a04b9a2fbae03a3b6a880e770275b3d10dd91`.
Measured worker image64,562,016 bytes fits the conservative1-GB runtime allowance;
Compose now bounds worker daemon logs to3×10MB. The frozen final footprint tool
hash is`1bd23b49ad85846fd8dfc240d415bd7ddc063ee807705befbaddecefeaf7e795`;
its later committed type annotations/formatting are separate from executed input.
Supplementary full-mapping v4 image (from its retained build log):
`sha256:98f60489d4a468ceb4236fce1f64684bfe9cfda987eb6d05f5c358ac9b3cba8a`.
Known synthetic fixture compressed SHA
`0a1194c4a040537bd0176ee7f222048b72faf0ac74c99e03b563235de5ae0f4c`.
Known generated private ledger2,702,184,448 bytes, SHA
`c6edbfedacc1b6a2680a64ef975aa3af1a83327ae952a24b4d4e2f793daa404c`.
Private result/tool metadata live under
`/tmp/anibridge-retention-budget-v3` and`/tmp/anibridge-retention-budget-v5-tools`.

Final artifact**257,890,344 bytes**, SQLite1,050,615,808 bytes. At48 distinct
updates/provider/day, three selected-size providers imply37,136,209,536
bytes/client/day and1,114,086,286,080 over30 days;100/1000/10000 clients multiply
that total. At10Mbit/s the raw body alone is206.312s/snapshot (8.25h/day serial
bodies for144); the earlier actual full install281.548s models11.26h/day.
These are measured-byte **models**, not observed live cadence, sustained installs
or billing. A single episode or truthful recheck changes the entire snapshot.
Unchanged pointer polls skip artifact transfer, but a new daily signed revision
currently re-downloads identical bytes even after worker reuse: no-collection
three-provider renewal model773,671,032 bytes/client/day. This is a concrete
consumer inefficiency, separate from retention, not silently hidden behind reuse.
No delta/shard/distribution protocol change or consumer memory increase is added.

M0–M4 remain incomplete. The earlier real24h/100-update run is failed, its120s
validator timeout cause unresolved, with saved active/floor10 preserved.
Six-hour end-to-end freshness, selected provider/client/fault matrices, native
amd64/Windows and live Megakino media gates remain open/blocked independently.
The rejected576-GiB environment requirement is superseded, not a current blocker.
No new maintainer decision/credential is required for this retention revision.
M5/public launch stays closed.

Actual final procedure: Docker `--rm --memory=2g --cpus=2 --entrypoint python`,
frozen v5 tool bound to `/retention_capacity.py`, generated ledger to
`/source.sqlite:ro`, generated catalog directory to `/fixture:ro`, with
`/tmp:/proof`; invoked `/retention_capacity.py /source.sqlite /fixture
/proof/anibridge-retention-budget-v3 --reuse-owned-pressure --updates 3`.
Only the owned proof root was written; future reproduction should bind that
root alone rather than all temporary files. No provider requests or user
installation data were accessed.

Failed endurance resource inspection:116 minute samples over6919.606s after
warmup. Source parent RSS44,228,608 bytes throughout, FD4–6, stored bytes peak
1,824,092,215; CPU increases446,642,180µs. Consumer parent RSS190,136,320→
193,937,408 bytes, FD19–37 (last19), stored bytes2,105,564,420→3,414,312,501;
CPU increases1,892,148,229µs. Cgroup peaks reach2GiB source/1GiB consumer;
consumer memory.max events90035, OOM/OOMKilled zero. These counters include
page cache/children and do not explain the120s validator timeout; no sustained
pass or leak-free claim. Monitor-failed absent and monitor-finished present.
Final minute sampler hash alone is
`a2246dddc389a2a73b5fcbe2f976e05eee89f336049729b890b11501a84f6fb4`;
it is separate from frozen source/consumer/fixture hashes in run.json.

Preserved result/progress, durable jobs DB (active/accepted floor10), exit/final
Docker state, all sampler segments, frozen tools, small receipt metadata and
large-file hash inventories. Removed only the two stopped owned run containers/
network and owned source/consumer catalog files; removed completed capacity
pressure state/output after preserving inventories. The follow-up remains
paused and only its owned keep-awake PID was stopped. No broad Docker cleanup,
provider media download, user installation migration or production change.

Local commits so far:`ee96fef fix(catalog): recover from superseded snapshot
references`;`67b3937 fix(catalog-worker)!: bound snapshot retention to 30 GB`.
Final source audit covers397 source/config/test files, fingerprint
`098ba3279738be6919b6b539f5666c5e3882b6ca7a6ff4193b0f95fdb5719783`.
Changed tracked/untracked task paths contain no supplied credential bytes,
forbidden data/media/database artifacts or Python syntax failures. Frozen
executed harness and image hashes remain separately recorded above; the
committed fixture subprocess-string formatting change has no runtime effect.

## Trusted identical-artifact renewal (2026-10-03)

Current source implements signed manifest verification plus bounded retained
file hashing before zero-body renewal. Receipt context binds source/origin/pins;
NULL/old receipts receive full semantic admission once. Migration0008 preserves
old rows and mainline state. Shared activation atomically persists trust floor,
manifest, receipt and registry generation, retaining previous distinct content.
Missing files use full download; invalid manifests/corrupt local bytes leave
floor/last-good untouched. No deadline/consumer cap/distribution change.

Installed API image `bfc069b2bf65bfe54ec4881ec6f9360ada2586451b603aefbbc9bb83d2a919cc`:
`pytest /tests/unit/catalog /tests/unit/db/test_migrations.py -q -p no:cacheprovider`
**249pass64.16s**, Linux arm64/Python3.14.8/SQLite3.46.1/HTTPX0.28.1,1 GiB/two
CPUs. Real local HTTP tests count zero artifact bodies at renewal and after
restart; trust changes require full admission. Atomic/cancel/corrupt/missing/
invalid manifest and nullable migration/DDL-interruption cases pass. First run
67pass/1fail used identical bytes in the obsolete-remote-artifact test; corrected
that fixture to genuinely distinct content rather than disabling renewal.
Logs `/tmp/anibridge-renewal-tests-v{1,2}.log`; no live providers/media involved.
Full-size short and renewal evidence follows separately; sustained proof remains open.

## Fresh exports and bandwidth (2026-10-03)

Six actual full-cardinality worker exports pass metadata/hash/discovery checks:
unchanged is byte-identical; listing, title observation and canonical checked
timestamps produce distinct artifacts.60 new language releases cost a257.885-MB
full artifact; even offline1-MiB chunk reuse would transfer176.783 MB due to
compact-key/index churn. Timestamp-only changed chunks are0.240–0.499 MB.
The six cumulative cases retain50k/1m/2m counts plus the60 genuinely new variants.
Peak isolated accounted footprint6,107,614,272 bytes; no CPU/RSS trend sampler
for this bandwidth subset. Exact commands/tool/image digests, timings and failed
harness attempts are in11. Full worker footprint and endurance are separate.

48 daily distinct changes across three measured-size providers derive37.136GB/
client/day; hourly coalescing would still cost18.568GB/day. Identical signed
renewals now transfer zero bodies. Recommend first benchmarking stable internal
key assignment and bounded current→next binary deltas, with full fallback and
all bytes charged to30 GB, before designing/approving a versioned distribution
extension. Fixed byte chunks alone are ineffective for this sparse insert test.
No delta/sharding protocol, freshness relaxation or quota increase is implemented.

## Full shaped regression and HTTP renewal (2026-10-03)

Command: `DURATION_S=900 UPDATES=2 SWITCH_EVERY=2 INTERRUPT_EVERY=2 bash
scripts/catalog/start-sustained-validation.sh /tmp/anibridge-bulk-fixtures-50k/fixture
/tmp/anibridge-sustained-renewal-short-v2 sha256:bfc069… sha256:daa7ce…`.
Actual **900.881s/debug-passed**, two distinct full artifacts,10-Mbit/s shaping,
**8900 searches/zero errors**, segment p95.066/.052s,p99.073/.057s,12 durable
blocked/retry/pause/cancel histories. Publications43.952/45.166s, installs
261.402/261.833s; source-switch recovery0.738s,503 and15.037s stalled-response
failures retain revision1 before revision2 installs. Consumer exit0/noOOM.

Owned run `ab-sustained-1791043190-90246`, proof path above. Shaper image
`22ee7b3725ad1d26197b1ff59194bd092163306b87b9b4155a769fdcc4ddddc8`,
base worker`daa7ce8fc4e75f78aaa40a41b25c3a2c7dee465f7d95c15d88a934149e913c1e`,
API`bfc069b2bf65bfe54ec4881ec6f9360ada2586451b603aefbbc9bb83d2a919cc`.
Linux arm64/Python3.14.8/SQLite3.46.1, source2 GiB/consumer1 GiB,two CPUs each.
Frozen consumer/source/fixture tool hashes in run.json remain separate from
sampler SHA`4aa378fd878800fe6cf222be8cd514d082257f996b2ac65c55b7a4e9347f1e21`.

Independent sampler16 minute rows spans901.496s and finishes normally; no
monitor-failed file. It starts after source warmup and consumer launch, includes
subsequent installs, cannot measure prelaunch source preparation. Source RSS
42.557→43.606 MB,FD4–6,CPU87.228s sampled delta,disk1.051→1.566 GB. Consumer
starts30.31 MB before warmup,144 MB during initial transfer,185.65 MB after
8-reader startup, then187.78 MB plateau for the final three samples. Final after
reader shutdown155.103 MB. FD19 steady, temporary21/25 during second update,
final20 versus permitted baseline+8. Disk rises only with transfer/new retained
generation to2.102 GB; final private1.350 MB. Cgroup peaks exactly2/1 GiB,
noOOM; consumer CPU196.094s sampled delta includes supervised children versus
109.814s parent CPU. No CPU quota throttle; consumer memory pressure0.176s and
I/O pressure18.174s over the run, consistent with repeated local reads and
cache reclaim (memory.max15349). Warmup/replacement explain short-run steps;
this plateau cannot prove24h leak freedom. This is **not** a24h or100-update pass.

Full-size renewal command: installed API Docker run,1 GiB/two CPUs, isolated
network alias`worker`, `renewal_probe.py /original /proof` on copies of the
completed generated short-run DB/files. Proof `/tmp/anibridge-full-renewal-v3`;
script SHA`f58042c1a1009f3283b7341a98299c8989a207b26ff15bc9f028e1746e1c2f23`.
Source ID/origin/pins remain the same synthetic trust context. Real HTTP serves
new signed manifests3/4 and rejects any artifact GET. **Zero artifact bytes/
requests**,1050562560-byte SQLite, recovery0.664/0.608s and renewal0.774/0.697s
including restart. Parent peak86.876 MB,cgroup1 GiB,noOOM; cache reclaim remains
visible. Original short DB unchanged. Units separately prove trust changes,
invalid manifests and corrupt/missing file cases; no live-provider proof.

Preserved harness failures: short-v1 failed Dockerfile FROM before containers
(a named owned alias fixes local image-ID use). Renewal-v1 read-only WAL-mode
copy could not create shared-memory state; quiescent no-WAL input now uses
immutable read-only backup. Renewal-v2 had the wrong fixture pointer path and
returned404; corrected to the existing catalog/v1 layout. These are failed
harness attempts, not application regressions or relabelled passes.

Final renewal race correction: exact repeated poll now rechecks trust and
cancellation after hashing. Pre-fix reproducer1failed/1passed; current installed
renewal/update/snapshot/trust **54pass22.07s**, image
`713553d06dae362af6ecbd461bef57273638d2db74c3ef0f5046094104fbb2d7`.
Shared install/activation code passes**600 actual SIGKILL recoveries** at six
named boundaries with8 readers; APIbfc069…/1 GiB/two CPUs, recorded in11.
This small crash subset remains separate from C4. Docs build5.79s/Ruff/diff
checks pass. Original 24h failed result and all its limits remain unchanged.

Final current-image full-size renewal repetition also passes, proof
`/tmp/anibridge-full-renewal-v4`,API713553…; tool SHA
`41f5a5dd8f9641e8f6e0b551704f2feca4460193993a1b6ba6a311f4205a7a01`.
Real HTTP:4 pointers/4 manifests,zero artifact requests/bytes; recovery0.799/
0.638s,renewal0.796/0.662s,exact repeated poll0.614/0.637s,including restart.
Parent peak86.761 MB,cgroup1 GiB,noOOM. This is the short current-image
regression after the final guard; prior shaped two-update proof retains its
separately pinned image. No full-admission path changed after that shaped run.

## Second actual24h/100-update attempt — FAILED; launch record

Started2026-10-03T16:32:05UTC,owned run`ab-sustained-1791045121-3846`,
proof`/tmp/anibridge-sustained-24h-renewal-v2`. Same launcher command as the
short regression with default DURATION_S=86400/UPDATES=100/SWITCH_EVERY=20/
INTERRUPT_EVERY=25,using final consumer image
`713553d06dae362af6ecbd461bef57273638d2db74c3ef0f5046094104fbb2d7`,
worker base`daa7ce8fc4e75f78aaa40a41b25c3a2c7dee465f7d95c15d88a934149e913c1e`,
shaper`bf7bfcaa8e94e72a2a0e6ae6afdbb4b2c0265f61cdd7b04f567648c2aa6ac0b6`.
Launch Git head af40604; later documentation commits do not modify frozen inputs.

Frozen consumer SHA6dee4384486fda9d9b3e2a365a10c8627d3e31680d99945d5aa6c8a1713bca04,
source fb62a0a3d73b5e310bafcc81c736e2607dda58497f8aeee3de75707a173862c3,
fixture d9ca48df75a2aa93ac1679e527e3b2db23c572aff5aa93d89967014aeb4049f5;
sampler separately4aa378fd878800fe6cf222be8cd514d082257f996b2ac65c55b7a4e9347f1e21.
Detached minute sampling covers installs after source warmup,with explicit
prelaunch coverage limit. Both processes initially Running/ExitCode0/OOMfalse;
no completed result or sampler failure. Consumer healthcheck is disabled.
Host free disk22 GiB after preparation; no overlapping large experiment.
Earlier completed large copies were inventoried/removed,results/private DBs/
frozen tools retained; failed candidate reconstruction remains available.
The intentionally stopped short source ended137 after Docker's stop timeout,
OOMfalse,after the consumer completed exit0; this is cleanup, not a run failure.

Owned keep-awake PID5012 watches sampler3904,recorded in keep-awake.json.
Existing catalog-endurance-follow-up resumed hourly,quiet while healthy;
no continuous reasoning/suite runs. On completion/failure it preserves evidence,
checks resource trends and required elapsed/update semantics,cleans only owned
files/containers/network and disables itself. The two-artifact fixture source
cannot establish actual collector endurance,total producer retention/freshness,
live providers/client import or native amd64/Windows. Original failed run stays
failed. M0–M4 remain incomplete; M5/public actions remain closed.

Final source audit:404 files,fingerprint
`63244c055b8cfb488f01b0c836b037fe7f8c5ecc80348653e66ed9d9bbe37df3`,
no supplied-credential bytes/artifacts/syntax failures/untracked omissions.
Tracked source matches the committed implementation; only this evidence changed
after the launch. No push/PR/deployment/production migration/publication.

## Second timeout investigation and bounded regressions (2026-10-04)

Full procedures, hashes, failed drafts and coverage limits are in the dated 11
entry. Both original endurance attempts remain failed. No new 24h run started.

| Gate / procedure | Environment | Executed result | Remaining gap |
| --- | --- | --- | --- |
| C4 preservation:31-file rehash, 94 signed envelopes, readonly DB/frozen tools/Docker logs/inspect | Original 713553… arm64 image; proof `/tmp/anibridge-sustained-24h-renewal-v2` | Exact 93/92/91 bytes retained; active/floor 92, 1,822 cancelled jobs/zero leases; follow-up PAUSED, source stopped | Failed staging inode/cache state already gone; original lacks per-child stage/CPU/host-pressure counters |
| `validator_probe.py probe --cache-mib 32` isolated/8-reader | Same installed image;1 GiB/2 CPU, child 256 MiB/120 s |93 validates 44.618/45.913 s, 41.526/42.258 CPU;714 error-free loaded searches | Historical timeout not reproduced; fadvise does not prove cold host cache |
| Stage and older 11 comparison; bounded release-join experiments | Identical fixtures/caps; retained probe hashes in 11 | Integrity 13.297 GB/release 6.787 GB logical reads; older 11 validates 45.231 s; reordered/sorted joins rejected for unchanged/worse I/O | No justified validator algorithm fix demonstrated; byte counts are logical, not host physical I/O |
| Four copied-state real HTTP admission replays |713553…;1 GiB/2 CPU, 8 readers | Validator 43.310–46.789 s; receipts/floors/jobs/first_seen correct | Same-byte short evidence, not 92-update trend or sustained pass |
| Actual Runtime.poll retry: injected first TimeoutError, then real signed 93 admission | Installed c3444c9…;1 GiB/2 CPU;failed-run parent RSS target 200.827 MB |300.012 s actual retry delay; validator 45.931 s/42.438 CPU;5,082 error-free searches; whole job/request/alias digest unchanged | Injection proves scheduling/recovery, not cause of original deadline; backoff is process-local |
|900 s/two distinct full shaped updates; source switch/503/stall/history |c3444c9… API/9429052… source;10Mbit, full 50k/1m/2m fixture |**debug-passed 900.587 s**;8,666 searches, p95≤.072/p99≤.078;installs 260.267/264.929 s; 11 histories;normal 16-row sampler | Not100 updates/24h/actual worker footprint/real provider-client-media/native proof |
| Installed runtime/update/diagnostic tests; wheel imports outside checkout |c3444c9… Linux arm64/Python3.14.8/SQLite3.46.1 |18 focused checks pass; real traced valid/hostile child, timeout and diagnostic-write failures; Ruff/shell/diff checks pass | Full required C4/C5/C6/platform matrices remain open |

Demonstrated scheduler defect is fixed in 34249b9: after failed admissions,
retry 5/15/60 minutes, then normal phase; success resets the sequence. The
harness no longer loses accepted-update journals on late exception exits.
Fixture-only admission/pressure diagnostics are committed in e6e226a; future
launches freeze them too. Their production-cache mode leaves supervisor,
validator checks,120 s deadline and 256 MiB/1 GiB limits unchanged. Current timed
background trace uses a separately frozen earlier helper; final write-error
handling is covered by installed tests, not silently credited to that trace.

Original samples show late RSS plateau near 200.8 MB and increasing I/O pressure,
not an established leak or explained timeout. Earlier sampling gaps correspond
to host sleep, outside the final failure window. **The intermittent valid-update
admission timeout remains an unresolved defect/validation failure.** Present-day
replays have≥73 s timing margin; this does not establish that margin across 24h
or retrospectively explain the failure. C4 and M0–M4 remain incomplete.

Bandwidth remains a proposal: same-byte consumer polls/renewals transfer 0 bodies;
truthful worker rechecks that change exported observations and even sparse
changes can still dirty a ~258 MB full artifact. This short run transfers 515.680 MB
for two updates. The earlier 48-distinct-publications/day/three-provider scenario
is 37.136 GB/client/day. Keep local search and 30 GB total worker disk; benchmark
stable internal keys/bounded deltas in disposable experiments before proposing
an approved protocol. No delta/sharding/distribution change is implemented.

Native amd64/Windows, live Megakino media and all-provider canonical-to-client/
import/playback/end-to-end freshness remain separately open. No new TMDb input
is needed. Original failed inputs stay preserved; only the new short run's
five owned large files, two containers and their network were removed after
inventory; failed-run reproduction inputs remain intact. Docs build passes 5.84 s. No push/PR/production migration/deployment/publication; M5 stays closed.
