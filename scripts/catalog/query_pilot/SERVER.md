# Private collector and metadata service

Use `server.yaml` for real collection and `compose.yaml` only for generated
fixtures. This guide prepares a new explicitly authorized installation; use
[WORKER_UPDATES.md](WORKER_UPDATES.md) for an existing service. Never start a
second collector against retained live volumes. Current acceptance gaps are in
[the open-work list](../../../internal/specs/020-catalog-query-api-evaluation/ISSUES.md).

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
`client.json` and a bearer file. Review provider origins and optional canonical
sources before initialization; secrets stay outside Git. Optional Megakino needs
explicit origin/sitemap aliases and observed language evidence. A canonical
credential cannot establish a missing player language.

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

Copy only `client.json` and the bearer file into a private client configuration
directory. Keep worker state on the server. For a new disposable client:

```sh
export PILOT_CLIENT_CONFIG_DIR="$HOME/anibridge-private-client-config"
export PILOT_DOWNLOAD_DIR="$HOME/anibridge-pilot-downloads"
export COMPOSE_FILE=scripts/catalog/query_pilot/local-client.yaml
docker compose -p anibridge-private-client config --quiet
docker compose -p anibridge-private-client build
docker compose -p anibridge-private-client up -d
```

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
