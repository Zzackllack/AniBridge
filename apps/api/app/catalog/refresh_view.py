"""Read validated local observations without replacing immutable central data."""

import re
import time
from pathlib import Path

from .refresh_observations import cache_kind


def qualify(sql: str, alias: str, tables: str) -> str:
    """Qualify fixed internal SELECT templates; query values stay bound."""
    return re.sub(
        rf"\b(FROM|JOIN)\s+({tables})\b",
        lambda match: match[1] + " " + alias + "." + match[2],
        sql,
        flags=re.IGNORECASE,
    )


def attach(private, catalog, alias: str) -> str:
    if isinstance(catalog, ObservationCatalog):
        return catalog.alias
    filename = catalog.execute("PRAGMA database_list").fetchone()[2]
    # Transfer the handle: never add a second provider file for this reader.
    catalog.close()
    private.execute(
        f"ATTACH DATABASE ? AS {alias}",
        (Path(filename).as_uri() + "?mode=ro&immutable=1",),
    )
    private.execute(f"PRAGMA {alias}.cache_size=-8192")
    private.execute(f"PRAGMA {alias}.mmap_size=0")
    return alias


class ObservationCatalog:
    def __init__(self, private, catalog, provider: str, alias: str, now: int):
        self.db = private
        self.schema_version = catalog.execute("PRAGMA user_version").fetchone()[0]
        self.alias = attach(private, catalog, alias)
        self.prefix = (
            "WITH " + prefix(provider, self.alias, now, self.schema_version) + " "
        )
        self.observations = True

    def execute(self, sql: str, args=()):
        if sql.lstrip().upper().startswith("PRAGMA "):
            return self.db.execute(sql, args)
        sql = sql.replace(" INDEXED BY release_recent", "")
        return self.db.execute(
            self.prefix
            + qualify(
                sql, self.alias, "alias|canonical_title|canonical_episode|catalog"
            ),
            args,
        )

    def set_progress_handler(self, *args):
        self.db.set_progress_handler(*args)

    def close(self):
        # The owning pinned private connection closes all attached files.
        pass


def observed(private, catalog, provider: str, index: int, now: int | None = None):
    if isinstance(catalog, ObservationCatalog):
        return catalog
    now = int(time.time()) if now is None else now
    return (
        ObservationCatalog(private, catalog, provider, f"catalog_read_{index}", now)
        if has_observations(private, provider, now)
        else catalog
    )


def has_observations(db, provider: str, now: int) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM catalog_cache WHERE kind IN (?,?,?) AND expires_at>? LIMIT 1",
            (
                cache_kind("title", provider),
                cache_kind("entity", provider),
                cache_kind("seen", provider),
                now,
            ),
        ).fetchone()
        is not None
    )


def columns(names: tuple[str, ...], source: str) -> str:
    return ",".join(
        f"json_extract({source}.body,'$.{name}') AS {name}" for name in names
    )


def prefix(provider: str, alias: str, now: int, schema_version: int = 1) -> str:
    published_entity = "entity_data" if schema_version == 2 else "entity"
    title_fields = (
        "title_id",
        "identity_anchor",
        "slug",
        "display_title",
        "search_key",
        "media_type",
        "year",
        "path",
        "observed_at",
        "detail_status",
    )
    entity_fields = (
        "entity_id",
        "title_id",
        "identity_anchor",
        "kind",
        "native_season",
        "native_episode",
        "display_title",
        "path",
        "observed_at",
    )
    local_release = ",".join(
        f"json_extract(j.value,'$.{name}') AS {name}"
        for name in (
            "release_id",
            "entity_id",
            "language",
            "first_seen_at",
            "observed_at",
        )
    )
    # Public enum and an internal integer are the only interpolated values.
    # Split normal releases from the discovery-ledger join so the large central
    # branch retains direct indexed columns for recent ordering/filtering.
    return f"""local_titles AS (
      SELECT {columns(title_fields, "l")} FROM main.catalog_cache l JOIN {alias}.title t ON t.title_id=l.key
      WHERE l.kind='{cache_kind("title", provider)}' AND l.expires_at>{int(now)}
        AND json_extract(l.body,'$.observed_at')>t.observed_at
        AND json_extract(l.body,'$.identity_anchor')=t.identity_anchor
        AND json_extract(l.body,'$.path')=t.path AND json_extract(l.body,'$.media_type')=t.media_type
    ), flat_title AS (
      SELECT t.title_id,t.identity_anchor,t.slug,coalesce(l.display_title,t.display_title) AS display_title,
        coalesce(l.search_key,t.search_key) AS search_key,t.media_type,
        CASE WHEN l.title_id IS NULL THEN t.year ELSE l.year END AS year,t.path,
        coalesce(l.observed_at,t.observed_at) AS observed_at,t.detail_status
      FROM {alias}.title t LEFT JOIN local_titles l ON l.title_id=t.title_id
    ), title AS (
      SELECT * FROM local_titles UNION ALL SELECT t.* FROM {alias}.title t
      WHERE NOT EXISTS(SELECT 1 FROM local_titles l WHERE l.title_id=t.title_id)
    ), local_entities AS (
      SELECT {columns(entity_fields, "l")},l.body FROM main.catalog_cache l
      JOIN {alias}.title t ON t.title_id=json_extract(l.body,'$.title_id')
      LEFT JOIN {alias}.{published_entity} e ON e.entity_id=l.key
      WHERE l.kind='{cache_kind("entity", provider)}' AND l.expires_at>{int(now)}
        AND (e.entity_id IS NULL OR json_extract(l.body,'$.observed_at')>e.observed_at)
        AND (json_extract(l.body,'$.path')=t.path AND t.media_type='movie'
          OR substr(json_extract(l.body,'$.path'),1,length(t.path)+1)=t.path||'/' AND t.media_type='series')
    ), entity AS (
      SELECT {",".join(entity_fields)} FROM local_entities UNION ALL SELECT e.* FROM {alias}.entity e
      WHERE NOT EXISTS(SELECT 1 FROM local_entities l WHERE l.entity_id=e.entity_id)
    ), local_releases AS (
      SELECT {local_release} FROM local_entities l JOIN json_each(l.body,'$.releases') j
    ), local_effective_releases AS (
      SELECT r.release_id,r.entity_id,r.language,
        min(r.first_seen_at,coalesce((SELECT p.first_seen_at FROM {alias}.release p WHERE p.release_id=r.release_id),r.first_seen_at)) AS first_seen_at,r.observed_at
      FROM local_releases r
    ), release AS (
      SELECT r.* FROM {alias}.release r
      WHERE NOT EXISTS(SELECT 1 FROM local_entities l WHERE l.entity_id=r.entity_id)
        AND NOT EXISTS(SELECT 1 FROM main.catalog_cache s WHERE s.kind='{cache_kind("seen", provider)}' AND s.key=r.release_id)
      UNION ALL
      SELECT r.release_id,r.entity_id,r.language,min(r.first_seen_at,json_extract(s.body,'$.first_seen_at')),r.observed_at
      FROM main.catalog_cache s JOIN {alias}.release r ON r.release_id=s.key
      WHERE s.kind='{cache_kind("seen", provider)}'
        AND NOT EXISTS(SELECT 1 FROM local_entities l WHERE l.entity_id=r.entity_id)
      UNION ALL
      SELECT r.release_id,r.entity_id,r.language,
        min(r.first_seen_at,coalesce((SELECT p.first_seen_at FROM {alias}.release p WHERE p.release_id=r.release_id),r.first_seen_at)),r.observed_at
      FROM local_releases r
    )"""
