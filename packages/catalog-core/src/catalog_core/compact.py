"""Artifact-local integer relationships; public records and identities stay v1.

No lookup cache grows with the catalog. Indexed parent lookups translate each
exported record, while the fixed read views expose the established record shape.
"""

import sqlite3
from contextlib import closing

from .json_codec import require

TABLES = ("title", "alias", "entity", "release", "canonical_title", "canonical_episode")
KEYS = {"title": "title", "entity": "entity", "canonical_title": "mapping"}


class Writer:
    def __init__(self, db: sqlite3.Connection, version: int = 2) -> None:
        self.db, self.version = db, version

    def key(self, table: str, public_id: str) -> int:
        stem = KEYS[table]
        row = self.db.execute(
            f"SELECT {stem}_key FROM {table}_data WHERE {stem}_id=?", (public_id,)
        ).fetchone()
        require(row is not None, "missing compact parent")
        return row[0]

    def insert(self, table: str, record: tuple) -> None:
        require(table in ("catalog", "identity_alias", *TABLES), "unknown record")
        values = tuple(record)
        physical = table
        if self.version == 2:
            if table == "catalog":
                values = (*values[:2], 2, *values[3:])
            elif table in TABLES:
                physical += "_data"
                if table == "title":
                    values = (
                        *values[:7],
                        None if values[7] == values[1] else values[7],
                        *values[8:],
                    )
                    values = (None, *values)
                elif table == "alias":
                    values = (self.key("title", values[0]), *values[1:])
                elif table in ("entity", "canonical_title"):
                    if table == "entity":
                        values = (
                            *values[:7],
                            None if values[7] == values[2] else values[7],
                            *values[8:],
                        )
                    values = (
                        None,
                        values[0],
                        self.key("title", values[1]),
                        *values[2:],
                    )
                elif table == "release":
                    values = (
                        None,
                        values[0],
                        self.key("entity", values[1]),
                        *values[2:],
                    )
                else:
                    values = (
                        self.key("canonical_title", values[0]),
                        self.key("entity", values[1]),
                        *values[2:],
                    )
        self.db.execute(
            f"INSERT INTO {physical} VALUES({','.join('?' for _ in values)})", values
        )


def validate_physical(db: sqlite3.Connection) -> None:
    """Check stored key types/nulls even when a hostile writer disabled checks."""
    from .schema import DDL_V2

    with closing(sqlite3.connect(":memory:")) as expected:
        expected.executescript(DDL_V2)
        for table in TABLES:
            physical = table + "_data"
            invalid = []
            for _, name, kind, nonnull, _, _ in expected.execute(
                f"PRAGMA table_info({physical})"
            ):
                storage = "integer" if kind == "INTEGER" else "text"
                invalid.append(f"({name} IS NOT NULL AND typeof({name})<>'{storage}')")
                if nonnull:
                    invalid.append(f"{name} IS NULL")
                if name in {"title_key", "entity_key", "release_key", "mapping_key"}:
                    invalid.append(f"({name} IS NULL OR {name}<=0)")
            if table in ("title", "entity"):
                invalid.append("path=identity_anchor")
            require(
                db.execute(
                    f"SELECT 1 FROM {physical} WHERE "
                    + " OR ".join(invalid)
                    + " LIMIT 1"
                ).fetchone()
                is None,
                "invalid compact storage",
            )


# Each fixed schema2 relationship has a covering child index. Walking it in
# parent-key order avoids millions of random parent-page reads in the small
# admission pager. Exact DDL and full integrity_check are proved first.
FOREIGN_KEYS = (
    ("alias_data", "title_data", "title_key", "sqlite_autoindex_alias_data_1"),
    ("entity_data", "title_data", "title_key", "entity_title"),
    ("release_data", "entity_data", "entity_key", "sqlite_autoindex_release_data_2"),
    (
        "canonical_title_data",
        "title_data",
        "title_key",
        "sqlite_autoindex_canonical_title_data_2",
    ),
    (
        "canonical_episode_data",
        "canonical_title_data",
        "mapping_key",
        "sqlite_autoindex_canonical_episode_data_1",
    ),
    ("canonical_episode_data", "entity_data", "entity_key", "canonical_episode_entity"),
)


