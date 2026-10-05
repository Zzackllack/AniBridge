"""Fresh allowlisted exports and hostile SQLite validation.

Call validation inside the bounded child process, never in a request handler.
Schema inspection precedes every query against publisher-controlled rows.
"""

import re
import sqlite3
import time
from contextlib import closing
from importlib.resources import files
from pathlib import Path

from . import identity, row_validation
from .json_codec import require
from .manifest import TABLE_LIMITS, hex_digest

DDL = files("catalog_core").joinpath("schema.sql").read_text()
# Private admission receipts change when a validator bug is fixed. This is not
# a wire schema/identity version and does not change published artifact bytes.
VALIDATION_VERSION = 3
DDL_V2 = files("catalog_core").joinpath("schema-v2.sql").read_text()
SCHEMAS = {1: DDL, 2: DDL_V2}


def create(path: Path, version: int = 1) -> sqlite3.Connection:
    require(not path.exists(), "export must be a fresh database")
    db = sqlite3.connect(path)
    require(version in SCHEMAS, "unsupported artifact schema")
    db.executescript(SCHEMAS[version])
    return db


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA trusted_schema=OFF")
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA cache_size=-8192")
    db.execute("PRAGMA mmap_size=0")
    db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 8192)
    return db


def _definitions(db: sqlite3.Connection) -> list[tuple]:
    return [
        (kind, name, table, " ".join(sql.rstrip(";").split()) if sql else None)
        for kind, name, table, sql in db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
        )
    ]


def _validate_definitions(
    db: sqlite3.Connection,
    version: int = 1,
) -> dict[str, list[tuple[str, str, bool]]]:
    with closing(sqlite3.connect(":memory:")) as expected:
        expected.executescript(SCHEMAS[version])
        require(_definitions(db) == _definitions(expected), "unexpected SQLite schema")
    with closing(sqlite3.connect(":memory:")) as records:
        records.executescript(DDL)
        columns = {
            table: [
                (name, declared_type, bool(nonnull))
                for _, name, declared_type, nonnull, _, _ in records.execute(
                    f"PRAGMA table_info({table})"
                )
            ]
            for table in ("catalog", *TABLE_LIMITS)
        }
    for pragma, value in (
        ("application_id", 1094861633),
        ("user_version", version),
        ("page_size", 4096),
        ("encoding", "UTF-8"),
        ("journal_mode", "delete"),
    ):
        require(
            db.execute(f"PRAGMA {pragma}").fetchone()[0] == value,
            "invalid SQLite header",
        )
    return columns


CONTROL = re.compile(r"[\x00-\x1f\x7f]")
SAFE_PATH = re.compile(r"/[A-Za-z0-9/_~.-]*")


def _canonical_path(value: str) -> bool:
    # Unescaped ASCII in quote's safe alphabet is already NFC and cannot hide
    # a decoded delimiter. All other input still uses the full path recipe.
    # This avoids URL parsing/quoting a million ordinary episode anchors.
    if (
        SAFE_PATH.fullmatch(value)
        and "//" not in value
        and "/./" not in value
        and "/../" not in value
        and not value.endswith(("/.", "/.."))
        and (value == "/" or not value.endswith("/"))
    ):
        return True
    return identity.path(value) == value


def _strings(row: sqlite3.Row) -> None:
    checked_paths = set()
    for column in row.keys():  # noqa: SIM118 -- sqlite3.Row iterates values
        value = row[column]
        if not isinstance(value, str):
            continue
        if column.endswith("_id") and column not in {
            "external_id",
            "external_episode_id",
        }:
            hex_digest(value)
            # A canonical 64-byte ASCII digest already satisfies length and
            # control-character checks. Rewalking its characters dominates
            # validation at millions of relationships.
            continue
        limit = (
            1024
            if column in {"path", "identity_anchor"}
            else 256
            if column == "slug"
            else 128
            if column in {"external_id", "external_episode_id"}
            else 512
        )
        require(len(value.encode("utf-8")) <= limit, "string too large")
        require(CONTROL.search(value) is None, "string control")
        if column in {"path", "identity_anchor"} and value not in checked_paths:
            require(_canonical_path(value), "noncanonical path")
            checked_paths.add(value)


