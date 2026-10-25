"""Version-4 private evidence and bounded lifetime performance counters."""

DDL = """
CREATE TABLE entity_alias (
 entity_id TEXT NOT NULL REFERENCES entity(entity_id), title_key TEXT NOT NULL,
 display_title TEXT NOT NULL, PRIMARY KEY(entity_id,title_key)
);
CREATE TABLE batch_observation (
 path TEXT PRIMARY KEY REFERENCES work(path), fingerprint TEXT NOT NULL
);
CREATE TABLE season_batch_checkpoint (
 path TEXT PRIMARY KEY REFERENCES work(path), checked_at INTEGER NOT NULL
);
CREATE TABLE collection_stats (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), started_at INTEGER NOT NULL DEFAULT 0,
 requests INTEGER NOT NULL DEFAULT 0, pages INTEGER NOT NULL DEFAULT 0,
 batch_rows INTEGER NOT NULL DEFAULT 0, network_ms INTEGER NOT NULL DEFAULT 0,
 parser_ms INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
 admission_deferrals INTEGER NOT NULL DEFAULT 0
);
INSERT INTO collection_stats(singleton) VALUES(1);
"""
VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=4))"
