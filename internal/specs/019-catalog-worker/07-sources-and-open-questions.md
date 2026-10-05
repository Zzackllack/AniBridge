# Evidence register and remaining release decisions

Review date 2026-09-26. Engineering contracts are normative in 02/03/04/08/09;
there are no intentionally deferred routine schema/lifecycle decisions here.
Implementation may start privately. Release gates are not evidence of success.

## Verified repository evidence

`git ls-remote origin` and `gh pr view 119` confirmed main
`e14a041c0a8ddeac71aab7b8f564ac4a9584603a` and open PR head
`61351bbcbfc1295ab597f8385f063598c25f3191`. No merge/fetch/checkout or GitHub
write was performed. The working branch had an untracked spec folder before
this review; it is user work, not disposable generated output.

[01](01-current-state-and-reuse.md) records inspected paths and reuse choices.
Lockfile inspection: aniworld 5.0.6, HTTPX 0.28.1, FastAPI 0.135.1,
SQLAlchemy 2.0.48, SQLModel 0.0.37, Alembic 1.18.4; runtime baseline Python 3.14.
Dependency minimums in pyproject are not installed/locked versions. No lockfile
was changed and no full application suite or provider crawl ran in this review.

Code/test inspection establishes legacy hash omission of site, ignored offset,
fake recent test entries, guessed SD/H264, scheduling before ClientTask write,
paused adds still calling schedule_download, fixed unauthenticated SID, three
mainline Alembic revisions and incomplete persisted job request data. These are
implementation hazards, not claims that all client failures were reproduced.
PR #119's metadata matcher permits a 0.45 similarity threshold and boosts ID
search candidates; do not copy that as sufficient download mapping evidence.
Its cache tests verify eviction, not mapping correctness. New exact matching
rules deliberately favor unresolved over wrong episode acquisition.

The old PR performance document records multi-gigabyte bootstrap observations;
that is historical reported evidence, not a current measurement. It forbids
hosted catalogs under its earlier architecture; this specification supersedes
that distribution decision, preserving its useful memory analysis. Nothing
here changes `018-upstream-compatibility` or claims its download checks proved
Sonarr library import or playback.

## Primary technical documentation/source consulted

Context7 was used for SQLite, cryptography, HTTPX and TMDb documentation retrieval;
its SQLite answer was broad, so the exact immutable behavior was checked in
SQLite's official documentation. Official source/documentation fills gaps:

