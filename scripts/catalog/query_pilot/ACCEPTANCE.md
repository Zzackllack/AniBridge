# Generated-media Sonarr acceptance

Run real Sonarr/Prowlarr and the production AniBridge job path on an isolated
Docker project with generated media. The test-only input hook supplies provider,
player and media responses; it must never enter normal images/installations.
This proves the generated workflow, not provider extraction/import/playback,
whole-catalog accuracy or sustained capacity.

## Run

Use the existing overlays from repository root, after disk admission. Never
combine them with developer `data/`, a VPN dev stack or retained live volumes.
The fixture generates a bounded video/audio test pattern; Sonarr can fetch its
fixed external metadata/artwork, so that dependency must be available.

```sh
export PILOT_COMMIT=$(git rev-parse HEAD)
export COMPOSE_FILE=scripts/catalog/query_pilot/compose.yaml:scripts/catalog/query_pilot/clients.yaml:scripts/catalog/query_pilot/acceptance.yaml
docker compose -p anibridge-query-acceptance config --quiet
docker compose -p anibridge-query-acceptance build
docker compose -p anibridge-query-acceptance up -d catalog api sonarr prowlarr
timeout 12m docker compose -p anibridge-query-acceptance exec -T --user 1000 api \
  python /pilot/acceptance/run.py
docker compose -p anibridge-query-acceptance exec -T api \
  cat /data/acceptance-result.json
```

The runner exercises query → Torznab → Sonarr grab → durable production job →
resolution/download/remux/probe → verified output → Sonarr library import.
No helper may fabricate completion, copy the expected result into the library,
weaken identity checks or acquire real provider media to rescue a failed test.

Required assertions include initially empty queues/library, real client tests,
one intended grab/attempt, intermediate byte progress in both AniBridge and
Sonarr, verified video/audio output, and imported library bytes matching the
published file. A complete streamed response is required; HTTP 200 headers alone
do not establish success. Failed/blocked jobs or failed imports fail the run.

## Restart and second provider

After a passing run, restart only this disposable API and check the completed
job, one attempt, library digest and availability over the runner's finite window:

```sh
docker compose -p anibridge-query-acceptance restart api
docker compose -p anibridge-query-acceptance exec -T --user 1000 api \
  python /pilot/acceptance/run.py --verify-restart
```

For Serienstream, append `scripts/catalog/query_pilot/acceptance-sto.yaml` to
`COMPOSE_FILE` and use the separate `anibridge-query-sto-acceptance` project.
Run the same build/start/acceptance/result/restart checks with that project name.
Keep provider results separate; one passing fixture is not whole-provider proof.

## Retention and limits

Retain results privately under ignored `internal/local/` or an external archive.
Stop the disposable project even after failure:

```sh
docker compose -p anibridge-query-acceptance down
```

Only after retiring that project's needed results, use its same project and
overlays with `down -v --remove-orphans`. Never remove unrelated retained volumes.
The library and downloads are separate volumes; container/client resource limits
come from the reviewed overlays. Do not point them at a real media library.

The base scenario keeps the source file. Actual Sonarr move/recovery, credentialed
ingress, differing scene/canonical numbering and longer duplicate-prevention
checks remain explicit acceptance work in
[ISSUES.md](../../../internal/specs/020-catalog-query-api-evaluation/ISSUES.md).
The broader E2E proposal in issue #175 is not an implemented suite. No visible
browser progress-bar or real-provider-media claim follows from API fixtures.
