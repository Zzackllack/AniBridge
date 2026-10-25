# State-preserving worker updates

Updates require a tested full commit and an immutable manifest digest. Moving
PR/source tags can change on rebuild. Publishing an image never authorizes a
deployment. Re-read saved Compose and current worker configuration before
preparing a plan; preserve unrelated editor drafts.

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
