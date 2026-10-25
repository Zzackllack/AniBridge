# Catalog acceptance and remaining work

This is the current open-work list, not a run history. Detailed audit matrices,
measurements, deployment receipts and PR drafts are local-only under ignored
`internal/local/catalog-history/`. Test fixtures remain tracked beside tests.
Always verify the selected revision/environment before relying on prior results.

## Open gates

| Area | Required work / acceptance boundary |
| --- | --- |
| Hosted v7 upgrade and recovery | The full-ledger v6→v7→v6 copy rehearsal passes at worker `f709263`: all 39 existing data tables, later observations, interruption recovery, retained backups and reopening with the deployed v6 worker. The live cutover still needs its stopped snapshot/publication/verification and operational approval. Repeat the rehearsal if migration behavior changes. |
| Storage admission | Recalculate the next workload's aggregate peak, including images/shared caches, new copies, migration backups, publication scratch, logs and reserve. Cleanup alone does not certify the 30-GB cap. |
| Mapping accuracy | Freeze independently verified expected matches before tuning and evaluate held-out ordinary/large/multilingual/special/reordered-season cases. Report incorrect acceptances, abstentions and conflicts separately. Existing post-implementation labels are regression evidence, not a blind precision estimate. |
| Provider coverage and freshness | Recompute per-provider observed/usable/mapped/unresolved denominators and disjoint unresolved reasons on one consistent snapshot. Measure eligible age and requests per useful map. Do not infer completeness or an SLA from a short run. |
| Failure attribution | v7 detail receipts need runtime verification. Missing historical first-failure clocks cannot be reconstructed; listing/signal and complete per-title canonical attribution remain separate gaps. Conflicting canonical IDs require verified correction evidence, not weaker matching. |
| Real client acceptance | Run current AniBridge with real isolated Sonarr/Prowlarr: configured authentication, intermediate progress, differing episode numbering without double conversion, actual file movement, restart and duplicate prevention. Generated media proves that workflow only. |
| Client storage | Move retained developer state from the observed unsafe Mac bind to storage that enforces locks, using an admitted consistent backup and preservation checks. Do not disable the guard or reset jobs. |
| Publication and capacity | Run final-source full-size publication/query overlap; retain last-good serving through failures. Measure writer occupancy, CPU/memory/I/O and bounded latency. Native tests do not establish sustained capacity. |
| Merge policy | Verify final-head CI and manifests, enforce `Tests / Required Gate`, obtain eligible human/CODEOWNER approval and review the current PR description. Configured workflows and enforced branch rules are separate. |
| Public release | Decide public scope, all-router authentication/TLS/privacy/rights, destination OS/dependency exposure, external outage handling, release/retention policy and supported capacity before release. Optional qBittorrent credentials alone are insufficient. |

## Working boundaries

Implemented regressions cover malformed canonical/cache evidence, due retries,
failure checkpoint atomicity, writer failure propagation, progress/history,
login/session limits, quota errors and native media resource admission. Their
passing source/environment must still be verified for the chosen candidate.

The last audited hosted worker used private v6; the candidate uses v7/public
schema2. Pushing code or publishing previews does not upgrade that service.
Re-query actual containers/configuration before any operation. Keep `main`
default/stable and `v3` the integration target.

Review, merge, private deployment and public production are separate decisions.
The existing acceptance criteria remain open; archival of reports waives none.
Use [generated acceptance](../../../scripts/catalog/query_pilot/ACCEPTANCE.md),
[worker updates](../../../scripts/catalog/query_pilot/WORKER_UPDATES.md) and
[the v3 transition checklist](../../releases/v3-transition.md) for execution.
