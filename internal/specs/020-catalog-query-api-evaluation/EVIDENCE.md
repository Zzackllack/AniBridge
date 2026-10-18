# Private request API pilot evidence

2026-10-05. Contract: [IMPLEMENTATION.md](IMPLEMENTATION.md). Operator entry:
[pilot README](../../../scripts/catalog/query_pilot/README.md). Machine-readable
measurements: [pilot-results.json](evidence/pilot-results.json). No database,
credential, provider media or real search transcript is included.

## Canonical failure classification and partial metadata — 2026-10-18

[Aggregate evidence](evidence/mapping-failures-2026-10-18.json) records the local
implementation and bounded read-only pilot checks. The live worker remains
`d85ed05` at the existing allocations; nothing was pushed, published or deployed.

The pilot retains 48 AniWorld and 902 Serienstream `source_failure` title outcomes.
Four highest repeated failures/provider and four additional seeded, distinct-parent
held-out titles were selected. Sampling used 28 canonical HTTP starts including
redirects, yielded 19 recorded payloads and stopped at its local budgets. There
was no provider-page crawl or competing collector. A series present under both
providers may reuse the same explicitly identified recording.

Two parser defects are repaired: v2 envelopes with legacy explicit TVDB episode
ID/parent fields, and optional translations with a verified series identity but
no language tag or translated names. The latter supplies no aliases and retains
verified English evidence. Private `missing_languages` distinguishes a checked
empty translation from positive multilingual metadata. Conflicting/partial ID
pairs and named untagged translations remain rejected. Safe `canonical_failure`
events identify phases and typed causes without exception text or metadata names.

The real Enricher replay ran offline against complete, consistent SQLite copies
at 2 CPU/2 GiB with no extra swap. Its clock advances to existing retry deadlines;
it never clears failures or resets the live state. Of twelve selected titles:

- Four held-out lookups now refresh successfully, recording German names as
  unavailable. Their next normal eligibility is 604,800 seconds; the second
  unchanged tick makes zero HTTP calls and zero row mutations. This is a copied
  scheduling observation, not a freshness SLA or live rate reduction measurement.
- Six development cases return a different series ID and one returns a
  conflicting IMDb ID. These remain rejected, with all existing maps retained.
- One development case has incomplete recordings within the finite probe budget.

**No new episode maps were gained.** AniWorld remains 46,545/63,628 usable maps
(73.1518%); Serienstream remains 237,313/298,745 (79.4366%). The full copied ledger
retains all 497,678 releases/first-seen times and 288,876 complete existing episode
map rows. Parent identities, work retries/leases, quarantines, omissions, season
checkpoints, signal queues, title schedules and observation gaps compare unchanged.
Fifteen logical recorded requests produce zero new maps, so requests/new-map is
undefined. This restores valid maintenance, not demonstrated coverage growth.

The measured replay/preflight/comparison takes 28.2975s wall and 16.8674s process
CPU, with 113,504,256 bytes read and 794,624 written during that phase. Process
peak RSS is 167,720 KiB; cgroup peak 1,346,416,640 bytes includes preceding copy
restoration/page cache. No OOM, memory-limit event or CPU throttling occurs in
this run. The earlier layout-only replay added zero maps and still failed at
parent/translation gates; its result is retained privately. Initial harness
attempts exposed wrong entrypoint/permissions and absent SQL scratch; final
comparisons use bounded writable `/tmp` and in-memory SQL scratch. No production
mount or allocation was changed to repair the experiment. The final accounted
upper bound is 25,842,006,528 bytes including retained consistent copies, images/
logs allowance, SQL scratch allowance and the 1 GB reserve, below the 30 GB budget.
Only our failed duplicate scratch copies were discarded; all retained state and
backup generations remain.

Worker tests pass locally: 223 passed, 13 platform skips; core: 310 passed. Changed
files pass Ruff lint/format. Three pre-existing worker-wide Ruff discrepancies
outside this change remain recorded in JSON. The Linux replay uses a current
source overlay, not a newly published/installed worker image. Four held-out
series' explicit ID facts were reviewed before compatibility implementation;
source-name spot reviews occurred during implementation. These are metadata-format
regressions, not a prospective population precision estimate.

Separately, six live old-runtime queries match exact same-revision SQL totals and
provider isolation, taking 5.5–59.6ms; the public proxy returns 200 in 61.1ms.
These do not verify the new code in deployment or extraction/import/playback.
Publication itself is unchanged: the October 16 sample measured Serienstream
median export/validation of 35.06s/28.58s. Readers retain the previous good catalog
while the next catalog is prepared. Publication optimization remains open.

Reproduce with `recorded_failure_replay.py --baseline ... --candidate ...
--metadata ... --output ...` in a network-disabled 2/2 helper. Both state folders
must have `COPY_ONLY`; baseline must be a WAL-free consistent SQLite backup and
mounted read-only. Keep the private original recordings outside Git. The public
fixture contains only selected names, IDs and coordinates. No matcher fingerprint,
public protocol or state-schema bump is needed. A future rollout can use the
existing state-preserving SERVER.md flow; code rollback retains v5 volumes and
the pinned `9a0df2b...` worker, with no database restore or private-table removal.

**Status:** diagnostics, compatibility/empty-translation fixes and bounded local
verification are implemented+verified. Classifying the entire failure population,
reviewing the seven conflicting identities and optimizing publication are not
implemented here. The current pilot's old coarse events cannot retrospectively
classify all 950 failures; the finite sample does not close that gap.

## Subsequent canonical budget tuning — 2026-10-14

[Rate evidence](evidence/canonical-rate-tuning-2026-10-14.json) records implementation,
bounded canonical-only trials on consistent copies and the approved 90/minute
pilot rollout. Default is 30; configurable range 4–120 is our guard, not a Skyhook
quota. Rate changes do not invalidate matching inputs. Runtime `d85ed05` pins
manifest `sha256:9a0df2b03fd386142f36a5ba8704c17e2e1489bd2519d88959d62753d2157218`.

| Configured/minute | Starts / completed | New usable maps | Starts/new map | HTTP results | Network p95 |
| ---: | ---: | ---: | ---: | --- | ---: |
| 30 | 61 / 60 | 10 | 6.1000 | 60 × 200 | 0.4373s |
| 60 | 124 / 124 | 20 | 6.2000 | 124 × 200 | 0.5866s |
| 90 | 181 / 180 | 99 | 1.8283 | 180 × 200 | 0.5776s |
| 120 | 243 / 242 | 102 | 2.3824 | 241 × 200, one 500 | 0.5487s |

Each enrichment window is 130 seconds at 2 CPU/2 GiB from the same frozen ledger.
The collector is paused and automatically resumed. No provider pages, media,
publication or copied-state import. Sequential wall clocks and series mix vary;
new additions lack independent labels. Rolling start maxima are 28/58/88/118.
Starts include cancelled attempts. No 403/429; the single 500 cannot establish
rate-induced throttling. No upstream ceiling or full-service capacity claim.

Process CPU deltas are 23.9329/20.5890/15.3801/14.7775s including post-window metrics
and preservation checks, excluding copying/preflight. RSS is about 126 MiB.
The first three steps share cumulative counters and reach about 2 GiB, mostly
file cache, with reclamation/max events and no OOM. Separate 120-step peak is
about 1.32 GiB. Warmth/container boundaries prevent a causal CPU/memory comparison.
Numeric cgroup I/O counters are retained in the JSON. No larger resource profile.

All four copies retain 482,963 releases/first-seen and 246,491 prior maps; work
retry/lease differences are zero. Corrected common-clock eligibility counts
include missing episode replays: baseline 1,710/10,290 parents; 90-step 1,666/10,246.
Oldest positive due ages change 12,635→12,400s / 43,084→42,841s. Another 1,111/2,105
records lack a trustworthy eligibility start clock; last attempt is not that clock.
No freshness SLA follows from this sample. Existing frozen matching labels retain
their separate chronology/accuracy limits; no matcher tuning occurred here.

