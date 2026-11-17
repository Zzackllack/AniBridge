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
