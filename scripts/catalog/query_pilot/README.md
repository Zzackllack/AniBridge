# Private request API pilot

Writable state requires effective process locks. The current guard refuses
filesystems that accept conflicting `flock` owners, observed with Docker Desktop
Mac bind mounts. Use Docker named volumes/Linux-local storage for databases and
publication state. Preserve SQLite/WAL data and stop writers before any approved
storage move; deleting a lock file does not repair filesystem semantics.

Normal all-provider wiring and Linux operation now use [SERVER.md](SERVER.md):
separate collector/API server and local client, bootstrap/resume, HTTPS ingress,
status, backup and restore. AniWorld + Serienstream are usable; Megakino remains
optional with the observed live language gap. Commands below retain the original
generated and one-title rehearsals.

The original AniWorld metadata/season-1 discovery is closed. The passing generated-media acceptance and private
readiness verdict are in [ACCEPTANCE.md](ACCEPTANCE.md). Do not expand the pilot
or recollect the retained selected show to run that generated-media scenario.

Run from the repository root. Everything below uses a **new disposable stack**;
no existing installation, supplied media, hosted endpoint or credentials are used.
Requires Docker Compose and enough free disk for the images (check `df -h .`).
This branch starts at main `e14a041` / v2.6.0. Build labels pin your selected commit.

```sh
export PILOT_COMMIT=$(git rev-parse HEAD)
export COMPOSE_FILE=scripts/catalog/query_pilot/compose.yaml
docker compose build
docker compose up -d
docker compose exec -T api python /pilot/smoke.py
```

Expected: `smoke=passed`, 40 season releases and a paused accepted job. The
metadata fixture is **generated Breaking Bad metadata**, tied to TVDB 81189 for
real-client compatibility; it is not AniWorld coverage or provider validation.
The generated collector/parser path observes German dub and English sub for
20 episodes, assigns explicitly generated canonical coordinates, then exports
one read catalog. The initializer has networking disabled and its fake fetcher sends no requests. No fixture media
exists. Never resume this synthetic grab against a real provider.

AniBridge is at <http://127.0.0.1:18000>; metadata service port is loopback 18080.
The metadata bearer is generated into the private `config` volume, not committed
or printed. `client.json` explicitly selects `private-fixture` and HTTP on the
dedicated Docker bridge; normal external configuration requires verified HTTPS.
The source identity, auth token fingerprint and complete request scope the cache.
Ports and volumes use the fixed Compose project `anibridge-query-pilot`.

Startup does not crawl. Search only queries collected metadata. `t=caps` works
during a metadata outage. Prior positive pages may be stale up to 24 hours,
identified with `X-AniBridge-Catalog-Stale: true` and age seconds; cold or invalid
requests fail with HTTP 503/XML 900. No successful empty outage response.
Search terms/IDs and IPs are visible to your chosen service/operator. App access
logs are disabled for this pilot; proxies and operators can still observe them.

## Status, restart and cleanup

```sh
docker compose ps
docker compose logs --tail 30 catalog api
docker compose restart catalog api
docker compose exec -T api python /pilot/smoke.py
docker compose down                  # retain this pilot's state
# When finished, delete ONLY this named stack's disposable volumes:
docker compose down -v --remove-orphans
```

Logs rotate at 10 MB x3 per container. Worker files + WAL + read/staging +
backups + logs + 1-GB runtime reserve fit the enforced 30,000,000,000-byte budget.
API container: 1 GiB/2 CPUs/no swap; one local download at a time. Metadata
service: 512 MiB/2 CPUs. The smoke always accepts paused; restart preserves it.
Do not point these mounts at `data/` or a real private DB. Default mainline
routes remain available when `CATALOG_CONFIG_FILE` is absent. This compatible
build still runs additive migrations and creates the preupgrade backup; the
opt-in controls search routing, not whether the private schema upgrades.

## Optional real clients and bounded checks

