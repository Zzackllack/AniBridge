# Validation, measurements, and release gates

Build a deterministic fixture publisher/provider server for CI. It serves
synthetic title/episode pages, challenge pages, signed artifacts, corrupt
artifacts, and controlled failures. No tests should depend on scraped public
provider content or commit a real catalog to this repository. Live probes
supplement, never replace, deterministic tests.

## Contract and failure tests

- Sign a tiny known artifact with a test key; publish fixture bytes and
  signature vectors. Client accepts known-good v1 and rejects bad signature,
  wrong key, wrong provider, wrong source, wrong schema, rollback revision,
  path traversal, cross-origin artifact, truncated body, digest mismatch,
  decompression bomb, extra unexpected tables, and invalid SQLite.
- Simulate a crash at each publication/update stage; after restart, search
  sees either the complete prior version or the complete new version, never
  half-updated rows. Keep concurrent search traffic running during switches.
- Feed the collector 200/CAPTCHA, 403, 429, empty valid page, malformed page,
  title-count collapse, single-title 404, and transient timeouts. Challenge or
  parser anomalies never create mass deletion. Other providers continue.
- Restart the worker mid-crawl and after a writer error. Check persisted
  checkpoints, no duplicate rows, bounded retries, and completed prior work
  not repeated needlessly.
- Verify identical artifact protocol from official-style and self-hosted
  worker deployment, including custom pinned public key and explicit source
  switch behavior.
- Verify metadata provenance and rights filter: an unapproved canonical
  source cannot enter the public artifact; no cookie, token, job, media URL,
  or private path appears in an inspected artifact or log.

## Behavior regressions

Run exact Torznab contract cases against both current mainline and the new
consumer to record intended differences. Include search by title/alias,
season, explicit episode, TVDB/TMDb/IMDb IDs, rejection of rid/tvmaze, specials, s.to alternate
language, AniWorld anime, megakino movie and series, duplicate title across
providers, missing mappings, and wrong mappings with local override.
Validate RSS category, GUID, release name, magnet decoding, language,
season/episode numbers, result limit, and STRM mode. Include a case where the
catalog says an episode exists but no video host is playable.
For broad season searches, assert zero provider/video-host requests attributable
to synchronous search; optional background sampling obeys the one-scope rule
in 08. Compare unknown quality and scoped estimates against Sonarr/Radarr
profiles; verify size-filter behavior with size=0 for unknown bytes. An absent
height/codec must not silently become an asserted `SD`/`H264` release.
Verify cold-cache search returns without waiting for a sample; no assumed
720p fallback, per-episode probe fan-out, or unbounded background queue. Test
sample deduplication, deadline cleanup, cooldown and estimate scope. A local
ID hit must not contact a canonical source; a miss may use only the configured
bounded lookup and must not invent missing episode mappings.
For that case, exercise both an explicit episode search and a broad search,
then grab the result through AniBridge's qBittorrent-compatible API. Record
whether Sonarr/Radarr retries another result, leaves a queue item, or needs
operator action after an asynchronous job failure. Invalid grabs may be
rejected; temporary source failure must not reject an otherwise valid add.
Test challenge-blocked persistence across restart, paused jobs causing no
network requests, deduplicated adds, explicit retry/cancel, and catalog
replacement while jobs remain queued.

Test queryless recent-release RSS, offset/limit, stable GUIDs and discovery
times across rebuilds, new languages, and updates during pagination. Assert
that metadata edits, unchanged upserts, worker restart, and temporary
removal/reappearance preserve `first_seen_at`; a genuinely new language
variant gets a new discovery time without changing the existing variants.
Verify integer timestamps survive artifact export/import and convert correctly
to RSS dates. Measure timestamp and feed-index disk/transfer overhead separately
from the total catalog; do not use illustrative byte arithmetic as a benchmark.
Unknown languages must not produce invented variants; record incomplete
coverage. Test management API authentication, validation, correction
conflicts, refresh deduplication, bounded jobs, and typed status responses.
Reject unsupported experimental DB schemas without modifying them; prove
upgrade from the latest mainline release preserves private state.

