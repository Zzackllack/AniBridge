"""Version-3 private scheduling data; never part of a published artifact."""

DDL = """
CREATE TABLE signal_meta (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), origin TEXT NOT NULL DEFAULT '',
 checked_at INTEGER NOT NULL DEFAULT 0, next_due INTEGER NOT NULL DEFAULT 0,
 lease_until INTEGER NOT NULL DEFAULT 0, coverage TEXT NOT NULL DEFAULT 'unknown',
 gap_since INTEGER, entries INTEGER NOT NULL DEFAULT 0, overlaps INTEGER NOT NULL DEFAULT 0,
 unknown_languages INTEGER NOT NULL DEFAULT 0, polls INTEGER NOT NULL DEFAULT 0
);
INSERT INTO signal_meta(singleton) VALUES(1);
CREATE TABLE signal_window (
 path TEXT NOT NULL, language TEXT NOT NULL, PRIMARY KEY(path,language)
);
CREATE TABLE signal_pending (
 path TEXT PRIMARY KEY REFERENCES work(path), due INTEGER NOT NULL,
 generation INTEGER NOT NULL DEFAULT 1, first_observed INTEGER NOT NULL,
 expected TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX signal_due ON signal_pending(due,path);
CREATE TABLE reconciliation_start(at INTEGER NOT NULL);
CREATE INDEX reconciliation_time ON reconciliation_start(at);
CREATE INDEX work_new ON work(due,path) WHERE checked_at IS NULL;
CREATE INDEX work_reconcile ON work(checked_at,path) WHERE checked_at IS NOT NULL;
CREATE INDEX work_title ON work(title_id,path);
CREATE INDEX mapping_due ON mapping_input(next_due,title_id);
CREATE TABLE canonical_cache (
 title_id TEXT PRIMARY KEY REFERENCES title(title_id), input_hash TEXT NOT NULL,
 matcher TEXT NOT NULL, checked_at INTEGER NOT NULL
);
CREATE TABLE canonical_hint (
 title_id TEXT NOT NULL REFERENCES canonical_cache(title_id) ON DELETE CASCADE,
 season INTEGER NOT NULL, title_key TEXT NOT NULL, episode INTEGER,
 PRIMARY KEY(title_id,season,title_key)
);
"""
VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=3))"
