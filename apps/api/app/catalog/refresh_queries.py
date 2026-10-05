"""Keep central/local query branches separate until their bounded final merge.

Joining compound release/entity views makes SQLite materialize entire catalogs.
These fixed internal templates keep the central branch on its original indexes.
"""

import re

from .refresh_observations import cache_kind
from .refresh_view import qualify


def primary_join(sql: str, alias: str, schema_version: int = 1) -> str:
    """Choose a title's effective primary map using indexed per-title reads."""
    old = """LEFT JOIN canonical_title ct ON ct.mapping_id=(SELECT c.mapping_id FROM canonical_title c
                    WHERE c.title_id=t.title_id ORDER BY CASE c.namespace WHEN 'tvdb' THEN 0 WHEN 'tmdb-tv' THEN 1 ELSE 2 END,c.namespace LIMIT 1)"""
    if old not in sql:
        return sql
    # Joining the compound canonical_title view first materializes every title
    # map on each RSS poll. Restrict both branches before choosing the primary.
    choice = f"""(SELECT mapping_id FROM (
        SELECT l.mapping_id,l.namespace FROM local_title l WHERE l.title_id=t.title_id
        UNION ALL SELECT p.mapping_id,p.namespace FROM {alias}.canonical_title p
        WHERE p.title_id=t.title_id AND NOT EXISTS(
          SELECT 1 FROM local_title l WHERE l.title_id=p.title_id AND l.namespace=p.namespace)
      ) ORDER BY CASE namespace WHEN 'tvdb' THEN 0 WHEN 'tmdb-tv' THEN 1 ELSE 2 END,namespace LIMIT 1)"""
    sql = sql.replace(
        old,
        f"LEFT JOIN {alias}.canonical_title pub_ct ON pub_ct.mapping_id={choice} "
        f"LEFT JOIN local_title loc_ct ON loc_ct.mapping_id={choice}",
    )
    # A chosen mapping belongs to exactly one of the two disjoint branches.
    sql = sql.replace(
        "ct.namespace,ct.external_id",
        "coalesce(loc_ct.namespace,pub_ct.namespace) AS namespace,"
        "coalesce(loc_ct.external_id,pub_ct.external_id) AS external_id",
    )
    for column in ("mapping_id", "namespace", "external_id"):
        sql = re.sub(
            rf"\bct\.{column}\b",
            f"coalesce(loc_ct.{column},pub_ct.{column})",
            sql,
        )
    if schema_version == 2:
        sql = sql.replace(
            f"LEFT JOIN {alias}.canonical_title pub_ct",
            f"LEFT JOIN {alias}.canonical_title_data pub_ct",
        )
    return sql


def effective_joins(body: str, alias: str, schema_version: int) -> str:
    old = "LEFT JOIN canonical_episode ce ON ce.mapping_id=ct.mapping_id AND ce.entity_id=e.entity_id"
    if schema_version == 2:
        new = f"""LEFT JOIN {alias}.canonical_episode_data pce ON pce.entity_key=
          (SELECT entity_key FROM {alias}.entity_data WHERE entity_id=e.entity_id)
          AND pce.mapping_key=(SELECT pc.mapping_key FROM {alias}.canonical_title_data pc
            WHERE pc.title_key=(SELECT title_key FROM {alias}.title_data WHERE title_id=t.title_id)
              AND pc.namespace=ct.namespace AND pc.external_id=ct.external_id)
          LEFT JOIN local_map lo ON lo.entity_kind='episode' AND lo.entity_id=e.entity_id
            AND lo.namespace=ct.namespace AND lo.external_id=ct.external_id"""
    else:
        new = f"""LEFT JOIN {alias}.canonical_episode pce ON pce.entity_id=e.entity_id
          AND pce.mapping_id=(SELECT pc.mapping_id FROM {alias}.canonical_title pc
            WHERE pc.title_id=t.title_id AND pc.namespace=ct.namespace AND pc.external_id=ct.external_id)
          LEFT JOIN local_map lo ON lo.entity_kind='episode' AND lo.entity_id=e.entity_id
            AND lo.namespace=ct.namespace AND lo.external_id=ct.external_id"""
    if old in body:
        body = body.replace(old, new).replace(
            "ce.season,ce.episode",
            "coalesce(lo.season,pce.season) AS season,coalesce(lo.episode,pce.episode) AS episode",
        )
        for column in ("entity_id", "season", "episode"):
            published = (
                "CASE WHEN pce.entity_key IS NOT NULL THEN e.entity_id END"
                if schema_version == 2 and column == "entity_id"
                else f"pce.{column}"
            )
            body = re.sub(
                rf"\bce\.{column}\b", f"coalesce(lo.{column},{published})", body
            )
    return primary_join(body, alias, schema_version)


