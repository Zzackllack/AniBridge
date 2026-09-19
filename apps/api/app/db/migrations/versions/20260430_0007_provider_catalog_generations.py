"""Make provider catalog rows generation-distinct

Revision ID: 20260430_0007
Revises: 20260429_0006
Create Date: 2026-04-30 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430_0007"
down_revision = "20260429_0006"
branch_labels = None
depends_on = None


def _rebuild_table(
    *,
    table_name: str,
    temp_table: str,
    create_sql: str,
    copy_sql: str,
    index_sql: list[str],
    require_generation_in_pk: bool,
) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return
    pk = inspector.get_pk_constraint(table_name) or {}
    pk_columns = pk.get("constrained_columns") or []
    if ("indexed_generation" in pk_columns) is require_generation_in_pk:
        return

    op.execute(sa.text(f"DROP TABLE IF EXISTS {temp_table}"))
    op.execute(sa.text(create_sql))
    op.execute(sa.text(copy_sql))
    op.drop_table(table_name)
    op.rename_table(temp_table, table_name)
    for statement in index_sql:
        op.execute(sa.text(statement))


def upgrade() -> None:
    specs = {
        "providercatalogtitle": {
            "temp_table": "providercatalogtitle_v2",
            "create_sql": """
                CREATE TABLE providercatalogtitle_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    title VARCHAR NOT NULL,
                    normalized_title VARCHAR NOT NULL,
                    media_type_hint VARCHAR NOT NULL,
                    relative_path VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, indexed_generation)
                )
            """,
            "copy_sql": """
                INSERT INTO providercatalogtitle_v2 (
                    provider,
                    slug,
                    indexed_generation,
                    title,
                    normalized_title,
                    media_type_hint,
                    relative_path,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    indexed_generation,
                    title,
                    normalized_title,
                    media_type_hint,
                    relative_path,
                    last_indexed_at
                FROM providercatalogtitle
            """,
            "index_sql": [
                "CREATE INDEX ix_providercatalogtitle_title ON providercatalogtitle (title)",
                "CREATE INDEX ix_providercatalogtitle_normalized_title ON providercatalogtitle (normalized_title)",
                "CREATE INDEX ix_providercatalogtitle_media_type_hint ON providercatalogtitle (media_type_hint)",
                "CREATE INDEX ix_providercatalogtitle_indexed_generation ON providercatalogtitle (indexed_generation)",
                "CREATE INDEX ix_providercatalogtitle_last_indexed_at ON providercatalogtitle (last_indexed_at)",
            ],
        },
        "providercatalogalias": {
            "temp_table": "providercatalogalias_v2",
            "create_sql": """
                CREATE TABLE providercatalogalias_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    alias VARCHAR NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    normalized_alias VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, alias, indexed_generation)
                )
            """,
            "copy_sql": """
                INSERT INTO providercatalogalias_v2 (
                    provider,
                    slug,
                    alias,
                    indexed_generation,
                    normalized_alias,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    alias,
                    indexed_generation,
                    normalized_alias,
                    last_indexed_at
                FROM providercatalogalias
            """,
            "index_sql": [
                "CREATE INDEX ix_providercatalogalias_normalized_alias ON providercatalogalias (normalized_alias)",
                "CREATE INDEX ix_providercatalogalias_indexed_generation ON providercatalogalias (indexed_generation)",
                "CREATE INDEX ix_providercatalogalias_last_indexed_at ON providercatalogalias (last_indexed_at)",
            ],
        },
        "providercatalogepisode": {
            "temp_table": "providercatalogepisode_v2",
            "create_sql": """
                CREATE TABLE providercatalogepisode_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    title_primary VARCHAR,
                    title_secondary VARCHAR,
                    relative_path VARCHAR NOT NULL,
                    media_type_hint VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, season, episode, indexed_generation)
                )
            """,
            "copy_sql": """
                INSERT INTO providercatalogepisode_v2 (
                    provider,
                    slug,
                    season,
                    episode,
                    indexed_generation,
                    title_primary,
                    title_secondary,
                    relative_path,
                    media_type_hint,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    season,
                    episode,
                    indexed_generation,
                    title_primary,
                    title_secondary,
                    relative_path,
                    media_type_hint,
                    last_indexed_at
                FROM providercatalogepisode
            """,
            "index_sql": [
                "CREATE INDEX ix_providercatalogepisode_media_type_hint ON providercatalogepisode (media_type_hint)",
                "CREATE INDEX ix_providercatalogepisode_indexed_generation ON providercatalogepisode (indexed_generation)",
                "CREATE INDEX ix_providercatalogepisode_last_indexed_at ON providercatalogepisode (last_indexed_at)",
            ],
        },
        "providerepisodelanguage": {
            "temp_table": "providerepisodelanguage_v2",
            "create_sql": """
                CREATE TABLE providerepisodelanguage_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    language VARCHAR NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    normalized_language VARCHAR NOT NULL,
                    host_hints JSON,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (
                        provider,
                        slug,
                        season,
                        episode,
                        language,
                        indexed_generation
                    )
                )
            """,
            "copy_sql": """
                INSERT INTO providerepisodelanguage_v2 (
                    provider,
                    slug,
                    season,
                    episode,
                    language,
                    indexed_generation,
                    normalized_language,
                    host_hints,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    season,
                    episode,
                    language,
                    indexed_generation,
                    normalized_language,
                    host_hints,
                    last_indexed_at
                FROM providerepisodelanguage
            """,
            "index_sql": [
                "CREATE INDEX ix_providerepisodelanguage_normalized_language ON providerepisodelanguage (normalized_language)",
                "CREATE INDEX ix_providerepisodelanguage_indexed_generation ON providerepisodelanguage (indexed_generation)",
                "CREATE INDEX ix_providerepisodelanguage_last_indexed_at ON providerepisodelanguage (last_indexed_at)",
            ],
        },
    }

    for table_name, spec in specs.items():
        _rebuild_table(
            table_name=table_name,
            temp_table=spec["temp_table"],
            create_sql=spec["create_sql"],
            copy_sql=spec["copy_sql"],
            index_sql=spec["index_sql"],
            require_generation_in_pk=True,
        )


def downgrade() -> None:
    specs = {
        "providercatalogtitle": {
            "temp_table": "providercatalogtitle_v2",
            "create_sql": """
                CREATE TABLE providercatalogtitle_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    title VARCHAR NOT NULL,
                    normalized_title VARCHAR NOT NULL,
                    media_type_hint VARCHAR NOT NULL,
                    relative_path VARCHAR NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug)
                )
            """,
            "copy_sql": """
                INSERT INTO providercatalogtitle_v2 (
                    provider,
                    slug,
                    title,
                    normalized_title,
                    media_type_hint,
                    relative_path,
                    indexed_generation,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    title,
                    normalized_title,
                    media_type_hint,
                    relative_path,
                    indexed_generation,
                    last_indexed_at
                FROM (
                    SELECT
                        provider,
                        slug,
                        title,
                        normalized_title,
                        media_type_hint,
                        relative_path,
                        indexed_generation,
                        last_indexed_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY provider, slug
                            ORDER BY indexed_generation DESC, last_indexed_at DESC
                        ) AS rn
                    FROM providercatalogtitle
                )
                WHERE rn = 1
            """,
            "index_sql": [
                "CREATE INDEX ix_providercatalogtitle_title ON providercatalogtitle (title)",
                "CREATE INDEX ix_providercatalogtitle_normalized_title ON providercatalogtitle (normalized_title)",
                "CREATE INDEX ix_providercatalogtitle_media_type_hint ON providercatalogtitle (media_type_hint)",
                "CREATE INDEX ix_providercatalogtitle_indexed_generation ON providercatalogtitle (indexed_generation)",
                "CREATE INDEX ix_providercatalogtitle_last_indexed_at ON providercatalogtitle (last_indexed_at)",
            ],
        },
        "providercatalogalias": {
            "temp_table": "providercatalogalias_v2",
            "create_sql": """
                CREATE TABLE providercatalogalias_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    alias VARCHAR NOT NULL,
                    normalized_alias VARCHAR NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, alias)
                )
            """,
            "copy_sql": """
                INSERT INTO providercatalogalias_v2 (
                    provider,
                    slug,
                    alias,
                    normalized_alias,
                    indexed_generation,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    alias,
                    normalized_alias,
                    indexed_generation,
                    last_indexed_at
                FROM (
                    SELECT
                        provider,
                        slug,
                        alias,
                        normalized_alias,
                        indexed_generation,
                        last_indexed_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY provider, slug, alias
                            ORDER BY indexed_generation DESC, last_indexed_at DESC
                        ) AS rn
                    FROM providercatalogalias
                )
                WHERE rn = 1
            """,
            "index_sql": [
                "CREATE INDEX ix_providercatalogalias_normalized_alias ON providercatalogalias (normalized_alias)",
                "CREATE INDEX ix_providercatalogalias_indexed_generation ON providercatalogalias (indexed_generation)",
                "CREATE INDEX ix_providercatalogalias_last_indexed_at ON providercatalogalias (last_indexed_at)",
            ],
        },
        "providercatalogepisode": {
            "temp_table": "providercatalogepisode_v2",
            "create_sql": """
                CREATE TABLE providercatalogepisode_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    title_primary VARCHAR,
                    title_secondary VARCHAR,
                    relative_path VARCHAR NOT NULL,
                    media_type_hint VARCHAR NOT NULL,
                    indexed_generation VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, season, episode)
                )
            """,
            "copy_sql": """
                INSERT INTO providercatalogepisode_v2 (
                    provider,
                    slug,
                    season,
                    episode,
                    title_primary,
                    title_secondary,
                    relative_path,
                    media_type_hint,
                    indexed_generation,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    season,
                    episode,
                    title_primary,
                    title_secondary,
                    relative_path,
                    media_type_hint,
                    indexed_generation,
                    last_indexed_at
                FROM (
                    SELECT
                        provider,
                        slug,
                        season,
                        episode,
                        title_primary,
                        title_secondary,
                        relative_path,
                        media_type_hint,
                        indexed_generation,
                        last_indexed_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY provider, slug, season, episode
                            ORDER BY indexed_generation DESC, last_indexed_at DESC
                        ) AS rn
                    FROM providercatalogepisode
                )
                WHERE rn = 1
            """,
            "index_sql": [
                "CREATE INDEX ix_providercatalogepisode_media_type_hint ON providercatalogepisode (media_type_hint)",
                "CREATE INDEX ix_providercatalogepisode_indexed_generation ON providercatalogepisode (indexed_generation)",
                "CREATE INDEX ix_providercatalogepisode_last_indexed_at ON providercatalogepisode (last_indexed_at)",
            ],
        },
        "providerepisodelanguage": {
            "temp_table": "providerepisodelanguage_v2",
            "create_sql": """
                CREATE TABLE providerepisodelanguage_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    language VARCHAR NOT NULL,
                    normalized_language VARCHAR NOT NULL,
                    host_hints JSON,
                    indexed_generation VARCHAR NOT NULL,
                    last_indexed_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, season, episode, language)
                )
            """,
            "copy_sql": """
                INSERT INTO providerepisodelanguage_v2 (
                    provider,
                    slug,
                    season,
                    episode,
                    language,
                    normalized_language,
                    host_hints,
                    indexed_generation,
                    last_indexed_at
                )
                SELECT
                    provider,
                    slug,
                    season,
                    episode,
                    language,
                    normalized_language,
                    host_hints,
                    indexed_generation,
                    last_indexed_at
                FROM (
                    SELECT
                        provider,
                        slug,
                        season,
                        episode,
                        language,
                        normalized_language,
                        host_hints,
                        indexed_generation,
                        last_indexed_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY provider, slug, season, episode, language
                            ORDER BY indexed_generation DESC, last_indexed_at DESC
                        ) AS rn
                    FROM providerepisodelanguage
                )
                WHERE rn = 1
            """,
            "index_sql": [
                "CREATE INDEX ix_providerepisodelanguage_normalized_language ON providerepisodelanguage (normalized_language)",
                "CREATE INDEX ix_providerepisodelanguage_indexed_generation ON providerepisodelanguage (indexed_generation)",
                "CREATE INDEX ix_providerepisodelanguage_last_indexed_at ON providerepisodelanguage (last_indexed_at)",
            ],
        },
    }

    for table_name, spec in specs.items():
        _rebuild_table(
            table_name=table_name,
            temp_table=spec["temp_table"],
            create_sql=spec["create_sql"],
            copy_sql=spec["copy_sql"],
            index_sql=spec["index_sql"],
            require_generation_in_pk=False,
        )
