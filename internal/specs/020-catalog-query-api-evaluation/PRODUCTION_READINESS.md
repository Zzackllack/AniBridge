# October 14 production-readiness follow-up

This follows the implemented [mapping repair](MAPPING_IMPLEMENTATION.md), not a
replacement investigation. The user subsequently authorized pushing, preview
publication and interaction with the existing Coolify pilot. Code through
`2240b9119797bf3346444e719eef3e78fd0c83e4` is pushed without resetting history.
PR #170 remains a draft into protected `v3`; `main` remains default.

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

Live cutover is authorized but environment-blocked: the Mac is locked and native
Zen refuses interaction. The user identified the unsaved Coolify form as an old
unused draft, allowing it to be discarded. It has not been reset or saved. Keep
the read-only API credential read-only; do not bypass the required authenticated
Zen path. Existing resources, networks, volumes and collected state are intact.
The stopped local client remains at `71988fc`; its actual upgrade/live subtitle
behavior is still unverified. Exact worker/client rollback is in
[SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md).

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

1. **Approved deployment/client verification — implemented, environment-blocked.**
   Unlock the Mac, discard the identified unused draft, review fresh raw Compose
   and worker config, stage the pinned images with `stage_registry_upgrade.py`,
   then follow SERVER.md. Stop both service processes before offline migration;
   compare all releases/first-seen/maps against the no-overwrite pre-v5 backup
   before resuming. Check actual image, publication phases, provider isolation,
   totals, targeted retrieval, due ages and limits. Rehearse exact rollback on
   copies; never restore an old ledger over newer observations. Upgrade the
   stopped disposable client retaining state and verify real metadata/corrections
   without initiating media acquisition.
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
   cross-title request coalescing. Preserve the durable shared 30/min admission,
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