Run full `cd apps/api && pytest` and new worker/shared-package tests. Use
installed-wheel tests for shared packages so import-order side effects and
missing package data are visible. Build/run both Docker images on supported
Linux architectures (amd64 and arm64 if both remain promised). Verify a
real Prowlarr/Sonarr path from indexer registration to episode acquisition
and import, plus Radarr movie flow if movie support is claimed. A local
Torznab XML response is not proof of import.

## Performance and capacity experiment

Record environment, image digests, provider sample, code SHA, source revision,
and measurement method. Test both a modest worker profile and the intended
maintainer-hosted profile. Data must reflect realistic title and episode
cardinality; scale synthetic fixtures if live requests are blocked.

| Measurement | Initial target / question |
| --- | --- |
| AniBridge idle, startup, update, search peak RSS | At or below 1 GiB in 2-vCPU consumer envelope; report typical and peak separately. |
| Existing install startup | Serve from local last-good catalog promptly; measure p50/p95 with source unavailable. |
| Fresh install time | Measure pointer fetch, transfer, decompression, validation, and first useful search. "Minutes" is the planning target, not a proven SLA. |
| Consumer disk | Measure compressed transfer, old/new uncompressed versions, temp file, private DB, safety headroom; verify the 02 free-space check. |
| Worker cold crawl and steady state | Peak RSS, CPU, open FDs, in-flight requests, SQLite/WAL size, provider request counts and elapsed time. No linear memory growth with title count. |
| Search | Indexed title/ID/season query p50/p95/p99, with concurrent snapshot switch. No provider HTTP in the normal query path. |
| Distribution | Artifact bytes per provider, unchanged re-publication frequency, likely monthly egress at selected user counts. |
| Freshness | New episode provider-visible to worker-observed to published to consumer-installed; report each stage and misses of six-hour target. |

Do not select sharding/deltas/Turso from intuition. A 1-GiB RSS target is not
automatically a 1-GiB disk or transfer target. The worker's 24-GiB available
host is not evidence of bounded behavior. Profile under forced memory limits
and interruption; adjust batch sizes or design when the data fails the target.

## Gates by milestone

**Private vertical slice** (one AniWorld provider): signed small artifact,
independent worker and client containers, local search, interrupted crawl,
bad artifact rejection, no search downtime during switch, and measured
resource usage. This may use synthetic/provider-permitted data and a private
network. It does not imply permission to run a public catalog.

**Three-provider functional release:** all three adapters pass parser and
failure fixtures; real bounded provider checks demonstrate titles, episodes,
languages, movies/specials, and documented gaps. Search and download behavior
meets the test matrix. Per-provider failures do not block others. User docs,
Compose examples, configuration and agent guidance are current.

**Public hosted default:** specific source and canonical data rights reviewed
for the exact fields and redistribution model; signing key custody and
rotation rehearsed; bounded transfer/disk budgets and failure monitoring;
public endpoint serves only allowlisted artifacts; rollback rehearsed; users
can configure their own source. No public release based solely on placing
the artifact outside GitHub. Treat this as a separate deployment decision.

## Risks and rollback

Use the supported migration/downgrade procedure in 04; select a retained
compatible artifact through the private-DB activation transaction in 02. Never
delete `anibridge_jobs.db`, local corrections, or downloads as
part of rollback. The worker can pause collection and retain its last signed
artifact. If a provider adapter starts parsing a challenge page as content,
disable publication for that provider, preserve its last good revision, fix
the parser/health rule, and re-publish with a higher revision after validation.

## Executable gate register and requirement traceability

These experiments are required future work, **not results of this documentation
review**. Each report records code SHA, dependency lock hash, image digests,
commands, fixture seed/cardinality, CPU/RAM/disk limits, timings, request counts,
assertions and raw private logs. Keep fixture code synthetic; no scraped corpus
or credentials in commits. Implement the harness alongside each milestone,
with a one-command entry point documented in its report; do not claim the
future test modules already exist. Existing baseline command is
`cd apps/api && uv run --locked pytest` in a disposable checkout/data directory.

