"""Refresh changed title partitions in a private clone; keep compact keys stable."""

import sqlite3

from .export import QUERIES

KEYS = {
    "title_data": "title_id",
    "entity_data": "entity_id",
    "release_data": "release_id",
    "canonical_title_data": "mapping_id",
}
SCOPES = {
    "title_data": "t.title_id IN (SELECT title_id FROM changed_title)",
    "alias_data": "t.title_id IN (SELECT id FROM keep_title_data)",
    "entity_data": "e.title_id IN (SELECT id FROM keep_title_data)",
    "release_data": "e.entity_id IN (SELECT id FROM keep_entity_data)",
    "canonical_title_data": "c.title_id IN (SELECT id FROM keep_title_data)",
    "canonical_episode_data": "m.mapping_id IN (SELECT id FROM keep_canonical_title_data) AND e.entity_id IN (SELECT id FROM keep_entity_data)",
}


def query(table: str, approved: frozenset[str]) -> tuple[str, tuple[str, ...]]:
    """Add only fixed predicates to the reviewed full-export projections."""
    sql = QUERIES[table]
    values = tuple(sorted(approved)) if table == "canonical_title_data" else ()
    if table == "canonical_title_data":
        sql = sql.format(approved=",".join("?" for _ in values) or "NULL")
    if table in SCOPES:
        head, order = sql.rsplit(" ORDER BY ", 1)
        sql = (
            head
            + (" AND " if " WHERE " in head else " WHERE ")
            + SCOPES[table]
            + " ORDER BY "
            + order
        )
    return sql, values


def upsert(db: sqlite3.Connection, table: str, approved: frozenset[str]) -> None:
    """SQL handles bulk comparison; unchanged rows never trigger validation work."""
    columns = [r[1] for r in db.execute(f"PRAGMA main.table_info({table})")]
    db.execute(f"CREATE TEMP TABLE selected AS SELECT * FROM main.{table} WHERE 0")
    sql, values = query(table, approved)
    db.execute(f"INSERT INTO selected {sql}", values)
    key = KEYS[table]
    updated = [c for c in columns if c not in {columns[0], key}]
    db.execute(
        f"INSERT INTO main.{table} SELECT * FROM selected WHERE 1 ON CONFLICT({key}) DO UPDATE SET "
        + ",".join(f"{c}=excluded.{c}" for c in updated)
        + " WHERE "
        + " OR ".join(f"{table}.{c} IS NOT excluded.{c}" for c in updated)
    )
    db.execute(f"CREATE TEMP TABLE keep_{table}(id TEXT PRIMARY KEY)")
    db.execute(f"INSERT INTO keep_{table} SELECT {key} FROM selected")
    db.execute("DROP TABLE selected")


def refresh(db: sqlite3.Connection, approved: frozenset[str]) -> None:
    """All deletions apply only to the changed partitions and source tombstones."""
    upsert(db, "title_data", approved)
    db.execute(
        "CREATE TEMP TABLE affected_title AS SELECT title_key FROM main.title_data WHERE title_id IN (SELECT title_id FROM changed_title)"
    )
    db.execute("DELETE FROM main.alias_data WHERE title_key IN affected_title")
    sql, values = query("alias_data", approved)
    db.execute(f"INSERT INTO main.alias_data {sql}", values)
    for table in ("entity_data", "release_data", "canonical_title_data"):
        upsert(db, table, approved)
    db.execute(
        "DELETE FROM main.canonical_episode_data WHERE mapping_key IN (SELECT mapping_key FROM main.canonical_title_data WHERE title_key IN affected_title)"
    )
    db.execute(
        "DELETE FROM main.canonical_title_data WHERE title_key IN affected_title AND mapping_id NOT IN (SELECT id FROM keep_canonical_title_data)"
    )
    sql, values = query("canonical_episode_data", approved)
    db.execute(f"INSERT INTO main.canonical_episode_data {sql}", values)
    db.execute(
        "DELETE FROM main.release_data WHERE entity_key IN (SELECT entity_key FROM main.entity_data WHERE title_key IN affected_title) AND release_id NOT IN (SELECT id FROM keep_release_data)"
    )
    db.execute(
        "DELETE FROM main.entity_data WHERE title_key IN affected_title AND entity_id NOT IN (SELECT id FROM keep_entity_data)"
    )
    db.execute(
        "DELETE FROM main.title_data WHERE title_key IN affected_title AND title_id NOT IN (SELECT id FROM keep_title_data)"
    )
    db.execute("DELETE FROM main.identity_alias")
    sql, values = query("identity_alias", approved)
    db.execute(f"INSERT INTO main.identity_alias {sql}", values)
