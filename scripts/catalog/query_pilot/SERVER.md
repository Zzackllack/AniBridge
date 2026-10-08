# Private Linux collector and separate local client

Use `server.yaml`, not the generated fixture `compose.yaml`, for normal collection.
AniWorld and Serienstream are enabled. Megakino is optional and currently has a
live language-observation blocker; it is not required for this pilot. Nothing in
this guide deploys a host automatically or authorizes a public/default service.

### Running the deployed Coolify pilot

The authorized October 6 pilot is managed in the separate **AniBridge Private
Pilot** project, service **anibridge-private-catalog**, on `fra-node-01`. Use its
**Actions → Restart** after saving an image update. Images are built locally on
that server and pinned by commit; keep `pull_policy: never` and avoid **Restart
(pull latest)**. Retain its three prefixed volumes. Do not start a second manual
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

Local commits have not been pushed. Transfer this branch through your chosen
XPipe-managed connection, for example using an operator-created Git bundle:

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

Current repaired defaults: four fetch slots, two per provider, 2-second start spacing and at most
1,800 provider requests/hour; recent feeds every 15 minutes for TV, full listings
and active work every four hours. Historical work has a weekly target cadence,
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
Each collector/API container is 512 MiB, two CPUs, no swap, 64 PIDs. Docker logs
are 3 × 10 MB per service and worker events are 5 × 10 MiB. Do not raise limits to
mask a failure. Run one collector; its process lock rejects a competing writer.

Collector state v4 adds source episode aliases, season-row checkpoints and
bounded lifetime counters; the verified `.pre-v4.backup` is never overwritten.
Older worker binaries refuse v4; use a forward repair, or rehearse recovery from
the retained backup in an isolated copy. Never blindly downgrade the live ledger
or discard records collected after that backup.
Retain the current ledgers/volumes during upgrades. Existing failure and cooldown
checkpoints are not cleared. First-pass season refreshes accelerate the old
never-checked episode queue exactly once, including rows unsupported by batching.

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
canonical resolution or lossless recent-feed coverage. Recent gaps remain latched
until a separate reconciliation proof exists. Events include UTC timestamps,
HTTP status/error class, retry due/reason, budget waits and network/parser times.
No paths, response bodies, bearer credentials or private query/IP history.

Finite Linux measurements and remaining complete-bootstrap limit are in
[EVIDENCE.md](../../../internal/specs/020-catalog-query-api-evaluation/EVIDENCE.md).
The repaired defaults are not a measured full-bootstrap duration or sustained
provider-capacity promise. Preserve the 512 MiB/2 CPU/64 PID and disk limits.

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
Only AniWorld's demonstrated trailing `[Final Episode]` annotation has a
conservative unique-name fallback. Local correction commands in README remain
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
