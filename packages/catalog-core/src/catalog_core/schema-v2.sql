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
