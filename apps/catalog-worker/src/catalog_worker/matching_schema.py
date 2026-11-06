"""Additive v5 evidence/attempt clocks, kept out of public catalogs."""

DDL = """
CREATE TABLE matching_replay (
 title_id TEXT PRIMARY KEY REFERENCES title(title_id), source_hash TEXT NOT NULL,
 descriptor_hash TEXT NOT NULL, matcher TEXT NOT NULL, examined_at INTEGER NOT NULL,
 counts TEXT NOT NULL
);
CREATE TABLE canonical_descriptor (
 external_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, payload TEXT NOT NULL,
 acquired_at INTEGER NOT NULL, next_due INTEGER NOT NULL
);
CREATE TABLE canonical_request_start(at INTEGER NOT NULL);
CREATE INDEX canonical_request_time ON canonical_request_start(at);
CREATE TABLE canonical_scheduler (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), slot INTEGER NOT NULL DEFAULT 0
);
INSERT INTO canonical_scheduler(singleton) VALUES(1);
CREATE TABLE canonical_hint_identity (
 title_id TEXT NOT NULL REFERENCES canonical_cache(title_id) ON DELETE CASCADE,
 season INTEGER NOT NULL, episode INTEGER NOT NULL, external_id TEXT NOT NULL,
 PRIMARY KEY(title_id,season,episode)
);
"""
VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=5))"
