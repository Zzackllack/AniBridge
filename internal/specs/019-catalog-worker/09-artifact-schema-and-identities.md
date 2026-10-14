# Artifact schemas and identity contract

Normative design, not an implemented format. Gate C1 executes this DDL and
freezes golden bytes before implementation depends on it. SQLite is selected;
JSON blobs, FTS extensions and a copy of the worker DB are not the artifact.
All tables are STRICT; all foreign keys are checked on export and import.
`user_version=1`, `application_id=1094861633` (0x41424341, ABCA), UTF-8,
4096-byte pages, DELETE journal, no WAL/SHM, views, triggers, virtual tables,
extensions or extra application tables/indexes. Validate stored table/index
definitions against the normalized fixed DDL, including CHECK/FK expressions,
not column names alone; no source-provided functions/default expressions. SQLite's primary/unique
constraint autoindexes are allowed. `sqlite_stat*` is not exported.

## Exact DDL

```sql
PRAGMA page_size=4096;
PRAGMA encoding='UTF-8';
PRAGMA journal_mode=DELETE;
PRAGMA foreign_keys=ON;
PRAGMA application_id=1094861633;
PRAGMA user_version=1;
CREATE TABLE catalog (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  provider TEXT NOT NULL CHECK(provider IN ('aniworld.to','s.to','megakino')),
  schema_version INTEGER NOT NULL CHECK(schema_version=1),
  identity_version INTEGER NOT NULL CHECK(identity_version=1),
  listing_checked_at INTEGER NOT NULL CHECK(listing_checked_at>=0)
) STRICT;
CREATE TABLE title (
  title_id TEXT PRIMARY KEY NOT NULL,
  identity_anchor TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL,
  display_title TEXT NOT NULL,
  search_key TEXT NOT NULL COLLATE NOCASE,
  media_type TEXT NOT NULL CHECK(media_type IN ('series','movie','unknown')),
  year INTEGER CHECK(year BETWEEN 1800 AND 2200),
  path TEXT NOT NULL UNIQUE,
  observed_at INTEGER NOT NULL CHECK(observed_at>=0),
  detail_status TEXT NOT NULL CHECK(detail_status IN ('pending','partial','complete','stale'))
) STRICT;
CREATE INDEX title_search ON title(search_key,title_id);
CREATE INDEX title_slug ON title(slug,title_id);
CREATE TABLE alias (
  title_id TEXT NOT NULL REFERENCES title(title_id),
  search_key TEXT NOT NULL COLLATE NOCASE,
  display_alias TEXT NOT NULL,
  PRIMARY KEY(title_id,search_key)
) STRICT;
CREATE INDEX alias_search ON alias(search_key,title_id);
CREATE TABLE entity (
  entity_id TEXT PRIMARY KEY NOT NULL,
  title_id TEXT NOT NULL REFERENCES title(title_id),
  identity_anchor TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('episode','movie')),
  native_season INTEGER,
  native_episode INTEGER,
  display_title TEXT,
  path TEXT NOT NULL UNIQUE,
  observed_at INTEGER NOT NULL CHECK(observed_at>=0),
  CHECK((kind='movie' AND native_season IS NULL AND native_episode IS NULL)
     OR (kind='episode' AND native_season>=0 AND native_episode>=1
         AND native_season IS NOT NULL AND native_episode IS NOT NULL))
) STRICT;
CREATE INDEX entity_title ON entity(title_id,native_season,native_episode,entity_id);
CREATE TABLE release (
  release_id TEXT PRIMARY KEY NOT NULL,
  entity_id TEXT NOT NULL REFERENCES entity(entity_id),
  language TEXT NOT NULL CHECK(language IN ('de-dub','en-dub','de-sub','en-sub')),
  first_seen_at INTEGER NOT NULL CHECK(first_seen_at>=0),
  observed_at INTEGER NOT NULL CHECK(observed_at>=first_seen_at),
  UNIQUE(entity_id,language)
) STRICT;
CREATE INDEX release_recent ON release(first_seen_at DESC,release_id ASC);
CREATE TABLE canonical_title (
  mapping_id TEXT PRIMARY KEY NOT NULL,
  title_id TEXT NOT NULL REFERENCES title(title_id),
  namespace TEXT NOT NULL CHECK(namespace IN ('tvdb','tmdb-tv','tmdb-movie','imdb')),
  external_id TEXT NOT NULL,
  source TEXT NOT NULL,
  evidence TEXT NOT NULL CHECK(evidence IN ('explicit_id','exact_title_year','reviewed')),
  checked_at INTEGER NOT NULL CHECK(checked_at>=0),
  UNIQUE(title_id,namespace)
) STRICT;
CREATE INDEX canonical_lookup ON canonical_title(namespace,external_id,title_id);
CREATE TABLE canonical_episode (
  mapping_id TEXT NOT NULL REFERENCES canonical_title(mapping_id),
  entity_id TEXT NOT NULL REFERENCES entity(entity_id),
  season INTEGER NOT NULL CHECK(season>=0),
  episode INTEGER NOT NULL CHECK(episode>=1),
  external_episode_id TEXT,
  evidence TEXT NOT NULL CHECK(evidence IN ('explicit_id','exact_title','reviewed')),
  checked_at INTEGER NOT NULL CHECK(checked_at>=0),
  PRIMARY KEY(mapping_id,season,episode),
  UNIQUE(mapping_id,entity_id)
) STRICT;
CREATE INDEX canonical_episode_entity ON canonical_episode(entity_id,mapping_id);
CREATE TABLE identity_alias (
  kind TEXT NOT NULL CHECK(kind IN ('title','entity')),
  old_id TEXT NOT NULL,
  current_id TEXT NOT NULL,
  PRIMARY KEY(kind,old_id),
  CHECK(old_id<>current_id)
) STRICT;
```

