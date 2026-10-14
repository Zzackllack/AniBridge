# Implementation handoff: practical mapping and sustainable maintenance

Copy the prompt below into a fresh local agent chat attached to this checkout.
This file prepares the handoff; it does not start another agent or approve a
deployment. The detailed acceptance criteria are in `MAPPING_REPAIR.md`.

---

Implement AniBridge's mapping/maintenance follow-up. Deliver working code,
focused verification, measured before/after results and coherent local commits.
This is an implementation task; do not stop at another investigation report.

Repository: `/Users/zacklack/Developer/Own/Repos/AniBridge`.
Continue `zzackllack-aux/catalog-query-api-implementation`. Inspect Git state
before editing; preserve all existing commits, uncommitted changes and unpushed
recheck/handoff commits. Do not reset to the deployed revision or remote HEAD.
Draft PR #170 targets protected `v3`; `main` stays default. Do not push, edit
the PR, merge, publish, redeploy, restart or change live allocations without
explicit authorization for the new action.

Read first:

- `AGENTS.md` and relevant `internal/agents/*` guidance.
- `internal/specs/020-catalog-query-api-evaluation/IMPLEMENTATION.md`.
- `MAPPING_REPAIR.md`, `ISSUES.md`, `EVIDENCE.md` in that folder.
- `evidence/pilot-recheck-2026-10-14.json` and
  `evidence/mapping-diagnosis-2026-10-14.json` in that folder.
- `scripts/catalog/query_pilot/SERVER.md` and `ACCEPTANCE.md`.
- `internal/releases/v3-transition.md` for CI/integration constraints.

Current historical baseline, October 14; reverify before diagnosing:

- Existing fra-node-01 Coolify service `anibridge-private-catalog`, UUID
  `ev7cds2lpqyvqfxpcm4wp4tc`. Collector and metadata names use that suffix.
- Worker source revision `36fbd511890b0c08a80385b0a2542d3c6b51c1d3`, pinned image
  `ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1277d1fd6ec7130a53c5ed4a694dd8efada7e95db6c86bd897e3e446f2149e0a`.
- Collector 2 CPU/2 GiB with no extra swap; metadata 2 CPU/512 MiB. No OOM kills
  or restarts since October 11. Storage 3.98 GB/30 GB including backup/reserve.
- Last retained 24 hours: 284 successful publications/provider, no maintenance
  failures; 3,639 Serienstream HTTP-200 parse failures and 288 transport failures,
  mostly HTTP 500. No observed page 403/429. Historical discarded maintenance
  stderr cannot establish the original CQ-22 cause.
- AniWorld 63,601 episodes/116,409 releases, 65.31% usable mapping; Serienstream
  306,895 episodes/355,722 releases, 64.62% usable mapping, 141 pending/143 failed
  pages, 25,135 unknown-language observations and 8,350 unavailable observations.
  These are sequential snapshots; pending and failed sets overlap.
- A later matching diagnostic found zero never-checked matching-input entries,
  15,280/92,506 usable episodes unresolved with descriptors already cached, and
  6,775/8,345 usable episodes without a TVDB series association. Descriptor
  presence does not prove its correctness or explain every rejection.
- Six concentrated large cohorts: 4,739 names absent from the selected descriptor,
  1,104 unusable generic names, four repeated source names. Freeze a broader,
  independently labelled development/held-out evaluation set before tuning.
- 8,611 partial series trigger 30-minute descriptor eligibility, versus a shared
  30/min canonical cap. At least 17,222 requests/hour would be needed for that
  cadence, exceeding 1,800/hour admission. This is a derived lower bound, not a
  measured trace. Increasing RAM or this cap does not fix missing name evidence.
- Exact anime source One Piece S01E06/S21E14 return three releases each; S01E01
  remains explicitly unresolved. Its first episode has ordinary English wording
  differences between source and canonical titles, plus a German source alias.
  Do not resolve it from equal numbering or hardcoded series-specific mappings.
- An explicit-unavailable episode lacking its episode heading is rejected by
  `sto.Parser.missing_video()` as `metadata_incomplete`. A season still rejects
  the contract; a sampled title returns HTTP 500 after hundreds of attempts.
- All 439,035 backed-up release IDs/first-seen times survived. Four removal
  quarantines remain unapproved. Recent gap-parent queues were 0/5, but capped
  feed gaps stay explicit. The disposable local client is still `71988fc` with
  zero corrections; it has not verified the new client-side subtitle changes.