| Gate | Requirements and milestone | Environment, inputs and procedure | Pass criteria / failure action |
| --- | --- | --- | --- |
| C0 baseline/package | 01/02; M0–M1 | Fresh main checkout; record tests/versions; build core/API/worker wheels, install into clean Python 3.14 envs, run both images from root context; repeat amd64/arm64 and existing PyInstaller target. | Existing tests pass; no worker import starts API/config/DB; zstd/Ed25519/SQLite STRICT available. Failure blocks package milestone; do not silently drop a released packaging target. |
| C1 schema/identity | 02/09; M1 | Execute DDL in temp SQLite; fixtures for movie, episode, season 0, four languages, ambiguous/combined episodes, renamed anchor, aliases; deterministic Unicode/hash/magnet/signature vectors. Mutate each schema/type/count/path/signature constraint. | Exact accepted/rejected set; stable IDs across label/revision changes; distinct providers/modes; old magnet bytes unchanged. No unsupported episode map emitted. Failure blocks producer/consumer integration. |
| C2 collector | 03; M2 | Local fixture HTTP server with paged listings, 1→100k titles, >30-page title detail, success/404/200-challenge/429/malformed/count collapse. Fake clock for 48h deletion and cadence; kill after each checkpoint. | No destructive publication from failure; only 3 complete observations/48h delete; first_seen unchanged through restart/disappearance/correction; due work resumes, exact request/queue caps respected; other providers progress. Failure blocks slice. |
| C3 trust/activation | 02; M3 | Signed fixture source A/B; expire metadata, move clock ±301s, rotate/revoke keys, offer unsupported schema and huge revision with invalid bytes; truncate/corrupt/bomb artifacts. Inject ENOSPC, DB commit failure and SIGKILL at each fsync/rename/commit/registry swap under 8 readers. | 100 repetitions per crash point see only complete old/new DB; accepted floor and active pointer agree; rollback never lowers floor; no leased file deleted; invalid/expired candidate rejected; stale accepted catalog still searches; closed FDs/no orphan child. Failure blocks any default switch. |
| C4 capacity/freshness | 02/03/04/08; M3 then M4 | Consumer `--memory=1g --cpus=2`, worker `--memory=2g --cpus=2`, separate local source with 10 Mbit/s shaping. Seed 10k/50k titles with respectively 200k/1m entities and 2 languages, then legal representative cardinality when available. Stream generator rather than retaining fixture in memory. Run cold install, 100 updates, 8 searches in parallel, 24h steady work and slow/hung responses. Collect cgroup memory.peak (including children), RSS, FD, disk, p50/95/99 query/activation, request starts, backlog and transfer bytes. | No OOM; <=1 GiB consumer/2 GiB worker, no growing memory/FD trend after warmup, byte/queue/rate/storage caps hold. Saved-catalog readiness <=10s; local-query p95 <=500ms/p99 <=2s; 10-Mbit/s install <=15m for artifact within cap. These are provisional acceptance targets, not measurements. Miss → profile/tune bounded work; size or product-target changes need explicit review. |
| C5 real clients | 04/08/09; M3 TV slice, M4 full | Pin supported stable Prowlarr/Sonarr/Radarr images and digests. Fresh profiles with Unknown allowed and normal restrictive profiles. Fixture catalog/extractor serves a short locally generated licensed test video, plus blocked/404 cases; no provider scraping/video download needed. Register indexer/client, poll recent feed, title/ID/season/special/movie searches, grab through actual client, observe queue/import. Repeat paused, blocked across restart, retry/cancel/remove and query 503/partial states. | Correct entity/language/path reaches library; blocked job visible >2 poll cycles and after restart, never completed; no duplicate job for same proven identity; paused causes zero requests; unknown labels/size accepted with documented profile or release blocked. Record restrictive-profile rejection honestly. A fixture extractor proves *arr contract only, not a real provider/host. |
| C5a RSS/estimates | 04/08; M4 | Same pinned real clients: initial unmonitored catalog, explicit search for old monitored missing content, then 1000 new releases with tied seconds and an interrupted-polling 23-hour cursor gap. Preserve normal backoff and restart both client/API. Separately paginate while activating a new artifact; metadata correction, reappearance/new language; sample quality disagreement/hangs/hostile nested URL. | Historical monitored content outside initial RSS is discoverable via normal explicit search; bootstrap downloads no unmonitored content. Every eligible new/catch-up release is observed within two configured RSS cycles; repeated polling/restart preserves GUIDs without repeat grabs. No sample-trigger on RSS; <=1 enqueue/search and caps/cooldowns hold; kill/reap <=deadline+2s; no forbidden network escape. The original exhaustive-bootstrap experiment remains failed; it is replaced only by documented and measured client workflows. Miss gates release; report concrete alternatives. |
| C6 mainline migration | 04/08/09; M4 | Copies of released v2.6.0 DB plus fixtures for each 0001/0002/0003 and exact recognized unversioned schema: jobs in every state, STRM maps, files, legacy/mode hashes, cross-site collision and incomplete old request. Upgrade, interrupt migration, restart, retry adds, rehearse supported rollback on copies. Also feed #119 and unknown schemas. | Original private rows/hashes/paths/bytes preserved; backup usable; unprovable resume is visible error; new jobs durable; foreign schema rejected unchanged. No application release until pass. |
| C7 redistribution | 00/03/07; public-data gate | Dated provider/canonical source-field matrix, exact export inspected for disallowed data, applicable permission/terms/attribution evidence reviewed by maintainer. | Explicit clearance for each distributed source/field; denied/unresolved field omitted, required capability missing postpones hosted launch. This is not a technical test or legal conclusion. |
| C8 operations | 02/07; M5 hosted-default gate | Private rehearsal of same static layout, signing custody, 90-day key overlap with accelerated clock and budget-reviewed schema transition, lost/compromised key, source switch, quota exhaustion, backup restore, provider blocks. From C4 bytes calculate 100/1000/10000-client transfer at measured change rate and 30m polling; maintainer approves host/domain/monthly budget. | Recovery runbook works, alerts before expiry/storage exhaustion, older unsupported readers retain local last-good with an explicit update requirement; any future compatible stream needs a budget review, no public mutation, explicit deploy approval after C7. Failure keeps official default disabled. |

