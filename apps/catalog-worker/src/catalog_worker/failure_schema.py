"""Private v7: one current, sanitized failure receipt per durable page."""

DDL = """
CREATE TABLE work_failure (
 path TEXT PRIMARY KEY REFERENCES work(path),
 observed_since INTEGER NOT NULL,
 first_failed_at INTEGER,
 last_failed_at INTEGER NOT NULL,
 outcome TEXT NOT NULL,
 http_status INTEGER,
 parser_reason TEXT
);
"""
VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=7))"