Semantic validator: exactly one catalog row; IDs recompute correctly; anchors
and paths meet the rules below; alias targets exist with the declared kind,
are acyclic and flattened (no alias-to-alias); title/entity kinds agree (an
unknown title may contain explicitly typed entities); movie has at most one
movie entity per title; episode mapping points to that canonical title's own
episode entity. IMDb has no episode-coordinate rows in v1. `tmdb-movie`
requires movie type, `tvdb`/`tmdb-tv` series type. Decimal IDs are positive
canonical decimal strings, IMDb is `tt` plus 7–12 digits. Only validated,
permitted associations are exported. Absent rows mean unresolved, not identity
numbering. Split/combined episodes and conflicting specials stay unresolved:
v1 deliberately supports one provider entity to one canonical episode only.
No quality table: estimates are private, and provider hints are deferred.

Read-only SQLite integrity checks alone do not establish these row constraints.
Recheck stored types, nullability, ranges, enums and associations independently;
inspect the database header's read/write versions to require rollback-journal
format. An immutable connection's reported journal mode is not sufficient WAL
rejection. This preserves the selected DDL and read-only artifact boundary.

`source` is a versioned adapter/provenance name from the publisher's approved
source inventory, not a URL or arbitrary free text. Consumers validate its
syntax `[a-z0-9][a-z0-9._-]{0,63}`; rights clearance is a publication gate,
not something a signature or string can prove. No upstream payloads.

Limits per string: 64 hex characters for digest IDs; 512 UTF-8 bytes for names,
aliases and search keys; 128 for external IDs; 1024 for paths/anchors; 256 for
slug. Reject overflows, do not truncate identities. Maximum counts per
provider: 100,000 titles, 1,000,000 aliases, 2,000,000 entities, 8,000,000
releases, 400,000 canonical titles, 8,000,000 canonical episodes, 2,000,000
identity aliases. Artifact byte limits usually bind first. These are safety
ceilings, not measured provider counts. Reject the entire candidate on breach.

## Normalization, languages and matching

Search keys: Unicode NFKC, casefold, replace each run of non-alphanumeric
Unicode characters with one ASCII space, collapse/strip spaces. Do not strip
diacritics or translate titles. Index exact and prefix keys; use escaped LIKE
prefix matching, never a user wildcard. Exact display/alias match ranks first,
prefix next; ties sort provider key/title ID. Bound candidate scoring to 200
rows/provider. Fetch at most 201 to detect overflow; >200 candidates yields
query_too_broad (HTTP 400/error 200), not a silently truncated total. Recent
RSS does not use this title-candidate cap. NOCASE indexes match SQLite LIKE
prefix optimization; Unicode casefolding happens before SQL. No whole-catalog
fuzzy scan or new search dependency.

