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
| Merge policy | Verify final-head CI and manifests, obtain eligible human/CODEOWNER approval and replace the stale PR description. The active `v3` ruleset (24885997) now requires both `Conventional Commit Title` and `Tests / Required Gate`, with review, CODEOWNER, conversation resolution and CodeQL rules preserved. Re-read the ruleset and the selected head's run before relying on either; a historical passing run is not current-head or deployment proof. |
| Public release | Implement the [public service gates](#public-service-gates-release) below. Optional qBittorrent credentials, a private pilot or a preview image are insufficient. |

## Merge blockers

Keep this list short; everything else is release or product work.

- Final-head CI passes the enforced `Tests / Required Gate` and
  `Conventional Commit Title` checks, and CodeQL reports no new blocking alert.
- Eligible human/CODEOWNER approval exists and all review conversations are
  resolved.
- The PR description matches the actual scope and current head.
- No P1/P2 finding from the security review remains unresolved or undocumented.
- Record focused candidate Sonarr/Radarr acceptance for the supported paths,
  including differing numbering, intermediate progress, file movement, cleanup
  and restart without duplicate jobs. Separate fixture, generated-media and
  live-provider results; list any remaining gap explicitly in the PR.

## Public service gates (release)

Target contract: [PUBLIC_SERVICE.md](PUBLIC_SERVICE.md). These gates apply to the
normal public product: a built-in official read-only metadata endpoint with no
signup, API key, endpoint URL or token configuration for end users. They do not
block merging the existing private/catalog work, and unrelated product gaps
(new providers, Filmo breadth, mapping precision, endurance) do not block a
declared v1 scope unless they invalidate a published claim. Execute in order.

1. Choose the official hostname, supported providers/client versions, operator,
   privacy/retention policy and measured capacity target. Keep the pilot private.
2. Verify the selected candidate on the retained pilot: actual digests, queries,
   publication, retry preservation, resource/storage headroom and restore.
3. Expose only anonymous read queries through trusted TLS ingress; keep the
   backend bearer and all local job, management, qBittorrent and STRM boundaries.
   Confirm spoofed forwarding headers cannot bypass admission.
4. Measure and enforce per-identity request/work allowances and global active
   limits. Check several identities, NAT sharing and saturation; return explicit
   retryable errors and retain capacity for healthy clients. Size operation
   weights from measurements. Validate any shared cache/coalescing policy and
   bounded outage behavior against that workload.
5. Ship official client defaults without user-entered catalog settings or a
   bundled bearer. Test a fresh install, explicit legacy/private overrides,
   unsupported versions/providers and a hosted outage.
6. Complete focused real-client acceptance, including numbering, intermediate
   progress, file movement, cleanup, restart and duplicate prevention. Keep
   generated-media and live-provider evidence distinct.
7. Establish the prerelease/image-channel path before promising a v3 beta.
   The current stable-only release workflow is not that path. Promote the tested
   digest through a bounded production canary with rollback thresholds and
   operator instructions; publishing or merging alone must not deploy it.

Each step's detailed contract and evidence boundary is in
[PUBLIC_SERVICE.md](PUBLIC_SERVICE.md). No production URL, capacity number or
successful restore is implied by this list.

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
Merge blockers are listed separately from the public-service gates; the latter
describe the currently identified launch work and are not satisfied by private
pilot acceptance. Measured failures may reveal additional work.
Use the [public service contract](PUBLIC_SERVICE.md),
[generated acceptance](../../../scripts/catalog/query_pilot/ACCEPTANCE.md),
[worker updates](../../../scripts/catalog/query_pilot/WORKER_UPDATES.md) and
[the v3 transition checklist](../../releases/v3-transition.md) for execution.
