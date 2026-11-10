# Private collector and metadata service

Use `server.yaml` for real collection and `compose.yaml` only for generated
fixtures. This guide prepares a new explicitly authorized installation; use
[WORKER_UPDATES.md](WORKER_UPDATES.md) for an existing service. Never start a
second collector against retained live volumes. Current acceptance gaps are in
[the open-work list](../../../internal/specs/020-catalog-query-api-evaluation/ISSUES.md).

## Metadata network and credentials

The metadata server uses HTTP behind the operator's TLS ingress. An omitted
`bind_host` now binds `127.0.0.1`; the container setup helper explicitly writes
`0.0.0.0` so the private backend network can reach it. Keep that backend port
private and expose only the authenticated query route through TLS. A configured
non-loopback bind is an explicit network exposure choice, not automatic TLS.

The pilot uses one shared bearer credential. To rotate it, generate a new private
token file, update every client's inline token or mounted token file, and restart
the metadata process with the new credential. Old tokens then stop working;
there is no overlap or per-client revocation. For independently revocable clients,
use separate authenticated ingress identities instead of sharing the pilot token.
Never use the same token for another service.

`ingress.yaml` restricts the route and enables TLS. For additional source-IP
restriction, copy it to a private operator directory and attach a Traefik
`ipAllowList` middleware with the intended NetBird/VPN CIDRs. Match the address
Traefik actually receives; its default policy uses the immediate peer address.
Do not blindly trust client-supplied forwarding headers or use an unverified
VPN prefix. This optional policy requires a separately reviewed ingress change.

Image references of the form `sha-<commit>` identify source revisions but remain
mutable registry tags. Resolve and pin `image@sha256:...` for migration and
rollback plans; the explicit moving-tag private-test workflow in
[WORKER_UPDATES.md](WORKER_UPDATES.md) retains its own verification requirements.

## Prepare a new installation

Work from the repository root on the selected Linux host. Obtain SSH parameters
through the maintained XPipe-to-SSH workflow. Check free space and the complete
aggregate budget before building images or copying data. Verify provider origins
and the metadata hostname; do not assume historical domains still work.

```sh
export PILOT_COMMIT=$(git rev-parse HEAD)
export PILOT_CONFIG_DIR="$HOME/anibridge-private-config"
export PILOT_BACKEND_SUBNET=172.16.27.0/24
uv run --project apps/api --frozen python scripts/catalog/query_pilot/prepare_server.py \
  "$PILOT_CONFIG_DIR" --metadata-origin https://YOUR-METADATA-HOST
```

The helper requires an empty private directory and creates `worker.json`,
`client.env` and a bearer file. Review provider origins and optional canonical
sources before initialization; secrets stay outside Git. Optional Megakino needs
explicit origin/sitemap aliases and observed language evidence. A canonical
credential cannot establish a missing player language.

For optional Filmo movies, add `--filmo-origin https://filmo.to` when preparing
a new installation. The helper leaves canonical movie matching off. To enable
background movie matching, choose one worker `canonical_sources.movie` source.
`radarr` requires no credential. It uses an explicit IMDb ID when available;
otherwise it searches up to two distinct names with the year, accepts only a
unique exact-title/year candidate and verifies the movie detail independently.
This matches the TV title-selection policy; ambiguous results remain unresolved.
Search results do not establish exhaustive worldwide uniqueness. Its
provenance is `radarr-skyhook-v1`; add that value to `publication_sources` to
publish those maps. `tmdb` retains the TMDb v3 path and requires `tmdb_token_file`
to point to a private mounted read credential; add `tmdb-v3` to
`publication_sources`. Keep any token outside Git and public catalogs. Configure
the separate local client with query mode,
`CATALOG_SITES=aniworld.to,s.to,filmo.to` and matching `FILMO_BASE_URL`.
Movie text search can expose unresolved entries. A qBittorrent grab needs an
accepted canonical movie map. Filmo does not supply TV seasons/episodes here.
Filmo's `provider_settings["filmo.to"].headers` may set `"Accept-Language": "en"`
for English catalog titles. This changes title presentation, not the advertised
audio tracks. Collection uses one locale and does not join translated aliases.