def validate(path: Path, payload: dict, deadline_s: float = 120) -> dict[str, int]:
    started = time.monotonic()
    with path.open("rb") as stream:
        header = stream.read(100)
    # Immutable SQLite readers report journal_mode=delete even when the file's
    # read/write header versions require WAL. Inspect the actual signed bytes.
    require(
        len(header) == 100
        and header[:16] == b"SQLite format 3\x00"
        and header[18:20] == b"\x01\x01",
        "invalid SQLite header",
    )
    db = connect(path)
    # Full index integrity checks revisit distant pages. The 8-MiB search pager
    # thrashed under a cold 1-GiB consumer plus eight readers (120s rejection).
    # A measured 32-MiB validator pager stays inside the existing 256-MiB child
    # limit; ordinary search connections retain their 8-MiB cache.
    db.execute("PRAGMA cache_size=-32768")
    db.set_progress_handler(lambda: int(time.monotonic() - started > deadline_s), 1000)
    try:
        version = payload["catalog_schema_version"]
        require(version in SCHEMAS, "unsupported artifact schema")
        columns = _validate_definitions(db, version)
        if version == 2:
            from .compact import validate_physical

            validate_physical(db)
        require(
            db.execute("PRAGMA integrity_check").fetchall()[0][0] == "ok",
            "corrupt SQLite",
        )
        if version == 2:
            from .compact import validate_foreign_keys

            validate_foreign_keys(db)
        else:
            require(
                db.execute("PRAGMA foreign_key_check").fetchone() is None,
                "invalid foreign keys",
            )
        catalog = db.execute("SELECT * FROM catalog").fetchall()
        require(len(catalog) == 1, "catalog singleton missing")
        row_validation.validate(
            "catalog", catalog[0], columns["catalog"], payload["published_at"]
        )
        provider = payload["provider"]
        require(
            type(provider) is str and provider in identity.PROVIDERS, "unknown provider"
        )
        require(
            tuple(catalog[0])
            == (1, provider, version, 1, payload["listing_checked_at"]),
            "catalog metadata mismatch",
        )
        counts = {}
        for table, maximum in TABLE_LIMITS.items():
            counts[table] = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            require(
                counts[table] <= maximum and counts[table] == payload["counts"][table],
                "count mismatch/overflow",
            )
            for row in db.execute(f"SELECT * FROM {table}"):
                require(time.monotonic() - started <= deadline_s, "validation deadline")
                row_validation.validate(
                    table, row, columns[table], payload["published_at"]
                )
                _strings(row)
                # _strings already proves canonical anchors. Reuse that proof
                # for the fixed v1 digest recipe instead of reparsing every
                # entity path a second time. No unvalidated path reaches it.
                if table == "title":
                    require(
                        row["title_id"]
                        == identity.digest(
                            "ab-title-1", provider, row["identity_anchor"]
                        ),
                        "title identity mismatch",
                    )
                    require(
                        row["search_key"] == identity.search_key(row["display_title"]),
                        "title normalization mismatch",
                    )
                elif table == "alias":
                    require(
                        row["search_key"] == identity.search_key(row["display_alias"]),
                        "alias normalization mismatch",
                    )
                elif table == "entity":
                    require(
                        row["entity_id"]
                        == identity.digest(
                            "ab-entity-1", provider, row["identity_anchor"]
                        ),
                        "entity identity mismatch",
                    )
                elif table == "release":
                    require(
                        row["release_id"]
                        == identity.release_id(
                            provider, row["entity_id"], row["language"]
                        ),
                        "release identity mismatch",
                    )
                elif table == "canonical_title":
                    require(
                        row["mapping_id"]
                        == identity.mapping_id(
                            provider,
                            row["title_id"],
                            row["namespace"],
                            row["external_id"],
                        ),
                        "mapping identity mismatch",
                    )
                    require(
                        re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", row["source"])
                        is not None,
                        "invalid provenance",
                    )
        # These joins use indexes and avoid retaining the catalog in Python.
        invalid_queries = [
            "SELECT 1 FROM entity e JOIN title t USING(title_id) WHERE (t.media_type='movie' AND e.kind<>'movie') OR (t.media_type='series' AND e.kind<>'episode') LIMIT 1",
            "SELECT 1 FROM entity WHERE kind='movie' GROUP BY title_id HAVING count(*)>1 LIMIT 1",
            "SELECT 1 FROM canonical_title c JOIN title t USING(title_id) WHERE (c.namespace='tmdb-movie' AND t.media_type<>'movie') OR (c.namespace IN ('tvdb','tmdb-tv') AND t.media_type<>'series') LIMIT 1",
            "SELECT 1 FROM canonical_episode c JOIN canonical_title m USING(mapping_id) JOIN entity e USING(entity_id) WHERE m.title_id<>e.title_id OR e.kind<>'episode' OR m.namespace='imdb' LIMIT 1",
            "SELECT 1 FROM identity_alias a LEFT JOIN title t ON a.current_id=t.title_id WHERE a.kind='title' AND t.title_id IS NULL LIMIT 1",
            "SELECT 1 FROM identity_alias a LEFT JOIN entity e ON a.current_id=e.entity_id WHERE a.kind='entity' AND e.entity_id IS NULL LIMIT 1",
            "SELECT 1 FROM identity_alias a JOIN identity_alias b ON a.kind=b.kind AND a.current_id=b.old_id LIMIT 1",
            "SELECT 1 FROM identity_alias a JOIN title t ON a.old_id=t.title_id WHERE a.kind='title' LIMIT 1",
            "SELECT 1 FROM identity_alias a JOIN entity e ON a.old_id=e.entity_id WHERE a.kind='entity' LIMIT 1",
        ]
        for query in invalid_queries:
            require(
                db.execute(query).fetchone() is None, "invalid semantic association"
            )
        if payload["coverage"]["details"] == "complete":
            require(
                db.execute(
                    "SELECT 1 FROM title WHERE detail_status<>'complete' LIMIT 1"
                ).fetchone()
                is None,
                "false detail coverage",
            )
        if payload["coverage"]["mappings"] == "complete":
            require(
                db.execute(
                    "SELECT 1 FROM entity e WHERE (e.kind='episode' AND NOT EXISTS (SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)) OR (e.kind='movie' AND NOT EXISTS (SELECT 1 FROM canonical_title c WHERE c.title_id=e.title_id AND c.namespace IN ('tmdb-movie','imdb'))) LIMIT 1"
                ).fetchone()
                is None,
                "false mapping coverage",
            )
        return counts
    finally:
        db.close()
