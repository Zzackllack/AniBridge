# Anime-Lists and AniWorld correspondence — 2026-10-21

Anime-Lists is a useful additional source for anime identity and episode ordering.
It does **not** directly map AniWorld URLs or seasons. The missing join is still
AniWorld's exact season/cut → AniDB entry and episode order. A matching franchise
name, IMDb ID or episode count alone cannot establish that join.

This is research, not a deployed matcher change. Measurements and provenance (`evidence/anime-lists-research-2026-10-21.json`, local-only)
separate current public metadata reads from an October 20 copied ledger. No maps,
failures, scheduling receipts, live state or configuration were changed.

## What the dataset provides

Inspected upstream revision: `9ed90bf804bb24d58c99ea653e095194df494b52`, committed
October 19. Its [format documentation](https://github.com/Anime-Lists/anime-lists/blob/9ed90bf804bb24d58c99ea653e095194df494b52/README.md)
describes AniDB identities, target database identities and correspondence rules.
The master contains incomplete entries as well as usable ones. Counts from our
local parse of the pinned XML:

| Property | Count |
| --- | ---: |
| AniDB entries | 17,050 |
| Entries with numeric TVDB series IDs | 7,514 |
| Distinct TVDB series IDs | 4,389 |
| TVDB IDs associated with several AniDB entries | 1,307 |
| Entries containing a mapping-list element | 1,428 |
| Entries with a nonempty TMDB television field | 7,093 |

The [pinned master](https://github.com/Anime-Lists/anime-lists/blob/9ed90bf804bb24d58c99ea653e095194df494b52/anime-list-master.xml)
supplies season/offset rules and explicit episode pairs. Its title dictionary
supplies multilingual **series** names, not an episode-name database. There is no
numerical confidence score. A TVDB franchise can contain many AniDB entries,
covering separate seasons, specials and versions; selecting the first is unsafe.

Importer semantics matter: explicit pairs override offsets; absolute numbering
needs its own interpretation; zero targets represent intentional non-matches;
trailers/other episode types have reserved number ranges. One-to-many and
many-to-one pairs must survive parsing. TVDB series, TMDB television and TMDB movie
IDs are different namespaces. The README limits its IMDb field to standalone
entries, so that field is not a complete IMDb-series → AniDB lookup table.

## What AniWorld actually exposes

Five bounded HTML metadata reads covered three title pages and two season pages:
Classroom of the Elite, Attack on Titan and Ikki Tousen; Classroom season 4 and
Ikki season 6. All returned HTTP 200. They expose an IMDb ID, titles/aliases,
series year, native URL coordinates and Schema.org TVSeries/TVSeason/Episode
markup. No inspected identity attribute or metadata link exposed an AniDB,
TVDB, TMDB, MAL or AniList ID. A supplementary Classroom read found WebPage/
Organization/SearchAction JSON-LD, with no external identity fields. The site's
linked main JavaScript had none of the checked metadata-provider names.

This is a bounded sample, not proof that such IDs occur nowhere on the site.
Schema.org is an HTML vocabulary, not a declaration of which database's order is
used. IMDb identifies the franchise but does not settle its season/cut ordering.
Our worker already reads valid AniWorld `data-imdb` evidence; it is not a newly
discovered unused identity shortcut.

Public operator statements also do not establish a single numbering contract:

- In [June 2021](https://aniworld.to/support/frage/animewnsche-quelle), the AniWorld
  Team names TheMovieDB and AniSearch as example reference sources for requests.
  That permits multiple references; it does not say the catalog follows either
  database's episode ordering or is synchronized automatically.
- In [July 2024](https://aniworld.to/support/frage/generelle-frage-episodentitel-kein-intresse),
  the Team explains that checking/backfilling episode titles takes manual work
  and some retain generic Episode 1/2/3 names. Waiting for a presumed automatic
  metadata update cannot be our only recovery strategy.

Searches of public support material did not locate an operator statement that
all numbering follows AniDB, TVDB or TMDB, or a documented public identity/order
API. Community replies recommending AniSearch/AniDB are not operator contracts.
The site's internal metadata import sources remain unverified.

## Concrete cases worth testing

**Ikki Tousen:** current AniWorld season 6 contains `Encounter` and `Exchange`.
Our copied TVDB descriptor has `Extravaganza Epoch 1: Encounter` and
`Extravaganza Epoch 2: Exchange` at S00E20/E21, with episode IDs 5141698/5141699.
Neither source episode is mapped in the copied ledger. Anime-Lists associates
AniDB 10812, Extravaganza Epoch, with TVDB 80158 season 0 and offset 19. These
independent records are consistent with the same two episodes. This is a strong
review candidate, not a claim that a production source→AniDB binding is already
implemented or independently accuracy-tested. The franchise page also lists
several cuts in its global aliases, so an alias alone cannot pick season 6.

**Attack on Titan:** AniDB 14444, the 2019 continuation, maps to TVDB 267440
season 3 with offset 12. Once an AniWorld season is independently bound to that
entry and ordering, episode 1 translates to TVDB S03E13. This is a conditional
format example; this research did not certify a particular AniWorld season bind.

**One Piece:** AniDB 69 contains absolute-number ranges spanning TVDB seasons.
AniWorld is already seasonized. Applying the table to the number at the end of
an AniWorld URL would feed it the wrong numbering system. The table is useful
only after establishing the source absolute coordinate independently.

**Classroom:** Anime-Lists has separate AniDB entries for seasons 1–4 under the
same TVDB franchise. Its existence does not independently prove source episode
16's identity. The prior finale-annotation repair remains a separate fix.

## Measured overlap with our backlog

These are sequential independent provider snapshots from October 20, not a new
live coverage report. Both database hashes match the frozen retry-replay inputs.
An episode is counted here if it has a retained release and no canonical episode
row. This query defines the denominator, rather than every discovered URL:

```sql
SELECT e.title_id, count(*)
FROM entity e
WHERE e.kind = 'episode'
  AND EXISTS (SELECT 1 FROM release r WHERE r.entity_id = e.entity_id)
  AND NOT EXISTS (
    SELECT 1 FROM canonical_episode c WHERE c.entity_id = e.entity_id
  )
GROUP BY e.title_id;
```

| Classification | AniWorld episodes | Serienstream episodes |
| --- | ---: | ---: |
| Unmapped usable total | 16,916 | 61,496 |
| Existing TVDB parent also appears in Anime-Lists | 9,970 | 11,730 |
| Existing TVDB parent absent from Anime-Lists | 1,431 | 40,797 |
| No TVDB parent, one exact-name TVDB candidate | 4,457 | 1,187 |
| No TVDB parent, several exact-name TVDB candidates | 545 | 238 |
| Exact name candidates, none with numeric TVDB IDs | 197 | 177 |
| No exact main/official name candidate | 316 | 7,367 |

For the no-parent rows, join provider display title plus stored aliases to
`animetitles.xml` main/official names using the existing `search_key`; then join
AniDB IDs to numeric TVDB IDs in the master, deduplicating TVDB candidates per
provider title. No year, IMDb, edition or episode validation is applied in this
candidate count. AniWorld's single-TVDB-candidate group covers 118 titles;
Serienstream's covers 59. Several AniDB entries can still sit behind one TVDB ID.

**None of these counts is a recovery prediction.** Parent overlap proves only
dataset relevance. Exact name matching proposes identities, including possible
wrong editions. There were zero accepted new maps and no population precision
evaluation. This anime-specific source leaves most general Serienstream TV
outside its coverage.

## Recommended integration boundary

1. Import a pinned, digest-checked data version into a private local index. Use
   the existing hardened XML tooling and storage admission. Validate ranges,
   namespaces, contradictions and ambiguous pairs; retain the last admitted
   version if an update fails. Do not download the table during searches.
2. Generate parent/cut candidates from verified IDs and multilingual names.
   Check parent year/kind/IDs against existing canonical evidence. A whole-series
   start year must not be substituted for a later AniDB season's release year.
3. Record an explicit provider-season/segment → AniDB entry/order binding, with
   independently reviewed evidence or a tested automatic proof rule. Support
   manual reviewed bindings for otherwise generic names. A franchise alias,
   matching count, matching numbering or text similarity alone is insufficient.
4. Compose that binding with the table, then validate the target against the
   canonical descriptor and episode IDs/order actually used by our Sonarr path.
   TVDB itself supports multiple [season types](https://github.com/thetvdb/v4-api/blob/main/docs/swagger.yml).
   Reject conflicts; preserve native coordinates, previous valid maps and local
   correction precedence. Do not flatten split/combined episodes to one target.
5. Fingerprint source, binding, table row/version, descriptor and matcher. Rematch
   affected titles locally when evidence changes. Canonical fetching remains
   cached and subject to existing shared admission; no new provider-wide crawl.
6. Freeze development and separate held-out series across specials, split seasons,
   generic names, alternate cuts and split/combined episodes before tuning rules.
   Report exact correct additions, wrong additions, unresolved reasons and full
   ledger preservation. Counts in this note do not replace that evaluation.

Data-use terms need clarification before product integration/distribution. The
inspected root has no license file and GitHub reports no recognized license.
[Issue 613](https://github.com/Anime-Lists/anime-lists/issues/613) explicitly asks
for one and remains open. The encouraging reply in
[issue 143](https://github.com/Anime-Lists/anime-lists/issues/143) expressly says
the commenter cannot speak officially. No outreach was sent and no dataset is
vendored here. This uncertainty does not prevent the present metadata analysis.

**Status:** upstream inspection, bounded AniWorld metadata inspection and offline
overlap measurement are verified. Runtime import, source-order bindings and
held-out recovery evaluation are not implemented by this research. Better aliases
can help identify series; explicit order tables can help differing season layouts;
truly absent or contradictory source evidence still requires review or must stay
unresolved. Neither more CPU nor a higher canonical request rate supplies that
missing evidence.

## TheXEM follow-up — 2026-10-21

[TheXEM](https://thexem.info/) is relevant to both AniWorld and Serienstream. Its
entities include scene, TVDB and AniDB; scene means release-group numbering, not
Serienstream. Its [API documentation](https://thexem.info/doc) describes season/
episode and absolute-coordinate conversion, including multiple destinations.
Neither provider is a declared source namespace. The same provider-order binding
requirement therefore remains.

Five bounded `map/all?origin=tvdb&id=...` reads returned HTTP 200:

| TVDB series | API result | Mapping rows | Scene vs TVDB season/episode differences |
| --- | --- | ---: | ---: |
| Attack on Titan, 267440 | success | 89 | 0 |
| Classroom of the Elite, 329822 | success | 54 | 0 |
| American Dad, 73141 | success | 404 | 397 |
| Ikki Tousen, 80158 | no show with this TVDB ID | 0 | — |
| One Piece, 81797 | no show with this TVDB ID | 0 | — |

These are response snapshots, not complete/freshness guarantees. Both successful
anime responses include AniDB coordinates. Attack on Titan has 40 AniDB↔TVDB
season/episode differences. Classroom's returned S04E16 has scene absolute 16
and TVDB absolute 54, illustrating that the numbering systems can differ even
when season/episode pairs agree. These scoped coordinates must not be confused
with AniDB entry IDs or blindly substituted for Anime-Lists coordinates.

American Dad's scene S01E08→TVDB S02E01 agrees with the October 20 copied
Serienstream observation `Bullocks to Stan` and its existing accepted map. This
is corroboration of a correct map, not a newly recovered episode. TheXEM can
support recovery when source ordering is independently established; it does not
automatically identify an unassociated series, a different cut or a generic name.

[Sonarr's FAQ](https://github.com/Servarr/Wiki/blob/master/sonarr/faq.md#how-sonarr-handles-scene-numbering-issues)
documents its existing TheXEM integration for numbering and anime aliases.
Inspected Sonarr `main` revision `bc54afbdd0e38bdb0fca4785fcf7d7a6af77bf9a`
confirms fetching scene↔TVDB maps and names. This does not establish the installed
client's current mapping state. Context7's retrieved Sonarr API documentation was
for v5-develop; v4/main behavior here was checked directly in upstream source.

There is a concrete integration risk to test before adding conversions:
AniBridge's catalog formatter emits canonical coordinates, while Sonarr's
[ParsingService](https://github.com/Sonarr/Sonarr/blob/bc54afbdd0e38bdb0fca4785fcf7d7a6af77bf9a/src/NzbDrone.Core/Parser/ParsingService.cs)
defaults remote releases to scene-origin interpretation unless an applicable
scene mapping declares TVDB origin. A TVDB ID identifies the series; it does not
by itself bypass this episode conversion. Test a genuinely differing map across
the full Sonarr→Prowlarr→AniBridge search and result-interpretation path before
choosing an output convention. Do not globally disable TheXEM for other indexers,
or change canonical search semantics to accept ambiguous numbering silently.

Recommendation: share the candidate/binding/target-validation boundary with
Anime-Lists, while keeping both data-source adapters separate. Cache acquired
evidence in the worker and retain last-good data on outages; no query-time XEM
HTTP dependency is needed. Runtime integration, held-out recovery and reproduction
of the suspected double-conversion problem remain unimplemented by this research.
