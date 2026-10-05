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
