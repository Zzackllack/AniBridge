"""Private release metadata for stable movie source variants."""

VERSION_DDL = "CREATE TABLE worker_schema(version INTEGER PRIMARY KEY CHECK(version=8))"

DDL = """
CREATE TABLE release_metadata (
 release_id TEXT PRIMARY KEY REFERENCES release(release_id),
 variant_anchor TEXT NOT NULL CHECK(length(variant_anchor)<=256),
 metadata_json TEXT NOT NULL CHECK(length(metadata_json)<=4096),
 available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1))
) STRICT;
"""


def publication_ddl() -> str:
    """Track metadata edits in the same changed-title journal as releases."""
    parent = "(SELECT e.title_id FROM release r JOIN entity e USING(entity_id) WHERE r.release_id={row}.release_id)"
    statements = []
    for action, row in (("INSERT", "NEW"), ("DELETE", "OLD"), ("UPDATE", "NEW")):
        where = ""
        if action == "UPDATE":
            where = "WHEN NEW.release_id IS NOT OLD.release_id OR NEW.variant_anchor IS NOT OLD.variant_anchor OR NEW.metadata_json IS NOT OLD.metadata_json OR NEW.available IS NOT OLD.available "
        statements.append(
            f"CREATE TRIGGER offer_pub_{action.lower()} AFTER {action} ON release_metadata {where}"
            "BEGIN "
            "UPDATE publication_meta SET generation=generation+1,content_generation=content_generation+1; "
            f"INSERT INTO publication_change SELECT coalesce({parent.format(row=row)},'@full'),(SELECT generation FROM publication_meta) "
            "ON CONFLICT(title_id) DO UPDATE SET generation=excluded.generation; END;"
        )
    return "\n".join(statements)