Provider request spacing and hourly admission are separate limits. For example,
five-second spacing with a 120/hour cap permits a short burst followed by a long
local wait; five-second spacing alone permits at most 720/hour. Neither value is
an upstream quota. The canonical request budget is shared across providers and
is separate from catalog HTTP admission. More CPU does not raise these budgets.

Benchmark metadata from the intended host with bounded steps and count existing
collector traffic. Stop on throttling/challenges; do not rotate IP families to
bypass them. Short successful trials establish only the tested envelope. Check
eligible-work age, useful observations, parser cost and publication alongside
HTTP throughput before changing budgets. Search serves the published subset
during bootstrap; complete collection is not required for initial use.

For an opt-in five-request/second pilot trial, update only the selected entry
under `provider_settings` in the existing worker JSON:

```json
"filmo.to": {
  "limits": {
    "provider_concurrency": 4,
    "provider_request_interval_ms": 200,
    "provider_requests_per_hour": 18000
  }
}
```

Merge these limits into the entry; retain its headers and all other settings.
Positive `provider_request_interval_ms` takes precedence over seconds; zero uses
`provider_request_interval_s`. A provider-specific seconds override also replaces
an inherited global millisecond interval. Milliseconds must be integer 200–60000
(or zero); hourly admission accepts 1–18000. Existing defaults stay unchanged.
Concurrency and processing cost can keep actual throughput below this ceiling.
Canonical matching retains its separate budget; this setting does not raise it.

Catalog 429/503 pauses and canonical 429/503 origin pauses survive restarts.
The latter use `/state/canonical-cooldowns.json`, an atomic, bounded recovery
receipt containing only fixed source origins and expiry times. Retain it with
state/backup sets. Corruption refuses collection startup; a failed receipt write
stops collection. No catalog schema migration or public protocol change is needed.
Admission records can retain fractional seconds in existing SQLite columns.
Every hop rechecks provider cooldowns, including redirects already in progress;
recovery waits start when the failed result is handled, not when it was planned.

Save the original private config before editing, then pull/redeploy the verified
new worker image through Coolify. Leave all volumes and resource limits intact.
For code rollback, restore the saved config before starting the old pinned image:
old versions reject the new millisecond field and hourly values over 3600. Keep
the current ledger, backups and recovery receipt. Old code ignores the canonical
receipt, so wait for any active source cooldown to expire before starting it.
This pacing change does not require restoring a historical database.

The base template gives metadata 512 MiB. Add the collector's minimum separately:

```sh
cat > "$PILOT_CONFIG_DIR/collector-limits.yaml" <<'YAML'
services:
  collector:
    mem_limit: 2g
    memswap_limit: 2g
YAML
export COMPOSE_FILE="scripts/catalog/query_pilot/server.yaml:$PILOT_CONFIG_DIR/collector-limits.yaml"
docker compose -p anibridge-private-catalog config --quiet
docker compose -p anibridge-private-catalog build
docker compose -p anibridge-private-catalog run --rm initialize
docker compose -p anibridge-private-catalog up -d collector metadata
```

Both services retain 2 CPU; collector minimum is 2 GiB, metadata 512 MiB.
These are finite allocation policies, not bootstrap/freshness guarantees.
Preserve NetBird routing, backend `172.16.27.0/24` and the Docker pool
`10.254.0.0/16` split into /24s. Never change host routing to simplify a test.

## Inspect and expose

```sh
docker compose -p anibridge-private-catalog exec -T collector \
  anibridge-catalog-worker --config /config/worker.json --status
docker compose -p anibridge-private-catalog logs --tail 50 collector metadata
```

Collection events are under `/state/logs/worker.jsonl`. Inspect narrowly and keep
only bounded reason/status counts in shared diagnostics. Admission waits, parse
failures, remote HTTP failures and explicit challenges are different outcomes.
Check progress/publication revisions and real requests, not just container state.
Initial queries can return 503 before the first useful publication.

Metadata binds loopback port 18080. For an existing operator-managed Traefik,
`ingress.yaml` requires `PILOT_PROXY_NETWORK`, `PILOT_METADATA_HOST` and
`PILOT_TLS_RESOLVER`; review that overlay before adding it to `COMPOSE_FILE`.
Use verified HTTPS and bearer authentication. Do not expose the collector or
enable raw query/IP access logs. Existing Coolify service writes require their
own approval through authenticated Zen; the token remains read-only.

## Separate local client

