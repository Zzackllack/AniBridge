# Publication follow-up, October 18

Publication turns the collector's ledger into the separate catalog read by the
metadata API. Previously, even another “checked this page” timestamp could cause
all rows and indexes to be rebuilt and every row to be checked again. Collection
for that provider waited for publication to finish.

## Implemented work

| Item | Change | Status |
| --- | --- | --- |
| 1. Track actual changes | A transactional v6 journal records affected titles. Names, releases, maps and effective removals keep the content cadence. Timestamp-only observations have separate hourly eligibility by default. | Implemented + verified on fixtures and copied ledgers |
| 2. Cheaper validation | Separate timings identify schema, integrity, relationships, row checks, semantics and summaries. Exact physical counts avoid repeated view joins. A digest/metadata/policy/validator receipt permits reuse of unchanged row proofs. | Implemented + verified; independent full admission also passes |
| 3. Incremental publication | Clone the previous good catalog, update changed title partitions and keep indexes. Missing/stale/tampered bases, unclassified changes, broad changes or incompatible intermediate constraints use a full rebuild. | Implemented + verified, including additions, deletion, reparenting and tombstones |
| 4. Keep collecting | Publication takes a WAL read snapshot and acknowledges its captured generation. Later writes remain pending. The provider-wide collection fence is removed; staging ownership and a short reader handoff lease remain. | Implemented + verified, including a concurrent writer and acknowledgement crash |

Full file integrity, schema, foreign-key relationships, semantic consistency,
counts and release-summary checks still run. Public/untrusted validation defaults
to checking every row. An invalid previous digest or receipt cannot authorize
partial row admission. Unexpected writes on the staging connection are captured;
external-connection writes invalidate staging. Clock rollback invalidates reuse.
No public schema, matching rule, client correction precedence or release identity
changes are part of this work.

## Controlled comparison

The exact measurements are in
[publication-followup-2026-10-18.json](evidence/publication-followup-2026-10-18.json).
The workload changes one generated episode name in an ordinary title and one in
the largest title, separately for each provider. These are generated metadata
edits, not evidence that a provider supplied those names. The ordinary/large
partitions contain 26/1,288 AniWorld episodes and 14/1,384 Serienstream episodes.

All runs use the same consistent copied ledger, 2 CPU/2 GiB, no extra swap and
networking disabled. The old `d85ed05` image performs its old full publication
against unchanged public ledger tables; its v5 startup is deliberately not run
on v6 bookkeeping. New-worker source preflight remains enabled and is timed
separately. This is a sequential warm-cache comparison, not an engine benchmark,
a cold-storage guarantee, a sustained load test or full-bootstrap capacity proof.
The new run also serves bounded overlapping metadata requests in the same
capped container; it does not measure a separate 512-MiB metadata service.

| Provider | Old full publication | New incremental publication | Speedup | New source preflight, separate |
| --- | ---: | ---: | ---: | ---: |
| AniWorld | 11.7888 s | 3.6671 s | 3.21× | 0.7543 s |
| Serienstream | 56.2486 s | 12.8327 s | 4.38× | 4.1756 s |

Process CPU time falls from 11.34 to 4.02 seconds for AniWorld and from
55.09 to 11.59 seconds for Serienstream; the new values include overlapping
query work. Process peak RSS rises from about 139/162 MiB to 159/190 MiB.
Cgroup peaks, including cache and prior work in each process, remain below
510 MB in the measured incremental run, with no OOM events. Block writes are
68.25→68.04 MB and 273.92→257.96 MB: copying the complete file still costs I/O.
The warm page cache makes physical read bytes unrepresentative of cold storage.

The two selected partitions require 3,534/4,125 row checks, versus
245,531/972,365 public rows in full admission. These counts are derived from
the selected partitions; catalog singleton and global checks remain additional
work. The timestamp-only trace also defers routine observations at five minutes
and admits them at one hour. Actual content changes can still cause frequent
publication, so this is not a measured 12× reduction in live publication count.

All seven public tables exactly match independent old full exports in both
directions. Both incremental files also pass the complete untrusted validator.
All 60 overlapping queries return 200 with exact SQL totals: median 57.88 ms,
maximum 140.088 ms. All 31 ordinary/large retrieval pages return the exact SQL
release ID sets. Failed exports retain the last good pointers; an unavailable
AniWorld pointer returns 503 while Serienstream continues returning 200.

