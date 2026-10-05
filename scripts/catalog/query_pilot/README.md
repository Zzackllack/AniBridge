# Private request API pilot

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
one read catalog. The fake fetcher sends no network requests. No fixture media
exists. Never resume this synthetic grab against a real provider.

AniBridge is at <http://127.0.0.1:18000>; metadata service port is loopback 18080.
The metadata bearer is generated into the private `config` volume, not committed
or printed. `client.json` explicitly selects `private-fixture` and HTTP on the
isolated Docker network; normal external configuration requires verified HTTPS.
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
routes remain available when `CATALOG_CONFIG_FILE` is absent.

## Test a familiar show next

First choose **one exact AniWorld title path** and your own service/provider
configuration. That input is the next concrete maintainer action. This task has
not fetched it. Keep the generated stack as a rehearsal or clean it up first.

Use a second disposable Compose project/config volume for real metadata. Set
`worker.json` from `apps/catalog-worker/config.example.json`, your source ID,
credential file and local `client.json`; change the API's `ANIWORLD_BASE_URL`
from `https://fixture.invalid` to the explicitly selected provider origin. The
private fixture network has no Internet egress: grant outbound access only to
the selected collector/user-local grab processes when deliberately testing them.
Run the one-title collector command instead of a catalogue-wide scrape:

```sh
# Catalog service stopped during the deliberately bounded collection pass.
# Replace /anime/stream/SHOW with the exact selected native title path.
anibridge-catalog-worker --config worker.json --collect-title /anime/stream/SHOW
anibridge-catalog-worker --config worker.json --serve --token-file metadata-token
```

The first command is Linux/Docker only, empty or matching one-title state,
at most 30 metadata requests and 120 seconds. Larger titles can be partial;
unknown languages/maps remain unknown. It preserves observed first-seen dates.
An explicit second bounded pass may continue pending detail work. It does not
fetch video. Canonical matching uses exact available evidence; an unresolved
canonical season is **not** guessed from provider numbering. Review an explicit
season correspondence with `--review-season FILE`, then `--publish`, if a
validated title ID map exists (see the retained 019 mapping contract). This is
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

The first slice serves AniWorld only. Broad searches (>200 candidate titles,
>2,000 observed releases, >8 correction targets) fail explicitly. Full title
batches can overfetch other seasons; normal seasons fit one 500-record request.
Recent offset pages can straddle updates: overlap polls and deduplicate GUIDs.
The cache covers prior queries/pages only, not complete offline search. Old
snapshot tables are retained solely for compatible private-schema upgrades;
no snapshot client/updater is present. Native job enforcement, public rights,
public hosting/defaults, larger capacity/freshness and other providers remain
release work. The old snapshot validator timeout remains failed evidence.

Results and exact measurement scope: [EVIDENCE.md](../../../internal/specs/020-catalog-query-api-evaluation/EVIDENCE.md).
