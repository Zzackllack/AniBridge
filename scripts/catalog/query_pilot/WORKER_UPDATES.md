# Updating the existing private worker

Use a tested commit and **pin its image digest**. The preview worker has no
supported `latest` channel. `pr-170` moves whenever another build finishes; even
a `sha-<commit>` tag can move on a rebuild. A digest identifies the exact image
and makes rollback repeatable. Docker also pulls `latest` even with
[`pull_policy: missing`](https://docs.docker.com/reference/compose-file/services/#pull_policy).

Image publishing is already automatic through the preview workflow. Deployment
is an explicit operator action: a new worker can migrate private state. The
current Coolify token is read-only; use the authenticated **Zen** session for
service writes. Do not add an unattended image updater to this service.

## 1. Prepare the update on this Mac

Requirements: `gh` authenticated to GitHub, Docker/buildx, and `uv`. Work from the
repository root. Choose a full commit whose tests and worker image build passed.

Create a private working folder outside Git. In Coolify open the existing
`anibridge-private-catalog` service → **Edit Compose File** → **Use plain-text
editor**. Copy its entire saved Compose into `current-compose.yaml` in that
folder. Keep any unrelated draft edits separate. Obtain the current worker JSON
without printing credentials, using the XPipe SSH workflow in AGENTS.md:

```sh
UPDATE_DIR="$HOME/anibridge-worker-updates/$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 -p "$UPDATE_DIR"
# Copy the saved Compose in Zen, then:
pbpaste > "$UPDATE_DIR/current-compose.yaml"
uv run --project /Users/zacklack/Developer/Own/Repos/XPipe-to-SSH \
  xpipe-to-ssh oracle-oc1 --shell json
# Use that command's current host, user and agent socket; the following is
# the connection verified October 19, not a permanently guaranteed address.
SSH_AUTH_SOCK=/Users/zacklack/.bitwarden-ssh-agent.sock \
  ssh -l zacklack fra-node-01.nb.internal \
  'docker exec collector-ev7cds2lpqyvqfxpcm4wp4tc cat /config/worker.json' \
  > "$UPDATE_DIR/worker.json"
chmod 600 "$UPDATE_DIR/"*
```

If the NetBird name cannot resolve, use an alternate address from the current
XPipe JSON and keep `-o HostKeyAlias=fra-node-01.nb.internal` so SSH still verifies
the saved server key. Do not disable host-key checks or change routing for an update.

Read the current image digest from those saved Compose bytes. Pass it explicitly;
the helper refuses drift, moving tags, unsuccessful checks or missing native
architectures. Substitute the **reviewed full commit** and **current old digest**:

```sh
uv run --project apps/api --frozen python \
  scripts/catalog/query_pilot/prepare_worker_update.py \
  --revision FULL_40_CHARACTER_COMMIT \
  --compose "$UPDATE_DIR/current-compose.yaml" \
  --worker-config "$UPDATE_DIR/worker.json" \
  --expected-old-image ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:CURRENT_DIGEST \
  --directory "$UPDATE_DIR/reviewed"
```

This creates `candidate.yaml`, exact `rollback.yaml`, original worker JSON,
`plan.json` with image/check receipts, and guarded `stopped-state.sh` commands.
It changes all three image references together and preserves configuration,
networking, volumes, resource limits and pull policy. It does **not** deploy.
Review the YAML diff. Copy the reviewed folder to a new private durable folder
on fra-node-01 with the same XPipe-derived SSH connection. Keep a Mac copy too.

## 2. Apply the reviewed update

1. On the server, pull the exact `image` from `plan.json` while the old service
   still runs. Check its `org.opencontainers.image.revision` label against the
   selected commit. Retain the old image.
2. Admit the complete disk projection under **30,000,000,000 bytes**: live state,
   read files, existing backups, experiment copies, the new stopped snapshots,
   migration backups, publication scratch, images/logs and a **1 GB reserve**.
   Check filesystem free space as well. The script is not a host-wide quota
   manager. Move disposable research copies into a verified archive if needed.
   Use `--log-driver none` for disposable containers streaming binary archives;
   Docker's default JSON logging can retain another expanded copy of that output.
   The generated one-off update commands disable Docker logging; capture their
   small structured receipts in the private plan folder. Live logging is unchanged.
3. In Zen, stop this existing service with **Docker Cleanup unchecked**. Wait
   until both collector and metadata have stopped. Do not start a second stack.
4. In the server's reviewed folder, run these commands in order:

   ```sh
   bash stopped-state.sh snapshot
   bash stopped-state.sh publish
   bash stopped-state.sh verify
   ```

   Each command refuses to run while this Compose project has running
   containers. Work runs without network at 2 CPU/2 GiB. Snapshots use SQLite's
   backup API so committed WAL data is included. Verification compares every
   prior release row/first-seen, accepted map and collection/retry/history row.
   Only publication bookkeeping, matcher receipts and new maps may differ.
   Stop on any failure; do not restore a snapshot over the live ledger.
5. Only after successful validation, paste **candidate.yaml** into the Zen
   Compose editor, save, and start the service. Keep Docker Cleanup off.
6. Verify both running containers' source revision, pinned image, resource limits,
   unchanged mounts and network ranges. Check real authenticated metadata
   queries for both providers, an ordinary title and the affected episode. Check
   a later publication, restart/OOM counters and last-good serving. A running
   status alone is insufficient. Retain the plan and preservation receipt.

The helper supports the current **private v5/v6** worker formats. Future schema
versions need a reviewed migration/rollback path before using this procedure.
No client upgrade is needed for the current schema2 read contract. Local matcher
version changes normally rematch cached evidence in the background; publication
alone does not perform that rematch. It never restarts bootstrap or clears errors.
If a separately reviewed offline operation explicitly ran one cached
`Enricher.tick` for AniWorld, use `bash stopped-state.sh verify --local-rematch
aniworld.to`. This checks exactly one fairness-slot advancement and at most one
changed matching receipt, retaining its source/descriptor fingerprints. It does
not exempt retry history or collection checkpoints. Omit this option for an
ordinary update with no targeted rematch; never add it just to bypass a failure.

## Roll back code while retaining collected data

Stop the service in Zen first, with cleanup off. If the update migrated **v5 to
v6**, run `bash stopped-state.sh rollback-v5` using the **new image**, then restore
`rollback.yaml` in Zen and start the old image. The command refuses a baseline
that was already v6. It removes only v6 publication bookkeeping; observations,
releases, accepted maps, retries and all pre-v4/pre-v5/pre-v6 backups remain.

For a **v6 to v6** code update, restore `rollback.yaml` directly after stopping;
do not downgrade the state format. Never use `down -v`, remove volumes, clear
failures or restore an old ledger to make rollback appear successful. Preserve
both original configuration locations and `/state/backup`.

The exact October 19 digest and observed outcome are recorded in SERVER.md and
the catalog evidence ledger. This remains a private pilot, not a v3 release gate.