Language tokens encode the provider's selection label, not inferred audio:
`de-dub` → German Dub/Deutsch, `en-dub` → English Dub,
`de-sub` → German Sub, `en-sub` → English Sub. Sub tokens assert the observed
subtitle language only; audio is unknown unless separately measured locally.
Do not copy mainline's inference that German Sub implies German audio.
Unknown/new provider labels are counted as coverage gaps and emit no release.
An adapter may map a numeric provider code only with a provider-specific
fixture; AniWorld and s.to codes are not interchangeable. Changes to this
vocabulary require a new supported schema, not silently broadened validation.

## Stable identities

Let `H(parts)` be lowercase SHA-256 of UTF-8 JSON array serialization with
`ensure_ascii=False`, separators `(',', ':')`, no whitespace/newline. Inputs
are strings only, NFC normalized, with no optional/omitted elements.

- `title_id = H(['ab-title-1', provider, identity_anchor])`.
- `entity_id = H(['ab-entity-1', provider, identity_anchor])`.
- `release_id = H(['ab-release-1', provider, entity_id, language])`.
- `mapping_id = H(['ab-map-1', provider, title_id, namespace, external_id])`.
- Mode identity: `H(['ab-grab-1', release_id, mode])`, mode `download` or `strm`.
  Infohash is its first 40 hex characters (identifier, not a content checksum).
  GUID is `urn:anibridge:release:1:{release_id}:{mode}`, `isPermaLink=false`.

Identity anchor is the first validated provider-relative path for that entity,
including site-native episode/movie identity, excluding origin. Do not derive
from canonical numbering, display text, quality, publication or source_id.
Provider paths start with one `/`, contain no scheme, authority, query,
fragment, backslash, control, dot segment, encoded slash/backslash/dot-segment
or double decoding. Parse once, NFC-normalize decoded path text, percent-encode UTF-8 with uppercase hex,
preserve path case, remove trailing slash except `/`. Reject ambiguous input.
Current path may change while anchor/ID remains. Known same-origin redirect
plus matching provider-native identity, or a reviewed correction, may link a
rename; title similarity alone cannot. Unproved rename stays separate and
unresolved. Never silently reuse an old anchor for different content.

Persist anchors, aliases and release discovery ledger across rebuilds in the
worker state volume. On a proven merge keep the earliest-created identity
(tie: lexical ID), alias the other, and preserve the minimum first_seen_at for
each language. Do not apply alias redirection to a frozen queued job without
checking its original source identity. An independently bootstrapped publisher
can differ after renames; source switching does not promise universal identity
history. It preserves jobs and local aliases and reports conflicts. A restore
from backup, not a fresh crawl, is how a publisher preserves its history.

## Magnet v2 and released-mainline compatibility

New magnets contain exactly one `xt=urn:btih:{infohash}`, display-only `dn`,
`ab_v=2`, and `ab_data` (unpadded base64url UTF-8 JSON, maximum 8 KiB decoded).
Payload fields are required: `provider`, `title_id`, `entity_id`, `release_id`,
`title_anchor`, `entity_anchor`, `slug`, `path`, `kind`, `native_season`,
`native_episode`, `language`, `mode`, `canonical` (null or object with
`namespace`, `external_id`, `season`, `episode`; coordinates null for movie).
JSON has no duplicate/unknown keys; validate/recompute identities and hash;
path/origin and save-path policy applies even to a valid hash. Hash is not
authorization. Canonical selection is frozen at acceptance with provenance
`magnet` and compared to a local mapping if available; conflicts reject with
409 rather than silently remap. No catalog/network is required to queue a
valid legacy grab. V2 may likewise queue using its validated self-contained
identity when the catalog is absent; actual resolution still uses local policy.