def branches(
    prefix: str,
    alias: str,
    provider: str,
    sql: str,
    args,
    overrides: bool,
    schema_version: int = 1,
):
    rows = sql.startswith("SELECT r.*")
    count = sql.startswith("SELECT count(*) ")
    if not (rows or count) or "FROM release r" not in sql:
        return None
    if rows:
        body, ending = sql.rsplit(
            " ORDER BY r.first_seen_at DESC,r.release_id ASC LIMIT ?", 1
        )
        if ending:
            raise ValueError("unexpected internal query template")
        values, limit = list(args[:-1]), args[-1]
    else:
        body, values, limit = sql, list(args), None
    body = body.replace("FROM release r INDEXED BY release_recent", "FROM release r")
    if overrides:
        body = effective_joins(body, alias, schema_version)
    elif schema_version == 2:
        from catalog_core.compact import query_joins

        body = query_joins(body)
    ledger = f"""(SELECT p.release_id,p.entity_id,p.language,
        min(p.first_seen_at,json_extract(s.body,'$.first_seen_at')) AS first_seen_at,p.observed_at
        FROM main.catalog_cache s JOIN {alias}.release p ON p.release_id=s.key
        WHERE s.kind='{cache_kind("seen", provider)}') r"""
    from catalog_core.compact import release_from

    central = (
        release_from(2, ordered=True).removeprefix("FROM ")
        if schema_version == 2 and rows and " INDEXED BY release_recent" in sql
        else f"{alias}.release r"
    )
    sources = (central, ledger, "local_effective_releases r")
    clauses = (
        f"NOT EXISTS(SELECT 1 FROM local_entities l WHERE l.entity_id=r.entity_id) AND NOT EXISTS(SELECT 1 FROM main.catalog_cache s WHERE s.kind='{cache_kind('seen', provider)}' AND s.key=r.release_id)",
        "NOT EXISTS(SELECT 1 FROM local_entities l WHERE l.entity_id=r.entity_id)",
        "1=1",
    )
    queries, parameters = [], []
    for index, (source, clause) in enumerate(zip(sources, clauses)):
        branch = body.replace("FROM release r", "FROM " + source)
        branch = branch.replace(
            "JOIN entity e",
            "JOIN " + ("local_entities" if index == 2 else f"{alias}.entity") + " e",
        )
        branch = branch.replace("JOIN title t", "JOIN flat_title t")
        branch += (" AND " if " WHERE " in body else " WHERE ") + clause
        branch = qualify(
            branch,
            alias,
            ("alias" if overrides else "alias|canonical_title|canonical_episode")
            + "|release_data|entity_data|canonical_title_data|canonical_episode_data",
        )
        if rows:
            branch += " ORDER BY r.first_seen_at DESC,r.release_id ASC LIMIT ?"
            queries.append("SELECT * FROM (" + branch + ")")
            parameters.extend([*values, limit])
        else:
            queries.append(
                branch.replace("SELECT count(*) ", "SELECT count(*) AS n ", 1)
            )
            parameters.extend(values)
    union = " UNION ALL ".join(queries)
    if rows:
        combined = (
            "SELECT * FROM ("
            + union
            + ") ORDER BY first_seen_at DESC,release_id ASC LIMIT ?"
        )
        parameters.append(limit)
    else:
        combined = "SELECT sum(n) FROM (" + union + ")"
    return prefix + combined, parameters