Implement in this order, following the full plan's acceptance criteria:

1. Add reproducible bounded rejection diagnostics and a fixed independently
   labelled cohort/hold-out baseline, then proceed directly to implementation.
   Separate waiting work from failed correspondence, stale/wrong descriptors,
   missing names, ambiguity and conflicts. Do not turn diagnosis into a new
   provider-wide crawl or a standalone handoff report.
2. Separate descriptor acquisition from local rematching. Reuse verified evidence
   across provider titles where safe; fingerprint source/descriptor/matcher inputs.
   Avoid unchanged partial-series download/rematch churn. Prioritize genuinely
   new evidence and first attempts, retain bounded canonical freshness and real
   failure recovery, and prove demand/fairness fits the existing shared budget.
3. Improve demonstrated parent/episode gaps with verified aliases, multilingual
   canonical metadata/IDs and unique source-aware contextual evidence. Approximate
   text can propose candidates; never accept on similarity or number equality
   alone. Preserve native coordinates, ambiguity, local corrections and correct
   existing maps. Test at least two recurring mismatch families on held-out
   series; do not hardcode One Piece or silently repoint conflicting identities.
4. Fix the missing-heading unavailable case, diagnose the season rejection and
   representative language gaps, and distinguish stable parse-gap scheduling from
   transient HTTP failures. Preserve useful metadata/releases and retry history;
   no guessed audio language, release date, or missing-evidence tombstones.
5. Run/add worker/core CI regressions while implementing these fixes. Add frozen
   project jobs and an always-running gate for PRs into main/v3; current green
   pytest CI covers API only. Do not let CI refactoring replace the mapping work
   or change GitHub protection policy without authorization.

Use the existing libraries/helpers and Context7 for current external docs.
Inspect maintained upstream source when needed. Keep concerns modular. Safe
runtime diagnostics must never contain raw stderr, HTML, player URLs, terms,
user IPs or credentials. Useful rejection subcodes must be bounded/allowlisted.
Small sanitized metadata fixtures can include episode names needed for tests.

Read-only inspection of the existing pilot is authorized. Follow the XPipe-to-SSH
workflow in AGENTS.md; its old Configs README currently redirects to
`/Users/zacklack/Developer/Own/Repos/XPipe-to-SSH/README.md`. Do not start a
competing collector against live volumes. Preserve checkpoints, failures, leases,
release identities/first-seen, pre-v4 backups and `/state/backup`; never clear
failures or restart bootstrap to improve apparent results. Use consistent
disposable SQLite copies for experiments. Keep NetBird routing, backend
172.16.27.0/24 and Docker pool 10.254.0.0/16 split into /24s intact.

The total disk budget stays 30,000,000,000 bytes, including copies, migrations,
backups, SQL scratch, staging/logs and 1 GB reserve. Use short bounded workloads
at 2 CPU/2 GiB; rerun 4 CPU/4 GiB only for a justified comparison. Do not launch
a full Mac crawl, daily episode recrawl, long endurance/crash campaign, synchronous
query scraping, demand-refresh system or client snapshot distribution. Search
stays catalog-only. Megakino is optional and must not delay this work. No
browser/CAPTCHA solver or live media acquisition is authorized.

Finish with measured full-copied-ledger and cohort/held-out before/after coverage,
accuracy limits, requests per useful new map, avoided unchanged work, eligible
work age, CPU/memory/I/O and query/publication latency. Verify exact totals,
last-good retention, provider isolation, ordinary/large targeted retrieval, local
correction precedence, cache/outage, late canonical arrivals and restart/resume.
Compare all prior release identities/first-seen and valid maps. Keep fixture,
copied state, live metadata, client and generated-media evidence separate from
live extraction/import/playback. Report why remaining cases cannot be accepted.

Update the existing issue/evidence documents. Make modular multiline Conventional
Commits; do not push. Prepare tested state-preserving worker/client upgrade and
exact rollback commands. Ask for deployment approval only after the result is
concrete and reviewable; previous rollout approval does not authorize this one.
The Coolify API token was read-only: use the existing authenticated Zen browser
for any later approved write, not the in-app browser or broadened credentials.
Give every work item an honest implemented+verified, implemented+environment-
blocked, or not-implemented status with its exact blocker. Do not claim complete
mapping, a freshness SLA or full-bootstrap capacity from a short cohort. Do not
conclude with “next we should implement” for work required by this prompt.
