# October 14 production-readiness follow-up

This follows the implemented [mapping repair](MAPPING_IMPLEMENTATION.md), not a
replacement investigation. The user subsequently authorized pushing, preview
publication and interaction with the existing Coolify pilot. Code through
`2240b9119797bf3346444e719eef3e78fd0c83e4` is pushed without resetting history.
PR #170 remains a draft into protected `v3`; `main` remains default.

Later canonical tuning is implemented and deployed: current worker is `d85ed05`,
manifest `sha256:9a0df2b03fd386142f36a5ba8704c17e2e1489bd2519d88959d62753d2157218`,
with shared admission configured at 90/minute. It followed bounded 30/60/90/120
copied-ledger metadata trials and preserves existing state/resources/networks.
See [rate evidence](evidence/canonical-rate-tuning-2026-10-14.json), EVIDENCE.md and
SERVER.md's v5 code/config-only rollback. The 30/minute value was our initial
design choice, not an established upstream quota. Broader labels, publication
cost and sustained capacity remain open; a short rate trial does not close them.

## Delivered and remaining boundaries

Hosted test run [38598340921](https://github.com/Zzackllack/AniBridge/actions/runs/38598340921)
passed the frozen API/core/worker projects, installed-wheel checks and final gate.
Ruff lint/format, Pylint and CodeQL passed. The formerly branch-mutating Ruff
workflow now checks only, with read-only permissions and no persisted checkout
credentials. Native AMD64/ARM64 preview run
[38598341152](https://github.com/Zzackllack/AniBridge/actions/runs/38598341152)
built/import-tested both components and published matching manifests:

- Worker: `ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:250313035479c17e0df65cbc5347261536f2c8bba34b8e11ed3ba05ed399278f`.
- API: `ghcr.io/zzackllack/anibridge-api-preview@sha256:eef48b9211d2a5e01d34568d464e3cbf7d647a4ba1f4b6d4544496772f857e58`.

The actual worker pulled on fra-node-01 reports ARM64 and the full source SHA
above. Its offline full-copy publication/query verification is recorded separately
in the accompanying evidence. These are published preview images, not a stable
release or proof of a deployed upgrade.

After the user unlocked the Mac, the pilot cutover completed through authenticated
native Zen, with Docker cleanup disabled. The old unused form was reset/reloaded,
fresh raw Compose/config reviewed and all three saved images pinned together.
The initializer's operator config and config volume were both updated atomically;
updating the volume alone would have lost German metadata configuration on restart.
The read-only API credential stayed read-only. Existing resources/networks/volumes
are intact; collector/metadata run on `2240b91`, no OOM/restart loop observed.
The local client first ran the matching `2240b91` API, then the hosted-tested
`6818115` privacy follow-up, retaining its original 2 CPU/1 GiB allocation,
volumes and zero jobs/tasks/corrections. Health and metadata queries pass.
The installed client subtitle selection fixture passes without HTTP/media access;
actual metadata Torznab queries pass. Live extraction/import/playback remains
unverified. Exact worker/client rollback is in
[SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md).

Pre-restart comparison against both retained pre-v5 backups preserves all
481,435 releases/first-seen and 239,690 maps across 32 v4 tables per provider.
Only `worker_meta.dirty` and `worker_meta.published_at` change as expected after
successful publication; all other retained table columns compare exactly.
Six SQL-total/native probes and the authenticated public route return 200.
The early live sample adds 144/32 maps and stores 54/22 verified descriptors,
while ordinary provider observations continue. This is not the earlier copied
ledger's 4,932-map gain, and neither these new live maps nor an entire population
received independent labels. Exact AniWorld One Piece S01E01 is still unresolved
live pending descriptor acquisition; the copied-state three-release proof remains
separate. Cross-provider client search can return Serienstream results with an
explicit unresolved-provider header; do not attribute those to AniWorld.

## What is limiting progress

The same frozen copied ledger gained 4,932 usable maps: AniWorld 65.3141% to
67.4231%, Serienstream 64.6355% to 65.8926%. That is a modest coverage gain.
Unchanged cohort rematching improved 4.1050s to 0.5299s, with 2,823 row mutations
reduced to zero. Preservation and removal of repeated work account for much of
this repair; complete mapping was not delivered.

After repair, the fixed 60-title diagnostics still contain 4,460 absent name
candidates, 1,176 generic names, 994 unresolved-parent episodes and 496 waiting
for parent verification, plus ambiguity/conflict rejections. These are sampled
episode diagnostics, not full-provider usable-coverage estimates. A DB engine,
more CPU or a higher request cap cannot create those missing identity facts.
Do not accept a wrong series cut, ordinal name or similar wording merely to
increase the percentage.

Fresh read-only live inspection at epoch `1791995769` still sees the old worker:

| Provider | Episodes | Releases | Usable episodes | Usable maps | Canonical due | Failed work | Unknown language observations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AniWorld | 63,609 | 116,428 | 63,593 | 41,530 | 1,024 | 0 | 0 |
| Serienstream | 306,912 | 364,645 | 289,615 | 187,465 | 8,457 | 140 | 16,242 |

These are sequential live reads and cannot be used as an after measurement for
the earlier frozen copy. There are zero never-checked canonical title records;
four removal quarantines remain unapproved. Provider HTML/500/language evidence
gaps are separate from canonical correspondence gaps. A short host sample showed
6.05% collector CPU/226 MiB and 0.13% metadata CPU/64.4 MiB, zero recorded restarts
or OOM kills. This is not a sustained utilization trace.

Full-copy read-only preflight at 2 CPU/2 GiB, no network and no extra swap took
19.6629s/74.7822s for AniWorld/Serienstream. The whole instrumented run took
98.824s with 18.1110 cgroup CPU seconds, 984,178,688 bytes read and 161,934 read
operations. Peak cgroup memory was 1,073,176,576 bytes; no OOM or CPU throttling.
Immediately repeated quick/FK checks took 0.7721s/3.6019s combined. No child-key
prefix was unindexed. Warm/cold ordering is explicit; this is not an engine A/B
benchmark or a measured storage-upgrade benefit.

An additional finite 20-parent lookup per provider confirmed existing `work_title`
index use. A disposable alternative index was rolled back, restoring schema;
Serienstream CPU was 0.01654s before/0.01671s after. Cold/warm differences do not
justify adding a redundant index. Publication still takes about 20s/72s, while
concurrent queries have about 45ms median and 270ms p95. Repeated full integrity
reads are a demonstrated cost worth isolating by phase, not proof that SQL query
execution or SQLite's writer lock is the primary system bottleneck.

## Infrastructure decisions

Keep SQLite for this single-host collector and independent immutable read
catalogs. This matches [SQLite's intended local usage](https://www.sqlite.org/whentouse.html).
No measured multi-writer queue contention or query throughput ceiling presently
justifies an engine migration. Existing local query/descriptor caches and OS
page cache already matter; caching is not absent.

| Option | Decision for the current pilot | Evidence or adoption trigger |
| --- | --- | --- |
| Local Turso Rust engine | Do not replace SQLite now | Current [compatibility document](https://github.com/tursodatabase/turso/blob/main/COMPAT.md) rejects secondary UNIQUE/index/FK on experimental WITHOUT ROWID tables; `schema-v2.sql` uses these. Mixed SQLite/Turso multi-process access is unsupported. This assessment concerns the local new engine, not hosted Turso or a benchmark of libSQL. |
| PostgreSQL | Candidate for future shared collector state | Its [concurrency model](https://www.postgresql.org/docs/current/mvcc.html) is appropriate when multiple workers/hosts need shared transactional queues. First measure lock wait and writer occupancy. Immutable SQLite serving can remain separate. |
| MySQL/InnoDB | No demonstrated advantage over keeping current storage | Another transactional server option, requiring the same migration, identity and recovery proof. No AniBridge engine comparison was run. |
| ClickHouse | Do not use for operational state | Its own [transaction guidance](https://clickhouse.com/docs/concepts/features/operations/insert/transactions) recommends Postgres for frequent individual-record application reads/writes. Analytics is a different possible future use. |
| Redis | Defer | Add shared cache/admission only when replicas or measured hot-query misses require it. Current latency and local caches do not establish that need. Preserve revision invalidation, outage behavior and correction precedence. |
| More/faster CPU or RAM | No live allocation change now | The preflight run is dominated by reads and waiting rather than CPU saturation. Memory reclaim occurred in the earlier rematch run, but no OOM. Measure phase-specific benefit with a paired bounded copy experiment before resizing. |
| Faster storage/network | Profile first | Cold reference checks are expensive; no storage replacement benchmark or bandwidth ceiling was measured. Source latency/errors and bounded admission differ from bulk network bandwidth. |

## Ordered production work and acceptance

1. **Approved deployment/client verification — implemented and verified within
   the stated bounds.** Pilot/client cutover, pinned image/resource/network checks,
   offline migration/publication, pre-restart release/map/history preservation,
   live totals/native/public route/client metadata queries pass. Keep the pre-v5
   backup and exact rollback, including both initializer/volume config locations.
   Existing live corrections are zero; nonempty correction precedence and outage
   recovery remain fixture proof. No media acquisition was initiated.
2. **Broader correspondence evidence — not implemented beyond this repair.**
   Freeze a genuinely prospective, independently labelled development/held-out
   set before further tuning; current labels are honest regression evidence.
   Prioritize unresolved parents and the highest missing-name cohorts. Verify
   canonical aliases, episode IDs, alternate orders/cuts and multilingual names
   before accepting contextual candidates. Report precision, abstentions and
   conflicting identities separately; do not promise population-wide accuracy.
3. **Publication cost reduction — not implemented.**
   Instrument state preflight, consistent export, read validation, locking and
   pointer publication independently. Then remove repeated unchanged work using
   trustworthy generation/file identity and consistent snapshots, retaining
   integrity/reference checks on changed or untrusted inputs. Benchmark identical
   copied ledgers at 2/2, preserving last-good and corruption/tampering rejection.
   Do not weaken validation solely because warm checks are faster.
4. **Fair maintenance throughput — implemented scheduling; live capacity open.**
   Track eligible age by first/changed/retry/old class, requests per useful map,
   descriptor reuse, parse time and publication occupancy over ordinary maintenance.
   The 646/hour cadence projection excludes searches/retries/initial verification.
   Profile canonical lock/network waits before adding bounded in-flight work and
   cross-title request coalescing. Preserve durable shared admission (default
   30/min, approved pilot now 90/min after bounded comparison),
   leases/backoff and provider isolation. Existing HTTPX async pools are already
   used; an unbounded async rewrite or daily full recrawl is not the next step.
5. **Source gaps — parser/backoff implemented; missing evidence remains open.**
   Stable empty-season templates, transient 500s and subtitle-only language labels
   remain distinct. Retain releases and retry history, report safe subcodes, and
   acquire only bounded representative positive metadata when needed. Audio,
   release dates and deletion evidence must not be invented.
6. **v3 integration — tests implemented/hosted verified; enforcement open.**
   Read-only inspection confirms v3 requires only `Conventional Commit Title`
   as a status, plus its existing review/CodeQL rules. Require the final test gate
   and an unconditional build gate after safe fork/Dependabot handling exists;
   current preview builds are path-filtered and registry-privileged. Verify an
   intentionally failing test/build blocks ordinary merge. Keep reviews, stable
   main/release policy and preview/stable images separate. No protection change
   or merge was performed. Full-bootstrap capacity and live extraction/import/
   playback remain unverified and cannot be inferred from this finite replay.

No DB/cache migration, allocation change, new crawl or competing collector was
performed. The accompanying aggregate evidence contains no raw stderr, HTML,
player URLs, query terms, IPs or credentials.

## Additional concrete release hygiene

Legacy Torznab logging exposed rejected API keys and request search inputs even
though opt-in catalog mode already avoided these logs. `6818115` replaces those
messages with a bounded operation and constant authentication warning, with two
captured-log regressions. All 267 API tests pass locally (18 existing skips),
with Ruff lint/format clean. Hosted tests `38604860503` and both native previews
`38604860757` pass. The local client now runs the installed privacy fix at
`ghcr.io/zzackllack/anibridge-api-preview@sha256:5d7b6bc059ee60f5385e87c2d380c724be8fc07e869b60c0700fba0fe1d452a9`;
its captured-log regression, health and metadata query pass. The unchanged worker
stays on tested `2240b91`; neither matching nor public wire schemas changed in
this API-only privacy fix. Client rollback remains the retained `71988fc` image,
with the initial `2240b91` override also retained privately.

`install_reviewed_worker_config.py` now maintains the two-location atomic config
procedure and exact-byte rollback. Four regressions pass on Mac and the installed
Linux worker, including partial second-write failure recovery. Copied actual
config bytes also pass rollback/reupgrade against installed worker core helpers;
no live volume is mounted in that rehearsal. The full Mac worker suite passes
173 tests with 13 existing platform skips; earlier installed Linux runtime suite
passes 182. This operations helper does not change the deployed worker runtime.

Read-only Dependabot inventory found three open default-branch alerts: Werkzeug
GHSA-g6x2-hccm-hh4m (medium, fixed 3.1.9), setuptools GHSA-h35f-9h28-mq5c (medium,
fixed 83.0.0), esbuild GHSA-g7r4-m6w7-qqqr (low, fixed 0.28.1). This branch also
locks Werkzeug 3.1.6 and setuptools 82.0.1. Dependency upgrades/advisory exposure
review are not implemented in this mapping repair and remain an explicit release
gate; the alert inventory alone does not prove exploitation of the pilot.

## October 18 local publication follow-up

The earlier publication optimization gap now has a local implementation and
bounded copied-ledger verification. [PUBLICATION_FOLLOWUP.md](PUBLICATION_FOLLOWUP.md)
records v6 change tracking, unchanged row-proof reuse, incremental export and
collection during publication, with 3.21×/4.38× measured warm publication speedups.
All release/first-seen, map and private-history preservation/rollback checks pass.
This is not a new hosted CI, registry publication, live rollout or capacity SLA;
the read-only checked live service remains `d85ed05`. See SERVER.md's newer v6
rollback instructions before using an older worker on upgraded state.
