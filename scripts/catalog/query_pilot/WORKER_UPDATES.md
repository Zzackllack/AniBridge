# State-preserving worker updates

Migration/recovery plans require a tested full commit and an immutable manifest
digest. Moving PR/source tags can change on rebuild. Publishing never authorizes a
deployment. A `sha-<commit>` tag can also move after a rebuild; use the resolved
`image@sha256:...` in migration/rollback plans. Re-read saved Compose and current worker configuration before
preparing a plan; preserve unrelated editor drafts.

## Routine private-pilot updates

Before adopting the hardened server image, inspect `worker.json` for an explicit
`bind_host`. Older images defaulted an omitted value to `0.0.0.0`; current images
default to `127.0.0.1`. A metadata container reached through another container's
TLS ingress needs an explicitly reviewed backend-network bind, normally
`"bind_host": "0.0.0.0"`, with its port kept private and the query route
authenticated. A host loopback port mapping does not make a container's loopback
listener reachable from that ingress. This configuration change is separate
from pulling an image; preserve the original config and review its rollback.
Do not classify such an upgrade as code-only or silently broaden a bind.

A maintainer may explicitly choose the moving `pr-170` preview tag for this
disposable testing service. With `pull_policy: always` on all three components,
Coolify's **Pull latest and restart** adopts the published image. Pushing alone
does not deploy it; wait for the chosen commit's tests and manifest publication.
Record the actual source revision and digest before and after the update, retain
the previous compatible image and backups, and verify queries and collection.
Keep volumes, configuration, resources and networks intact.

For a code-only update that preserves the private/public schemas and recovery
behavior, a full-ledger copy rehearsal is not required on every push. Use the
full procedure below when migrations, storage formats or recovery change, or
when investigating preservation. A reported backup is not a tested restore.
Moving tags do not make an older binary able to read a newer schema.

## Prepare and review

Use a new private directory outside Git. Obtain the complete saved Compose from
the existing service through authenticated Zen and the worker JSON through the
current XPipe-generated SSH connection. Keep credentials private; do not use a
historical socket/host assumption or disable host-key checks. The Coolify token
is read-only. The existing pilot's service UUID is `ev7cds2lpqyvqfxpcm4wp4tc`.

```sh
uv run --project apps/api --frozen python \
  scripts/catalog/query_pilot/prepare_worker_update.py \
  --revision FULL_40_CHARACTER_COMMIT \
  --compose "$UPDATE_DIR/current-compose.yaml" \
  --worker-config "$UPDATE_DIR/worker.json" \
  --expected-old-image ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:CURRENT_DIGEST \
  --directory "$UPDATE_DIR/reviewed"
```

The helper refuses incomplete/failed checks, drift and missing architectures.
Review `candidate.yaml`, exact `rollback.yaml`, `plan.json`, original worker
configuration and `stopped-state.sh`. All initializer/collector/metadata image
references change together; config, resources, pull policy, networks and volumes
remain. A mount/ingress/config change needs a separate reviewed diff. Keep the
plan both locally and on the host; it does not deploy itself.
Snapshot, verification and rollback containers use root to read the private
operator directory and receipts. Normal collector/metadata users stay unchanged.
Keep the old image referenced while rollback is required: scheduled cleanup can
remove a cached, unused digest. A stopped retention container needs no volumes
or network and must override the worker entrypoint, for example with
`--entrypoint python OLD_IMAGE -c pass`, so it cannot accidentally collect.

## Apply only after operational approval

1. Verify the candidate's immutable image/source label and retain the old image.
2. Admit live state, every backup, copies, migration scratch, publication staging,
   images/logs and a 1-GB reserve under 30,000,000,000 bytes; check actual free
   space too. The helper is not a host-wide quota manager. Binary exports use
   `--log-driver none`.
3. Stop both existing services through Zen with Docker Cleanup off. Do not start
   another stack against their volumes.
4. In the reviewed server plan directory, run:

   ```sh
   bash stopped-state.sh snapshot
   bash stopped-state.sh publish
   bash stopped-state.sh verify
   ```

   These commands refuse a running project, use consistent WAL-inclusive SQLite
   backups and run bounded offline work at 2 CPU/2 GiB. Verification compares
   prior release/first-seen, map, collection/retry/history rows. Stop on failure;
   never overwrite a later ledger with a backup to make the check pass.
5. Apply the reviewed candidate Compose in Zen, start, and verify source/digest,
   limits, mounts, networks, restart/OOM counters, both providers' real queries
   and a later validated publication. Retain the private verification receipts.

## Schema-specific rollback

Filmo is a new optional provider: private v8/public schema3/identity2, with
magnet v3 understood by the matching local client. Enabling it does not migrate
existing v7 provider ledgers. For rollback to a pre-Filmo image, disable Filmo in
the candidate worker/client configuration and retain its state/read directories
untouched; do not feed v8 to the old binary or convert its source variants into
v7 language-only releases. Existing providers can return to their unchanged
v7-compatible image. Keep the matching client available for already-saved Filmo
jobs; a pre-Filmo client cannot execute those grabs. No v8→v7 data downgrade is
provided. Immutable candidate/rollback digests and storage admission still need
to be reviewed before deployment.

The helper supports private v5/v6/v7. Public read schema2 is separate. A v7
upgrade retains an original no-overwrite `.pre-v7.backup`; admit both its
temporary and final storage before migration. Old first-failure times remain
unknown. Public exports omit the new private detail-failure receipts.

Stop both services first, with cleanup off. Use the **new candidate image's**
guarded script for a format downgrade:

| Upgrade / rollback target | Command before restoring the plan's rollback Compose |
| --- | --- |
| v6→v7, return to v6 | `bash stopped-state.sh rollback-v6` |
| v5→v6, return to v5 | `bash stopped-state.sh rollback-v5` |
| Same private schema | Restore the reviewed `rollback.yaml` directly; no schema downgrade |

The script checks its original baseline. Then restore that plan's `rollback.yaml`
in Zen and start the old pinned image with existing volumes/configuration.
Preserve observations collected after upgrade, all old tables/maps/corrections,
every backup generation and `/state/backup`. Never restore an old ledger over
new data, clear failures, or use a v5 downgrade against a v6 baseline.

Matcher changes normally rematch cached evidence through maintenance. Publishing
alone does not rematch. Use `verify --local-rematch aniworld.to` only for an
explicitly reviewed single cached tick; it checks one fairness-slot advancement
and at most one matching receipt, not arbitrary retry/queue changes.

The remaining acceptance and release gates are in
[ISSUES.md](../../../internal/specs/020-catalog-query-api-evaluation/ISSUES.md).
Client upgrades are separate: preserve jobs/downloads and the auth boundary.
An old unauthenticated image is not equivalent security rollback. PBKDF2 session
key changes require clients to log in again. Writable client state must enforce
locks; do not bypass that guard on an unsafe Mac bind mount.
