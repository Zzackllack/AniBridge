"""V6 durable publication generations, separate from the public read schema."""

import sqlite3
from contextlib import closing

from catalog_core import schema

VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=6))"
TABLES = """
CREATE TABLE publication_meta (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation INTEGER NOT NULL DEFAULT 0,
 content_generation INTEGER NOT NULL DEFAULT 0, published_generation INTEGER NOT NULL DEFAULT -1,
 published_content_generation INTEGER NOT NULL DEFAULT -1, receipt TEXT NOT NULL DEFAULT ''
);
INSERT INTO publication_meta(singleton) VALUES(1);
CREATE TABLE publication_change (title_id TEXT PRIMARY KEY, generation INTEGER NOT NULL);
"""

# Changes are journalled in the same transaction as observations, including raw
# SQL writes by review/repair commands. A title partition includes its children.
PARENTS = {
    "title": "{r}.title_id",
    "alias": "{r}.title_id",
    "entity": "{r}.title_id",
    "release": "(SELECT title_id FROM entity WHERE entity_id={r}.entity_id)",
    "canonical_title": "{r}.title_id",
    "canonical_episode": "(SELECT title_id FROM canonical_title WHERE mapping_id={r}.mapping_id)",
    "identity_alias": "'@identity_alias'",
    "catalog": "'@catalog'",
}


def journal(title: str, content: str, when: str = "1") -> str:
    """One bounded row per affected title; generation never resets on publish."""
    return f"""
    UPDATE publication_meta SET generation=generation+1,
      content_generation=content_generation+({content}) WHERE {when};
    INSERT INTO publication_change SELECT coalesce({title},'@full'),
      (SELECT generation FROM publication_meta) WHERE {when}
    ON CONFLICT(title_id) DO UPDATE SET generation=excluded.generation;
    """


def definitions() -> str:
    """Generate fixed triggers from the frozen ledger contract, not live data."""
    statements = [TABLES]
    with closing(sqlite3.connect(":memory:")) as db:
        db.executescript(schema.DDL)
        for table, parent in PARENTS.items():
            columns = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
            changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in columns)
            meaningful = (
                " OR ".join(
                    f"NEW.{c} IS NOT OLD.{c}"
                    for c in columns
                    if c not in {"observed_at", "checked_at", "listing_checked_at"}
                )
                or "0"
            )
            for action, row in (
                ("INSERT", "NEW"),
                ("DELETE", "OLD"),
                ("UPDATE", "NEW"),
            ):
                content = (
                    "0"
                    if table == "catalog"
                    else f"({meaningful})"
                    if action == "UPDATE"
                    else "1"
                )
                body = journal(parent.format(r=row), content)
                if action == "UPDATE":
                    # Reparenting must refresh the old partition too.
                    body += journal(
                        parent.format(r="OLD"),
                        "0",
                        f"({parent.format(r='OLD')}) IS NOT ({parent.format(r='NEW')})",
                    )
                statements.append(
                    f"CREATE TRIGGER pub_{table}_{action.lower()} AFTER {action} ON {table} "
                    + (f"WHEN {changed} " if action == "UPDATE" else "")
                    + f"BEGIN {body} END;"
                )
    parent = """CASE {r}.kind WHEN 'title' THEN {r}.id WHEN 'entity' THEN
      (SELECT title_id FROM entity WHERE entity_id={r}.id) WHEN 'release' THEN
      (SELECT e.title_id FROM release x JOIN entity e USING(entity_id) WHERE x.release_id={r}.id) END"""
    for action, row in (("INSERT", "NEW"), ("DELETE", "OLD"), ("UPDATE", "NEW")):
        condition = (
            "NEW.tombstoned IS NOT OLD.tombstoned OR ((NEW.tombstoned<>0 OR OLD.tombstoned<>0) AND (NEW.kind IS NOT OLD.kind OR NEW.id IS NOT OLD.id))"
            if action == "UPDATE"
            else f"{row}.tombstoned<>0"
        )
        body = journal(parent.format(r=row), "1")
        if action == "UPDATE":
            body += journal(
                parent.format(r="OLD"),
                "0",
                f"({parent.format(r='OLD')}) IS NOT ({parent.format(r='NEW')})",
            )
        statements.append(
            f"CREATE TRIGGER pub_omissions_{action.lower()} AFTER {action} ON omissions "
            f"WHEN {condition} BEGIN {body} END;"
        )
    return "\n".join(statements)


DDL = definitions()
