# Private request API pilot evidence

2026-10-05. Contract: [IMPLEMENTATION.md](IMPLEMENTATION.md). Operator entry:
[pilot README](../../../scripts/catalog/query_pilot/README.md). Machine-readable
measurements: [pilot-results.json](evidence/pilot-results.json). No database,
credential, provider media or real search transcript is included.

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