C4 freshness procedure: retain the original50k/1m/2m fixture and full-active
sweep failure. Use its stored history plus60 sparse release changes/15m and
bounded recent windows. Measure actual SQL admission, request starts by class,
window overlap/coverage, oldest pending age, canonical delay, historical progress,
CPU/RSS/cgroup and persisted growth. Add reordering/duplicates/new language,
window overflow, missing pagination, unknown labels, process death/provider block
and extended downtime. Gaps never count as covered intervals or deletions.
Define the healthy workload from03, measure every provider-visible/observed/
published/installed stage, and report six-hour misses. Seven days is historical
eligibility, not a complete sweep SLA; report the measured sweep capacity.
Simulated clock/direct fixture observations are scheduling evidence only. Actual
shaped installation/publication and actual24h elapsed endurance are separate
required measurements; neither a shortened nor simulated run passes24h.
Permitted bounded real page checks (maximum5 titles/provider, normal caps) may
establish signal markup/accuracy, not completeness, import or redistribution.

The real-provider end-to-end gate C5b (M4) is separate from controlled C5: with explicit authorized
content and deployment permission, one permitted AniWorld episode, one s.to
episode and one megakino movie must traverse metadata→grab→local extraction→
output→client import; STRM additionally needs actual playback evidence if claimed.
Do not perform that gate by bulk scraping or downloading video during this
specification review. If lawful/available inputs cannot be obtained, mark the
gate unverified and do not describe the release as fully integration-proven.

Minimum resource evidence includes mapping/index overhead and first_seen index
cost measured by otherwise identical fixtures with/without those columns/indexes.
Byte arithmetic (8 bytes times row count) is not the storage benchmark. A bounded
queue is not a memory result. Baseline/full pytest alone is not a client result.

## Sustained private fixture procedure

After targeted changes stabilize, run
`bash scripts/catalog/start-sustained-validation.sh <absolute-signed-compact50k-fixture> <new-absolute-disposable-proof-dir>`.
Defaults are100 distinct shaped full snapshots over86400 actual monotonic
seconds, with eight local search threads, source A/B switching/recovery every20
updates,503 and one bounded20s hung response every25, and durable paused/blocked/
retry/cancel history activity. The source enforces10Mbit/s; Linux consumer1GiB/
worker-derived fixture source2GiB/two CPUs and256MiB children remain unchanged.
Frozen tool hashes, Git SHA and actual image digests are recorded in `run.json`.
No host ports or provider/media/client API requests are used.

