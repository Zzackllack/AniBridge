"""Private schema introduced by 0004; keep this migration contract immutable."""

from .management_schema import STATEMENTS as MANAGEMENT_STATEMENTS
from .override_indexes import STATEMENTS as OVERRIDE_INDEXES

V4_STATEMENTS = (
    "CREATE TABLE catalog_source(source_id TEXT PRIMARY KEY,root TEXT NOT NULL,keys_json TEXT NOT NULL)",
    """CREATE TABLE catalog_clock(singleton INTEGER PRIMARY KEY CHECK(singleton=1),wall INTEGER NOT NULL)""",
    "INSERT INTO catalog_clock VALUES(1,0)",
    """CREATE TABLE catalog_trust(source_id TEXT NOT NULL,provider TEXT NOT NULL,
        accepted_revision INTEGER NOT NULL,payload_digest TEXT NOT NULL,published_at INTEGER NOT NULL,
        hold_revision INTEGER,PRIMARY KEY(source_id,provider))""",
    """CREATE TABLE catalog_version(source_id TEXT NOT NULL,provider TEXT NOT NULL,revision INTEGER NOT NULL,
        manifest BLOB NOT NULL,filename TEXT NOT NULL,sqlite_sha256 TEXT NOT NULL,
        PRIMARY KEY(source_id,provider,revision))""",
    """CREATE TABLE catalog_active(provider TEXT PRIMARY KEY,source_id TEXT NOT NULL,revision INTEGER NOT NULL,
        previous_source TEXT,previous_revision INTEGER,generation INTEGER NOT NULL,activated_at INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'ready')""",
    """CREATE TABLE durable_request(job_id TEXT PRIMARY KEY REFERENCES job(id),payload TEXT NOT NULL,
        identity_key TEXT UNIQUE,version INTEGER NOT NULL DEFAULT 1,generation INTEGER NOT NULL DEFAULT 1,
        attempts INTEGER NOT NULL DEFAULT 0,lease_until INTEGER NOT NULL DEFAULT 0,
        next_retry_at INTEGER,last_attempt_at INTEGER,last_retry_at INTEGER,
        prior_state TEXT,error_code TEXT)""",
    """CREATE TABLE grab_alias(hash TEXT PRIMARY KEY REFERENCES clienttask(hash),job_id TEXT NOT NULL REFERENCES job(id))""",
    "CREATE INDEX grab_alias_job ON grab_alias(job_id)",
    """CREATE TABLE catalog_override(id TEXT PRIMARY KEY,provider TEXT NOT NULL,title_id TEXT NOT NULL,
        entity_id TEXT,namespace TEXT NOT NULL,body TEXT NOT NULL,version INTEGER NOT NULL,
        created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)""",
    """CREATE TABLE catalog_task(id TEXT PRIMARY KEY,type TEXT NOT NULL,state TEXT NOT NULL,
        body TEXT NOT NULL,version INTEGER NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)""",
    """CREATE TABLE management_idempotency(key TEXT PRIMARY KEY,body_digest TEXT NOT NULL,
        response TEXT NOT NULL,expires_at INTEGER NOT NULL)""",
    """CREATE TABLE catalog_cache(kind TEXT NOT NULL,key TEXT NOT NULL,body TEXT NOT NULL,
        expires_at INTEGER NOT NULL,used_at INTEGER NOT NULL,PRIMARY KEY(kind,key))""",
)

# Scratch databases use the full current schema; 0004 imports its frozen subset.

V5_STATEMENTS = V4_STATEMENTS + MANAGEMENT_STATEMENTS
V6_STATEMENTS = V5_STATEMENTS + OVERRIDE_INDEXES
VALIDATION_STATEMENTS = (
    "ALTER TABLE catalog_version ADD COLUMN validation_version INTEGER NOT NULL DEFAULT 0",
)
V7_STATEMENTS = V6_STATEMENTS + VALIDATION_STATEMENTS
RECEIPT_STATEMENTS = ("ALTER TABLE catalog_version ADD COLUMN validation_context TEXT",)
STATEMENTS = V7_STATEMENTS + RECEIPT_STATEMENTS
