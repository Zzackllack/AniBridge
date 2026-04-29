"""Make provider mappings generation-aware

Revision ID: 20260429_0005
Revises: 20260428_0004
Create Date: 2026-04-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_0005"
down_revision = "20260428_0004"
branch_labels = None
depends_on = None


def _rebuild_provider_mapping_table(
    *,
    table_name: str,
    create_sql: str,
    copy_sql: str,
    index_sql: list[str],
) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "indexed_generation" in columns:
        return

    temp_table = f"{table_name}_v2"
    op.execute(sa.text(f"DROP TABLE IF EXISTS {temp_table}"))
    op.execute(sa.text(create_sql))
    op.execute(sa.text(copy_sql))
    op.drop_table(table_name)
    op.rename_table(temp_table, table_name)
    for statement in index_sql:
        op.execute(sa.text(statement))


def upgrade() -> None:
    _rebuild_provider_mapping_table(
        table_name="providerseriesmapping",
        create_sql="""
        CREATE TABLE providerseriesmapping_v2 (
            provider VARCHAR NOT NULL,
            slug VARCHAR NOT NULL,
            tvdb_id INTEGER NOT NULL,
            indexed_generation VARCHAR NOT NULL,
            confidence VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            rationale VARCHAR,
            last_verified_at DATETIME NOT NULL,
            PRIMARY KEY (provider, slug, tvdb_id, indexed_generation)
        )
        """,
        copy_sql="""
        INSERT INTO providerseriesmapping_v2 (
            provider,
            slug,
            tvdb_id,
            indexed_generation,
            confidence,
            source,
            rationale,
            last_verified_at
        )
        SELECT
            mapping.provider,
            mapping.slug,
            mapping.tvdb_id,
            COALESCE(status.latest_success_generation, status.current_generation, 'legacy'),
            mapping.confidence,
            mapping.source,
            mapping.rationale,
            mapping.last_verified_at
        FROM providerseriesmapping AS mapping
        LEFT JOIN providerindexstatus AS status
            ON status.provider = mapping.provider
        """,
        index_sql=[
            "CREATE INDEX ix_providerseriesmapping_confidence ON providerseriesmapping (confidence)",
            "CREATE INDEX ix_providerseriesmapping_source ON providerseriesmapping (source)",
            "CREATE INDEX ix_providerseriesmapping_last_verified_at ON providerseriesmapping (last_verified_at)",
            "CREATE INDEX ix_providerseriesmapping_indexed_generation ON providerseriesmapping (indexed_generation)",
        ],
    )
    _rebuild_provider_mapping_table(
        table_name="providerepisodemapping",
        create_sql="""
        CREATE TABLE providerepisodemapping_v2 (
            provider VARCHAR NOT NULL,
            slug VARCHAR NOT NULL,
            provider_season INTEGER NOT NULL,
            provider_episode INTEGER NOT NULL,
            tvdb_id INTEGER NOT NULL,
            canonical_season INTEGER NOT NULL,
            canonical_episode INTEGER NOT NULL,
            indexed_generation VARCHAR NOT NULL,
            confidence VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            rationale VARCHAR,
            last_verified_at DATETIME NOT NULL,
            PRIMARY KEY (
                provider,
                slug,
                provider_season,
                provider_episode,
                tvdb_id,
                canonical_season,
                canonical_episode,
                indexed_generation
            )
        )
        """,
        copy_sql="""
        INSERT INTO providerepisodemapping_v2 (
            provider,
            slug,
            provider_season,
            provider_episode,
            tvdb_id,
            canonical_season,
            canonical_episode,
            indexed_generation,
            confidence,
            source,
            rationale,
            last_verified_at
        )
        SELECT
            mapping.provider,
            mapping.slug,
            mapping.provider_season,
            mapping.provider_episode,
            mapping.tvdb_id,
            mapping.canonical_season,
            mapping.canonical_episode,
            COALESCE(status.latest_success_generation, status.current_generation, 'legacy'),
            mapping.confidence,
            mapping.source,
            mapping.rationale,
            mapping.last_verified_at
        FROM providerepisodemapping AS mapping
        LEFT JOIN providerindexstatus AS status
            ON status.provider = mapping.provider
        """,
        index_sql=[
            "CREATE INDEX ix_providerepisodemapping_confidence ON providerepisodemapping (confidence)",
            "CREATE INDEX ix_providerepisodemapping_source ON providerepisodemapping (source)",
            "CREATE INDEX ix_providerepisodemapping_last_verified_at ON providerepisodemapping (last_verified_at)",
            "CREATE INDEX ix_providerepisodemapping_indexed_generation ON providerepisodemapping (indexed_generation)",
        ],
    )
    _rebuild_provider_mapping_table(
        table_name="providermoviemapping",
        create_sql="""
        CREATE TABLE providermoviemapping_v2 (
            provider VARCHAR NOT NULL,
            slug VARCHAR NOT NULL,
            tmdb_id INTEGER NOT NULL,
            indexed_generation VARCHAR NOT NULL,
            confidence VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            rationale VARCHAR,
            last_verified_at DATETIME NOT NULL,
            PRIMARY KEY (provider, slug, tmdb_id, indexed_generation)
        )
        """,
        copy_sql="""
        INSERT INTO providermoviemapping_v2 (
            provider,
            slug,
            tmdb_id,
            indexed_generation,
            confidence,
            source,
            rationale,
            last_verified_at
        )
        SELECT
            mapping.provider,
            mapping.slug,
            mapping.tmdb_id,
            COALESCE(status.latest_success_generation, status.current_generation, 'legacy'),
            mapping.confidence,
            mapping.source,
            mapping.rationale,
            mapping.last_verified_at
        FROM providermoviemapping AS mapping
        LEFT JOIN providerindexstatus AS status
            ON status.provider = mapping.provider
        """,
        index_sql=[
            "CREATE INDEX ix_providermoviemapping_confidence ON providermoviemapping (confidence)",
            "CREATE INDEX ix_providermoviemapping_source ON providermoviemapping (source)",
            "CREATE INDEX ix_providermoviemapping_last_verified_at ON providermoviemapping (last_verified_at)",
            "CREATE INDEX ix_providermoviemapping_indexed_generation ON providermoviemapping (indexed_generation)",
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    downgrade_specs = {
        "providerseriesmapping": {
            "create_sql": """
                CREATE TABLE providerseriesmapping_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    tvdb_id INTEGER NOT NULL,
                    confidence VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    rationale VARCHAR,
                    last_verified_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, tvdb_id)
                )
            """,
            "copy_sql": """
                INSERT INTO providerseriesmapping_v2 (
                    provider,
                    slug,
                    tvdb_id,
                    confidence,
                    source,
                    rationale,
                    last_verified_at
                )
                SELECT
                    provider,
                    slug,
                    tvdb_id,
                    confidence,
                    source,
                    rationale,
                    last_verified_at
                FROM providerseriesmapping
            """,
            "indexes": [
                "CREATE INDEX ix_providerseriesmapping_confidence ON providerseriesmapping (confidence)",
                "CREATE INDEX ix_providerseriesmapping_source ON providerseriesmapping (source)",
                "CREATE INDEX ix_providerseriesmapping_last_verified_at ON providerseriesmapping (last_verified_at)",
            ],
        },
        "providerepisodemapping": {
            "create_sql": """
                CREATE TABLE providerepisodemapping_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    provider_season INTEGER NOT NULL,
                    provider_episode INTEGER NOT NULL,
                    tvdb_id INTEGER NOT NULL,
                    canonical_season INTEGER NOT NULL,
                    canonical_episode INTEGER NOT NULL,
                    confidence VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    rationale VARCHAR,
                    last_verified_at DATETIME NOT NULL,
                    PRIMARY KEY (
                        provider,
                        slug,
                        provider_season,
                        provider_episode,
                        tvdb_id,
                        canonical_season,
                        canonical_episode
                    )
                )
            """,
            "copy_sql": """
                INSERT INTO providerepisodemapping_v2 (
                    provider,
                    slug,
                    provider_season,
                    provider_episode,
                    tvdb_id,
                    canonical_season,
                    canonical_episode,
                    confidence,
                    source,
                    rationale,
                    last_verified_at
                )
                SELECT
                    provider,
                    slug,
                    provider_season,
                    provider_episode,
                    tvdb_id,
                    canonical_season,
                    canonical_episode,
                    confidence,
                    source,
                    rationale,
                    last_verified_at
                FROM providerepisodemapping
            """,
            "indexes": [
                "CREATE INDEX ix_providerepisodemapping_confidence ON providerepisodemapping (confidence)",
                "CREATE INDEX ix_providerepisodemapping_source ON providerepisodemapping (source)",
                "CREATE INDEX ix_providerepisodemapping_last_verified_at ON providerepisodemapping (last_verified_at)",
            ],
        },
        "providermoviemapping": {
            "create_sql": """
                CREATE TABLE providermoviemapping_v2 (
                    provider VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL,
                    tmdb_id INTEGER NOT NULL,
                    confidence VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    rationale VARCHAR,
                    last_verified_at DATETIME NOT NULL,
                    PRIMARY KEY (provider, slug, tmdb_id)
                )
            """,
            "copy_sql": """
                INSERT INTO providermoviemapping_v2 (
                    provider,
                    slug,
                    tmdb_id,
                    confidence,
                    source,
                    rationale,
                    last_verified_at
                )
                SELECT
                    provider,
                    slug,
                    tmdb_id,
                    confidence,
                    source,
                    rationale,
                    last_verified_at
                FROM providermoviemapping
            """,
            "indexes": [
                "CREATE INDEX ix_providermoviemapping_confidence ON providermoviemapping (confidence)",
                "CREATE INDEX ix_providermoviemapping_source ON providermoviemapping (source)",
                "CREATE INDEX ix_providermoviemapping_last_verified_at ON providermoviemapping (last_verified_at)",
            ],
        },
    }

    for table_name, spec in downgrade_specs.items():
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "indexed_generation" not in columns:
            continue
        temp_table = f"{table_name}_v2"
        op.execute(sa.text(f"DROP TABLE IF EXISTS {temp_table}"))
        op.execute(sa.text(spec["create_sql"]))
        op.execute(sa.text(spec["copy_sql"]))
        op.drop_table(table_name)
        op.rename_table(temp_table, table_name)
        for statement in spec["indexes"]:
            op.execute(sa.text(statement))