Copy only `client.env` and the bearer file into a private client configuration
directory. Keep worker state on the server. For a new disposable client:

```sh
export PILOT_CLIENT_CONFIG_DIR="$HOME/anibridge-private-client-config"
export PILOT_DOWNLOAD_DIR="$HOME/anibridge-pilot-downloads"
export COMPOSE_FILE=scripts/catalog/query_pilot/local-client.yaml
docker compose -p anibridge-private-client config --quiet
docker compose -p anibridge-private-client build
docker compose -p anibridge-private-client up -d
```

The API reads catalog configuration from environment variables only. The
default `CATALOG_MODE` is `legacy`, retained for existing installations; query
mode is explicit. Legacy query-time scraping is deprecated and may be removed
in a future release. Query mode searches collected metadata, so freshness and
mapping quality affect results. This moves search work to the collector; media
downloads still happen locally.

```dotenv
CATALOG_MODE=query
CATALOG_API_URL=https://YOUR-METADATA-HOST
CATALOG_SOURCE_ID=aniworld.to
CATALOG_API_TOKEN_FILE=/run/secrets/catalog-api-token
CATALOG_ALLOW_PRIVATE_HTTP=
```

Mount the token file read-only at `/run/secrets/catalog-api-token` inside the
API container; host paths are not container paths. The URL is the HTTPS origin
root, with no endpoint path. There is no preset endpoint. For HTTP testing on a
trusted network, set `CATALOG_ALLOW_PRIVATE_HTTP=true`; this permits unencrypted
HTTP to non-loopback hosts and does not enforce private IP addresses. Loopback
HTTP needs no opt-in. Keep the token out of the dotenv file. If a mounted token
file is not available, use `CATALOG_API_TOKEN=<secret>` instead and leave
`CATALOG_API_TOKEN_FILE` blank. Set exactly one token source.

JSON file configuration is removed. A nonempty `CATALOG_CONFIG_FILE` fails
startup instead of silently selecting legacy search; migrate the old JSON
values to the environment variables above. The Oracle-hosted endpoint is private
testing infrastructure and must not be treated as a production default.

The `local-client.yaml` above sources the copied `client.env` inside the API
container; host shell variables alone do not enter a container. When rolling
back to an API image that predates environment configuration, restore the
equivalent JSON configuration and remove the new settings first; older clients
otherwise ignore these variables and may resume legacy search.

The client uses named local-state storage; do not substitute an unsafe shared
filesystem or developer `data/` bind. Secure qBittorrent sessions require the
documented environment settings and real-client acceptance. Search stays
catalog-only; acquisition occurs only for an accepted grab.

## Backup and recovery

Keep durable observations, corrections, jobs, failures/checkpoints and every
backup generation. Use SQLite backup operations including committed WAL, never
an active main-file copy or immutable active WAL database. Stop writers for an
upgrade and use the version-guarded [update procedure](WORKER_UPDATES.md).
Keep configuration, all three worker image references, limits and mounts in the
reviewed private plan. A moving tag is not a rollback identity.

Do not use `down -v` or clear failures/checkpoints on a retained installation.
Generated acceptance has its own [disposable-volume procedure](ACCEPTANCE.md).

## Explicit canonical cooldown recovery

A persisted upstream pause is capped at 24 hours. After confirming that the
source has recovered, an operator can stop the collector and run the worker
with its same private config and state mount:

```sh
anibridge-catalog-worker --config /config/worker.json --clear-cooldown ORIGIN
```

Use an exact configured canonical origin (or `all`); the command acquires the
worker process lock and rewrites only a valid cooldown receipt. It neither
bypasses a running collector nor repairs corrupted receipts. Ordinary restart
keeps cooldowns; manual clearing is an explicit recovery action, not automatic
retry behavior.

Collection and `--publish` require Linux because quota accounting includes
open-but-unlinked SQLite files through `/proc`. Use the worker image for those
commands on macOS/Windows; local inspection/tests do not establish that quota.

## Query bounds

The 500-row and 200-title bounds are cardinality ceilings, alongside an independent
2-MiB serialized-response cap. Exceptionally large legal labels/aliases can exceed
that cap; the server rejects the result as `503 response_too_large` without
truncating it or pretending the total is smaller. Use smaller row windows or more
specific title queries. The byte cap remains part of the private memory budget.