Continue decoding released `aw_*` and `sto_*` magnets, including missing site
(default aw→aniworld.to, sto→s.to), explicit aw_site=megakino, legacy language
labels, and mode=strm. Preserve the supplied valid 40-hex BTIH and all existing
ClientTask hashes; never rehash a persisted job. Mainline hash is SHA-1 of
`slug|season|episode|language` plus `|mode` when supplied, omitting site.
Tests must include these exact historical bytes. No conversion to fake movie
S01E01 for new magnets; old movie payloads keep their legacy resolver semantics.

Maintain private hash→job aliases so v1/v2 adds of the same *proven* provider,
entity, language and mode do not run twice. Each submitted hash remains
queryable/removable by its submitted hash. This is hash aliasing, not client
account isolation (the compatibility API has no such identity). Deleting one
hash alias does not remove another hash alias; stop the shared job only when the last alias
is removed or management explicitly cancels it. A legacy hash already bound
to a different provider/entity returns 409 identity_conflict, never overwrites
it. Unprovable equivalence is not automatically merged. Preserve original
hash/name/category/path and IDs throughout upgrade. Tests cover collisions,
legacy STRM ambiguity and jobs whose provider is now disabled or absent.

## Reproducible identity vector

Synthetic inputs: provider `aniworld.to`, title anchor
`/anime/stream/example`, entity anchor
`/anime/stream/example/staffel-1/episode-2`, language `de-dub`.
The hash functions above produce these values (computed during this review):

```json
{
  "title_id": "4b02f8e62ca7ae58ff7abfe4ca6e6a91c9b3e602e8e9f2b747cd07b7b4371e23",
  "entity_id": "fe8964f7cc42e76e3301675ec46234048b7c87538d896de995eb873ff3271ba2",
  "release_id": "ae735d09c7310ed45a6fa94d9193ffa7e80b741e84986366c6d133eb5ddc988b",
  "download_infohash": "9faa798f6414ce25f3035566d891ed3fb27267dc",
  "strm_infohash": "6a9679b805403831a6087132b442543d0a656c55",
  "legacy_infohash": "b3dd9fbac3813f8cc32be2f44824cbba3e52a46c",
  "legacy_strm_infohash": "8705552cc6a4c31ac6e5c352414ea2cd251090ce"
}
```

Legacy vector inputs are slug `example`, season 1, episode 2, language
`German Dub`, with absent mode or `strm`. Goldens must additionally cover
NFC-equivalent text, each provider, movie null coordinates, changed labels and
same-hash conflicts. Signature/artifact-byte goldens are C1 implementation
fixtures: no real catalog or production signing key is needed.

## Compact artifact schema 2 (private pilot refinement, 2026-09-30)

The maintainer approved compact internal join keys after the full schema1
fixture exceeded both maximum artifact caps. Protocol and identity versions
remain **1**, while `catalog_schema_version`, SQLite `user_version` and the
`catalog.schema_version` row are **2**. Readers accept exact schema1 or schema2
by the signed version; they never interpret a changed layout as schema1.
Older pilot readers reject schema2 and retain their last-good schema1 snapshot.
This private change does not touch released-mainline private state or worker
ledgers; the worker's artifact-shaped private tables retain schema1 DDL
inside their already-versioned private worker state2. There is no public
compatible-stream/default transition while M5 is closed.

Eight physical tables replace the layout's repeated relationship digests with
positive artifact-local integer keys; six fixed read views expose exactly the
original logical record fields. Keys are rebuilt during each export and have
no identity meaning. Public IDs, GUIDs, magnets, identity aliases, discovery
times and mapping provenance retain their v1 bytes/semantics. Public digest
columns remain lowercase hexadecimal text with unique indexes. Canonical episode
associations use their existing compound primary key in a `WITHOUT ROWID` table
to avoid a duplicate rowid tree. The current path is stored
only when it differs from the identity anchor; fixed `coalesce` views and unique
expression indexes preserve the original path value and uniqueness. The unique
episode `(entity_key,mapping_key)` index also serves entity lookup, removing a
duplicate index without relaxing its constraint.

Validate the exact physical tables, indexes **and views** before any read.
Independently check stored key types/positivity/nullability, foreign keys and
all original logical row/association constraints. Views must not conceal
orphaned/null relationships. No triggers, virtual tables, additional objects
or publisher-defined expressions are admitted. Receipt validator version3
requires older private receipts to undergo full validation before fast recovery.

