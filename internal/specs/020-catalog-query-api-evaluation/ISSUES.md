# Catalog acceptance and remaining work

This is the current open-work list, not a run history. Detailed audit matrices,
measurements, deployment receipts and PR drafts are local-only under ignored
`internal/local/catalog-history/`. Test fixtures remain tracked beside tests.
Always verify the selected revision/environment before relying on prior results.

Runtime image identities and verification receipts remain local. Re-query the
deployed image, state and disk before an upgrade; repeat preservation proof when
migration behavior changes. Publishing a preview does not deploy that image.

## Open gates

| Area | Required work / acceptance boundary |
| --- | --- |
| Filmo acceptance | Verify final candidate native images. The generated real Radarr/Prowlarr scenario covers authenticated multipart grabs, selected variants, byte progress, embedded tracks, explicit `Move` import and a bounded restart. Its separate HLS overlay still needs a completed real-Radarr run, including intermediate estimated progress before audio transfer. Investigate live extraction failures with the new parent-operation diagnostics; historical generic outcomes cannot identify their cause. This does not prove live provider acquisition/playback or independently labelled movie mappings. Unknown audio remains retained but withheld from automatic language claims. |
| Filmo media breadth | Known SRT/WebVTT captions and group-bound HLS audio are implemented; extend unknown formats only with observed metadata and native regressions. Unsupported or ambiguous layouts still fail explicitly. No universal host-format coverage is claimed. |
| Filmo movie identity | Keyless Radarr matching uses explicit IMDb evidence or unique exact-title/year candidates with independent detail verification, following the TV policy. Evaluate accepted IDs, ambiguity and abstentions against frozen independent labels. Search responses are not proof of exhaustive candidate completeness; neither endpoint success nor fixture matches establish provider-wide accuracy. |
| Filmo publication capacity | Measure full schema3 export/validation at representative scale and resource limits before increasing provider budgets. Existing schema2 incremental-proof results do not establish schema3 performance or sustained Filmo freshness. |
| Storage admission | Recalculate the next workload's aggregate peak, including images/shared caches, new copies, migration backups, publication scratch, logs and reserve. Cleanup alone does not certify the 30-GB cap. |
| Mapping accuracy | Freeze independently verified expected matches before tuning and evaluate held-out ordinary/large/multilingual/special/reordered-season cases. Report incorrect acceptances, abstentions and conflicts separately. Existing post-implementation labels are regression evidence, not a blind precision estimate. |
| Provider coverage and freshness | Recompute per-provider observed/usable/mapped/unresolved denominators and disjoint unresolved reasons on one consistent snapshot. Measure eligible age and requests per useful map. Do not infer completeness or an SLA from a short run. |
| Recent-feed obligations | Verify the season-batch settlement and bounded language-mismatch retry fixes on retained state before a worker upgrade. Preserve failed detail retries and do not manually clear old pending entries. |
| Failure attribution | v7 detail receipts are recording real retries; historical first-failure clocks remain unknown. Listing/signal and complete per-title canonical attribution remain separate gaps. Conflicting canonical IDs require verified correction evidence, not weaker matching. |
| Real client acceptance | Run current AniBridge with real isolated Sonarr/Prowlarr: configured authentication, intermediate progress, differing episode numbering without double conversion, actual file movement, restart and duplicate prevention. Generated media proves that workflow only. |
| Client storage | Move retained developer state from the observed unsafe Mac bind to storage that enforces locks, using an admitted consistent backup and preservation checks. Do not disable the guard or reset jobs. |
| Publication and capacity | Run final-source full-size publication/query overlap; retain last-good serving through failures. Measure writer occupancy, CPU/memory/I/O and bounded latency. Native tests do not establish sustained capacity. |
| Resource pressure and reconciliation | Profile collector memory reclaim at its 2-GiB limit and overdue historical work under the existing reconciliation admission cap. Separate active parent refresh demand, unavailable episodes and persistent upstream errors before changing allocations or cadence. |
| Request budgets and recovery | Short paced metadata trials do not establish upstream ceilings or safe daily volume. Validate full-path bootstrap/publication before raising budgets. Canonical 429/503 origin pauses now have an atomic restart receipt; retain it with backups and verify selected-image recovery. Five/second admission is an opt-in ceiling, with unchanged defaults; sustained VPS/bootstrap/publication capacity remains unverified. |
| Client dependencies | Rebuild and verify selected images with the patched certifi bundle, Pylint and existing urllib3/Mako fixes. Installed native environments exclude the compromised emSign ECC G3 root and isolate AniWorld's HTTP fork from Requests; fresh candidate images and deployed services require their own verification. |
| Merge policy | Verify final-head CI and manifests, enforce `Tests / Required Gate`, obtain eligible human/CODEOWNER approval and replace the stale PR description. The active `v3` ruleset requires the conventional-title check, review and CodeQL, but does not enforce the configured test gate. |
| Public release | Decide public scope, all-router authentication/TLS/privacy/rights, destination OS/dependency exposure, external outage handling, release/retention policy and supported capacity before release. Optional qBittorrent credentials alone are insufficient. |

## Working boundaries

Implemented regressions cover malformed canonical/cache evidence, due retries,
failure checkpoint atomicity, writer failure propagation, progress/history,
login/session limits, quota errors and native media resource admission. Their
passing source/environment must still be verified for the chosen candidate.

Pushing code or publishing previews does not upgrade the hosted service.
Re-query actual containers/configuration before any operation. Keep `main`
default/stable and `v3` the integration target.

Review, merge, private deployment and public production are separate decisions.
The existing acceptance criteria remain open; archival of reports waives none.
Use [generated acceptance](../../../scripts/catalog/query_pilot/ACCEPTANCE.md),
[worker updates](../../../scripts/catalog/query_pilot/WORKER_UPDATES.md) and
[the v3 transition checklist](../../releases/v3-transition.md) for execution.
