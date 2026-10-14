# Private Linux collector and separate local client

Use `server.yaml`, not the generated fixture `compose.yaml`, for normal collection.
AniWorld and Serienstream are enabled. Megakino is optional and currently has a
live language-observation blocker; it is not required for this pilot. Nothing in
this guide deploys a host automatically or authorizes a public/default service.

### Running the deployed Coolify pilot

The existing pilot is managed in the separate **AniBridge Private Pilot**
project, service **anibridge-private-catalog**, on `fra-node-01`. The authorized
October 11 upgrade uses the pinned GHCR worker manifest and `pull_policy: missing`
from the [current deployment procedure](#october-11-published-preview-deployment).
Use **Restart current version** only for a separately approved change. The old
local image and `pull_policy: never` belong to rollback. Retain the three prefixed
volumes. Do not start a second manual
Compose stack for this deployment. **Running (no healthcheck)** describes these
worker containers; inspect actual collection progress with this command in the
collector's Coolify terminal:

```sh
anibridge-catalog-worker --config /config/worker.json --status
```

Normal collection events are in `/state/logs/worker.jsonl`, rather than Docker
stdout. In the same collector terminal, run:

```sh
tail -n 50 -f /state/logs/worker.jsonl
```

Coolify's Runtime Logs show startup/runtime errors; the metadata API deliberately
has no request access logs. Timestamped worker events retain sanitized HTTP
status/error classes, admission waits and retry reasons. A provider's `blocked`
status alone does not prove an IP ban: explicit challenges, remote throttling
and sustained actual transport failures have separate policies described below.
Local budget/pool waits and parser errors never establish a provider ban.

The pilot backend is pinned to **172.16.27.0/24**. On October 6, the unpinned
Coolify `default` network had allocated `192.168.0.0/20`, shadowing NetBird's
route to `192.168.2.1`. The source Compose was updated and that network replaced.
The authorized host-level repair also sets Docker's `default-address-pools` to
`[{"base":"10.254.0.0/16","size":24}]`; these ranges were checked against the
host's existing Docker and VPN routes. Changing the daemon pools does **not**
renumber existing networks. Preserve volumes when replacing a conflicting network.

The disposable Mac client configuration is under
`$HOME/anibridge-private-client-config`; its `pilot.env` contains paths/image tag,
not the bearer token. From the AniBridge checkout, start or stop that client with:

```sh
docker compose --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml up -d --no-build
docker compose --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml stop
```

Its Torznab URL is `http://127.0.0.1:18000/torznab/api`, and its
qBittorrent-compatible base URL is `http://127.0.0.1:18000`. They are local only.
Use a separate test client/library, not the maintainer's real installation.

`Configs/docs/Infos.md` lists `eyg-node-01` (24fire, Debian 13) and `fra-node-01`
(OCI ARM, Ubuntu). Its hardware/disk figures are inventory, not current free-space
measurements. Either architecture is usable; choose a host with **at least 30 GB
actually available for the pilot data budget**, plus OS/other-service headroom.
Measure `df -h` on that host first. Do not assume Docker Desktop's thin virtual
filesystem free space is physical Mac capacity. No full crawl was run on the Mac.

## Transfer and configure

The implementation branch is now pushed as draft PR #170 into `v3`; `main`
remains default. Approved existing-pilot rollouts use pinned preview manifests.
For an offline source transfer instead, use the XPipe-managed connection and
an operator-created Git bundle:

```sh
# On the development machine:
git bundle create /tmp/anibridge-private-pilot.bundle zzackllack-aux/catalog-query-api-implementation
# Transfer that file yourself. On the selected Linux host:
git clone /path/to/anibridge-private-pilot.bundle anibridge-private-pilot
cd anibridge-private-pilot
git checkout zzackllack-aux/catalog-query-api-implementation
export PILOT_COMMIT=$(git rev-parse HEAD)
export PILOT_CONFIG_DIR="$HOME/anibridge-private-config"
# Verify this unused subnet against `ip route show table all` and Docker IPAM.
export PILOT_BACKEND_SUBNET=172.16.27.0/24
# Choose your DNS name; the HTTPS origin must have a normally verified certificate.
export PILOT_METADATA_HOST=YOUR-METADATA-HOSTNAME
python3 scripts/catalog/query_pilot/prepare_server.py "$PILOT_CONFIG_DIR" \
  --metadata-origin "https://$PILOT_METADATA_HOST" \
  --aniworld-origin https://aniworld.to \
  --serienstream-origin https://serienstream.to
export COMPOSE_FILE=scripts/catalog/query_pilot/server.yaml
docker compose -p anibridge-private-catalog config --quiet
docker compose -p anibridge-private-catalog build
docker compose -p anibridge-private-catalog run --rm initialize
```

The initializer copies operator-owned private files into a UID-1000 config
volume. The source directory and tokens remain mode 0700/0600. It never seeds
metadata. Source identity is independent of provider origins: Serienstream stays
`s.to` even though **do not use the broken s.to origin**. AniWorld `.cc` also
passed the bounded listing check. Plain HTTP IP origins are refused. HTTPS DNS,
certificates and every provider redirect are verified; no browser solver exists.

The generated configuration explicitly enables Skyhook TV descriptor enrichment
and permits publication of its compact mappings. Queries never perform those
lookups. Set TV enrichment to `off` if unwanted; TV ID discovery will then remain
unresolved. This does not authorize redistribution outside your private pilot.

Optional Megakino configuration uses these extra preparation arguments in a
**fresh** config directory:

```sh
--megakino-origin https://megakino22.com --megakino-sitemap-origin https://megakino3.com
```

The sitemap origin is an explicit metadata URL alias: only its path is retained;
no requests, redirects or credentials go to that old origin. Movie enrichment
requires your own TMDb bearer file in the config directory. Add
`"movie":"tmdb","tmdb_token_file":"/config/tmdb-token"` to `canonical_sources`
and `"tmdb-v3"` to `publication_sources`. After initialization, copy the secret
inside the isolated project:

```sh
docker compose -p anibridge-private-catalog run --rm --user root --entrypoint sh initialize \
  -ec 'cp /operator/tmdb-token /config/tmdb-token; chown 1000:1000 /config/tmdb-token; chmod 600 /config/tmdb-token'
```
A token alone does not resolve the live player-language gap. Unknown Megakino series remain inventoried as
unsupported; they are never processed as movies. Its recent-change feed is
unsupported, so only bounded historical reconciliation applies.

## Start, inspect, restart

```sh
# Server only: this is the real bootstrap and continuing scheduler.
docker compose -p anibridge-private-catalog up -d collector metadata
docker compose -p anibridge-private-catalog run --rm --no-deps collector \
  --config /config/worker.json --status
docker compose -p anibridge-private-catalog logs --tail 50 collector
docker compose -p anibridge-private-catalog restart collector metadata
```

Status reports counts, pending/failed pages, oldest checks, blocked-until times,
canonical title/episode coverage, ambiguity and recent-feed overlap/gaps. A
missing provider or unfinished bootstrap is never labelled complete. Initial
API responses may be 503 until the first useful publication. Publication begins
with partial detail coverage and thereafter uses a 300-second minimum interval.
Each provider has its own immutable pointer and last-good catalog. Publication
fences that provider's writer only; other providers and queries continue.

Current repaired defaults: four fetch slots, two per provider, 2-second start
spacing and at most 1,800 provider requests/hour; recent feeds every 15 minutes
for TV, full listings every four hours. Targeted recent hints take priority;
historical work has a weekly target cadence,
a reserved scheduler share and a 20% hourly request budget. Those are targets,
not a promise to finish a provider in a week. Failed/blocked requests use durable
provider-specific cooldowns. Restarts reuse page checkpoints, leases, first-seen
history and enrichment hints. TLS/parse failures preserve previous observations.

No all-provider bootstrap duration or capacity estimate has been measured.
The selected Serienstream run made 30 provider requests, with 57 seconds between
its first and last detail checkpoints; it was partial, not a full bootstrap.
Measure growth and mapping coverage with `--status` during the real server pilot.
The fixed **30,000,000,000-byte aggregate** is shared by all providers: state and
backups 20 GB, read catalogs/staging 9 GB, runtime/log/image reserve 1 GB. Builds
and collection refuse storage pressure. One globally serialized publication
child, current file per provider and bounded staging; no historical read archive.
The initial constrained pilot gave each collector/API container 512 MiB, two
CPUs, no swap, 64 PIDs. The authorized October 11 rollout raises only the
collector to 2 GiB; metadata remains 512 MiB. Production worker sizing is minimum
2 vCPU/2 GiB, recommended 4 vCPU/4 GiB, optional 6 GiB after profiling. The
metadata API has a separate budget. Docker logs
are 3 × 10 MB per service and worker events are 5 × 10 MiB. Do not raise limits to
mask a failure; change explicit profiles from measurements. Run one collector;
its process lock rejects a competing writer. The local client's metadata/search
target is 1 vCPU/512 MiB; whole extraction/job peaks still need separate proof.

Collector state v4 adds source episode aliases, season-row checkpoints and
bounded lifetime counters; the verified `.pre-v4.backup` is never overwritten.
Older worker binaries refuse v4; use a forward repair, or rehearse recovery from
the retained backup in an isolated copy. Never blindly downgrade the live ledger
or discard records collected after that backup.
Retain the current ledgers/volumes during upgrades. Existing failure and cooldown
checkpoints are not cleared. First-pass season refreshes accelerate the old
never-checked episode queue exactly once, including rows unsupported by batching.
After due work is exhausted, idle bootstrap admits never-checked descendants
deferred by a recent hint; failed/targeted work keeps its real retry deadline.

Hourly budgets defer before acquiring fetch slots. Short start-spacing waits
within redirect chains release/reacquire their cancellable slot outside HTTP
deadlines, retaining the same hop chain. Local pool timeouts defer work without
a provider failure. Transient pages retry with
5-second exponential base, jitter and a 300-second base ceiling; eight real
consecutive failures spanning at least 30 seconds in a two-minute window open a
60-second exponential circuit (900-second base ceiling). Success resets the
streak. Parser/resource waits never open circuits. Explicit blocks use one
half-open probe after 15 minutes, doubling up to six hours. Valid 429 seconds or
HTTP dates use a one-second to 24-hour bound; malformed values default to 60s.

`provider_settings` in worker JSON supports per-provider `limits` for
`provider_concurrency`, `provider_request_interval_s`, `provider_requests_per_hour`
and `headers` for `User-Agent`, `Accept`, `Accept-Language`, `Referer`. Only the
configured origin root is a valid Referer; `Accept-Encoding` remains identity.
Two/provider, four total and 2-second spacing are retained. The 1,800/hour cap
matches existing spacing rather than increasing start density. Bounded live
checks found no benefit from a Chrome header string, so the default identifies
AniBridge with stable HTML/German-English headers. This does not simulate browser
TLS or JavaScript. See `apps/catalog-worker/config.example.json`.

Status `progress` separates first-pass/detail evidence from usable and mapped
counts, reports current-queue rates and suppresses ETA while discovery can grow.
`complete` describes supported first-pass detail coverage, never universal
canonical resolution or lossless recent-feed coverage. Queue counts expose due,
deferred and leased first-pass work plus due failures. Recent gaps remain latched
until a separate reconciliation proof exists. Events include UTC timestamps,
HTTP status/error class, retry due/reason, budget waits and network/parser times.
No paths, response bodies, bearer credentials or private query/IP history.

Finite Linux measurements and remaining complete-bootstrap limit are in
[EVIDENCE.md](../../../internal/specs/020-catalog-query-api-evaluation/EVIDENCE.md).
The repaired defaults are not a measured full-bootstrap duration or sustained
provider-capacity promise. Keep historical 512-MiB measurements labelled as the
constrained test profile and retain the 30 GB aggregate storage budget.

Do not restart bootstrap daily. The normal work is recent-feed polling, targeted
metadata checks and rolling historical reconciliation. Active title/season
parents become eligible after four hours; gap parents share the existing 20%
reconciliation budget. Failed work keeps its retry deadline. Pending gap-parent
counts stay visible, and gaps remain latched until a separate coverage proof.
Eligibility does not guarantee a four-hour SLA. Search stays catalog-only.

## HTTPS ingress

The metadata listener is loopback-only on server port 18080. For the existing
Traefik setup, verify the live network/resolver names before opting in:

```sh
export PILOT_PROXY_NETWORK=coolify
export PILOT_TLS_ENTRYPOINT=https
export PILOT_TLS_RESOLVER=letsencrypt
export COMPOSE_FILE=scripts/catalog/query_pilot/server.yaml:scripts/catalog/query_pilot/ingress.yaml
docker compose -p anibridge-private-catalog config --quiet
docker compose -p anibridge-private-catalog up -d metadata
```

The names above match the checked-in `Configs/Coolify/Proxy/24fire-3.docker-compose.yaml`,
not a verified live proxy. Create the selected DNS record yourself; prefer private
network reachability. The router accepts only HTTPS POST `/catalog/v1/query` on
that hostname. AniBridge compatibility and management routes are on the separate
local client, never this server ingress. Bearer auth is still enforced by the
application. Router access logs, metrics and tracing are disabled (Traefik 3.7
configuration); check proxy logs if your installed version rejects those labels.
Upstream proxies/operators can observe queries/IPs despite application logging
being off. Official label reference: [Traefik routing](https://doc.traefik.io/traefik/reference/routing-configuration/http/routing/router).

Test TLS and authentication without printing credentials:

```sh
python3 - "$PILOT_CONFIG_DIR" <<'PY'
import json, sys, urllib.request, urllib.error
from pathlib import Path
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, *args):
        raise urllib.error.HTTPError(request.full_url, 302, 'redirect refused', {}, None)
http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
root = Path(sys.argv[1])
config = json.loads((root / 'client.json').read_text())
body = json.dumps({'operation':'recent','provider':'s.to','params':{'t':'search'},'limit':1}).encode()
url = config['origin'] + '/catalog/v1/query'
for authorized in (False, True):
    headers = {'Content-Type':'application/json'}
    if authorized:
        headers['Authorization'] = 'Bearer ' + (root/'metadata-token').read_text().strip()
    try:
        with http.open(urllib.request.Request(url, body, headers), timeout=5) as r:
            print('authorized' if authorized else 'unauthorized', r.status)
    except urllib.error.HTTPError as error:
        print('authorized' if authorized else 'unauthorized', error.code)
PY
```

Expected: unauthenticated 401; authenticated 200 after publication, or explicit
503 while cold/unavailable. No `-k`, HTTP remote fallback or authentication bypass.
Actual remote TLS has not been tested because no host/DNS deployment was requested.

## Separate local AniBridge

Copy **only** `client.json` and `metadata-token` to a new private local directory
through your secure operator connection. Do not copy the worker ledger or read
catalog to the client. Client JSON uses the verified remote HTTPS origin, source
ID and `/config/metadata-token`; leave `allow_private_http` absent/false.

```sh
# In the same committed checkout on the Mac/local Linux machine:
export PILOT_COMMIT=$(git rev-parse HEAD)
export PILOT_CLIENT_CONFIG_DIR="$HOME/anibridge-private-client-config"
export PILOT_DOWNLOAD_DIR="$HOME/anibridge-private-client-downloads"
mkdir -p "$PILOT_DOWNLOAD_DIR"
export PILOT_CATALOG_SITES=aniworld.to,s.to
export PILOT_ANIWORLD_ORIGIN=https://aniworld.to
export PILOT_STO_ORIGIN=https://serienstream.to
export COMPOSE_FILE=scripts/catalog/query_pilot/local-client.yaml
docker compose -p anibridge-private-client config --quiet
docker compose -p anibridge-private-client build
docker compose -p anibridge-private-client up -d
curl --fail http://127.0.0.1:18000/health
curl --fail --get http://127.0.0.1:18000/torznab/api \
  --data-urlencode t=tvsearch --data-urlencode tvdbid=81189 \
  --data-urlencode season=1 --data-urlencode ep=1
```

Configure Prowlarr/Sonarr with the local Torznab endpoint and qBittorrent-compatible
client. If clients are containers, put them on the local API's Docker network and
use `http://api:8000`; never publish that compatibility API to the Internet.
Mount the **same disposable downloads path** into AniBridge and the client with
the same path, or explicitly configure the client's remote-path mapping. Sonarr's
library remains a separate client-owned path. Allow Unknown quality explicitly
for this test; no codec/size/quality is inferred. STRM configuration and existing
mainline paths remain supported; this disposable example defaults to download.

Requests use a finite 128-entry cache, provider-scoped revision floors and the
existing 60-second TTL/24-hour positive stale fallback. Cold outages/authentication
failures remain explicit errors. Multi-provider partial results identify missing
providers in headers; totals describe the available providers. Large TV requests
select the requested canonical coordinates plus local correction entities before
batching. Limits remain 200 titles and 2,000 native releases per provider/search;
500/native page, 100/recent page, offset <=10,000 and 15 seconds/search. Broad
history requests still fail explicitly. Recent prefix merges are bounded by the
requested offset, page ceiling and deadline; they never fetch per episode.

## One familiar item per provider

Stop the collector before an operator-selected-title pass so its writer lock is
available. This command also works inside an existing normal bootstrap ledger;
it never treats other titles as absent. Maximum 30 requests/120 seconds/pass:

```sh
# Server COMPOSE_FILE/PILOT_CONFIG_DIR still selected:
docker compose -p anibridge-private-catalog stop collector
docker compose -p anibridge-private-catalog run --rm --no-deps collector \
  --config /config/worker.json --provider s.to --collect-title /serie/breaking-bad
# Choose a familiar AniWorld path yourself; retained Bunny discovery need not repeat.
docker compose -p anibridge-private-catalog run --rm --no-deps collector \
  --config /config/worker.json --provider aniworld.to --collect-title /anime/stream/YOUR-SHOW
# Optional only after enabling Megakino; expect zero releases if language is unknown:
docker compose -p anibridge-private-catalog run --rm --no-deps collector \
  --config /config/worker.json --provider megakino --collect-title /films/1014-inception.html
docker compose -p anibridge-private-catalog up -d collector
```

Start with local `t=search&q=TITLE` and inspect totals/languages. For canonical TV
use `t=tvsearch&tvdbid=ID&season=N`; for a mapped movie use
`t=movie&tmdbid=27205` or IMDb. Movies retain null episode coordinates. Radarr
live discovery is blocked for the tested Megakino movie's unlabelled player, not
turned into fake S01E01. Missing TV year/title evidence, repeated episode names,
split seasons and unresolved canonical correspondence stay explicit. Three
unique independent episode-name anchors can prove a season; numbering cannot.
AniWorld's demonstrated trailing `[Final Episode]` and `[Episode NNN]`
annotations have conservative unique-name fallbacks; other brackets do not. Local correction commands in README remain
available for exceptional cases and are applied before filters/totals/pages.

Use [ACCEPTANCE.md](ACCEPTANCE.md) for generated media. Add `acceptance-sto.yaml`
and a fresh `anibridge-query-sto-acceptance` project for the Serienstream scenario.
That passes through the real production resolver/download/remux/job completion
and Sonarr import. Never install its HTTP input hook in the real pilot. Live
extraction/import/playback needs suitable explicitly authorized media; metadata
requests alone do not prove that part.

## Backup, restore, cleanup and upgrades

```sh
# Server: the API can keep serving while the collector is stopped/backed up.
docker compose -p anibridge-private-catalog stop collector
docker compose -p anibridge-private-catalog run --rm --no-deps collector \
  --config /config/worker.json --backup
docker compose -p anibridge-private-catalog up -d collector
```

A single `/state/backup` set is admitted within the same disk quota and refuses
overwrite. Keep the matching operator config/token separately under private
permissions. Creating another full backup may be refused near the budget; do not
retain uncontrolled duplicate sets. SQLite's backup API includes committed WAL
state; do not copy only an active `.sqlite` file.

Restore that set only in the same **disposable** project:

```sh
docker compose -p anibridge-private-catalog stop collector metadata
docker compose -p anibridge-private-catalog run --rm -T --no-deps --entrypoint python collector - <<'PY'
import shutil
from pathlib import Path
root = Path('/state/backup')
assert root.is_dir() and not (root/'INCOMPLETE').exists()
for backup in root.glob('*.sqlite'):
    destination = Path('/state') / backup.name
    for suffix in ('-wal', '-shm'):
        destination.with_name(destination.name+suffix).unlink(missing_ok=True)
    shutil.copy2(backup, destination)
PY
docker compose -p anibridge-private-catalog run --rm --no-deps collector \
  --config /config/worker.json --publish
docker compose -p anibridge-private-catalog up -d collector metadata
# Stops and retains state:
docker compose -p anibridge-private-catalog down
# Deletes ONLY this disposable project's volumes, after retaining needed evidence:
docker compose -p anibridge-private-catalog down -v --remove-orphans
```

For local-client cleanup use its own Compose file and `anibridge-private-client`
project. Its downloads bind directory is not removed by `down -v`; inspect/delete
only that disposable directory yourself. Never target retained Bunny, old accepted
projects or an actual installation. The restore command restores metadata state;
read pointers retain monotonically increasing revisions, so clients do not
accept older replayed revisions. Publish rebuilds every configured provider.

Before upgrading, rehearse with an **already consistent released-mainline backup**
and matching STRM/files in a separate directory. Do not mount the installation:

```sh
export PILOT_REHEARSAL_DIR="$HOME/anibridge-private-upgrade-copy"
mkdir -m 700 "$PILOT_REHEARSAL_DIR"
cp -a "$RELEASED_PRIVATE_BACKUP/." "$PILOT_REHEARSAL_DIR/"
# Runs migrations only; no lifespan, network, scheduler or grabs.
docker run --rm --network none --user root \
  -e DATA_DIR=/data -e ANIBRIDGE_UPDATE_CHECK=false \
  -v "$PILOT_REHEARSAL_DIR:/data" \
  --entrypoint python "anibridge-query-api:$PILOT_COMMIT" \
  -c 'from app.db.models import apply_migrations; apply_migrations()'
```

Compare Job/ClientTask hashes, STRM rows/files and correction rows against the
input backup before starting this copied state. The additive migration keeps a
`anibridge_jobs.db.pre-catalog-v3.backup`; foreign schemas are refused. Tests cover
released schema variants and interrupted backup/upgrade recovery. Your actual
private backup was not supplied or accessed. For forward restoration remove
`CATALOG_CONFIG_FILE` using this compatible build. A released-v2.6.0 downgrade
requires the retained preupgrade backup plus matching files and loses subsequent
jobs; do not downgrade a migrated DB in place.

## October 11 existing Coolify upgrade and rollback

**Prepared and rehearsed, not deployed. Explicit approval is required before
image loading, stopping/restarting services, publication on live volumes or
updating the disposable client.** This image-only diagnostic upgrade retains
2 CPU/512 MiB; the independently measured production minimum remains 2 CPU/2 GiB.
Do not change allocations or deadlines to infer CQ-22's historical cause.

Both local ARM64 images were built and their OCI labels verified at
`73a996cbf78c524380f3ba387ebe97ed24b692cf`. Copied pilot ledgers were opened,
published and backed up without a schema upgrade. Rollback uses the same v4
ledgers and preserves observations made since the upgrade; it needs no restore.
All three worker references (`initialize`, `collector`, `metadata`) must change.
Keep the original config/token, three volumes, retry/checkpoint/pre-v4 backups,
release identities and first-seen times. Preserve backend `172.16.27.0/24`,
Docker pool `10.254.0.0/16` in `/24`s, and NetBird routes.

Prepare reviewable private API payloads locally. `COOLIFY_URL` is the existing
operator's Coolify origin; `COOLIFY_AUTH_FILE` is a mode-0600 curl config containing
its existing Authorization header. Do not print credentials or commit these
files. GET returns plain compose; PATCH expects base64, as specified by the
[maintained Coolify API schema](https://github.com/coollabsio/coolify-docs/blob/main/config/openapi.json).

```sh
set -e
: "${COOLIFY_URL:?Set the existing Coolify origin}"
: "${COOLIFY_AUTH_FILE:?Select private curl authorization config}"
SERVICE_UUID=ev7cds2lpqyvqfxpcm4wp4tc
REPAIR_REVISION=73a996cbf78c524380f3ba387ebe97ed24b692cf
UPGRADE_DIR="$HOME/anibridge-catalog-upgrade-$REPAIR_REVISION"
umask 077
mkdir "$UPGRADE_DIR"
curl --config "$COOLIFY_AUTH_FILE" --fail --silent --show-error \
  "$COOLIFY_URL/api/v1/services/$SERVICE_UUID" > "$UPGRADE_DIR/before.json"
uv run --with pyyaml scripts/catalog/query_pilot/stage_upgrade.py \
  --service "$UPGRADE_DIR/before.json" --revision "$REPAIR_REVISION" \
  --directory "$UPGRADE_DIR/patch"
# Review candidate.json and rollback.json privately before approving deployment.
```

The helper rejects another service or unexpected component/profile, changes
only image references, and produces `instant_deploy: false` payloads. All other
compose fields compare equal; rollback contains the original source bytes.
These assertions were checked against the captured deployed compose. Re-fetch
if someone changes the service after preparation. Never replace Coolify's raw
source with its generated prefixed-volume compose.

After approval, transfer the already tested local image without a registry push:

```sh
SSH_AUTH_SOCK=/Users/zacklack/.bitwarden-ssh-agent.sock \
  docker save "anibridge-query-worker:$REPAIR_REVISION" | \
  SSH_AUTH_SOCK=/Users/zacklack/.bitwarden-ssh-agent.sock \
  ssh -o BatchMode=yes -l zacklack fra-node-01.nb.internal docker load
curl --config "$COOLIFY_AUTH_FILE" --fail --silent --show-error --request POST \
  "$COOLIFY_URL/api/v1/services/$SERVICE_UUID/stop?docker_cleanup=false"
```

Wait for **both** collector and metadata to stop before a one-off volume writer.
On `fra-node-01`, verify the stopped state and create the admitted backup:

```sh
set -e
REPAIR_REVISION=73a996cbf78c524380f3ba387ebe97ed24b692cf
SERVICE_UUID=ev7cds2lpqyvqfxpcm4wp4tc
test "$(docker inspect --format '{{.State.Running}}' collector-$SERVICE_UUID)" = false
test "$(docker inspect --format '{{.State.Running}}' metadata-$SERVICE_UUID)" = false
docker run --rm --network none --cpus 2 --memory 512m --pids-limit 64 \
  -v "${SERVICE_UUID}_config:/config:ro" \
  -v "${SERVICE_UUID}_worker-state:/state" \
  -v "${SERVICE_UUID}_read-catalog:/read" \
  "anibridge-query-worker:$REPAIR_REVISION" --config /config/worker.json --backup
# A pre-existing /state/backup causes an explicit refusal; never delete/overwrite it.
# Validate and retain that existing complete set instead, then resume here only
# after its provenance is reviewed. An INCOMPLETE set cannot be used.
docker run --rm --network none --cpus 2 --memory 512m --pids-limit 64 \
  -v "${SERVICE_UUID}_config:/config:ro" \
  -v "${SERVICE_UUID}_worker-state:/state" \
  -v "${SERVICE_UUID}_read-catalog:/read" \
  "anibridge-query-worker:$REPAIR_REVISION" --config /config/worker.json --publish
```

`--publish` exports existing state only, without a provider request or bootstrap.
It builds validated summaries before starting the new server. Failure retains
last-good catalogs. Do not start the collector alongside either one-off command.
If preparation fails after stopping, use the rollback restart below. Backup,
logs, staging and SQL temporary space remain within the 30 GB budget and 1 GB
reserve; a budget refusal must not be bypassed.

From the original local terminal, save the candidate and restart without pulls:

```sh
curl --config "$COOLIFY_AUTH_FILE" --fail --silent --show-error --request PATCH \
  --header 'Content-Type: application/json' \
  --data-binary "@$UPGRADE_DIR/patch/candidate.json" \
  "$COOLIFY_URL/api/v1/services/$SERVICE_UUID"
curl --config "$COOLIFY_AUTH_FILE" --fail --silent --show-error --request POST \
  "$COOLIFY_URL/api/v1/services/$SERVICE_UUID/restart?latest=false"
# Update only the existing disposable client project, retaining corrections/data.
PILOT_COMMIT="$REPAIR_REVISION" docker compose \
  --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml \
  up -d --no-build
```

Inspect running image labels/resources, `/state/logs/worker.jsonl` phase outcomes,
`--status` pending gaps/retries and authenticated 100-row recent plus native
large-series queries. Repeat ordinary TV discovery and corrected targets through
the disposable client without grabs. Confirm unchanged volume/network identities,
NetBird routing and no OOM/restarts. Keep unknown mappings explicit. A limit-1
health probe is insufficient. Retained diagnostic events can then resolve CQ-22;
publication latency alone does not establish the historical failure cause.

Exact code rollback, from the original local terminal (same saved payload):

```sh
curl --config "$COOLIFY_AUTH_FILE" --fail --silent --show-error --request PATCH \
  --header 'Content-Type: application/json' \
  --data-binary "@$UPGRADE_DIR/patch/rollback.json" \
  "$COOLIFY_URL/api/v1/services/$SERVICE_UUID"
curl --config "$COOLIFY_AUTH_FILE" --fail --silent --show-error --request POST \
  "$COOLIFY_URL/api/v1/services/$SERVICE_UUID/restart?latest=false"
PILOT_COMMIT=71988fc8251e6a89823828ca3e871ab47ba2fc28 docker compose \
  --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml \
  up -d --no-build
```

The saved source restores worker `39ba345626a9535aac31e7e356c34b4e889530af`
and its original settings. Keep both old images locally. Do not restore a ledger,
clear failures, restart bootstrap, use `down -v`, replace networking or update
unrelated services during rollback. New subtitle observations are valid read
contract languages; the old worker can consume the compatible v4 state.

## October 11 published preview deployment

The earlier local-image preparation is historical. The existing private pilot
was upgraded with explicit maintainer authorization through Coolify's Zen UI.
It now uses the public multi-architecture preview package, pinned by digest:

```text
ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1277d1fd6ec7130a53c5ed4a694dd8efada7e95db6c86bd897e3e446f2149e0a
```

OCI revision: `36fbd511890b0c08a80385b0a2542d3c6b51c1d3`. All three worker
components use this image and `pull_policy: missing`. Only collector memory
changed: `mem_limit: 2g`, `memswap_limit: 2g`, `cpus: 2`. Initialization and
metadata retain 512 MiB. Never deploy the mutable `pr-170` alias implicitly:
later commits produce another image, without authorizing another deployment.

The supplied private `Configs/temp/anibridge-private-catalog.yaml` matches the
saved live source. Its sibling `anibridge-private-catalog.rollback-39ba345.yaml`
contains the original raw compose. Both files are ignored/private. Saved API
payloads also remain in `/tmp/anibridge-pilot-registry-upgrade/`; retain the YAML
sibling for rollback beyond temporary-directory cleanup. `/state/backup` now
holds a complete, integrity-checked 1,117,626,368-byte SQLite backup set; do not
overwrite it. Original pre-v4 backups remain. State is still v4-compatible.

For a repeat of this **specific pinned upgrade**, after separate authorization:

1. In the existing Coolify service's **Edit Compose File**, save the supplied
   current YAML. Verify all three pinned image references and only the collector
   2 GiB change. The connected API token is read-only and returns 403 for writes;
   use an existing authenticated Zen session or an already authorized write
   token. Do not broaden the read-only token merely to deploy.
2. On `fra-node-01`, run the commands below. Keep volumes and networks present.
   The existing backup is retained; no additional backup is created by this
   repeat procedure. Review its age before using it as a recovery point.
3. After successful publication, use **Deploy** (or **Restart current version**)
   on that same service. Verify authenticated queries, resources, preserved
   release identities and routes as above. This does not update the local client.

```sh
set -e
SERVICE_UUID=ev7cds2lpqyvqfxpcm4wp4tc
PILOT_WORKER=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1277d1fd6ec7130a53c5ed4a694dd8efada7e95db6c86bd897e3e446f2149e0a
docker pull "$PILOT_WORKER"
docker stop --timeout 45 "collector-$SERVICE_UUID"
docker stop --timeout 15 "metadata-$SERVICE_UUID"
test "$(docker inspect --format '{{.State.Running}}' collector-$SERVICE_UUID)" = false
test "$(docker inspect --format '{{.State.Running}}' metadata-$SERVICE_UUID)" = false
docker run --rm --network none --cpus 2 --memory 2g --memory-swap 2g --pids-limit 64 \
  -v "${SERVICE_UUID}_config:/config:ro" \
  -v "${SERVICE_UUID}_worker-state:/state" \
  -v "${SERVICE_UUID}_read-catalog:/read" \
  "$PILOT_WORKER" --config /config/worker.json --publish
```

Exact rollback: save `anibridge-private-catalog.rollback-39ba345.yaml` in that
same service's compose editor, then **Restart current version**. It restores
`anibridge-query-worker:39ba345626a9535aac31e7e356c34b4e889530af`, its original
`pull_policy: never` and collector 512 MiB limit. That image remains on the host;
verify before restart:

```sh
docker image inspect --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}' \
  anibridge-query-worker:39ba345626a9535aac31e7e356c34b4e889530af
```

With an existing write-capable API token, the exact original source payload is
also `/tmp/anibridge-pilot-registry-upgrade/rollback.json`; PATCH it and POST
`/api/v1/services/ev7cds2lpqyvqfxpcm4wp4tc/restart?latest=false` using the earlier
curl pattern. Do not restore ledgers for code rollback: it would discard newly
collected metadata. Do not clear failures, repeat bootstrap, use `down -v`, or
call the service stop API with its default Docker cleanup behavior. The original
512 MiB rollback profile is still constrained and can reproduce memory pressure.

## October 14 mapping follow-up: prepared upgrade and code rollback

This follow-up is **local and unpushed**. No new registry manifest exists yet.
ARM64 installed worker/API images, copied-ledger publication/query checks, v5/v4
rollback/resume and a copied disposable-client migration were tested. Native
AMD64, hosted CI, registry publication and live worker/client cutover remain
unverified. Publishing and deploying are separate approval decisions. The
existing service remains on the October 11 pinned digest. The Mac client is
stopped on `71988fc`; do not restart it as part of preparation.

After separately approved preview publication, inspect both native manifests and
record the actual source SHA and pinned digests. Never substitute the local
verification image IDs for GHCR manifest digests. Obtain a fresh read-only raw
Coolify service record and private worker configuration, then prepare files:

```sh
: "${WORKER_MANIFEST:?Reviewed ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256 digest}"
: "${SERVICE_RECORD:?Fresh private raw service JSON}"
: "${WORKER_CONFIG:?Private copy of current worker.json}"
: "${UPGRADE_DIR:?New private preparation directory}"
uv run --project apps/api --frozen python scripts/catalog/query_pilot/stage_registry_upgrade.py \
  --service "$SERVICE_RECORD" --worker-config "$WORKER_CONFIG" \
  --worker-image "$WORKER_MANIFEST" --directory "$UPGRADE_DIR"
```

The tested helper refuses the wrong UUID, a mutable image, unexpected old digest,
pull policy, languages or CPU/memory/swap profile. It changes all three worker
references together, adds `episode_languages: ["deu"]`, and retains the original
raw Compose bytes and parsed configuration for rollback. Review the generated
files privately. Preserve all volumes, backend `172.16.27.0/24`, Coolify's separate
managed network, Docker pool `10.254.0.0/16` in `/24`s and NetBird routes. No source
YAML replacement with generated prefixed-volume Compose is permitted.

Only **after explicit deployment approval**, use the existing authenticated Zen
browser to stop service `ev7cds2lpqyvqfxpcm4wp4tc`. The read-only API token cannot
perform writes; do not broaden credentials or use the in-app browser. Transfer
the reviewed config files plus `install_reviewed_worker_config.py` into an
operator-owned private directory on `fra-node-01`, set `UPGRADE_DIR` there, and
retain exact original source/volume config bytes as `operator-rollback.json` and
`volume-rollback.json` there. The initializer source must match the reviewed
active JSON before staging. Verify stopped writers:

```sh
SERVICE_UUID=ev7cds2lpqyvqfxpcm4wp4tc
OLD_WORKER=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1277d1fd6ec7130a53c5ed4a694dd8efada7e95db6c86bd897e3e446f2149e0a
test -z "$(docker ps --filter name=collector-$SERVICE_UUID --filter name=metadata-$SERVICE_UUID -q)"
# Retain /state/backup and every pre-v4/pre-v5 backup. Never overwrite them.
# Admit the migration copy, read staging/SQL scratch and 1 GB reserve under 30 GB.
docker run --rm --network none --cpus 2 --memory 2g --memory-swap 2g \
  --user root --entrypoint python \
  -v "${SERVICE_UUID}_config:/config" \
  -v /root/anibridge-private-config:/operator \
  -v "$UPGRADE_DIR:/review:ro" \
  "$WORKER_MANIFEST" /review/install_reviewed_worker_config.py \
  --plan /review --operator /operator --config /config
docker run --rm --network none --cpus 2 --memory 2g --memory-swap 2g --pids-limit 96 \
  -v "${SERVICE_UUID}_config:/config:ro" \
  -v "${SERVICE_UUID}_worker-state:/state" \
  -v "${SERVICE_UUID}_read-catalog:/read" \
  "$WORKER_MANIFEST" --config /config/worker.json --publish
```

Coolify Stop can remove the containers; the assertion above permits absent or
exited containers but rejects either running writer. Before changing either
configuration location, compare both current JSON objects privately against the
reviewed rollback config and retain their exact original bytes. The initializer
copies `/root/anibridge-private-config/worker.json` into the config volume on
startup, so **both** locations must change together. The actual October 14
rollout used `catalog_core.files.atomic_write`, guarded by exact original-byte
comparisons, preserving each file's owner and its separate rollback copy. The
maintained installer retains owner/0600 permissions and refuses an independent
edit before changing either location. A partial I/O failure permits retry or
rollback from either reviewed version; four focused regressions cover initializer
copy, exact-byte rollback, independent-edit veto and second-write failure recovery.

Publication is offline and upgrades only recognized private v4 state, retaining
a verified no-overwrite `.pre-v5.backup`. Failure retains last-good read pointers.
Do not start a collector alongside this command. In Zen, save the reviewed
`candidate.yaml` and use **Restart current version**. Recheck actual image SHA,
limits, volumes, routes, release/first-seen preservation, due ages, safe failure
subcodes, publication phases and exact-total metadata queries. A short recheck
cannot establish whole-provider freshness or full-bootstrap capacity.

If rollback is needed under the approved rollout, stop the same service in Zen
and repeat both stopped-container assertions. Wait at least 60 seconds after
its final canonical request; the tested rollback helper refuses an active durable
admission window. Run with the **new** image before reverting its image reference:

```sh
docker run --rm -i --network none --cpus 2 --memory 2g --memory-swap 2g --pids-limit 96 \
  --entrypoint python -v "${SERVICE_UUID}_worker-state:/state" \
  "$WORKER_MANIFEST" - <<'PY'
from pathlib import Path
from catalog_worker.state_migrations import preflight, rollback_matching
for provider in ('aniworld.to', 's.to'):
    path = Path('/state') / (provider + '.sqlite')
    if preflight(path, provider) == 5:
        rollback_matching(path, provider)
    assert preflight(path, provider) == 4
PY
docker run --rm --network none --cpus 2 --memory 2g --memory-swap 2g \
  --user root --entrypoint python \
  -v "${SERVICE_UUID}_config:/config" \
  -v /root/anibridge-private-config:/operator \
  -v "$UPGRADE_DIR:/review:ro" \
  "$WORKER_MANIFEST" /review/install_reviewed_worker_config.py \
  --plan /review --operator /operator --config /config --rollback
```

In Zen, restore `rollback.yaml` and **Restart current version**. This removes
only v5 private caches/clocks, retaining all v4 tables, accepted maps, source
coordinates, first-seen, failures, leases, checkpoints and quarantine decisions.
Never restore an old ledger over observations made since the upgrade. Both full
copied ledgers opened with the old installed worker after downgrade, then reopened
with the new worker twice; all 32 v4 table hashes and the new pre-v5 backup survived.

The client cutover is a separate approved action. Retain its stopped container,
`anibridge-private-client_local-state`, config volume, downloads and corrections.
After a matching API preview is approved, create two private override files:

```sh
: "${API_MANIFEST:?Reviewed matching ghcr.io/zzackllack/anibridge-api-preview@sha256 digest}"
CLIENT_PLAN="$HOME/anibridge-private-client-upgrade"
umask 077
mkdir "$CLIENT_PLAN"
cat > "$CLIENT_PLAN/candidate.yaml" <<EOF
services:
  initialize:
    image: $API_MANIFEST
  api:
    image: $API_MANIFEST
EOF
cat > "$CLIENT_PLAN/rollback.yaml" <<'EOF'
services:
  initialize:
    image: anibridge-query-api:71988fc8251e6a89823828ca3e871ab47ba2fc28
  api:
    image: anibridge-query-api:71988fc8251e6a89823828ca3e871ab47ba2fc28
EOF
docker compose --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml \
  -f "$CLIENT_PLAN/candidate.yaml" config --quiet
# After separate client approval:
docker compose --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml \
  -f "$CLIENT_PLAN/candidate.yaml" up -d --no-build
# Exact code rollback, retaining the same state and volumes:
docker compose --env-file "$HOME/anibridge-private-client-config/pilot.env" \
  -p anibridge-private-client -f scripts/catalog/query_pilot/local-client.yaml \
  -f "$CLIENT_PLAN/rollback.yaml" up -d --no-build
```

The existing client DB contains no jobs or corrections; copied migration retained
all 18 tables exactly. Current API/core metadata fixtures passed at 1 CPU/512 MiB;
this does not verify the stopped client against live metadata, or any live
extraction/import/playback. Retain its existing Compose allocations during a
later cutover; the smaller verification profile is not permission to resize it.

### October 14 matching published manifests

The subsequent user authorization permits this pilot/client cutover. Hosted
tests and native preview builds passed on `2240b91`. The following immutable
manifests are the tested pair for the procedure above; do not substitute a moving
PR alias. The actual registry ARM64 worker also passed offline full-copy
publication/query/last-good/isolation checks without a source overlay.

```sh
WORKER_MANIFEST=ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:250313035479c17e0df65cbc5347261536f2c8bba34b8e11ed3ba05ed399278f
API_MANIFEST=ghcr.io/zzackllack/anibridge-api-preview@sha256:eef48b9211d2a5e01d34568d464e3cbf7d647a4ba1f4b6d4544496772f857e58
```

After manual unlock, cutover completed through native Zen, with cleanup disabled.
The unused form was reset/reloaded, saved raw Compose reviewed and all three image
references changed together. Both configuration locations were updated atomically.
Before restart, 32 retained v4 tables/provider compared against the new pre-v5
backups: all 481,435 releases/first-seen and 239,690 existing maps survived; only
the publication timestamp/dirty fields changed as expected. Live SQL-total/native
queries and the authenticated public route pass. The earlier copied-state gains
remain separate: exact AniWorld One Piece S01E01 was still unresolved in the
short live recheck while new descriptors were being verified.

The local client subsequently received the tested API-only logging privacy fix
`6818115`, retaining its 2 CPU/1 GiB allocation, volumes and zero jobs/corrections:

```sh
API_MANIFEST=ghcr.io/zzackllack/anibridge-api-preview@sha256:5d7b6bc059ee60f5385e87c2d380c724be8fc07e869b60c0700fba0fe1d452a9
```

Hosted tests and native image builds passed; installed privacy/subtitle fixtures,
health and real metadata queries pass. The worker stays on the original tested
manifest above. No media acquisition/import/playback is claimed. Exact original
operator/volume config bytes and raw Compose are retained privately at
`/tmp/anibridge-mapping-followup-offline/live-upgrade` on fra-node-01, with the
same review copies on the Mac. Client overrides are retained at
`/Users/zacklack/anibridge-private-client-upgrade`; `rollback.yaml` pins `71988fc`,
`mapping-version.yaml` retains `2240b91`. Follow the full state-preserving rollback
above; never broaden the API token, start a competing collector or restore older
observations over newer ones.