Failures include missing/non-distinct updates, query errors or segment p95>500ms/
p99>2s, installation>15m, saved recovery>10s, changed first_seen, source-failure
replacement of last-good, OOM, increased final FDs>baseline+8 or parent RSS
last-hour maximum>first-hour maximum+32MiB. These final two thresholds are
bounded diagnostic tripwires; inspect minute/hour resource trends for growing
FD/RSS even if they do not trip. A process failure writes `failed`; a shorter run
writes `debug-passed`. Neither can close the100-update/24h subset.

The fixture source keeps only two disposable artifacts to bound local test
storage. This **cannot by itself pass actual worker total-budget/lease/recovery retention**, real collector
endurance, six-hour end-to-end provider freshness, all-provider association,
live media, client import or native-platform gates. Test producer capacity
separately under the30-GB total budget; record physical-environment blocks.

Use the independent `sustained_monitor.py <owned-proof-dir>` sampler to capture
parent RSS/FD, cgroup CPU/pressure/peak/OOM, process scheduler counters, guest
wall/monotonic clocks and persisted-byte counters during install
as well as idle phases. The launcher freezes/starts it for all positive-duration/update
runs, including short regressions; one-time `--once` checks the actual container probes.
Record aggregate host load/memory/swap/free disk separately from guest counters.
Keep each run's frozen hash and coverage declaration: earlier idle-only samples
and subsequently attached minute samples are separate historical evidence.
A monitor failure or unexplained
resource trend prevents a sustained pass even if the consumer reports passed.
It reads only owned containers and terminates on the durable result. Preserve
sampling gaps and compare guest/host clocks; keep-awake cannot prevent lid sleep.
Persist publication/install journals after each accepted update and on exception
exit. A failed admission must preserve active bytes, receipts/floors and jobs;
probe the normal runtime retry separately from the fail-fast fixture harness.
Same-byte repetitions, injected retry faults and short shaped runs are separate
proof levels. An unexplained repeat timeout keeps C4 failed even when bounded
replays pass; do not extend the120s admission deadline to conceal it. Future
fixture runs freeze `sustained_admission.py` and `validator_probe.py` too, retain
per-admission SQL-stage/logical-read/CPU/scheduler traces and cumulative child
usage keyed to the candidate digest. This instrumentation preserves the actual
supervisor, production pager and row checks; it is not an application feature.
Missing diagnostics cannot turn a failed admission into a pass or mask its
original exception. Cumulative child high-water RSS is not a per-stage resident
measurement; retain that distinction alongside cgroup peak and process samples.

## Revised retention gate (2026-10-02)

Exercise current/previous distinct generations, repeated unchanged renewal,
100,000 failed reservations, pointer-before-bookkeeping restart, process-shared
active transfers, open/unlink races,404/410 obsolete references, conditional
cache invalidation and schema1→2 transition. Assert two total unleased artifacts/
needed manifests per provider, compact publication rows, unchanged revision/
first_seen floors, and one refreshed-pointer retry without replacing last-good
on repeat miss/unsupported schema/signature failure. Measure total state/output
including WAL/SHM, staging/logs/backups and reserved runtime against30 GB.
Include prior-grace over-quota startup cleanup without DB mutation, abandoned
private scratch and unlinked-open SQLite sort bytes. Quota exhaustion stops admission; it cannot delete referenced local client data
or active producer transfers. Real24h/100-update evidence remains a separate gate.

## Identical-artifact renewal regression subset

Serve a real local HTTP fixture and count artifact-body GETs. After initial
full admission, a higher valid signed revision with identical bytes must
advance the floor atomically with zero artifact-body transfer; restart and
repeat. Reject invalid signature/expiry/schema/contracts without floor advance.
Changing source, origin, pins or validator receipt must not use this shortcut.
Missing files take full admission; corrupt/symlink files fail safely. Inject
before-commit/after-commit/registry exceptions and cancellation; preserve
previous distinct content and the complete old/new authoritative pointer.
Measure full-size digest/recovery time separately from semantic admission.