def validate_foreign_keys(db: sqlite3.Connection) -> None:
    for child, parent, key, index in FOREIGN_KEYS:
        require(
            db.execute(
                f"SELECT 1 FROM {child} c INDEXED BY {index} WHERE NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{key}=c.{key}) LIMIT 1"
            ).fetchone()
            is None,
            "invalid foreign keys",
        )


def release_from(version: int, *, ordered: bool = False) -> str:
    """Supply the physical ordering hint without putting INDEXED BY on a view."""
    if version == 1:
        return "FROM release r" + (" INDEXED BY release_recent" if ordered else "")
    if not ordered:
        return "FROM release r"
    return """FROM (SELECT p.release_id,k.entity_id,p.language,p.first_seen_at,p.observed_at
      FROM release_data p INDEXED BY release_recent
      JOIN entity_data k USING(entity_key)) r"""


def oldest_release(db: sqlite3.Connection, version: int) -> int | None:
    table = "release" if version == 1 else "release_data"
    return db.execute(f"SELECT min(first_seen_at) FROM {table}").fetchone()[0]


def release_summary(db: sqlite3.Connection) -> list[dict]:
    return [
        dict(zip(("kind", "language", "count", "oldest"), row, strict=True))
        for row in db.execute(
            "SELECT e.kind,r.language,count(*),min(r.first_seen_at) "
            "FROM release_data r JOIN entity_data e USING(entity_key) GROUP BY e.kind,r.language"
        )
    ]


def query_joins(sql: str) -> str:
    """Avoid materializing all canonical views on the right of a LEFT JOIN.

    These replacements apply only to our fixed query templates. Public-ID
    scalar lookups remain indexed; published views stay the record interface.
    """
    sql = sql.replace(
        "LEFT JOIN canonical_title ct ON ct.mapping_id=",
        "LEFT JOIN canonical_title_data ct ON ct.mapping_id=",
    )
    old = "LEFT JOIN canonical_episode ce ON ce.mapping_id=ct.mapping_id AND ce.entity_id=e.entity_id"
    if old in sql:
        sql = sql.replace(
            old,
            "LEFT JOIN canonical_episode_data ce "
            "ON ce.mapping_key=ct.mapping_key AND ce.entity_key="
            "(SELECT entity_key FROM entity_data WHERE entity_id=e.entity_id)",
        ).replace("ce.entity_id", "ce.entity_key")
    return sql


def physical_joins(sql: str) -> str:
    """Use compact keys once, rather than rejoining public views by text IDs.

    Recent TV totals scanned both entity views and their titles for each release.
    The redundant public-ID lookup exceeds the two-second budget at pilot scale.
    This applies to our fixed templates only, never arbitrary caller SQL.
    """
    sql = sql.replace("FROM release r", "FROM release_data r")
    sql = sql.replace(
        "JOIN entity e USING(entity_id)", "JOIN entity_data e USING(entity_key)"
    )
    sql = sql.replace(
        "JOIN title t USING(title_id)", "JOIN title_data t USING(title_key)"
    )
    sql = sql.replace(
        "LEFT JOIN canonical_title ct ON ct.mapping_id=",
        "LEFT JOIN canonical_title_data ct ON ct.mapping_id=",
    )
    sql = sql.replace("FROM canonical_title c", "FROM canonical_title_data c")
    sql = sql.replace("c.title_id=t.title_id", "c.title_key=t.title_key")
    sql = sql.replace(
        "LEFT JOIN canonical_episode ce ON ce.mapping_id=ct.mapping_id AND ce.entity_id=e.entity_id",
        "LEFT JOIN canonical_episode_data ce ON ce.mapping_key=ct.mapping_key AND ce.entity_key=e.entity_key",
    )
    return sql
