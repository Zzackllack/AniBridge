"""Read local corrections and leased immutable rows in one private read snapshot."""

import json
import time

from .overrides import resolution
from .refresh_view import (
    attach,
    has_observations,
    qualify,
)
from .refresh_view import (
    prefix as observation_prefix,
)


class AttachedCatalog:
    def __init__(self, db, alias: str, prefix: str = "") -> None:
        self.db, self.alias, self.prefix = db, alias, prefix

    def execute(self, sql: str, args=()):
        return self.db.execute(
            self.prefix
            + qualify(
                sql,
                self.alias,
                "canonical_title|canonical_episode"
                if self.prefix
                else "title|entity|canonical_title|canonical_episode",
            ),
            args,
        )


class MappingView:
    def __init__(self, private, catalog, provider: str, index: int, now: int) -> None:
        self.db = private
        self.provider = provider
        self.schema_version = (
            catalog.schema_version
            if hasattr(catalog, "schema_version")
            else catalog.execute("PRAGMA user_version").fetchone()[0]
        )
        self.observations = has_observations(private, provider, now)
        self.has_overrides = (
            private.execute(
                "SELECT 1 FROM catalog_override WHERE provider=? AND json_extract(body,'$.enabled')=1 LIMIT 1",
                (provider,),
            ).fetchone()
            is not None
        )
        alias = attach(private, catalog, f"catalog_read_{index}")
        observations = (
            observation_prefix(provider, alias, now, self.schema_version)
            if self.observations
            else ""
        )
        catalog = AttachedCatalog(
            private, alias, "WITH " + observations + " " if observations else ""
        )
        function = f"override_valid_{index}"

        def valid(encoded):
            body = json.loads(encoded)
            return int(resolution(body, private, catalog)[0] == "active")

        private.create_function(function, 1, valid)
        # provider is from the closed protocol enum; user text remains bound.
        self.prefix = f"""WITH local_map AS MATERIALIZED (
          SELECT *,json_extract(body,'$.entity_kind') AS entity_kind,
            json_extract(body,'$.target.external_id') AS external_id,
            json_extract(body,'$.target.season') AS season,
            json_extract(body,'$.target.episode') AS episode
          FROM main.catalog_override WHERE provider='{provider}' AND {function}(body)=1
        ), local_title AS (
          SELECT 'local:'||id AS mapping_id,title_id,namespace,external_id,
                 'local_operator' AS source,'reviewed' AS evidence,updated_at AS checked_at
          FROM local_map WHERE entity_kind IN ('title','movie')
        ), canonical_title AS (
          SELECT * FROM local_title UNION ALL
          SELECT p.* FROM {alias}.canonical_title p WHERE NOT EXISTS
            (SELECT 1 FROM local_title l WHERE l.title_id=p.title_id AND l.namespace=p.namespace)
        ), canonical_episode AS (
          SELECT c.mapping_id,l.entity_id,l.season,l.episode,NULL AS external_episode_id,
                 'reviewed' AS evidence,l.updated_at AS checked_at
          FROM local_map l JOIN canonical_title c ON c.title_id=l.title_id
            AND c.namespace=l.namespace AND c.external_id=l.external_id
          WHERE l.entity_kind='episode'
          UNION ALL
          SELECT c.mapping_id,p.entity_id,p.season,p.episode,p.external_episode_id,p.evidence,p.checked_at
          FROM {alias}.canonical_episode p JOIN {alias}.canonical_title original USING(mapping_id)
          JOIN canonical_title c ON c.title_id=original.title_id AND c.namespace=original.namespace
            AND c.external_id=original.external_id
          WHERE NOT EXISTS(SELECT 1 FROM local_map l WHERE l.entity_kind='episode'
            AND l.entity_id=p.entity_id AND l.namespace=original.namespace)
        ) """
        self.alias = alias
        if observations:
            self.prefix = (
                "WITH " + observations + "," + self.prefix.removeprefix("WITH ")
            )
        if not self.has_overrides:
            self.prefix = "WITH " + observations + " "

    def execute(self, sql: str, args=()):
        if self.observations:
            from .refresh_queries import branches

            branched = branches(
                self.prefix,
                self.alias,
                self.provider,
                sql,
                args,
                self.has_overrides,
                self.schema_version,
            )
            if branched is not None:
                return self.db.execute(*branched)
            sql = sql.replace(" INDEXED BY release_recent", "")
        elif self.schema_version == 2:
            from catalog_core.compact import release_from

            sql = sql.replace(
                "FROM release r INDEXED BY release_recent",
                release_from(2, ordered=True),
            )
        if not self.observations and self.has_overrides:
            from .refresh_queries import effective_joins

            sql = effective_joins(sql, self.alias, self.schema_version)
        sql = qualify(
            sql,
            self.alias,
            (
                "alias"
                if self.has_overrides
                else "alias|canonical_title|canonical_episode"
            )
            if self.observations
            else "release|entity|title|alias|release_data|entity_data",
        )
        return self.db.execute(self.prefix + sql, args)

    def set_progress_handler(self, *args):
        self.db.set_progress_handler(*args)

    def oldest_release(self):
        table = "release" if self.schema_version == 1 else "release_data"
        return self.db.execute(
            f"SELECT min(first_seen_at) FROM {self.alias}.{table}"
        ).fetchone()[0]

    def recent_count(self, central_count: int, cutoff: int) -> int:
        # Keep the small local observation set outermost. Joining the public
        # release view may otherwise walk the whole catalog to count zero hits.
        removed_from = (
            f"local_entities l CROSS JOIN {self.alias}.entity_data e ON e.entity_id=l.entity_id "
            f"CROSS JOIN {self.alias}.release_data r ON r.entity_key=e.entity_key"
            if self.schema_version == 2
            else f"local_entities l JOIN {self.alias}.release r ON r.entity_id=l.entity_id"
        )
        sql = f"""SELECT
          (SELECT count(*) FROM {removed_from}),
          (SELECT count(*) FROM main.catalog_cache s JOIN {self.alias}.release r ON r.release_id=s.key
             WHERE s.kind=? AND json_extract(s.body,'$.first_seen_at')<?
               AND NOT EXISTS(SELECT 1 FROM local_entities l WHERE l.entity_id=r.entity_id)),
          (SELECT count(*) FROM local_releases r WHERE
             min(r.first_seen_at,coalesce((SELECT p.first_seen_at FROM {self.alias}.release p WHERE p.release_id=r.release_id),r.first_seen_at))>=?)"""
        from .refresh_observations import cache_kind

        removed, old, added = self.db.execute(
            self.prefix + sql, (cache_kind("seen", self.provider), cutoff, cutoff)
        ).fetchone()
        return central_count - removed - old + added


def view(private, catalog, provider: str, index: int, *, now: int | None = None):
    now = int(time.time()) if now is None else now
    if private.execute(
        "SELECT 1 FROM catalog_override WHERE provider=? AND json_extract(body,'$.enabled')=1 LIMIT 1",
        (provider,),
    ).fetchone() is None and not has_observations(private, provider, now):
        return catalog
    return MappingView(private, catalog, provider, index, now)
