"""Frozen version-1 private worker DDL, separate from public artifact schema."""

PRIVATE_DDL = """
CREATE TABLE IF NOT EXISTS worker_meta (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision INTEGER NOT NULL DEFAULT 0,
 wall INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'bootstrap',
 next_listing INTEGER NOT NULL DEFAULT 0, blocked_until INTEGER NOT NULL DEFAULT 0,
 block_count INTEGER NOT NULL DEFAULT 0, dirty INTEGER NOT NULL DEFAULT 0,
 published_at INTEGER NOT NULL DEFAULT 0, listing_checked_at INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO worker_meta(singleton) VALUES(1);
CREATE TABLE IF NOT EXISTS work (
 path TEXT PRIMARY KEY, title_id TEXT NOT NULL REFERENCES title(title_id),
 kind TEXT NOT NULL, due INTEGER NOT NULL, lease_until INTEGER NOT NULL DEFAULT 0,
 failures INTEGER NOT NULL DEFAULT 0, checked_at INTEGER, fingerprint TEXT
);
CREATE INDEX IF NOT EXISTS work_due ON work(due,lease_until,path);
CREATE TABLE IF NOT EXISTS omissions (
 kind TEXT NOT NULL, id TEXT NOT NULL, first_missing INTEGER NOT NULL,
 count INTEGER NOT NULL, confirmed_404 INTEGER NOT NULL DEFAULT 0,
 tombstoned INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(kind,id)
);
CREATE TABLE IF NOT EXISTS quarantine (
 digest TEXT PRIMARY KEY, kind TEXT NOT NULL, old_count INTEGER NOT NULL,
 new_count INTEGER NOT NULL, created_at INTEGER NOT NULL, approved INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS publication (
 revision INTEGER PRIMARY KEY, published_at INTEGER NOT NULL,
 artifact TEXT, manifest TEXT, committed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS request_start(at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS request_time ON request_start(at);
CREATE TABLE IF NOT EXISTS transport_failure(at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS title_schedule (
 title_id TEXT PRIMARY KEY REFERENCES title(title_id), first_observed INTEGER NOT NULL,
 changed_at INTEGER NOT NULL, listed_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS observation_gap (
 path TEXT PRIMARY KEY REFERENCES work(path), unknown_languages INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS scheduler (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), slot INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO scheduler(singleton) VALUES(1);
CREATE TABLE IF NOT EXISTS season_correspondence (
 title_id TEXT NOT NULL REFERENCES title(title_id), namespace TEXT NOT NULL,
 external_id TEXT NOT NULL, native_season INTEGER NOT NULL, canonical_season INTEGER NOT NULL,
 evidence TEXT NOT NULL CHECK(evidence IN ('explicit_id','reviewed')),
 PRIMARY KEY(title_id,namespace,external_id,native_season)
);
CREATE TABLE IF NOT EXISTS mapping_input (
 title_id TEXT PRIMARY KEY REFERENCES title(title_id), explicit_imdb TEXT,
 input_hash TEXT, matcher TEXT, checked_at INTEGER, next_due INTEGER NOT NULL DEFAULT 0,
 outcome TEXT NOT NULL DEFAULT 'pending', failures INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS worker_schema(version INTEGER PRIMARY KEY CHECK(version=1));
INSERT OR IGNORE INTO worker_schema VALUES(1);
"""