Schema2 may prove each exact foreign-key relationship through ordered covering
child-index scans against its integer primary-key parent. The relationship
inventory must equal the validated DDL's `foreign_key_list`; hidden/missing
parents still reject. Schema1 retains `foreign_key_check`. Full integrity,
physical storage, logical rows/identities and association checks remain required.
Unescaped canonical ASCII anchors may avoid repeated URL normalization only
when a fixed safe alphabet and segment checks prove the identical path recipe;
all other paths use that recipe. These execution-order optimizations change
neither accepted records nor DDL/identity/schema/receipt versions. Admission's
120-second deadline and child/resource limits are unchanged.

Queries may force the physical recent-release index through an internal fixed
projection; putting `INDEXED BY` on a view is invalid. The minimum discovery
timestamp must use the physical indexed release table to avoid scanning a joined
view. Local corrections/observations continue to operate on public record shapes.

Caps/cardinalities are unchanged. The identical 50k/1m/2m fixture fits the
**default** 1-GiB/256-MiB byte caps after the measured refinements. Earlier
integer-only and release-WITHOUT-ROWID variants failed a default cap and were
not selected. Capacity, query/update costs and peak measurements remain gates,
not claims derived from the smaller layout. The measured comparison and
remaining failures are recorded in 10.

Exact schema2 DDL (also packaged as `catalog_core/schema-v2.sql`):