```sh
# Only this named disposable project; no existing Sonarr/Prowlarr config is used.
export COMPOSE_FILE=scripts/catalog/query_pilot/compose.yaml:scripts/catalog/query_pilot/clients.yaml
docker compose up -d sonarr prowlarr api
docker compose exec -T --user 1000 api python /pilot/clients.py
# Optional: one public series-descriptor lookup, unmonitored test series,
# Unknown-only profile and interactive episode search. No grab is issued.
docker compose exec -T --user 1000 api python /pilot/clients.py --episode-search
docker compose stop sonarr prowlarr
```

The client check also accepts an explicit `--tvdb-id`, `--season`, `--episode`,
expected release counts and `--season-search`. Use season matching against
reviewed real episode metadata: the generated Breaking Bad fixture does not
represent its complete real season. The retained maintainer-selected catalog and
its discovery commands are documented in [BUNNY_MATCHING.md](BUNNY_MATCHING.md).

The extra containers have separate disposable volumes, digest-pinned images,
512-MiB/1-CPU limits and no host ports. Sonarr may fetch descriptor/artwork data;
this does not validate the synthetic provider catalog. Keep both Compose files
selected for `down -v --remove-orphans` to delete these client volumes too.

```sh
# Short generated-data measurement, eight concurrent requests, 136 queries.
docker compose exec -T api python /pilot/benchmark.py
# Expire only this disposable cache by 61 seconds, then check outage handling.
docker compose exec -T api python /pilot/smoke.py
docker compose stop catalog
docker compose exec -T api python /pilot/outage.py
docker compose start catalog
docker compose exec -T api python /pilot/smoke.py
# Separate one-shot collector/export measurement; no network or retained state.
docker run --rm --network none --memory 512m --memory-swap 512m --cpus 2 \
  -v "$PWD/scripts/catalog/query_pilot:/pilot:ro" --entrypoint python \
  "anibridge-query-worker:$PILOT_COMMIT" /pilot/collector_benchmark.py
```

Stale age measures time since the cache fetched a page, not provider freshness.
Do not run these scripts against a real installation. The benchmark reports
small-fixture latency and payload bytes, not Internet/TLS capacity or an SLA.

## Test a familiar show next

First choose **one exact AniWorld title path** and your own service/provider
configuration. That input is the next concrete maintainer action. This task has
not fetched it. Keep the generated stack as a rehearsal or clean it up first.

After selecting that input, the following explicit commands prepare a second
fresh project. The initializer only writes configuration; it never collects or
seeds the generated show. Stop the generated stack to free its loopback ports.
Do not reuse its config/state volumes for this procedure.

```sh
docker compose down
export COMPOSE_FILE=scripts/catalog/query_pilot/compose.yaml:scripts/catalog/query_pilot/show.yaml
export PILOT_PROJECT=anibridge-query-one-show
# Set these to your explicitly chosen values; no live defaults are selected.
export PILOT_PROVIDER_ORIGIN=https://YOUR-ANIWORLD-ORIGIN
export PILOT_SOURCE_ID=private-one-show
export PILOT_TITLE_PATH=/anime/stream/YOUR-SHOW
# Default off. Choosing skyhook permits canonical descriptor lookups by collector.
export PILOT_CANONICAL_TV=off
docker compose -p "$PILOT_PROJECT" run --rm --no-deps init
docker compose -p "$PILOT_PROJECT" run --rm --no-deps catalog \
  --config /config/worker.json --collect-title "$PILOT_TITLE_PATH"
docker compose -p "$PILOT_PROJECT" up -d catalog api
curl --fail --get http://127.0.0.1:18000/torznab/api \
  --data-urlencode t=search --data-urlencode q=YOUR-SHOW-TITLE
# Status/restart/cleanup retain -p "$PILOT_PROJECT" and these Compose files.
```

