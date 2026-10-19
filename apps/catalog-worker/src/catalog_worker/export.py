"""Fixed allowlisted SQL export into schema2 without per-row Python joins.

Only the fresh destination is writable. SQLite's indexed integer joins stay
bounded by its pager cache; identities and rights filters are unchanged.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from catalog_core.diagnostics import phase

QUERIES = {
    "title_data": """SELECT NULL,t.title_id,t.identity_anchor,t.slug,t.display_title,t.search_key,
        t.media_type,t.year,nullif(t.path,t.identity_anchor),t.observed_at,t.detail_status
        FROM ledger.title t WHERE t.title_id NOT IN
        (SELECT id FROM ledger.omissions WHERE kind='title' AND tombstoned=1) ORDER BY t.title_id""",
    "alias_data": """SELECT t.title_key,a.search_key,a.display_alias
        FROM ledger.alias a JOIN main.title_data t USING(title_id) ORDER BY a.title_id,a.search_key""",
    "entity_data": """SELECT NULL,e.entity_id,t.title_key,e.identity_anchor,e.kind,e.native_season,
        e.native_episode,e.display_title,nullif(e.path,e.identity_anchor),e.observed_at
        FROM ledger.entity e JOIN main.title_data t USING(title_id) WHERE e.entity_id NOT IN
        (SELECT id FROM ledger.omissions WHERE kind='entity' AND tombstoned=1) ORDER BY e.entity_id""",
    "release_data": """SELECT NULL,r.release_id,e.entity_key,r.language,r.first_seen_at,r.observed_at
        FROM ledger.release r JOIN main.entity_data e USING(entity_id) WHERE r.release_id NOT IN
        (SELECT id FROM ledger.omissions WHERE kind='release' AND tombstoned=1) ORDER BY r.release_id""",
    "canonical_title_data": """SELECT NULL,c.mapping_id,t.title_key,c.namespace,c.external_id,c.source,c.evidence,c.checked_at
        FROM ledger.canonical_title c JOIN main.title_data t USING(title_id)
        WHERE c.source IN ({approved}) ORDER BY c.mapping_id""",
    "canonical_episode_data": """SELECT m.mapping_key,e.entity_key,c.season,c.episode,c.external_episode_id,c.evidence,c.checked_at
        FROM ledger.canonical_episode c JOIN main.canonical_title_data m USING(mapping_id)
        JOIN main.entity_data e USING(entity_id) ORDER BY c.mapping_id,c.season,c.episode""",
    "identity_alias": """SELECT a.* FROM ledger.identity_alias a WHERE
        (a.kind='title' AND EXISTS (SELECT 1 FROM main.title_data t WHERE t.title_id=a.current_id)) OR
        (a.kind='entity' AND EXISTS (SELECT 1 FROM main.entity_data e WHERE e.entity_id=a.current_id)) ORDER BY a.kind,a.old_id""",
}


@dataclass(frozen=True)
class Snapshot:
    generation: int
    content_generation: int
    listing_checked_at: int


class RebuildRequired(ValueError):
    """A broad or unclassified change needs the independently validated full path."""


def copy(
    db: sqlite3.Connection,
    filename: str,
    provider: str,
    approved: frozenset[str],
    *,
    incremental: bool = False,
) -> Snapshot:
    db.execute(
        "ATTACH DATABASE ? AS ledger", (Path(filename).resolve().as_uri() + "?mode=ro",)
    )
    indexes = db.execute(
        "SELECT name,sql FROM main.sqlite_schema WHERE type='index' AND sql IS NOT NULL AND name<>'release_recent'"
    ).fetchall()
    # Keep release_recent interleaved with release rows: rebuilding it at the
    # end separates duplicate public IDs beyond the zstd window (measured full
    # artifact: 323 MB). Rebuild the other secondary indexes from sorted runs.
    # Parent ID uniqueness stays live for joins. All deferred indexes are
    # restored before full independent validation of the complete artifact.
    if not incremental:
        for name, _ in indexes:
            db.execute(f"DROP INDEX main.{name}")
    db.execute("PRAGMA cache_size=-32768")
    if not incremental:
        db.execute("PRAGMA temp_store=FILE")
    db.execute("PRAGMA mmap_size=0")
    db.execute("PRAGMA ledger.cache_size=-32768")
    # The first attached read pins the entire ledger snapshot for this transaction.
    with db:
        db.execute("BEGIN")
        checked = db.execute(
            "SELECT listing_checked_at FROM ledger.worker_meta"
        ).fetchone()[0]
        generation, content = db.execute(
            "SELECT generation,content_generation FROM ledger.publication_meta"
        ).fetchone()
        with phase("export_rows"):
            if incremental:
                changes = [
                    r[0]
                    for r in db.execute(
                        "SELECT title_id FROM ledger.publication_change"
                    )
                ]
                if "@full" in changes or len(changes) > 1000:
                    raise RebuildRequired("full export required")
                db.execute("CREATE TEMP TABLE changed_title(title_id TEXT PRIMARY KEY)")
                db.executemany(
                    "INSERT INTO changed_title VALUES(?)",
                    ((tid,) for tid in changes if not tid.startswith("@")),
                )
                db.execute("UPDATE main.catalog SET listing_checked_at=?", (checked,))
                from .incremental_export import refresh

                refresh(db, approved)
            else:
                db.execute(
                    "INSERT INTO main.catalog VALUES(1,?,2,1,?)", (provider, checked)
                )
                for table, query in QUERIES.items():
                    values = ()
                    if table == "canonical_title_data":
                        values = tuple(sorted(approved))
                        query = query.format(
                            approved=",".join("?" for _ in values) if values else "NULL"
                        )
                    db.execute(f"INSERT INTO main.{table} {query}", values)
        if not incremental:
            with phase("export_indexes"):
                for _, definition in indexes:
                    db.execute(definition)
    return Snapshot(generation, content, checked)