## Verification and remaining costs

Across all 38 retained v5 tables per provider, all 497,678 release IDs and
first-seen times, 288,876 map rows, work/retry/lease/quarantine state and matching
history survive. Only the two generated entity name/time edits per provider,
publication clocks and schema version differ. The copied rollback/re-upgrade
retains identical pre-v6 backup hashes. Both providers fully publish again under
the normal 512-MiB address-space limit, producing files byte-identical to the old
full exports. Abandoned staging/sidecar recovery also passes on the full AniWorld
copy and cannot clear an active publisher's scratch.

Installed ARM64 Linux tests pass: **267 worker and 320 core**. API tests pass
**268 with 18 existing skips**. Focused cases include staged corruption, late maps,
concurrent source writes, policy/clock invalidation, upgrade interruptions,
acknowledgement crashes, and scratch recovery/ownership. Targeted Ruff checks
and `git diff --check` pass. New hosted CI and native AMD64 builds were not run.

The final accounted storage is 27,894,057,472 bytes including the old research
copies, this experiment, live state/read catalogs, 1-GB runtime reserve,
1.1-GB image/log allowance and 500-MB scratch allowance. Adding a full 1-GiB
publication staging reserve gives 28,967,799,296 bytes, below the 30-GB budget.
This is admission accounting with conservative allowances, not a continuous
measurement of every live file. No backup generation was removed.

The new publisher still copies the whole read file and scans it for global
integrity checks. Serienstream's integrity check alone takes 4.68 seconds in this
run. It still performs full source checks at startup; cold source preflight can
be much slower than the warm values above. Large pending batches use the full
path, so the incremental speedups do not apply to every publication.

The journal adds bookkeeping writes. In a separate rolled-back SQL test,
500 timestamp updates rise from about 2.1 ms without the journal to 7.2–7.3 ms with
it. That excludes durable commit cost and does not establish live collector
throughput. Raw due ages remain 70,083/365,255 seconds at the retained experiment
clock; they include work subject to other scheduling rules and are not live
eligible-queue ages. The entire work table remains unchanged.

An hour is an eligibility interval, not a catalog or provider freshness SLA.
Publication makes zero canonical/provider requests; requests per useful new map
is inapplicable here.
No mapping coverage or mapping accuracy gain is claimed by this publication work.

This is local code, installed-wheel Linux regression evidence and a source-overlay
full-copy experiment. It is not a new registry image, hosted CI result, live
upgrade, client upgrade, extraction, import or playback proof. The existing live
pilot remains on `d85ed05`; no resources, routing, volumes or GitHub policy changed.

## Reproduce and recover

The finite harness is `scripts/catalog/query_pilot/publication_benchmark.py`.
Use marked consistent disposable v5 SQLite copies and a separate output directory,
both containing `COPY_ONLY`. Run `seed`, `legacy`, then `incremental` sequentially,
with `--root` and `--state`. Seed and incremental use the new worker/core; legacy
uses the installed old worker/core without an overlay. Seed performs a full base
build before applying the generated edits. The harness bounds queries and pages,
checks exact results, rejects export failures and independently revalidates output.
Never run it on live volumes or alongside a collector writing those copies.

`publication_preservation.py verify` compares every retained v5 table against the
no-overwrite pre-v6 copy, allows only the documented generated entity fields and
publication clocks, checks timestamp-only admission and measures journal SQL cost.
Its `downgrade`/`reopen` modes exercise v6→v5→v6 on the same marked copies. Run
`legacy-check` from the benchmark harness with the old installed image between
those modes, with networking disabled. Reopening v6 resets its private publication receipt and requires a full first
publication; it never resets observations or matching history.

[SERVER.md](../../../scripts/catalog/query_pilot/SERVER.md#october-18-publication-upgrade-and-v6-rollback)
contains stopped-writer upgrade/rollback commands. Keep every backup generation
and `/state/backup`; rollback removes only v6 bookkeeping, never restores an old
ledger over newer observations. The API/client contract requires no migration.