- [SQLite URI](https://sqlite.org/uri.html): immutable disables change detection;
  changing an immutable file can return incorrect results.
- [SQLite backup](https://sqlite.org/backup.html) and
  [VACUUM](https://sqlite.org/lang_vacuum.html): consistent copies do not remove
  private tables. The specification selects a fresh allowlisted export.
- [cryptography Ed25519](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/):
  maintained signing/verifying of exact bytes; protocol policy remains ours.
- [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/) and
  [async streaming](https://www.python-httpx.org/async/): per-operation timeout
  and response closure, not proof of total wall-clock cancellation.
- [Python 3.14 zstd](https://docs.python.org/3.14/library/compression.zstd.html):
  standard-library streaming compression; verify availability in packaged builds.
- [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/):
  shared lock is optional architecture, not a catalog requirement.
- [FFmpeg protocols](https://ffmpeg.org/ffmpeg-protocols.html) and
  [ffprobe](https://ffmpeg.org/ffprobe.html): I/O/analysis limits alone do not
  supervise a complete extraction workflow.
- [Torznab draft](https://torznab.github.io/spec-1.3-draft/torznab/Specification-v1.3.html):
  capabilities, RSS pagination and IDs. Error 900 is our explicit extension;
  compatibility requires the client experiment.
- [qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-4.1%29):
  external state vocabulary. AniBridge emulates a subset; it is not a torrent engine.
- [Sonarr qBittorrent adapter](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Download/Clients/QBittorrent/QBittorrent.cs),
  [Radarr adapter](https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/Download/Clients/QBittorrent/QBittorrent.cs):
  source inspection of state handling; branches are mutable. Pin actual image
  versions/digests and source SHAs in C5. Sonarr treats stalledDL/error as warning,
  not proof of automatic replacement; queue visibility/import require execution.
- [TMDb movie details](https://developer.themoviedb.org/reference/movie-details),
  [external-ID find](https://developer.themoviedb.org/reference/find-by-id):
  proposed optional movie canonical adapter uses documented endpoints; no live
  credentialed request or redistribution permission established.
- [PR #119](https://github.com/Zzackllack/AniBridge/pull/119): local source at
  verified head; no adoption of its operational DB schema.

Skyhook endpoints are observed in AniBridge/PR source, not a published SLA or
redistribution grant. Earlier draft links to TheTVDB terms/TUF were research
leads, not approvals: [TVDB terms](https://www.thetvdb.com/tos),
[TUF overview](https://theupdateframework.io/docs/overview/). This review makes
no legal conclusion. C7 must collect dated terms/licensing evidence for each
field/source and intended redistribution; HTTP accessibility is insufficient.

## Outstanding maintainer decisions, only when their gates are reached

No answer is required to implement the private specification. These decisions
must not be silently resolved by code or by lack of response:

1. **Public redistribution (C7):** approve the exact provider/canonical field
   inventory based on source terms/permission. Recommendation: withhold any
   unapproved field/source and postpone hosted launch if required mappings
   cannot be distributed. Private fixture development can continue. An
   alternative licensed source has cost/coverage implications and needs approval.
2. **Hosted deployment (C8):** select domain, operator/key custody and monthly
   bandwidth budget from C4 measurements. Recommendation: portable existing
   host plus static serving initially; do not add cloud services until required.
3. **Only if experiments fail:** unknown-quality/size rejection, inadequate
   canonical coverage, missed freshness/capacity or RSS backlog cannot be hidden
   by invented quality, guessed numbering, more scraping, query telemetry or
   remote search. Present measured alternatives and obtain a product decision
   before changing those boundaries. Routine bounded tuning within the stated
   profile is engineering work and does not need a new product choice.

## Checks executed during this documentation review

Disposable Python/SQLite experiment on local SQLite 3.53.4 executed the exact
09 DDL: eight tables; movie and season-zero episode fixture insertion; six
negative cases (unknown language, invalid timestamp ordering, movie coordinates,
null episode season, missing FK, duplicate episode mapping) rejected by SQLite.
`integrity_check=ok`, `foreign_key_check=[]`; application_id matched. Prefix
query EXPLAIN used the covering title_search index after matching its collation.
This checks DDL syntax/selected constraints, not the unimplemented semantic
validator, target Docker SQLite version or production query performance.
The 09 identity vector was computed with Python hashlib/JSON, including the
legacy hash formula verified in mainline. No application tests, real *arr run,
provider scrape, media download, benchmark or deployment was performed.

A separate documentation check resolved all relative Markdown links, parsed
fenced JSON, checked balanced fences/whitespace, and verified the concrete reuse
matrix's referenced paths against the pinned Git trees. These checks cover the
previously untracked spec files directly; `git diff --check` alone cannot check
untracked content. The second consistency pass reconciled activation/rollback,
query/index collation, sampling admission, coverage and gate references.

## 2026-09-30 — RSS workflow refinement

Maintainer approved revising exhaustive initial RSS coverage after evidence.
Primary pinned [Sonarr README](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/README.md)
and [Radarr README](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/README.md)
describe RSS for new content and search for missing/historical content.
Their pinned [Sonarr HttpIndexerBase](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/NzbDrone.Core/Indexers/HttpIndexerBase.cs)
and [Radarr HttpIndexerBase](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/src/NzbDrone.Core/Indexers/HttpIndexerBase.cs)
stop an initial cursorless RSS sync after its first nonempty page. Subsequent
syncs page to the prior cursor; the 1,000-result stop additionally depends on
the oldest result being over 24 hours old. Persisted indexer status supplies
normal failure backoff. A detected coverage gap recommends search.
Context7 retrieved current Sonarr v5-development guidance; pinned v4 source and
real v4/v6 experiments, not development documentation, establish these behaviors.
05 now tests normal historical search/new RSS/catch-up workflows. Original
100/1,000 bootstrap failure is retained in 10/11 and its unchanged harness.

## 2026-10-01 — Pinned STRM parser behavior

Context7 retrieved Radarr import/parser documentation; the exact pinned
[Radarr MediaFileExtensions](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/src/NzbDrone.Core/MediaFiles/MediaFileExtensions.cs)
maps `.strm` to its SDTV default and recognizes it as a streaming extension.
Actual Radarr6.4.4.10685 and Sonarr4.0.20.3014 generated-media experiments reject
Unknown-only profiles, then import a copied proxy STRM under an explicit
Unknown+SDTV profile and decode the imported URL. These are client interpretations,
not height/codec evidence from AniBridge or proof of live-provider access.
Commands, image digests, resource measurements and limitations are in10/11.
