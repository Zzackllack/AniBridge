"""Row-validation reuse only for a digest-verified, previously admitted clone.

The public validator defaults to full admission. The publisher owns the staging
connection; temporary triggers capture every modified title partition, including
unexpected writes on that connection. Other-connection writes invalidate reuse.
Global schema, integrity, foreign-key and semantic checks are never scoped out.
"""

import sqlite3
from dataclasses import dataclass

from .json_codec import require

PARENTS = {
    "title_data": "{r}.title_key",
    "alias_data": "{r}.title_key",
    "entity_data": "{r}.title_key",
    "release_data": "(SELECT title_key FROM entity_data WHERE entity_key={r}.entity_key)",
    "canonical_title_data": "{r}.title_key",
    "canonical_episode_data": "(SELECT title_key FROM canonical_title_data WHERE mapping_key={r}.mapping_key)",
}


@dataclass(frozen=True)
class Scope:
    title_keys: tuple[int, ...]

    def query(self, table: str) -> str:
        """Only fixed schema2 views and validated integer keys enter this SQL."""
        require(
            all(type(k) is int and k > 0 for k in self.title_keys),
            "invalid validation scope",
        )
        keys = ",".join(str(k) for k in self.title_keys) or "NULL"
        predicates = {
            "title": f"title_id IN (SELECT title_id FROM title_data WHERE title_key IN ({keys}))",
            "alias": f"title_id IN (SELECT title_id FROM title_data WHERE title_key IN ({keys}))",
            "entity": f"entity_id IN (SELECT entity_id FROM entity_data WHERE title_key IN ({keys}))",
            "release": f"entity_id IN (SELECT entity_id FROM entity_data WHERE title_key IN ({keys}))",
            "canonical_title": f"mapping_id IN (SELECT mapping_id FROM canonical_title_data WHERE title_key IN ({keys}))",
            "canonical_episode": f"mapping_id IN (SELECT mapping_id FROM canonical_title_data WHERE title_key IN ({keys}))",
            "identity_alias": "1",
        }
        require(table in predicates, "unknown scoped table")
        return f"SELECT * FROM {table} WHERE {predicates[table]}"


def capture(db: sqlite3.Connection) -> None:
    """Start tracking before any mutation to a verified staging clone."""
    db.execute("CREATE TEMP TABLE validation_titles(title_key INTEGER PRIMARY KEY)")
    for table, parent in PARENTS.items():
        for action, row in (("INSERT", "NEW"), ("DELETE", "OLD"), ("UPDATE", "NEW")):
            expressions = [parent.format(r=row)]
            if action == "UPDATE":
                expressions.append(parent.format(r="OLD"))
            body = " ".join(
                f"INSERT INTO validation_titles SELECT coalesce({key},-1) WHERE NOT EXISTS (SELECT 1 FROM validation_titles WHERE title_key=coalesce({key},-1));"
                for key in expressions
            )
            db.execute(
                f"CREATE TEMP TRIGGER validation_{table}_{action.lower()} AFTER {action} ON main.{table} BEGIN {body} END"
            )


def captured(db: sqlite3.Connection) -> Scope:
    return Scope(
        tuple(
            r[0]
            for r in db.execute(
                "SELECT title_key FROM validation_titles ORDER BY title_key"
            )
        )
    )