[Native previews 38620494363](https://github.com/Zzackllack/AniBridge/actions/runs/38620494363)
and [frozen tests 38620494384](https://github.com/Zzackllack/AniBridge/actions/runs/38620494384)
pass: worker 202, core 310, API 280 with six skips. The subsequent age correction
passes 17 focused Mac cases. Guarded preparation verifies the current manifest,
refuses drift and retains raw rollback/config bytes.

Authenticated native Zen saved all three image references; both initializer and
volume configs contain 90/minute. Collector remains 2 CPU/2 GiB, metadata 2 CPU/
512 MiB, original volumes/networks and no OOM/restart loop. Full live comparison
retains 482,969 pre-upgrade releases/first-seen, 246,689 maps and parent identities.
Six revision/digest-paired queries match exact SQL totals and isolate providers.
AniWorld One Piece S01E01/S01E06/S21E14 each return three releases; ordinary
Serienstream S01E01 two. Acquisition timing cannot be attributed solely to this
rate change. An initial query assertion lacked status/revision capture and failed;
cause unestablished. Instrumented and repeated paired checks pass. Recorded queries
take 5–64ms internally and about 62ms via the authenticated public route.
Publication latency was not separately rebenchmarked per rate; new revisions and
last-good serving are observed. This is metadata evidence, without live playback.

A live counter sample has 1,016 × HTTP 200, no Retry-After and 78 joint retained
starts in its last minute. Accounted disk upper bound is 22,213,706,800 bytes,
including research copies, state/read, 1-GB reserve, summed worker-image logical
sizes, writable layers and conservative Docker logs. Shared image layers are
double-counted; unrelated host apps are outside the service budget. Original
backups/quarantines remain. Client/generated-media evidence is unchanged.

## Baseline and provenance

Implementation branch: `zzackllack-aux/catalog-query-api-implementation`, created
from current main/origin main `e14a041c0a8ddeac71aab7b8f564ac4a9584603a`, released
v2.6.0. Preserved worker `88b8796c6b614dc36f6806792ba2edaa8bb7c718` and evaluation
`4786f6e38e766cf1415d16d569e53474e9c58394`. Selected files were reused; neither
reference branch was merged or blindly cherry-picked. No history was rewritten,
push/PR/publication/deployment performed, or existing installation changed.

The tested runtime images carry revision
`8b5fa12ffed6943aeddcd828ae80961e315269c7`; subsequent evidence/operator-script
edits do not change installed application code. Image IDs are in the JSON.
Builds pin Python 3.14.8 and uv 0.12.23; dependency lockfiles are committed.
Local Docker client/server: 28.5.1; Compose: 2.40.2-desktop.1. Worker image:
SQLite 3.46.1, FastAPI 0.142.2, Pydantic 2.13.5, HTTPX 0.28.1, Uvicorn 0.54.0.
API image: FastAPI 0.135.1, Pydantic 2.12.5, HTTPX 0.28.1, Uvicorn 0.42.0.
Latest FastAPI auth/lifespan guidance was retrieved with Context7.

## Requirement checklist

| Requirement | Evidence and boundary |
| --- | --- |
| Title/ID, native season/episode/language, stable GUIDs | Core identity/query tests; worker `test_query.py`; local `test_query_local.py`; generated 40-release Torznab smoke |
| No query-time collection/extraction or episode fan-out | Query server imports only allowlisted read/schema/query modules; HTTP-only cold season measurement: candidate lookup + one native batch |
| Local corrections before discovery/filter/totals | New external-ID discovery and episode renumbering test; retained fingerprint/conflict view; TMDB-only coordinate regression |
| Durable recent first_seen_at | Retained ledger rebuild/reappearance tests; deterministic mode/language pagination; smoke offset page. Bootstrap discovery is not original broadcast date |
| Cache expiry/source/corruption/outage | Worker query tests: positive stale only, negative failure, origin/token/source separation, malformed/auth/replay rejection, cross-key revision invalidation |
| Identical concurrent misses and cancellation | Eight cold same-key searches share two requests; bounded tasks/waiters; cancelled waiter and settled SQL cancellation tests |
| Replacement during reads | Concurrent readers/atomic pointer replacement, same-digest corrupt-file repair, revision checking/retry tests |
| Durable local grab/pause/block/retry/restart | Retained Jobs/Runner/Executor tests with generated children; production qBittorrent paused admission + persistent source identity; Compose restart smoke |
| Mainline data/STRM/corrections/backup preservation | Released-schema matrix, retained files/hashes/STRM rows, interrupted backup/migration/foreign schema tests; no real DB migrated |
| Source/auth/validation/privacy | Bearer admission, strict IDs/paths/languages/payload limits, no redirects/proxy inheritance, pinned source context. App access logs off; operators/proxies can observe requests |
| Bounds and disk admission | Storage tests, small Linux measurements below; logs/container limits. No 24-hour run, automation, bulk scrape or large workload |
| Real *arr fixture | Actual digest-pinned Sonarr/Prowlarr tests below; generated catalog, no provider extraction/import/playback |
| Operator/restoration path | Disposable Compose, random token volume, smoke/status/restart/cleanup commands, local correction CLI, forward/downgrade restoration instructions |

## Tests and commands

Native Python 3.14.8: core **289 passed** (1.85 s); full API **253 passed,
18 skipped** (17.40 s). Skips are not passing platform proof. One existing
Starlette/HTTPX TestClient deprecation warning remains.

```sh
(cd packages/catalog-core && uv run pytest -q)
(cd apps/api && uv run pytest -q -o addopts=)
# Tested Linux runtime, no network, normal disposable container filesystem:
docker run --rm --network none --memory 1g --memory-swap 1g --cpus 2 \
  -v "$PWD:/repo:ro" -e PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/repo/apps/catalog-worker/src:/repo/packages/catalog-core/src \
  --workdir /repo/apps/catalog-worker --entrypoint python \
  "anibridge-query-worker:$PILOT_COMMIT" \
  -m pytest tests -q -o addopts= -p no:cacheprovider --tb=short
docker run --rm --network none --memory 1g --memory-swap 1g --cpus 2 \
  -v "$PWD:/repo:ro" -e PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/repo/apps/api:/repo/packages/catalog-core/src \
  --workdir /repo/apps/api --entrypoint python \
  "anibridge-query-api:$PILOT_COMMIT" \
  -m pytest tests/unit/catalog tests/unit/db \
  tests/unit/core/downloader/test_voe_fallback.py \
  -q -o addopts= -p no:cacheprovider --tb=short
```

Linux worker: **116 passed**, 16.87 s. Focused Linux API: **108 passed**,
27.98 s, same deprecation warning. Ruff check/format and `git diff --check` pass
for changed code. Initial worker tests on a 256-MiB tmpfs correctly rejected
insufficient publication headroom; rerun used normal disposable filesystem,
without weakening disk limits. An initial full API runtime-image test exposed
read-only-checkout and missing-Git tool environment failures; a whole runtime
image suite is not claimed green. Native full-suite and focused Linux proofs
above are the final supported results.

## Actual Docker fixture and measurements

Use the README commands; the scripts print bounded JSON and never credentials.
Host free disk was checked before experiments: about **20 GiB** on the final
measurement pass. Docker guest free space is thin virtual capacity, not proof
of that physical backing. No full-catalog capacity extrapolation is made.

Generated HTML → retained collector/parser/ledger → immutable read catalog:
one title, 20 episodes, 2 observed languages, 40 releases, 22 fake fetch calls.
The collector benchmark disables networking and deletes its temporary state.
Collector/export elapsed **5.009 s**, collector CPU **0.042 s** plus validator
child CPU **4.872 s**; container peak **58,961,920 bytes** under 512 MiB/2 CPUs.
Peak process RSS and allocated/logical storage are recorded in JSON.
Persistent managed files are **475,136 bytes**; including
the enforced 1,000,000,000-byte runtime/log allowance: **1,000,475,136 bytes**,
below the total 30,000,000,000-byte budget. Worker image is about 67.4 MB; bounded
three-container logs/config fit the allowance for this measured pilot. No
catalog-history copies are retained; validation uses one temporary staging file.

The final query benchmark ran **136 logical searches, concurrency 8**, in
**1.591 s**: p50 **83.478 ms**, p95 **134.967 ms**, p99 **155.536 ms**.
Consumer CPU **1.198 s**, process peak RSS **78,278,656 bytes**, temp cache
**98,304 bytes**. Five real metadata requests transferred **70,805 response-body
bytes**; eight identical cold season requests shared candidate + native requests
(two HTTP calls, **45,602 bytes**). HTTP framing/TLS traffic is not counted.
Server process peak RSS **76,341,248 bytes**; proc CPU increased **0.15 s**
over the observation interval, including incidental activity. API container
peak **603,197,440 bytes** includes application plus observer/benchmark
processes, under its 1-GiB/2-CPU/no-swap limit. No WAN delay/TLS/media was tested.
Earlier same-fixture p95 ranged 114–360 ms under different host load; these are
measurements, not an improvement/SLA claim.

Actual route smoke: 40 releases, stable repeated RSS, unknown quality omitted,
recent offset page, durable paused grab with `catalog_source` frozen. Catalog
outage: positive expiry was simulated by subtracting 61 seconds from only the
disposable cache fetch timestamps; stale HTTP 200/marked age, uncached HTTP
503/XML 900, caps still HTTP 200, paused job retained. Service recovery and
catalog/API restart both passed the smoke. Stale age is fetch age, not provider
freshness. This is not a 24-hour expiry or endurance run.

Digest-pinned real Sonarr **4.0.20.3014** and Prowlarr **2.6.5.5623** each accepted
and tested the Torznab indexer (HTTP 200). Prowlarr forwarded TVDB 81189/season 1
and received 40 generated releases. Sonarr's optional single public descriptor
lookup created an **unmonitored** disposable test series with Unknown-only
profile; actual episode-1 interactive search returned two Unknown releases.
The script asserts series/episode are unmonitored. No grab was issued by these
clients, no existing library was used, and no import/playback was performed.
Sonarr descriptor/artwork access is distinct from provider metadata/media access.

## Open gates and next action

No material decision blocks operating the generated private rehearsal. Next:
choose one exact AniWorld native title path and explicitly selected provider/
private-service configuration for a bounded Linux one-title metadata pass.
The README's one-show overlay was parsed and its network-disabled initializer
tested twice using only `https://fixture.invalid` in a separate temporary
project. It prepares matching source/auth configuration without collection;
its disposable volumes were removed. No live one-title pass was run.
Review canonical season correspondence when evidence is unresolved; then choose
an Unknown-permitting disposable client profile. Do not resume the synthetic job.

Live provider extraction/grab completion, Sonarr import/playback, HTTPS ingress/
WAN behavior, representative catalog size/update contention/freshness, supported
quality profiles, broader providers/platforms, redistribution and any public
hosted default remain open. User-local overrides remain private except ordinary
target-ID lookups. Old snapshot-validator/endurance timeouts remain **failed,
unexplained historical evidence**; this API pilot neither explains nor fixes them.
Obsolete client artifact/renewal gates are replaced by response/cache/revision/
outage tests; retained identity/mapping/migration/jobs/storage gates still apply.
The generated pilot containers were stopped/removed after validation, retaining
only that named project's disposable volumes and locally built images.


## Maintainer-selected live metadata pass (2026-10-05)

Input explicitly supplied by the maintainer:
`https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai`.
Executed committed `36ad9408fb6691f2dbddde9a6fa59f9167a45c36` images in
separate Compose project `anibridge-query-bunny-pilot`, using the base and
`show.yaml` overlays. Source `private-bunny-pilot`, canonical TV source `off`.
No application source changed for this experiment.

Two explicit `--collect-title` passes used the documented 30-page/120-second
per-pass bound. The first completed 30 checked work pages with three pending;
the second resumed them, reaching 33 checked pages and zero pending. This is
work-page accounting, not an instrumented total of HTTP starts/redirects.
One title, 29 native entities: season 1 has 13, season 2 has 13, and source
season 0 has three film entries. Observed variants: 16 German dub, 29 German
sub, 25 English sub (70 total). The title detail status became complete; export
coverage remains conservatively partial and canonical mappings are absent.
No assertion of full provider coverage, working host offers or video quality.

Actual local `t=search&q=Rascal Does Not Dream&limit=100` returned HTTP 200,
70 items in 0.126 seconds, partial mapping status, and no manufactured
720p/1080p/H264 release tokens. Initial full-title search returned 64 items in
0.153 seconds before the resume. `tvsearch` for season 1 returned empty with
canonical mapping off; this does not prove Sonarr discovery. Local qBittorrent
queue contained zero jobs. No video-host resolution, grab, media download,
client import or playback occurred.

**Observed defect:** the resume resets `title.display_title` to the URL slug.
`collect_title` seeds its listing with `Link(title_path, slug)` on every pass;
existing detail work is not due again, leaving the previously fetched heading
replaced. The first export preserved the proper heading; the second export
and release names used the slug. Fix this before canonical/live-client testing;
do not hide it by guessing a canonical mapping.

Stopped/removed only this project's service containers and network with
`docker compose ... down`. Its disposable volumes/config/catalog remain for
reproduction; the earlier synthetic project volumes were not changed. No
provider HTML, cookies, credentials or live catalog database is committed.

## Resume fix and selected Sonarr matching (2026-10-05)

Continues the selected pass above without resetting any existing volume.
Fix commit `0ce826fd30eba0cf8c0772a53e0695331028feb0` uses the stored display
title for resumed synthetic listing hints. The Linux regression resumes two
remaining episodes after a 30-work-page first pass, proving the heading,
release IDs and first-seen timestamps survive with only one title-detail fetch.
Full Linux worker suite: **117 passed in 27.75 s**, network disabled,
1-GiB/2-CPU container. Ruff/diff checks pass; both revision-labeled images built.

The already damaged heading was repaired through **one selected title-detail
work page** using the existing collector/parser. No episode/film pages or video
hosts were fetched for that repair. Setting `due=0` alone did not bypass
incremental reconciliation; the repair used an explicit normal detail claim.
Current heading: `Rascal Does Not Dream of Bunny Girl Senpai`. One bounded
no-overwrite worker backup remains at
`/state/aniworld.to.sqlite.before-sonarr-matching.backup`. The digest of all
ordered `(release_id, entity_id, language, first_seen_at)` tuples is unchanged:
**70 releases / 29 entities** preserved. Token/source/local private state and
download volumes were not replaced.

Explicit provider IMDb `tt8993398` matched exactly one Skyhook candidate:
TVDB **345596**. The full descriptor confirmed that IMDb ID, title and 2018
first-air year; it also supplied TMDB TV **82739**. Worker TV enrichment is now
explicitly `skyhook`, with `skyhook-v1` approved for publication. Reviewed
native season 1 → canonical season 1 from **13 unique exact normalized episode
title matches**; season 2 → season 2 from **12**. The retained matcher applied
descriptor episode coordinates, not ordinal equality. The old slug-context
cache was not reusable after the repair; a fresh descriptor refresh admitted
the corrected input context.

**25 mapped entities / 62 language variants**: season 1 **39 variants,
episodes 1–13**; season 2 **23 variants, episodes 1–12**, partial. Four entries /
eight variants remain unmapped: season 2 episode 13's `[Final Episode]` suffix
and three film entries' `[Movie]` annotations. No annotation stripping or guessed
special/film numbering. Accepted title matches were unique; the unmatched
annotations require specific review.

Real disposable Sonarr **4.0.20.3014** and Prowlarr **2.6.5.5623** both passed
indexer tests (HTTP 200). Prowlarr forwarded TVDB 345596/season 1 and returned
**39** releases. Sonarr's unmonitored series/episodes and Unknown-only test
profile returned **3** episode-1 releases and **39** season-search releases,
all mapped to the correct local series/season and episodes **1–13**, Unknown
quality, with no season-search rejections. No release POST, grab, provider-host
extraction, media download, import or playback. Sonarr descriptor/artwork access
is separate from provider media access.

Context7 guidance was checked against pinned v4
[ReleaseController](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/Sonarr.Api.V3/Indexers/ReleaseController.cs)
and [ReleaseResource](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/Sonarr.Api.V3/Indexers/ReleaseResource.cs).
The initial harness expected the manual-queue `seriesId` field; the final check
correctly validates `mappedSeriesId`, mapped coordinates and rejection status.

This tool session lost its Docker connection immediately after passing discovery.
The failed queue/status calls did not establish that Docker Desktop was down.
The short retained-queue check subsequently passed with `[]` (see below). No daemon
restart or volume deletion; existing Bunny volumes and new separate client
volumes were retained. Unrelated installations and the synthetic project were
not started or changed. Details: [bunny-matching.json](evidence/bunny-matching.json).
Discovery reproduction:
[BUNNY_MATCHING.md](../../../scripts/catalog/query_pilot/BUNNY_MATCHING.md).
Extraction/import/playback/public gates remain open; historical validator
failures remain failed evidence.

## Closed milestone and finite acceptance handoff (2026-10-05)

The selected AniWorld metadata/season-1 discovery milestone is **closed**.
No collection, mapping change, server access/deployment, live extraction,
endurance run or new product feature is authorized by this handoff.
[ACCEPTANCE.md](../../../scripts/catalog/query_pilot/ACCEPTANCE.md) records
implemented/demonstrated behavior, operational prerequisites, the single
generated workflow acceptance and deferred release coverage.

The prepared scenario uses a fresh named disposable project, existing API/
collector/client images, generated test-pattern/sine bytes and a test-only
fixed HTTP input fixture. It keeps normal API startup, Runner, SubprocessExecutor,
job_child, yt-dlp transfer, remux/probe/receipt/publication and Jobs.finish intact.
Sonarr queries through Prowlarr, initiates one grab and performs actual import.
No fake completed job, replacement download-child result or direct status write.
One attempt is required; no restart/retry matrix. Library/download path sharing,
UID ownership and explicit Unknown test policy are supplied by the scenario.

The finite acceptance **passed** on Docker Desktop Linux/arm64, build
`159fd2ac28e70518f74a1aaf27205a491aff277e`: Sonarr 4.0.20.3014/Prowlarr
2.6.5.5623 indexer tests, 40 generated season variants and 2 episode variants;
Sonarr's sole release POST durably admitted one job, completed in one attempt;
actual remux/probe/receipt/publication and completed-download import passed.
Imported S01E01 file SHA-256 equals the published MKV; ffprobe confirms video,
audio and >600-second duration. All four fixture reads originated in
`job_child.py` (provider, player, media prefix and media stream). No application
change or replacement executor was needed. Focused input test: **1 passed**.

Command: `docker compose -p anibridge-query-acceptance exec -T --user 1000 api
python /pilot/acceptance/run.py`, with the three files in ACCEPTANCE.md.
Docker 28.5.1, Desktop 4.49.0 (208700), Compose 2.40.2-desktop.1. Host free disk
was 14 GiB before the run. Job created 17:38:53 UTC, completed 17:38:57 UTC
(4 seconds at timestamp precision). Generated MP4 7,791,146 bytes; published/
imported MKV 7,862,192 bytes. Container lifetime cgroup memory peaks:
AniBridge 696,487,936 bytes under 1 GiB/2 CPUs; catalog 67,956,736 bytes under
512 MiB/2 CPUs. Worker state/read catalog logical sizes: 331,776/123,413 bytes.
These are short synthetic measurements, not capacity/endurance evidence.
Bounded result/resource record: [generated-acceptance.json](evidence/generated-acceptance.json).

Retained Bunny queue was checked read-only using a temporary SQLite/WAL copy:
**`[]`**. Bunny containers stayed stopped; no collection or mapping changes.
Only the acceptance stack was started/stopped; all disposable volumes remain.
No server access/deployment, supplied provider-media download or playback.

**No blocker remains for the scoped generated workflow; private-pilot ready.**
The real metadata/season-1 discovery milestone remains closed. Live provider
extraction/provider-media import, annotated entries, broader coverage/platform/
public-launch gates remain deferred limitations. Historical validator/endurance
failures remain failed evidence. There is no new implementation milestone.


## Provider implementation and real-server preparation — 2026-10-05

Finite local extension, preserving the existing implementation branch/commits.
Reference worker/evaluation heads were inspected, not merged. Normal operator
commands: [SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md). Measurements:
[provider-pilot.json](evidence/provider-pilot.json). No remote host was accessed,
full crawl launched on the Mac, real installation changed, push/PR/publication
performed, or accepted AniWorld workflow unnecessarily repeated.

| Requirement | Final status | Evidence / limit |
| --- | --- | --- |
| AniWorld → request API → Sonarr TV discovery | implemented + verified | Prior accepted live/real-client proof retained; default v1 requests preserved, current generic query tests pass |
| Serienstream → request API → Sonarr TV discovery | implemented + verified | Current HTTPS listing/detail parser; 30 bounded collector requests; production Torznab 32 title/14 season/2 episode releases; actual Sonarr/Prowlarr episode/season searches passed |
| Megakino movie identity/collection/query/grab wiring | implemented + verified | Normal collector created one movie entity with null TV coordinates; labelled fixture query/resolution tests; configurable HTTPS origin and explicit sitemap alias; no fake S01E01 |
| Megakino → real Radarr discovery | implemented + environment-blocked | Inception's live player is unlabelled: zero releases. Movie enrichment also requires an operator TMDb credential. No actual Radarr client proof is claimed |
| Practical canonical matching/coverage | implemented + verified | Three independent unique episode-name anchors, no number equality; reviewed maps retained; scoped AniWorld finale fallback; duplicate/empty/conflicting evidence unresolved. Live Serienstream 19/23 collected episodes mapped automatically; CLI exposes counts, ambiguity/outcomes and gaps |
| Large episode/season requests + local corrections | implemented + verified | 601 entities/2,404 variants in both read schemas; cold target = two HTTP requests; episode moved between seasons, old season empty, corrected season exact total 202 for two languages; broad history explicitly fails |
| Durable normal bootstrap/resume + early partial publication | implemented + verified | Actual Linux CLI through four finite generated two-provider passes; real publication subprocess, retained first-seen/checkpoints and independent pointers. A publication defect was fixed: `limit_child`'s second argument is file bytes, not the 420-second deadline |
| Targeted recent work, reconciliation, backoff, serving during replacement | implemented + verified | Retained signal/scheduler/circuit tests, normal provider-block isolation and concurrent read/replacement tests. TV feeds have explicit overlap/gap status; Megakino recent feed unsupported, serials inventoried as unsupported |
| Full live bootstrap time/coverage/capacity | implemented + environment-blocked | Commands are implemented; deliberately not run on the development Mac. Selected pass checkpoint span 57 seconds/30 requests is partial. Measure complete bootstrap on an operator-selected Linux host |
| Cache/outage/provider isolation | implemented + verified | Source/auth/provider revision scopes; replay/auth/negative/stale/coalescing tests; absent AniWorld still yielded live Serienstream results with explicit partial header; cold service/client outage 503/XML 900 |
| Mainline data, jobs, STRM paths and local corrections | implemented + verified | Full API migration/lifecycle/override suites; no new private API schema migration in this extension; real state untouched. Released schema copies and interrupted migrations/backups remain covered |
| Actual maintainer-state upgrade-copy rehearsal | implemented + environment-blocked | Offline no-network migration command supplied; no consistent private-state backup was supplied or accessed. It cannot be represented as tested against that installation |
| Linux Compose/status/resource budget/backup/restore | implemented + verified | Separate server/client stacks actually started; counts/status, independent volumes, resource/log bounds and no-overwrite backup. Incomplete marker is persisted before copying so interrupted sets are rejected. 30,000,000,000-byte total unchanged |
| Remote verified HTTPS ingress | implemented + environment-blocked | Opt-in existing Traefik network/router configuration validates locally; only authenticated POST catalog query routes. No authorized host/DNS/TLS deployment was requested; guide-only finish was requested |
| Query → grab → production completion → client import | implemented + verified | Prior AniWorld generated acceptance retained. New Serienstream: actual Sonarr/Prowlarr grab, real provider/host parser, production transfer/remux/receipt, durable completed job in one attempt, verified MKV and Sonarr import |
| Live extraction/provider-media import/playback | implemented + environment-blocked | Metadata checks and generated inputs are distinct; suitable authorized live media was not supplied. No live extraction/import/playback proof is claimed |

Tests: core **289 passed** (3.80 s); API full **255 passed, 18 skipped**
(19.59 s), followed by the expanded three provider/long-series cases **3 passed**
(0.94 s); final installed Linux worker **122 passed** (27.46 s). Generated input
resolver/stream boundary **2 passed** (0.48 s). Ruff for changed runtime/operator
files and Compose validation passed. The known TestClient deprecation remains.
The full API count preceded the extra compact-schema parameter case; counts are
not additive. No 24-hour workload, automation or 600-crash campaign was launched.

Actual Linux runtime builds: generated acquisition `7144be5`; separate live
server/client `e9284a7`; final worker and Linux suite `f253148`. Subsequent test/
operator/document edits do not alter the API application code. Worker image
`e9284a7` was 67,401,034 bytes; API 419,217,849 bytes. Selected live ledger/read
storage after Serienstream + one unresolved Megakino movie was **987,136 bytes**,
plus the fixed 1,000,000,000-byte runtime reserve. Generated acquisition AniBridge/metadata
service peaks were **689,999,872 / 57,643,008 bytes** under 1 GiB/512 MiB. These
small measurements are not whole-catalog sizing or endurance guarantees. Mac
physical free space was 12 GiB; the Linux VM's large thin-filesystem figure is
not physical capacity proof. All new stacks were stopped; disposable volumes
remain. Live-discovery queue was verified empty. Retained Bunny was not touched.

The first live-client probe failed rootfolder setup because the test used
separate downloads mounts and a root-owned directory. The isolated configuration
was corrected to the same bind and UID 1000; the subsequent actual Sonarr episode
and season searches passed. This was not a fabricated import or application fix.

**Draft-PR ready for an AniWorld + Serienstream private pilot.** Megakino is
optional and not ready for live Radarr discovery on the observed page. Ordinary
TVDB correspondence can be automatic; missing year/ID/name evidence, split
seasons, duplicate names and TMDB-only TV episode coordinates without explicit
maps remain unresolved. No public/default/redistribution readiness is claimed.
Historical 019/evaluation endurance failures remain failed evidence.

Concrete operator handoff: choose one Linux host with measured disk headroom,
transfer this committed branch, and run SERVER.md's fresh configuration/bootstrap
and private HTTPS ingress commands; then connect the separate disposable client.

## Authorized private Linux deployment — 2026-10-06

The maintainer selected `fra-node-01`, requested SSH continuation, created DNS and
clicked the initial Coolify deployment. A separate Coolify project now owns the
collector/metadata stack; the Mac runs a separate disposable query client. No
registry push, PR, existing installation change or live media acquisition occurred.
The runtime fix below was built on ARM Linux and applied through Coolify while
retaining the same config, ledger and read-catalog volumes.

Measured snapshot: [linux-private-pilot.json](evidence/linux-private-pilot.json).
Initial useful publication took **289 seconds for AniWorld** and **409 seconds for
Serienstream**, measured from the first listing checkpoint. These are partial
publication times, not full-bootstrap durations. Authenticated HTTPS returned 200
for both providers; missing bearer returned 401. The restricted ingress excluded
GET, compatibility and docs requests (the existing proxy fallback returned 503).
Local category searches returned the correct provider results. Actual local TVDB
episode requests returned three AniWorld releases (450072/S02E10) and two
Serienstream releases (442050/S01E01). These are metadata/query proofs only.

A collector restart and the subsequent Coolify image update retained checkpoints,
195 AniWorld releases and 162 Serienstream releases. Both providers entered a
30-minute transport-failure cooldown; last-good catalogs continued serving 200.
At the snapshot, only 3/85 AniWorld and 8/110 Serienstream collected episodes had
canonical mappings. Explicit unresolved mappings, recent-feed coverage gaps and
the eight unlabelled Serienstream feed entries remain visible. No complete
bootstrap or universal Sonarr match coverage is claimed. Megakino remains disabled.

The deployed worker is `3bf551e`; the local API is `71988fc`. The mapping fix defers
an entire lookup when fewer than three requests remain in the existing 30/minute
budget. It no longer counts its own throttling as an upstream failure or adds
failure backoff. Cached episode enrichment can still run. Focused TV/movie
canonical checks: **17 passed**; Ruff check/format passed. Historical failures
already persisted by the old worker are retained and retry normally.

Server free space was **105 GiB**. A sample after the update was collector
**60.83 MiB** and metadata **53.07 MiB** under their 512 MiB caps; the local API
sample was **162 MiB** under 1 GiB. The JSON contains measured managed storage and
the unchanged 30,000,000,000-byte total including the 1,000,000,000-byte reserve.
These are short live samples, not peak/endurance/capacity estimates. Collector
bootstrap runs on Linux, not on the development Mac. Full collection, a copied
maintainer-state migration rehearsal and authorized live media/import/playback
remain unverified.

### Authorized network repair and Docker restart — 2026-10-06

The maintainer reported an OpenStatus NetBird outage and authorized both the
pilot-network replacement and permanent Docker address-pool configuration.
Read-only diagnosis confirmed that the pilot's
`ev7cds2lpqyvqfxpcm4wp4tc_default` bridge allocated `192.168.0.0/20`; Linux chose
that bridge for `192.168.2.1` before the existing NetBird policy route. Its only
endpoints were metadata and the shared proxy, both with other attached networks.
After removing those endpoints and the bridge, the host selected `wt0 table
netbird` and ping succeeded 3/3. Coolify's saved source pins its replacement to
`172.16.27.0/24`; the actual replacement allocation was inspected.

`/etc/docker/daemon.json` now sets `default-address-pools` to
`[{"base":"10.254.0.0/16","size":24}]`, after an overlap check against all IPv4
routing tables and Docker IPAM, and successful `dockerd --validate`. The previous
configuration was absent. Configuration, network and running-container inventory
are retained in `/var/backups/anibridge-network-20261006T202626Z`. The authorized
daemon restart applied the new pool. A disposable automatic network obtained
`10.254.1.0/24` and was removed. Existing user-defined networks were retained;
changing the pools alone would not have repaired the existing conflicting route.

All **21 previously running container names** returned to running. Wings restored
its managed game container automatically; the recovery check initially caught
the interval before that recreation completed, then verified it returned. No
container with a configured healthcheck remained unhealthy, and no OOM was
reported in the final inventory. The OpenStatus probe's network namespace also
pinged `192.168.2.1` **3/3** after the restart. An HTTP diagnostic to port 80 was
refused by the destination; it is not evidence of an HTTP monitor recovery or
dashboard alarm clearance. No probe configuration was changed.

Authenticated remote metadata POSTs returned **200**, with totals **195 AniWorld
and 225 Serienstream releases**, and unauthenticated POST returned **401**.
The Mac client's health returned **200**. A first operator probe omitted the
required `params.t=search` and correctly returned 400; the corrected probe passed.
At the postrestart status check, both provider cooldowns had cleared and checked
pages had increased to **592 AniWorld / 591 Serienstream**. Managed storage was
**48,218,112 bytes**, plus the fixed runtime reserve. Bootstrap remained partial.

The earlier cooldowns were three transport failures within five minutes, rather
than a proven 401/403/challenge or 429 response. Hundreds of successful pages and
successful collection after automatic cooldown show the same origins/request
headers remain usable. The current transport collapses timeouts, connection/TLS
errors and other unsuccessful HTTP statuses into `transport_failure`; original
status/exception details were not retained. IP reputation, provider throttling
and header sensitivity cannot be distinguished retrospectively from this data.
The LAN-route conflict does not establish a cause for public-provider failures.

### Read-only pilot follow-up — 2026-10-08

[Follow-up measurements](evidence/linux-private-pilot-followup-2026-10-08.json)
cover approximately 37 hours since the last restart. Both worker containers had
zero restarts/OOMs. Authenticated remote POSTs and both local provider category
queries returned 200; missing authentication returned 401. The NetBird route and
new Docker address pool remained correct. Sample RAM was 125.8 MiB collector /
53.66 MiB metadata; managed storage was 367,706,112 bytes, or 1,367,706,112 bytes
including the unchanged runtime reserve. These remain samples, not peak claims.

The ledger grew to 36,875 AniWorld / 10,109 Serienstream releases. Approximately
68.3% / 48.0% of episodes with releases had canonical mappings in a nearby
read-only coverage sample. Remaining first-check queues were 31,601 / 157,790
pages, with 231 / 657 pages carrying failures. Recent feeds had each been polled
80 times; gaps remained latched and eight Serienstream hints remained pending.
At roughly 1,100 checked pages/hour, the known queues represent about one / six
more days, excluding new work discovered from remaining season pages and retries.
Neither provider bootstrap is complete; Megakino remains disabled.

Two concrete defects explain the recommended next engineering step. First, the
HTTP deadline wraps the local `before_request` budget wait. A local reproduction
with mocked DNS and an HTTP-call guard returned `transport_failure` with **zero
outbound HTTP calls** when that wait exceeded the deadline. Both live ledgers
had exactly 1,200 retained request starts at their new cooldowns. This strongly
implicates internal throttling, without identifying every past transport error.
Local budget exhaustion must defer work without consuming provider-failure
backoff; diagnostics should retain sanitized status/error classes.

Second, two bounded Serienstream metadata checks returned headings `S01E01:
Folge 1` and `S01E01: Leichtfertige Versprechen`, while the parser returned no
episode title for either. It currently requires a parenthesized English suffix.
Among 4,394 collected, unmapped Serienstream episodes with releases, 2,577 had
no captured episode title. Retain source-language headings and remeasure unique
matching evidence; generic labels do not justify copying provider coordinates
into canonical coordinates. No fixes or deployment changes were made in this
inspection. Generated acquisition/live extraction/import/playback were not rerun.

The maintainer subsequently rejected week-long bootstrap as a production outcome
and requested better volume, request compatibility and classified backoff. The
finite [issue/performance backlog](ISSUES.md) records these requirements and the
confirmed defects. PR #119 was inspected at `61351bb`: its AniWorld season-row
metadata is a candidate for reducing requests, but its direct-numbering matcher
is unsuitable for conservative canonical identities. No verified full-crawl
timing comparison was found. This documentation update changes no running code,
request rates or provider headers.

## Collector repairs and finite Linux rollout — 2026-10-08

CQ-01–11 are implemented on the preserved branch. Commits: `a4810e6`
(transport), `c6cb6ea` (durable admission/retries, batching/pools/parser imports),
`128f9eb` (source aliases, conservative matching and progress). The initial
fra-node-01 Coolify cutover used worker/metadata image
`128f9eb53b6a21e75b013f2c52ff1f99bcade162`, image ID
`sha256:19e40f9f61d8f732455a89f23b43e7f6ef7cb0a5d08bb39b80855e4e848e36dc`.
It was built locally on that server and applied through authenticated Coolify UI.
No push, PR, registry publication, full Mac crawl or media acquisition occurred.
The separate Mac client remains `71988fc`; its health returned 200. Generated
job/import evidence remains valid and was not rerun after these collector edits.

Both existing containers/three volumes, source/auth configuration, private ingress,
512 MiB/2 CPU/64 PID limits, `172.16.27.0/24` backend and `10.254.0.0/16` automatic
pool were preserved. State v3 upgraded to v4 with verified no-overwrite backups
of 112,742,400 and 210,939,904 bytes. A read-only post-cutover lookup preserved
**100/100 sampled release IDs/first-seen times per provider**. Historical failure
counts remained 249/738 during the finite window; they were not cleared.

Numeric outputs: [collector-repair-2026-10-08](evidence/collector-repair-2026-10-08/summary.json).
Reproduction: [finite benchmark](../../../scripts/catalog/collector_benchmark/README.md).
Private raw metadata bodies/ledger copies stay outside Git. Three real season
inputs were used: AniWorld Bunny season 1, Serienstream Breaking Bad season 1,
and Arthur season 1. The baseline checked six detail pages per season: **21
requests, 18 entities**. Candidate season rows supplied **71 entities from three
requests** (13/7/51); all **18 sampled row/detail language sets agreed**. Only
those sampled details were independently checked. Full-season request counts in
the output are code-path arithmetic, not a second fully measured detail crawl.
Six formerly null Arthur detail headings now retain their German names.

| Finite measure | Baseline | Candidate |
| --- | ---: | ---: |
| Offline replay requests / admitted entities | 21 / 18 | 3 / 71 |
| Checkpoint + publication + reopened identity verification | 14.768 s | 3.506 s |
| Container memory peak, replay | 67,895,296 bytes | 59,891,712 bytes |
| Parser time, three cohorts combined | 12.958 s | 1.577 s |
| Writer time, three cohorts combined | 0.109 s | 0.090 s |
| Publication time, three cohorts combined | 0.617 s | 0.834 s |

Publication/query totals matched admitted releases and reopened first-seen values
in every cohort. Parent title coordinates were seeded to isolate season work;
this is not full title discovery or an equal-work full-bootstrap benchmark.
Parser import profiling identified avoidable async/XML imports. Lazy imports
reduced startup while retaining fresh children, memory/file/PID limits, deadlines
and kill/reap guarantees. Writer/publication timings did not justify a rewrite.
16 bounded header/pool A/B requests returned 200 throughout, without 429/403.
Chrome headers showed no demonstrated benefit. Keep stable identifying headers,
identity encoding, two/provider slots and 2-second spacing. The **1,800/hour**
cap matches existing spacing, removing the old forced idle period without
increasing request start density; this sample is not a sustained safety ceiling.

Copied-ledger matching: 50 unresolved title caches/provider added **11 AniWorld /
7 Serienstream mappings**. Applying the same real season rows mapped **13/13,
7/7 and 33/51** cohort entities. Generic, duplicate, conflicting/split evidence
stayed unresolved. Production was not written by that copied-ledger experiment.
Native numbers never prove canonical coordinates; unknown quality is preserved.

Post-cutover live window **13:31:20–13:36:47 UTC (327.102 s)**:

| Live measure | AniWorld | Serienstream |
| --- | ---: | ---: |
| Requests / new entities | 157 / 1,701 | 156 / 1,530 |
| New entities/request | 10.834 | 9.808 |
| New entities/second | 5.200 | 4.677 |
| New releases | 2,999 | 2,143 |
| New recorded provider failures | 0 | 0 |
| Final titles / entities / releases | 2,516 / 26,170 / 47,118 | 10,947 / 15,445 / 15,799 |
| Usable episodes / mapped usable episodes | 26,155 / 17,776 (67.96%) | 12,968 / 6,801 (52.44%) |
| Remaining first-check pages / pages with failures | 29,083 / 249 | 157,190 / 738 |

AniWorld mapping fraction initially falls as batch discovery outruns enrichment;
it is not evidence of universal matching improvement. Both first passes remain
incomplete, discovery can grow and ETA is withheld. Recent gaps remain latched;
Serienstream still has 3,771 unknown-language observations. `live-sanitized.json`
contains title/season/episode phase counts, checked-age, throughput and mappings.
Live page events contain UTC timestamps, status 200, actual request counts and
network/parser durations, without paths/bodies/credentials/query/IP histories.

Authenticated HTTPS returned **200** for both providers throughout sampled
cutover/publication checks; unauthenticated returned **401**. Final published
query totals were 44,461/15,277, behind the current ledgers as expected between
publications. Collector RAM samples ranged 122.5–204.8 MiB, metadata about
52.1 MiB; instantaneous collector CPU samples 59–142% under two CPUs. The live
cgroup peak counter reached **537,038,848 bytes**, near/slightly above the
536,870,912-byte cap during kernel file-cache accounting/reclaim; 602 max-limit
events, **zero OOM/kill/restarts**. Current resource sample separates 134,217,728
anonymous bytes from 272,756,736 file-cache bytes. This is bounded operation,
not a claim of abundant memory headroom or endurance. Managed storage including
new backups was **723,611,648 bytes**, **1,723,611,648** including reserve, below
the unchanged **30,000,000,000-byte** aggregate budget.

Validation: final native core **301 passed**, worker **118 passed/13 skipped**;
additional truthful-completion regression **8 focused passed**. Installed Linux
worker suite **128 passed/1 initial spacing assertion failed**; that assertion
was corrected to wait the required spacing. Final installed focused Linux
worker **36 passed**, earlier changed parser/pipeline/publication cases **22
passed**, core transport/rows/supervisor/session **25 passed**. Local API catalog
compatibility **61 passed/18 platform skips**; known TestClient deprecation.
Ruff check/format and diff checks pass. These overlapping suites are not additive.

No collector-code or private-deployment blocker remains. **A complete supported
provider bootstrap duration and sustained capacity remain unmeasured**; neither
this finite throughput window nor a queue projection closes that measurement.
The existing Linux collector continues from retained checkpoints. Optional
Megakino languages/origins, suitable authorized live-media inputs and a supplied
consistent real-installation upgrade copy remain external validation gaps under
CQ-12. CQ-13/CQ-14 fixes and failed historical endurance evidence are preserved.

Latest closeout sample, **13:45:24 UTC / 15:45:24 CEST**, is `current.json`:
AniWorld 2,516 titles / 29,298 entities / 53,394 releases, 18,944 of 29,283 usable
episodes mapped (**64.69%**), 25,993 pending pages. Serienstream 10,947 / 18,095 /
19,013, 8,423 of 15,252 usable episodes mapped (**55.23%**), 155,072 pending pages.
Both remain incomplete. New failure counters remain zero after 409/415 starts;
historical failed-page counts remain 249/738. Authenticated HTTPS is still 200,
unauthenticated 401; total accounted storage 1,743,608,320 bytes. AniWorld's
falling global mapping fraction during discovery is explicit, despite improved
unique-name cohorts; enrichment/translation coverage is not universal.


### Redirect and bounded-queue follow-up

Review found a redirect admission edge case: durable deferral of every short
spacing wait could restart the original hop indefinitely. `1edbda8` resumes the
same redirect chain outside the HTTP deadline, releasing/reacquiring a
cancellable fetch lease during local spacing. Hourly admission still defers
durably. HTTPX pool exhaustion is now a local resource wait, not provider
evidence. `9afc52f` reserves result-queue capacity before acquiring that lease,
avoiding deadlock with a one-entry queue and one global fetch slot.

Final native worker **122 passed/13 platform skips**, core **302 passed**.
The locally built Linux image at `9afc52fd2c439126e22a353b9100eb834bfb1022`
passed **30 focused installed-package checks** (collector admission/HTTP,
pipeline, transport). These include zero-request budget deferral/reopen,
redirect continuation, cancellation without duplicate release, local pool
timeout and small-queue scheduling. No repeated endurance/crash campaign or
full-crawl benchmark was run. The finite throughput window above measures
`128f9eb`; it is not relabelled as a new measurement of the follow-up image.

The follow-up image ID is
`sha256:bc89461128b83deec7b7c470a78aff049546929c8f49727439e4c804da8eadc3`.
The authenticated Coolify save/restart subsequently applied this image to the
existing pilot. No alternate writer or unmanaged replacement stack was started.

The pre-follow-up sample at **14:10:22 UTC** is `followup-current.json`.
AniWorld: 2,516 titles / 38,184 episodes / 71,845 releases; 21,344 of
38,178 usable episodes mapped (**55.91%**), 17,236 pending pages.
Serienstream: 10,947 titles / 26,838 episodes / 29,174 releases; 13,823 of
23,263 usable episodes mapped (**59.42%**), 147,236 pending pages.
Historical failed pages remain 249/738. Authenticated HTTPS is 200/200 and
unauthenticated 401. Accounted storage including reserve: **1,803,766,272
bytes**. Both collections remain incomplete; AniWorld enrichment continues
to trail accelerated native discovery.

### Final deployed follow-up — 2026-10-08

The existing collector and metadata containers now run
`9afc52fd2c439126e22a353b9100eb834bfb1022`; both running containers' image IDs
and revision labels match the follow-up image above. Coolify shows Running and
no pending configuration changes. Retained mounts, 512 MiB/2 CPU/64 PID limits,
bounded logs, private authentication and both Docker/VPN network settings were
verified unchanged. No push, registry publication or additional writer occurred.

[final-deployment.json](evidence/collector-repair-2026-10-08/final-deployment.json)
records a **136.201-second** resumed window: **62/67 requests**, **674/673 new
episodes**, **1,329/768 new releases**, and **zero new failures** for
AniWorld/Serienstream. Both providers published after the restart; authenticated
HTTPS returned 200/200, unauthenticated 401, and Mac-client health 200.
All **200 sampled release IDs/first-seen times** survived, with both pre-v4 backup
sizes unchanged. Historical failed pages are now **243/735**, reflecting normal
successful retries during ongoing collection; no failures were manually cleared.

Latest sample **16:39:08 CEST / 14:39:08 UTC**:

| Coverage | AniWorld | Serienstream |
| --- | ---: | ---: |
| Discovered / checked titles | 2,516 / 2,512 | 10,947 / 10,853 |
| Discovered / checked episode work | 58,193 / 50,038 | 155,297 / 34,124 |
| Collected episode entities / releases | 50,247 / 92,242 | 37,898 / 41,651 |
| Mapped / usable episodes | 26,011 / 50,225 (51.79%) | 21,188 / 33,299 (63.63%) |
| Pending first-check pages | 9,013 | 141,249 |

The ongoing read-only status/count queries are sampled sequentially, not one
atomic snapshot of the running writer. Both first passes remain incomplete;
discovery can grow and ETA remains withheld. AniWorld's mapping fraction trails
its accelerated discovery despite improved unique-name cohorts. Serienstream's
unresolved/unknown-language work still requires detail evidence.

The new container's finite-window memory peak was **348,897,280 bytes**, with
zero max-limit/OOM events and zero restarts. One CPU/RAM sample was 175.71% /
137.7 MiB for collector, 0.13% / 53.09 MiB for metadata. Accounted storage including
reserve was **1,878,899,200 bytes**, below the unchanged 30 GB aggregate limit.
These short observations do not supersede earlier near-cap cache pressure or
prove endurance. Final native/installed-package results above remain applicable;
no code changed after the tested image.

The browser deployment blocker is resolved. Remaining limits are the complete
bootstrap/sustained-capacity measurement and optional CQ-12 external validation
gaps listed above. The retained Linux collector continues collecting normally.


## Later pilot review and resource clarification — 2026-10-08

At **22:13 CEST / 20:13 UTC**, the retained `9afc52f` pilot was still running
without OOMs/restarts. AniWorld had 60,704 episode entities / 110,939 releases,
36,149 of 60,681 usable episodes mapped (**59.57%**), 705 pending pages and
**one failed title** (down from 243). Serienstream had 152,540 / 161,029,
80,719 of 135,156 usable episodes mapped (**59.72%**), 103,864 pending pages
and **711 failed pages** (down from 735). HTTPS remained 200/200, unauthenticated
401; storage including reserve was 2,352,388,608 bytes. This is continued
collection from retained state, not a measured fresh complete bootstrap.

Follow-up findings and fixes:

- **CQ-15**, `211a68d`: direct pooling lost AsyncClient's default User-Agent on
  canonical calls. Four source-failure samples returned HTTP 400. A three-request
  control was 400 with no headers, 200 with identifying UA, 400 with Accept alone.
  Restored identifying transport defaults, preserving provider overrides and
  all pinning/cookie/encoding boundaries. Candidate checks in isolated scratch
  state recovered one failed lookup per provider into a genuine matched result
  (four HTTP 200 requests); no production ledger was mutated by those checks.
- **CQ-16**, `c75a150`: 704 nonfailed AniWorld descendants were left a week ahead
  by recent-hint admission while otherwise eligible bootstrap work was exhausted.
  Idle bootstrap now fills that backlog after all due/targeted/history work,
  excluding failures, targeted hints, leased and tombstoned work. Retry deadlines
  survive restart. Queue diagnostics distinguish due/deferred/leased work and
  due failures; failed work is never silently treated as complete.
- **CQ-18**, `39ba345`: the remaining AniWorld title returned HTTP 200 but an
  invalid optional IMDb hint caused whole-page rejection. Ignore that malformed
  hint without coercing/publishing it; conflicting valid hints still fail. A
  bounded check using the deployed parser now returns `ok` for the same page.
  Its real retry deadline was retained (**23:08:38 CEST**), not forced forward.
- **CQ-17 remains open**: the guide's four-hour active-work promise did not match
  the incremental scheduler. Corrected that promise; capped recent feeds and
  weekly reconciliation do not establish lossless freshness. A bounded active-
  parent/gap reconciliation policy and optional background demand refresh remain
  future work. No synchronous search crawl or daily complete recrawl was added.

The production sizing policy now separates collector minimum **2 vCPU/2 GiB**,
recommended **4 vCPU/4 GiB** (6 GiB only for demonstrated headroom benefit), from
the client's **1-vCPU/512-MiB metadata/search target**. Job peaks need separate
proof. The existing 512-MiB collector stays a constrained test profile; specs
alone do not change host allocations, provider budgets or the 30 GB disk budget.
User-facing public documentation is deferred as requested.

Validation: native core **305 passed**, worker **125 passed/13 platform skips**;
final installed Linux focused checks **57 passed**, with four SIGKILL cases
deliberately deselected rather than repeating the crash campaign. Ruff/diff
checks pass. Regressions cover default canonical headers, idle-bootstrap priority,
protected failure/hint deadlines across reopen, queue diagnostics, malformed
optional IDs and conflicting valid IDs.

The existing Coolify service now runs collector/metadata image
`39ba345626a9535aac31e7e356c34b4e889530af`, image ID
`sha256:a1adffcffc1e178ef8aed121af7c0b45e4f32a35e6d7e71292e97de90708527a`.
Both containers run with zero restarts/OOMs. All 200 sampled release IDs and
first-seen times survived; pre-v4 backups remain 112,742,400 / 210,939,904 bytes.
Original volumes, caps, authentication and source configuration were retained.
No push, PR, registry publication, media acquisition or competing writer occurred.

In **63.698 seconds** after the initial resumed sample, AniWorld/Serienstream
made **30/29 provider requests**, admitted **1,132/341 season-row observations**,
and recorded **zero new failures**. AniWorld pending work fell 488 → 410;
Serienstream 101,816 → 101,654. Canonical source-failure title outcomes fell
1,552 → 1,544 and 3,910 → 3,900 through normal successful/rejected lookups;
16 became matched and two became not-found. No failure counters were cleared
manually. Last-good authenticated publications remained available (200/200;
unauthenticated 401) while the next scheduled publication was pending.

Latest sample **22:36:54 CEST / 20:36:54 UTC**: AniWorld 62,568 entities /
113,934 releases, 36,279 of 62,557 usable episodes mapped (**57.99%**), 410
pending / one failed page. Serienstream 159,434 / 168,508, 84,592 of 141,196
usable episodes mapped (**59.91%**), 101,654 pending / 710 failed pages.
Counts are sequential read-only samples while the collector runs. Both remain
incomplete; AniWorld discovery again advances faster than enrichment.

The new container reached **536,875,008 bytes** in cache accounting/reclaim, with
238 max-limit events, zero OOMs/kills and zero restarts. The resource snapshot
separates 123,645,952 anonymous bytes from 312,066,048 file-cache bytes. This
reinforces that the old 512-MiB profile is a stress test with cache pressure;
it does not demonstrate a throughput gain at the newly recommended allocation.
Accounted storage including reserve was **2,305,653,248 bytes**.

Sanitized diagnostics and before/after/retry/resource results are in
[later-review.json](evidence/collector-repair-2026-10-08/later-review.json).
Source response bodies, lookup terms, provider paths and sampled IDs are omitted.
Failures remain durable retry work. Tombstoned confirmed removals and unsupported
work are distinct; no sampled omission was tombstoned. Unknown language labels
and ambiguous canonical evidence remain unresolved instead of being invented.

### October 9 recheck after Catalog-6

Read the referenced Catalog-6 conversation and checked the existing authorized
fra-node-01 pilot without changing services, ledgers, resource limits or retry
deadlines. Both containers still run `39ba345626a9535aac31e7e356c34b4e889530af`,
started October 8 at 20:34:31 UTC, with zero restarts and zero OOM kills.

At approximately **21:23 UTC / 23:23 CEST**, AniWorld has **63,558 entities /
116,308 releases**, zero pending pages and zero failed pages. Its discovered
first-pass/detail evidence is complete, including zero unknown-language
observations. **36,976 / 63,536 usable episodes are mapped (58.20%)**. That does
not establish complete canonical mapping or lossless freshness: three recent
hints and a latched feed coverage gap remain.

Serienstream has **300,821 entities / 321,185 releases**, **47,228 pending pages**
and **2,498 failed pages**, versus 101,654 pending / 710 failed in Catalog-6's
latest sample. **161,328 / 264,030 usable episodes are mapped (61.10%)**.
Discovery can still grow; 50,426 pages have unknown-language observations.
The last-hour rate was 1,112 checked pages / 1,050 requests. Dividing the current
queue by that rate gives roughly 42 hours, but excludes new discovery, failures
and language repair and is not a promised completion time or bootstrap benchmark.

Retained 24-hour logs (three files, 21,295,460 bytes) contain 19,662 Serienstream
and 112 AniWorld successful page events, and 2,505 Serienstream
`unexpected_structure` events. Those parse events all have HTTP 200 and null
error class; no 403/429 or transport-failure events occur in that retained window.
Six bounded metadata probes then checked three failed pages and three structural
samples. Two episode samples have complete HTML/body, titles and no recognized
video section; a language sample recognizes English audio but records `Ger-Sub`
as unknown. A failed title sample returns HTTP 500. These checks do not prove
all failures have one cause, and did not fetch player links or acquire media.
CQ-19–21 record the concrete follow-ups. One language-removal quarantine remains
unapproved; no last-good releases were deleted to make the status look complete.

Authenticated HTTPS recent queries return **200 for both providers**;
unauthenticated POST returns **401**. Serienstream's published total was 321,082
at the API sample, slightly behind the subsequent ledger count during ongoing
publication. `ip route get 192.168.2.1` still selects NetBird's `wt0` interface.
The Mac's active `desktop-linux` context cannot reach the Docker daemon on two
checks, so local client/job/import/playback availability was not verified today;
Docker Desktop was not started as part of this read-only check.

Accounted storage including the 1 GB reserve is **2,942,654,976 bytes**, within
30 GB, with roughly **102 GiB free** on the host. A Docker stats sample reports
collector 96.91% CPU / 215.6 MiB and metadata 0.17% / 52.21 MiB. Cgroup memory
is 476,110,848 bytes, with peak 537,149,440 and 2,186,490 cumulative max-limit
events but zero OOM kills. Docker stats and cgroup cache accounting differ;
the unchanged 512 MiB profile has substantial reclaim pressure and remains a
constrained test. No benefit from the recommended 4-vCPU/4-GiB profile was
measured here. No fresh bootstrap duration or live acquisition was measured.

Sanitized counts and observations: [pilot-recheck-2026-10-09.json](evidence/pilot-recheck-2026-10-09.json).

### October 11 recheck: continued collection and new availability findings

Read-only checks on fra-node-01 around **13:13–13:22 UTC / 15:13–15:22 CEST**
confirm the same deployed `39ba345` image, original October 8 start time and zero
restarts/OOM kills. No runtime settings, ledgers, retry deadlines or quarantines
were changed; no provider metadata or media URLs were fetched during this check.

AniWorld now has **63,579 episodes / 116,359 releases**, zero pending/failed pages
and zero unknown-language observations. Discovered first-pass/detail evidence
remains complete. **36,976 / 63,560 usable episodes are mapped (58.17%)**.
Serienstream has **302,107 episodes / 322,284 releases**, **20,061 pending** and
**6,620 failed pages**, versus 47,228 / 2,498 on October 9. **161,892 / 264,836
usable episodes are mapped (61.13%)**. Unknown-language observations rise to
**50,933**; 6,615 failed episode pages have never completed successfully. Two
language-removal quarantines remain unapproved. Discovery can still grow, so
the earlier queue projection is not a measured completion deadline.

The retained 24-hour page log window contains **13,537 successful Serienstream
pages, 2,400 HTTP-200 parse failures and 15 transport failures** (13 ReadTimeout,
two HTTP 502), plus 122 AniWorld successes and three ReadTimeout failures. No
HTTP 403/429 page events appear. These are page counts, not duplicated collect
events. The last-hour status rate is 249 checked pages / 261 requests, compared
with 1,112 / 1,050 on October 9. It is not established that provider pacing is
the current bottleneck. **48 maintenance ContractError and three TimeoutError
events** introduce CQ-22: the current logs cannot isolate enrichment, export,
validation, child limits or contention. A publication child was observed running;
successful publications continue, with last-good revisions 1212 / 1135 at
13:18 UTC. No speculative root cause was marked verified.

Initial authenticated remote recent checks pass 200 for both providers and
unauthenticated access is 401. However, a subsequent remote targeted Breaking
Bad request returns 503; local recent search also returns 503. Bounded repeats
recover: remote 100-row recent pages return 200 in **0.392 / 0.225 seconds**,
local recent search returns three results and total **438,643** in **3.391s**, and
Breaking Bad S01E01 by TVDB ID and text both return two releases. Initial One
Piece S01E01 results are empty, but the later local query returns two releases.
The local database has zero corrections. This is an inconsistent query result,
not proof of a persistent absent mapping. CQ-23 requires real-sized query /
publication overlap diagnosis, safe failure classification and cache/partial
behavior checks. The empty and failed samples are retained alongside recovery.
The Mac client is now running (`71988fc`), health 200, zero restarts/OOM kills.
No grab, extraction, acquisition, import or playback was attempted.

Both feeds retain their coverage gap; pending hints grew from 3 / 17 to 11 / 24.
Mapping-due counts are 816 / 7,323; canonical source failures have largely cleared
(zero / two), while aggregate usable mapping coverage barely changes. Continued
scraping alone does not close CQ-17 or matching gaps. Collector Docker stats
show **168.17% CPU / 216.2 MiB**, metadata **0.16% / 52.48 MiB**. Collector cgroup
memory is **535,523,328 bytes**, peak **537,452,544**, with **6,237,722** cumulative
max-limit events and no OOM kills. This is substantial pressure in the unchanged
512 MiB test allocation; a production-profile benefit remains unmeasured.

Storage including the reserve is **3,024,038,400 bytes of 30,000,000,000**;
host free space is approximately **98 GiB**. `192.168.2.1` still routes via `wt0`
in the NetBird table. No fresh complete-bootstrap benchmark or all-provider
production-readiness claim follows from these checks. Sanitized counters and
results: [pilot-recheck-2026-10-11.json](evidence/pilot-recheck-2026-10-11.json).

## October 11 four-workstream repair

Evidence: [sanitized aggregates](evidence/catalog-pilot-repair-2026-10-11.json).
Baseline branch `8adcbfa`; packaged candidate
`73a996cbf78c524380f3ba387ebe97ed24b692cf`. Read-only live recheck still shows
worker `39ba345`, 2 CPU/512 MiB, zero OOM/restarts and intact NetBird routing.
Consistent SQLite backup-API copies contain 63,579 AniWorld and 302,114
Serienstream episode entities, with 116,359/322,291 releases respectively.
Read-only status charged 2,791,254,528 bytes including the 1 GB reserve against
the 30 GB cap. Raw HTML, private compose, query inputs and ledgers stay outside Git.

| Workstream | Final status | Evidence and limit |
| --- | --- | --- |
| Query/publication, CQ-22/23 | implemented + environment-blocked | Demonstrated query defects fixed and verified; safe maintenance diagnostics implemented. Historical maintenance failures could not be reproduced from current-sized copies, including 512 MiB. Original stderr was discarded; cause confirmation requires an approved diagnostic deployment. |
| Serienstream parser/languages, CQ-19/20/21 | implemented + verified | Ten bounded live metadata requests, sanitized fixtures and eight-response offline replay. Ger-Sub recognized in detail/season/recent and local offer resolution; explicit unavailable metadata retained. Unknown cases/quarantines remain explicit. |
| Capacity/throughput | implemented + verified | Finite Linux copied-state profiles 2 CPU/2 GiB and 4 CPU/4 GiB, plus constrained 512 MiB control; reduced repeated empty backlog probes. No full crawl, rate increase or endurance proof. |
| Practical matching/freshness, CQ-06/17 | implemented + verified | Selected 50-title cohorts per provider, bounded exact-ID canonical metadata fallback and copied-state parent/retry scheduling. Four-hour eligibility is budgeted; full coverage/freshness SLA remains unmeasured. |

Query root causes were repeated public-ID view joins under the fixed read deadline,
and the recent-release index hint applied to targeted native selection. The old
Serienstream TV recent count repeatedly interrupted at about two seconds. Direct
integer joins cut standalone counts from 3.004s to 0.746s (Serienstream) and
0.885s to 0.191s (AniWorld). Independently validated recent summaries eliminate
that full count when their cutoff proof applies; narrower filters still count
exactly. A proper ordinary target remained two releases: three baseline timings
0.715/0.594/0.565s became 0.0065/0.0024/0.0019s. Failed providers no longer cache
empty success; positive siblings carry explicit partial status. Export/validation
failures preserve last-good pointers and clean staging. Safe phase/reason/exit
reports separate enrichment, export, validation, locking and publication without
capturing stderr/HTML/player URLs/credentials/query terms/IPs.

| Copied-state profile | Queries during publication | Maximum query latency | AniWorld / Serienstream publication | Peak cgroup memory |
| --- | --- | --- | --- | --- |
| 2 CPU / 2 GiB | 96/96 HTTP 200 | 0.162s | 9.07s / 37.25s | 1,012,838,400 bytes |
| 4 CPU / 4 GiB | 96/96 HTTP 200 | 0.173s | 10.20s / 38.82s | 1,016,619,008 bytes |
| 2 CPU / 512 MiB | 96/96 HTTP 200 | 0.719s | 34.13s / 123.58s | 536,870,912 bytes |

These include 100-row recent search/TV pages, title selection and native targets;
page totals remain 116,359/322,291. Publication/lease/identity/failed-validation
fixtures supplement finite overlap requests. The 512-MiB run recorded 7,036
memory-limit events but zero OOMs; this demonstrates pressure sensitivity, not
CQ-22's historical cause. No child/read deadline or live allocation changed.
The larger profile showed no benefit in this workload. CPU, anonymous/cache
memory, child RSS and cgroup I/O counters are recorded. Docker Desktop's host
cache/bind storage means near-zero block reads cannot establish production I/O
capacity; these are Linux ARM64 VM runs, not Oracle hardware throughput.

Three failed HTTP-200 samples explicitly say no episode player is available;
titles/aliases and prior releases now survive that case. Three detail samples,
25 combined-language season rows and four of 193 recent entries positively
establish Ger-Sub. Deutsch/Englisch remain supported; other labels remain unknown.
No subtitle audio language or unreleased date is guessed. Changed/missing markup
and explicit interstitials have separate reason codes. The maintained upstream
[Serienstream episode parser](https://github.com/phoenixthrush/AniWorld-Downloader/blob/d3ea32fe5e5b3175d762adb47670f5a7301ad7e1/src/aniworld/models/s_to/episode.py)
was inspected; its label coverage did not resolve this gap. Both retained removal
quarantines were rechecked with two metadata requests and remain unapproved;
one still lacks evidence for a previously retained language. Missing evidence
alone cannot remove a release.

Eight saved live responses at 2 CPU/2 GiB: baseline 40.99s/zero new releases;
candidate 14.11s/25 new releases, with all old release IDs/first-seen verified.
At 4 CPU/4 GiB candidate replay took 42.64s; no speed benefit is established.
Replay timings include filesystem/cache variance; the deterministic positive-row
gain is not a threefold live-throughput claim.
Parser/checkpoint/CPU/memory/I/O measurements are in the aggregate. A single
season response provides 25 positive rows (0.04 responses per usable row);
this saved-response efficiency is not live request throughput or a claim that
all 50,933 historical unknown-language observations share the same label.
Empty local season-backlog probes fell from 16 to one over 20 scheduler claims,
with a 60-second negative-probe cache that establishes no provider absence.
Pacing, bounded concurrency, Retry-After and real-failure backoff remain unchanged.

Matching adds 3,816 AniWorld maps (2,281→6,097) and 823 Serienstream maps
(2,660→3,483) in selected unresolved 50-title cohorts, zero conflicts and all
release identities/first-seen unchanged. Unique individual episode names can
span canonical seasons without asserting equal numbering or whole-season maps.
Only source-specific demonstrated AniWorld annotations are stripped as fallback.
Four bounded canonical requests establish that an empty explicit IMDb search
can recover through title search retaining the exact ID and descriptor identity;
three saved responses replay to a verified match. A mapped large-series target
returns three releases in 0.091s from 3,573-release history without fetching the
whole history. Copied AniWorld One Piece S01E01 remains unresolved: distinct title
wording and duplicate TVDB association prohibit a guessed match. These cohorts
are not provider-wide coverage estimates.

Twenty copied-state claims per provider exercise active/gap parent reconciliation
within the existing 360/hour share, retaining ten future failed-work deadlines.
Pending gap parents were 90/352 in these copies. Gaps stay latched; four-hour
eligibility cannot guarantee a four-hour sweep of all parents. Bootstrap is
retained once, episode fallback weekly, search catalog-only. No demand-refresh
system, synchronous scrape or daily complete episode recrawl was added.

Final installed images: **450 worker/core tests passed**, 15 kill/crash cases
excluded from this short run; **42 API tests passed**, one upstream Starlette/
httpx deprecation warning. They cover ordinary discovery, large targeted requests,
correction precedence, partial provider failures, cache/outage handling,
publication overlap/exact totals, retry admission, aliases and subtitle offers.
No live media was fetched. Historical generated acquisition/import acceptance
remains separate; this run adds no live extraction, import or playback proof.

Candidate backup at 512 MiB successfully copied and integrity-checked both
current-sized disposable ledgers without overwrite. State remains v4-compatible;
no API schema migration is introduced. The prepared Coolify patch changes only
three image references and preserves other compose settings; base64 PATCH format
and byte-identical rollback were checked against captured deployed compose.
Exact upgrade/rollback commands are in
[SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md#october-11-existing-coolify-upgrade-and-rollback).
No live redeploy/restart/resource change, push or PR occurred. The maintainer
can approve that image-only diagnostic upgrade to capture CQ-22 phase/exit evidence;
a resource change is a separate decision. All retained state/backups, networking
and the 30 GB budget including SQL scratch/logs/staging and 1 GB reserve remain.

### Authorized preview deployment, later October 11

The preparation-only statement above is historical. The maintainer subsequently
authorized publication and the pilot upgrade. Draft PR #170 targets `v3`; `main`
remains default. The existing Coolify service now runs preview revision
`36fbd511890b0c08a80385b0a2542d3c6b51c1d3`, pinned to worker manifest digest
`sha256:1277d1fd6ec7130a53c5ed4a694dd8efada7e95db6c86bd897e3e446f2149e0a`.
Collector limits are 2 CPU/2 GiB without additional swap; metadata remains
2 CPU/512 MiB. This adopts the documented minimum, not a measured 4-CPU gain
or an explanation of the historical maintenance failures.

Fresh no-overwrite SQLite backups passed integrity checks. Offline publication
succeeded with the writer stopped. All 439,035 backed-up release IDs/first-seen
times, pre-v4 backups, volume names/modes, three network IDs/subnets and NetBird
route survived. No bootstrap or failures were cleared. Eight authenticated
100-row HTTPS recent pages (search/TV, both providers, two offsets) returned 200,
with exact published totals 116,386/322,649 in 0.040–0.301s. Ordinary discovery
and its target returned two releases in 0.007s. A mapped large-series target
returned three of 3,573 historical releases in 0.067s. Its live S01E06 target
remained unmapped; copied-cohort mapping gains do not imply an immediate live
sweep. Startup showed zero OOM kills/restarts and normal collection/enrichment
successes. Charged storage including backup and 1 GB reserve was 3.906 GB/30 GB.

Normal maintenance subsequently published both providers successfully:
AniWorld export/validation 6.439/5.936s; Serienstream 29.930/25.594s, both child
exit zero. Twelve 100-row HTTPS follow-ups after publication returned 200 in
0.046–0.117s, with Serienstream's newly published total 322,732. These probes
started after publication completed, so they add no live-overlap claim; copied
state overlap verification remains separate.

The read-only Coolify API token rejected writes, so the authorized save/deploy
used the existing authenticated Zen session; saved source matched the candidate
exactly. The supplied Configs YAML now matches it, with a private original YAML
retained for rollback. Classified diagnostics are deployed; CQ-22's historical
cause still needs an actual retained failure. The local client was not changed.
No new extraction, acquisition, import or playback evidence is claimed. See
[deployment aggregate](evidence/pilot-preview-upgrade-2026-10-11.json) and the
[current rollback procedure](../../../scripts/catalog/query_pilot/SERVER.md#october-11-published-preview-deployment).

### October 14 operational recheck

[Sanitized evidence](evidence/pilot-recheck-2026-10-14.json), with sequential
snapshots beginning 08:27 UTC (10:27 Europe/Berlin). Worker remains pinned to
`36fbd51`; collector 2 CPU/2 GiB, metadata 512 MiB, zero OOM kills/restarts since
October 11 startup. No redeploy/restart/resource change occurred. Charged storage
is 3.980 GB/30 GB, including the retained backup and 1 GB reserve. All 439,035
backed-up release identities/first-seen times and pre-v4 backups remain intact;
NetBird routing remains intact.

| Observation | October 11 recheck | October 14 snapshot |
| --- | ---: | ---: |
| AniWorld episodes / releases | 63,579 / 116,359 | 63,601 / 116,409 |
| AniWorld usable episode mapping | 58.17% | 65.31% |
| Serienstream episodes / releases | 302,107 / 322,284 | 306,895 / 355,722 |
| Serienstream pending / failed pages | 20,061 / 6,620 | 141 / 143 |
| Serienstream unknown-language observations | 50,933 | 25,135 |
| Serienstream usable episode mapping | 61.13% | 64.62% |

Pending and failed pages overlap. There are 8,350 explicit unavailable episode
observations; these do not establish release dates. Recent gap parents are 0/5,
but capped-feed gaps remain latched. Four removal quarantines remain unapproved.
This is retained-state progress, not a measured fresh-bootstrap duration.

Retained last 24 hours: 568 successful publications (284/provider), no
maintenance/child failures. Median export/validation seconds are 7.847/6.416
AniWorld and 32.696/27.990 Serienstream; publication locks stayed below 0.126s.
Historical maintenance cause is still unproved. Serienstream nevertheless made
3,639 HTTP-200 parse failures: 3,522 incomplete metadata and 117 contract
rejections. Of 288 transport failures, 278 were HTTP 500. No page 403/429 events
were observed. Three bounded live metadata requests reproduce explicit player
unavailability with a missing episode heading, one season contract rejection,
and a title HTTP 500; this does not classify every remaining failed page.

All 25 remote HTTPS probes returned 200. Sixteen 100-row recent pages took
0.050–0.144s, passed contract checks, and had independently checked physical
totals. Ordinary native retrieval returned two rows. For the exact 3,573-release
anime source, One Piece S01E06 and S21E14 now return three rows each; S01E01
remains explicitly unresolved. Broad-title and cross-provider results are not
proof of that source's missing mapping. No new live-publication-overlap,
correction or outage-injection proof was added.

The disposable local client is still `71988fc`, with zero corrections. Recent
search returned 100 items in 1.093s; ordinary and One Piece S01E01 searches each
returned two in 0.193/0.150s. This is live catalog-only search evidence, not a
test of the newer client's subtitle changes or new extraction/import/playback.
PR #170 remains a draft into `v3`, `main` default, review required; completed
tests/lint/CodeQL/preview checks passed. Worker/core pytest CI and meaningful
required test/build gates remain missing. Priorities are recorded in
[ISSUES.md](ISSUES.md#october-14-read-only-recheck-and-priorities).

### October 14 matching diagnosis and implementation handoff

Subsequent bounded read-only ledger queries separated waiting from examined
gaps. [Mapping diagnosis](evidence/mapping-diagnosis-2026-10-14.json) records
15,280/92,506 usable episodes unresolved with descriptors cached, 6,775/8,345
without a TVDB series association, and zero never-checked matching-input entries.
Six concentrated large cohorts contain 4,739 names absent from the selected
descriptor, 1,104 unusable names and four repeated source names. Absence can
reflect different wording/language, incomplete canonical data or a wrong series
association; these aggregates do not yet separate those causes.

Code plus 8,611 partial-series records establish that two descriptor rechecks
per hour would demand at least 17,222 requests/hour under the current 1,800/hour
shared cap. This is a capacity lower bound, not a trace of actual request demand.
The new [repair phase](MAPPING_REPAIR.md) and [agent prompt](NEXT_AGENT_PROMPT.md)
prioritize sustainable evidence acquisition and held-out matching correctness.
They do not replace the request API architecture or authorize a deployment.
No code implementation or new live action is claimed by this handoff.

## October 14 implemented mapping/maintenance replay

The implementation, honest work-item statuses, before/after ledger and labelled
cohort limits are in [MAPPING_IMPLEMENTATION.md](MAPPING_IMPLEMENTATION.md).
Raw aggregate measurements are in
[mapping-implementation-2026-10-14.json](evidence/mapping-implementation-2026-10-14.json);
fixed provider title selections are the two `mapping-*-cohort-2026-10-14.json` files.
Required metadata names/IDs appear only in the sanitized worker test fixture.

Fresh consistent baseline copies yield +4,932 usable maps and +4,969 total maps.
Usable coverage becomes 67.4231%/65.8926%, with zero old release/first-seen or map
changes. Full replay runs offline at 2 CPU/2 GiB with bounded canonical metadata;
no full crawl or live-state experimental writer was launched. The original
439,035 backup release IDs and 221,475 maps also survive. Four quarantines remain
unapproved. Capped feed gaps, missing audio/names and uncertain parents remain
explicit. Existing eligible-work ages remain 3,613s/29,158s; no queues were reset.

All 118 metadata-labelled positives resolve, including 26/35 held-out positives;
38 new labelled acceptances have no observed errors. Six real supplementary
ambiguous entities remain unmapped; seven pre-existing uncertain maps are retained.
Labels followed initial implementation even though selections froze beforehand:
this is regression evidence, not a blind prospective evaluation or population-wide
accuracy guarantee. Full-copy One Piece S01E01 now resolves from verified German
alias/episode ID evidence, with three releases; S01E06/S21E14 retain three each.

Copied publications take 20.0487s/72.3104s. All 96 concurrent finite queries return
200, median 45.1ms, max 1.0214s. Follow-up SQL totals, last-good retention, provider
isolation and ordinary/large targeted retrieval pass. All 32 v4 tables survive
full-copy rollback, old installed-image open, v5 reupgrade and restart. Current
installed API/core fixtures pass 90 tests at 1 CPU/512 MiB; copied client migration
retains all 18 tables. Linux worker installed-wheel suite passes 182 tests; core 310; Mac API 265/18 skips.

Local ARM64 builds/imports, actionlint and aggregate gate failure/skip/cancellation
cases pass. The branch is unpushed; hosted CI, native AMD64 and matching published
manifests remain unverified. The disposable client is stopped on `71988fc` and no
new live extraction/import/playback occurred. SERVER.md contains state-preserving
worker/client preparation and exact code rollback. No Coolify write, restart,
allocation/network/default/protection/PR change or preview publication was made.

## October 14 authorized push and production profiling

The later user authorization supersedes the earlier no-push/publication boundary.
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) records the current outcome;
[aggregate evidence](evidence/production-readiness-2026-10-14.json) keeps it separate
from the earlier frozen before/after replay. Code through `2240b91` is pushed.
Hosted frozen API/core/worker tests, final gate, lint and native AMD64/ARM64
API/worker builds passed. Matching pinned manifests are published; the actual
registry ARM64 worker republished the full copied ledger offline and passed all
eight SQL-total/target checks, last-good retention and provider isolation without
a source overlay. This is packaged copied-state proof, not a live deployment.

Read-only full-copy preflight at 2 CPU/2 GiB took 98.824s total versus 18.1110
cgroup CPU seconds, reading 984 MB with no CPU throttling/OOM. Immediate warm
quick/FK checks totalled 4.374s. Existing child-key prefixes and parent-work
lookups are indexed; a rolled-back alternative work index showed no material
Serienstream CPU benefit. These observations prioritize repeated validation/I/O
measurement over an engine migration or CPU increase, without claiming an
engine comparison or storage-upgrade speedup. Current live counts are sequential
reads of the old worker, not the frozen replay's after state.

The upgrade is authorized and prepared but environment-blocked by the locked
Mac's authenticated Zen UI. Its old unused Coolify draft remains untouched.
No live restart/config/allocation/network/protection/default change was made.
The stopped client remains old; live extraction/import/playback are unverified.

### Subsequent authorized deployment outcome

Manual unlock cleared the Zen blocker. Pilot worker `2240b91` now runs at the
original 2 CPU/2 GiB collector and 2 CPU/512 MiB metadata limits. Both worker config
locations persist the German metadata setting across initializer startup. All
481,435 pre-upgrade releases/first-seen and 239,690 maps survive comparison with
no-overwrite pre-v5 backups; 32 v4 tables/provider match except the expected
publication dirty/time columns. NetBird/backend/pool/network ranges and volumes
are retained. Live SQL-total/native queries and the authenticated proxy route
return 200; zero restart-loop/OOM observations. The early live maintenance sample
adds 144/32 maps, independently of ordinary source observations.

Local client cutover retained 2 CPU/1 GiB, all volumes and zero jobs/tasks/corrections.
It now runs the subsequently hosted-tested `6818115` API privacy fix; its installed
subtitle and logging fixtures, health and metadata searches pass. Hosted tests
`38604860503` and both native previews `38604860757` succeed. The unchanged worker
remains pinned to `2240b91`. No live extraction/import/playback occurred.

Live cohort diagnostics still see 19/30 AniWorld and 30/30 Serienstream unverified
legacy descriptors. Eligible ages are 6,045s/34,788s, with 1,186/8,660 due titles;
a joint retained canonical-window sample has max 28 starts, within the shared 30
cap. The snapshots are sequential and do not prove sustained fairness/freshness.
Exact AniWorld One Piece S01E01 remains unresolved live; its copied-state result
cannot be substituted. Four quarantines and every historical limit remain explicit.

## October 18 publication follow-up

All four publication work items are implemented and verified locally. See
[PUBLICATION_FOLLOWUP.md](PUBLICATION_FOLLOWUP.md) and the separate
[aggregate evidence](evidence/publication-followup-2026-10-18.json).
Private state v6 records changed titles transactionally, separates content from
observation-only publication eligibility, reuses verified unchanged row proofs
and updates a cloned read catalog. Collection continues against a WAL snapshot;
only its captured generation is acknowledged. Global admission checks remain.

On the same full copied ledgers at 2 CPU/2 GiB, old/new publication takes
11.7888/3.6671 seconds for AniWorld and 56.2486/12.8327 seconds for Serienstream.
New source preflight is separate: 0.7543/4.1756 seconds in this warm comparison.
All seven public tables equal independent old full exports; both incremental
files also pass complete untrusted validation. All 60 overlapping queries return
200 with exact SQL totals (57.88-ms median, 140.088-ms maximum); 31 ordinary/large
retrieval pages match the exact release ID sets. Last-good retention and provider
isolation pass. This is a bounded warm-cache experiment, not cold performance,
a freshness SLA, sustained collection capacity or an engine comparison.

All 497,678 copied release IDs/first-seen times and 288,876 map rows survive.
All 38 v5 tables/provider compare, allowing only two generated entity name/time
edits/provider, expected publication clocks and the schema version. Work,
failures, leases, quarantine and matching histories remain unchanged. Copied
v6→v5 rollback, old installed-image open and exact-total queries, v6 re-upgrade
and a second open pass; the original pre-v6 backup SHA256 values remain identical.
Full publication after re-upgrade also passes with the normal 512-MiB address-space
limit and yields files byte-identical to the old full exports. This uses the
copied replay clock; no timestamp validation or source preflight is bypassed.

Installed ARM64 Linux regressions, core/API checks and the source-overlay copied
experiment are distinct evidence. These commits are local; no new registry
manifest, hosted CI result, live deployment, client cutover or media acceptance
is claimed. Read-only inspection still finds live `d85ed05`, unchanged resources,
zero restart count/OOM observations. Historical discarded CQ-22 stderr stays
unrecoverable. No provider/canonical requests, live-ledger experimental writes,
queue resets, backup restores, network or allocation changes were made.