The bearer is generated privately in the new config volume. Collector/service
and user-local provider origins match the explicitly selected HTTPS origin.
This rehearsal API uses private bridge HTTP explicitly; externally configured
metadata services require verified HTTPS/auth and their own ingress. The
fixture bridge has Internet routing; initial generated origins were `.invalid`
and generated grabs paused. Canonical source `off` retains unknown mappings;
select `skyhook` only if those additional descriptor requests are intended.

The collection command is Linux/Docker only, empty or matching one-title state,
at most 30 metadata requests and 120 seconds. Larger titles can be partial;
unknown languages/maps remain unknown. It preserves observed first-seen dates.
An explicit second bounded pass may continue pending detail work. It does not
fetch video. Canonical matching uses exact available evidence; an unresolved
canonical season is **not** guessed from provider numbering. Review an explicit
season correspondence with `--review-season /config/FILE`, then `--publish`,
using the same `docker compose ... run --rm --no-deps catalog --config
/config/worker.json` prefix, if a validated title ID map exists. Place the
reviewed JSON into that disposable config volume (see retained 019 mapping contract). This is
one selected collector, not authorization for a bulk scrape or public service.

On local AniBridge, an explicit query config enables the private source. Search
by `t=search&q=TITLE` first to inspect observed native metadata. Use a reviewed
canonical ID/season for Sonarr. Unknown quality is omitted; select an explicit
Unknown-permitting test profile if the client otherwise rejects it. Those client
policy choices and live provider access can block a real grab independently.

## Local corrections and jobs

Corrections never go to the service as override bodies. Save a JSON body with
`provider`, `entity_kind` (title/episode), stable `title_id`, `entity_id` (null for
title), `target` (`namespace`, `external_id`, `season`, `episode`), `reason`, and
`enabled`. Apply on the user-local instance:

```sh
python -m app.catalog.operator reviewed-correction.json
```

A title correction can introduce a new external ID; apply it before dependent
episode corrections. Targets are checked through ordinary external-ID lookup;
no reason/fingerprint/corrected coordinates are uploaded. Conflicts or changed
source fingerprints suspend application. Corrections precede filtering/totals.
The local schema retains all corrections and old private state. No WebUI is added.

qBittorrent pause/resume/info work on the same durable state. Optional
`MANAGEMENT_API_TOKEN` (32 random bytes base64url) enables local
`GET /api/v1/jobs/ID` and `POST /api/v1/jobs/ID/retry` or `/cancel` with Bearer,
`If-Match` using the returned ETag, and `{}`. Blocked jobs require explicit retry;
paused jobs do no extraction. Grabs freeze provider/path/native/canonical identity
and configured catalog source, so accepted jobs do not need the metadata API.

## Restoration and limits

Stop writers and remove `CATALOG_CONFIG_FILE` to return this build to mainline
search. Durable jobs/corrections/files stay retained; the query scheduler is off
until re-enabled. Do not downgrade v2.6.0 against migrated private state: restore
the retained `anibridge_jobs.db.pre-catalog-v3.backup` and matching files while
stopped. Restore loses post-backup changes; forward restoration is preferable.
Pilot cleanup deletes only disposable volumes, never a production backup.

Query mode supports the configured provider set. Broad searches (>200 candidate
titles, >2,000 native observed releases per provider, >8 correction targets) fail
explicitly. Episode/season requests retrieve canonical coordinate supersets plus
locally corrected entities, so a long show's history does not consume that bound.
Recent offset pages can straddle updates: overlap polls and deduplicate GUIDs.
The cache covers prior queries/pages only, not complete offline search. Old
snapshot tables are retained solely for compatible private-schema upgrades;
no snapshot client/updater is present. Native job enforcement, public rights,
public hosting/defaults, larger capacity/freshness remain
release work. The old snapshot validator timeout remains failed evidence.

Results and exact measurement scope: [EVIDENCE.md](../../../internal/specs/020-catalog-query-api-evaluation/EVIDENCE.md).