```sql
PRAGMA page_size=4096;
PRAGMA encoding='UTF-8';
PRAGMA journal_mode=DELETE;
PRAGMA foreign_keys=ON;
PRAGMA application_id=1094861633;
PRAGMA user_version=2;
CREATE TABLE catalog (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  provider TEXT NOT NULL CHECK(provider IN ('aniworld.to','s.to','megakino')),
  schema_version INTEGER NOT NULL CHECK(schema_version=2),
  identity_version INTEGER NOT NULL CHECK(identity_version=1),
  listing_checked_at INTEGER NOT NULL CHECK(listing_checked_at>=0)
) STRICT;
CREATE TABLE title_data (
  title_key INTEGER PRIMARY KEY CHECK(title_key>0),
  title_id TEXT NOT NULL UNIQUE,
  identity_anchor TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL,
  display_title TEXT NOT NULL,
  search_key TEXT NOT NULL COLLATE NOCASE,
  media_type TEXT NOT NULL CHECK(media_type IN ('series','movie','unknown')),
  year INTEGER CHECK(year BETWEEN 1800 AND 2200),
  path TEXT CHECK(path IS NULL OR path<>identity_anchor),
  observed_at INTEGER NOT NULL CHECK(observed_at>=0),
  detail_status TEXT NOT NULL CHECK(detail_status IN ('pending','partial','complete','stale'))
) STRICT;
CREATE UNIQUE INDEX title_path ON title_data(coalesce(path,identity_anchor));
CREATE INDEX title_search ON title_data(search_key,title_id);
CREATE INDEX title_slug ON title_data(slug,title_id);
CREATE TABLE alias_data (
  title_key INTEGER NOT NULL REFERENCES title_data(title_key),
  search_key TEXT NOT NULL COLLATE NOCASE,
  display_alias TEXT NOT NULL,
  PRIMARY KEY(title_key,search_key)
) STRICT;
CREATE INDEX alias_search ON alias_data(search_key,title_key);
CREATE TABLE entity_data (
  entity_key INTEGER PRIMARY KEY CHECK(entity_key>0),
  entity_id TEXT NOT NULL UNIQUE,
  title_key INTEGER NOT NULL REFERENCES title_data(title_key),
  identity_anchor TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('episode','movie')),
  native_season INTEGER,
  native_episode INTEGER,
  display_title TEXT,
  path TEXT CHECK(path IS NULL OR path<>identity_anchor),
  observed_at INTEGER NOT NULL CHECK(observed_at>=0),
  CHECK((kind='movie' AND native_season IS NULL AND native_episode IS NULL)
     OR (kind='episode' AND native_season>=0 AND native_episode>=1
         AND native_season IS NOT NULL AND native_episode IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX entity_path ON entity_data(coalesce(path,identity_anchor));
CREATE INDEX entity_title ON entity_data(title_key,native_season,native_episode,entity_key);
CREATE TABLE release_data (
  release_key INTEGER PRIMARY KEY CHECK(release_key>0),
  release_id TEXT NOT NULL UNIQUE,
  entity_key INTEGER NOT NULL REFERENCES entity_data(entity_key),
  language TEXT NOT NULL CHECK(language IN ('de-dub','en-dub','de-sub','en-sub')),
  first_seen_at INTEGER NOT NULL CHECK(first_seen_at>=0),
  observed_at INTEGER NOT NULL CHECK(observed_at>=first_seen_at),
  UNIQUE(entity_key,language)
) STRICT;
CREATE INDEX release_recent ON release_data(first_seen_at DESC,release_id ASC);
CREATE TABLE canonical_title_data (
  mapping_key INTEGER PRIMARY KEY CHECK(mapping_key>0),
  mapping_id TEXT NOT NULL UNIQUE,
  title_key INTEGER NOT NULL REFERENCES title_data(title_key),
  namespace TEXT NOT NULL CHECK(namespace IN ('tvdb','tmdb-tv','tmdb-movie','imdb')),
  external_id TEXT NOT NULL,
  source TEXT NOT NULL,
  evidence TEXT NOT NULL CHECK(evidence IN ('explicit_id','exact_title_year','reviewed')),
  checked_at INTEGER NOT NULL CHECK(checked_at>=0),
  UNIQUE(title_key,namespace)
) STRICT;
CREATE INDEX canonical_lookup ON canonical_title_data(namespace,external_id,title_key);
CREATE TABLE canonical_episode_data (
  mapping_key INTEGER NOT NULL REFERENCES canonical_title_data(mapping_key),
  entity_key INTEGER NOT NULL REFERENCES entity_data(entity_key),
  season INTEGER NOT NULL CHECK(season>=0),
  episode INTEGER NOT NULL CHECK(episode>=1),
  external_episode_id TEXT,
  evidence TEXT NOT NULL CHECK(evidence IN ('explicit_id','exact_title','reviewed')),
  checked_at INTEGER NOT NULL CHECK(checked_at>=0),
  PRIMARY KEY(mapping_key,season,episode)
) STRICT, WITHOUT ROWID;
CREATE UNIQUE INDEX canonical_episode_entity ON canonical_episode_data(entity_key,mapping_key);
CREATE TABLE identity_alias (
  kind TEXT NOT NULL CHECK(kind IN ('title','entity')),
  old_id TEXT NOT NULL,
  current_id TEXT NOT NULL,
  PRIMARY KEY(kind,old_id),
  CHECK(old_id<>current_id)
) STRICT;

CREATE VIEW title AS SELECT title_id,identity_anchor,slug,display_title,search_key,media_type,year,coalesce(path,identity_anchor) AS path,observed_at,detail_status FROM title_data;
CREATE VIEW alias AS SELECT t.title_id,a.search_key,a.display_alias FROM alias_data a JOIN title_data t USING(title_key);
CREATE VIEW entity AS SELECT e.entity_id,t.title_id,e.identity_anchor,e.kind,e.native_season,e.native_episode,e.display_title,coalesce(e.path,e.identity_anchor) AS path,e.observed_at FROM entity_data e JOIN title_data t USING(title_key);
CREATE VIEW release AS SELECT r.release_id,e.entity_id,r.language,r.first_seen_at,r.observed_at FROM release_data r JOIN entity_data e USING(entity_key);
CREATE VIEW canonical_title AS SELECT c.mapping_id,t.title_id,c.namespace,c.external_id,c.source,c.evidence,c.checked_at FROM canonical_title_data c JOIN title_data t USING(title_key);
CREATE VIEW canonical_episode AS SELECT m.mapping_id,e.entity_id,c.season,c.episode,c.external_episode_id,c.evidence,c.checked_at FROM canonical_episode_data c JOIN canonical_title_data m USING(mapping_key) JOIN entity_data e USING(entity_key);
```
