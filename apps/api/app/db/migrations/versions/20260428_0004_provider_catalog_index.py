"""Add provider catalog index and canonical mapping tables

Revision ID: 20260428_0004
Revises: 20260204_0003
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0004"
down_revision = "20260204_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("providerindexstatus"):
        op.create_table(
            "providerindexstatus",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("refresh_interval_hours", sa.Float(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("current_generation", sa.String(), nullable=True),
            sa.Column("latest_success_generation", sa.String(), nullable=True),
            sa.Column("latest_started_at", sa.DateTime(), nullable=True),
            sa.Column("latest_completed_at", sa.DateTime(), nullable=True),
            sa.Column("latest_success_at", sa.DateTime(), nullable=True),
            sa.Column("next_refresh_after", sa.DateTime(), nullable=True),
            sa.Column("bootstrap_completed", sa.Boolean(), nullable=False),
            sa.Column("failure_count", sa.Integer(), nullable=False),
            sa.Column("last_error_summary", sa.String(), nullable=True),
            sa.Column("cursor_title_slug", sa.String(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("provider", name="pk_providerindexstatus"),
        )
        op.create_index(
            "ix_providerindexstatus_status",
            "providerindexstatus",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_providerindexstatus_latest_started_at",
            "providerindexstatus",
            ["latest_started_at"],
            unique=False,
        )
        op.create_index(
            "ix_providerindexstatus_latest_completed_at",
            "providerindexstatus",
            ["latest_completed_at"],
            unique=False,
        )
        op.create_index(
            "ix_providerindexstatus_latest_success_at",
            "providerindexstatus",
            ["latest_success_at"],
            unique=False,
        )
        op.create_index(
            "ix_providerindexstatus_next_refresh_after",
            "providerindexstatus",
            ["next_refresh_after"],
            unique=False,
        )
        op.create_index(
            "ix_providerindexstatus_bootstrap_completed",
            "providerindexstatus",
            ["bootstrap_completed"],
            unique=False,
        )
        op.create_index(
            "ix_providerindexstatus_updated_at",
            "providerindexstatus",
            ["updated_at"],
            unique=False,
        )

    if not inspector.has_table("providertitleindexstate"):
        op.create_table(
            "providertitleindexstate",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("last_attempted_at", sa.DateTime(), nullable=True),
            sa.Column("last_success_at", sa.DateTime(), nullable=True),
            sa.Column("failure_count", sa.Integer(), nullable=False),
            sa.Column("last_error_summary", sa.String(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider", "slug", name="pk_providertitleindexstate"
            ),
        )
        op.create_index(
            "ix_providertitleindexstate_last_attempted_at",
            "providertitleindexstate",
            ["last_attempted_at"],
            unique=False,
        )
        op.create_index(
            "ix_providertitleindexstate_last_success_at",
            "providertitleindexstate",
            ["last_success_at"],
            unique=False,
        )
        op.create_index(
            "ix_providertitleindexstate_updated_at",
            "providertitleindexstate",
            ["updated_at"],
            unique=False,
        )

    if not inspector.has_table("providercatalogtitle"):
        op.create_table(
            "providercatalogtitle",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("normalized_title", sa.String(), nullable=False),
            sa.Column("media_type_hint", sa.String(), nullable=False),
            sa.Column("relative_path", sa.String(), nullable=False),
            sa.Column("indexed_generation", sa.String(), nullable=False),
            sa.Column("last_indexed_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("provider", "slug", name="pk_providercatalogtitle"),
        )
        op.create_index(
            "ix_providercatalogtitle_title",
            "providercatalogtitle",
            ["title"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogtitle_normalized_title",
            "providercatalogtitle",
            ["normalized_title"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogtitle_media_type_hint",
            "providercatalogtitle",
            ["media_type_hint"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogtitle_indexed_generation",
            "providercatalogtitle",
            ["indexed_generation"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogtitle_last_indexed_at",
            "providercatalogtitle",
            ["last_indexed_at"],
            unique=False,
        )

    if not inspector.has_table("providercatalogalias"):
        op.create_table(
            "providercatalogalias",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("alias", sa.String(), nullable=False),
            sa.Column("normalized_alias", sa.String(), nullable=False),
            sa.Column("indexed_generation", sa.String(), nullable=False),
            sa.Column("last_indexed_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider", "slug", "alias", name="pk_providercatalogalias"
            ),
        )
        op.create_index(
            "ix_providercatalogalias_normalized_alias",
            "providercatalogalias",
            ["normalized_alias"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogalias_indexed_generation",
            "providercatalogalias",
            ["indexed_generation"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogalias_last_indexed_at",
            "providercatalogalias",
            ["last_indexed_at"],
            unique=False,
        )

    if not inspector.has_table("providercatalogepisode"):
        op.create_table(
            "providercatalogepisode",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("season", sa.Integer(), nullable=False),
            sa.Column("episode", sa.Integer(), nullable=False),
            sa.Column("title_primary", sa.String(), nullable=True),
            sa.Column("title_secondary", sa.String(), nullable=True),
            sa.Column("relative_path", sa.String(), nullable=False),
            sa.Column("media_type_hint", sa.String(), nullable=False),
            sa.Column("indexed_generation", sa.String(), nullable=False),
            sa.Column("last_indexed_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider",
                "slug",
                "season",
                "episode",
                name="pk_providercatalogepisode",
            ),
        )
        op.create_index(
            "ix_providercatalogepisode_media_type_hint",
            "providercatalogepisode",
            ["media_type_hint"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogepisode_indexed_generation",
            "providercatalogepisode",
            ["indexed_generation"],
            unique=False,
        )
        op.create_index(
            "ix_providercatalogepisode_last_indexed_at",
            "providercatalogepisode",
            ["last_indexed_at"],
            unique=False,
        )

    if not inspector.has_table("providerepisodelanguage"):
        op.create_table(
            "providerepisodelanguage",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("season", sa.Integer(), nullable=False),
            sa.Column("episode", sa.Integer(), nullable=False),
            sa.Column("language", sa.String(), nullable=False),
            sa.Column("normalized_language", sa.String(), nullable=False),
            sa.Column("host_hints", sa.JSON(), nullable=True),
            sa.Column("indexed_generation", sa.String(), nullable=False),
            sa.Column("last_indexed_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider",
                "slug",
                "season",
                "episode",
                "language",
                name="pk_providerepisodelanguage",
            ),
        )
        op.create_index(
            "ix_providerepisodelanguage_normalized_language",
            "providerepisodelanguage",
            ["normalized_language"],
            unique=False,
        )
        op.create_index(
            "ix_providerepisodelanguage_indexed_generation",
            "providerepisodelanguage",
            ["indexed_generation"],
            unique=False,
        )
        op.create_index(
            "ix_providerepisodelanguage_last_indexed_at",
            "providerepisodelanguage",
            ["last_indexed_at"],
            unique=False,
        )

    if not inspector.has_table("canonicalseries"):
        op.create_table(
            "canonicalseries",
            sa.Column("tvdb_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("normalized_title", sa.String(), nullable=False),
            sa.Column("tmdb_id", sa.Integer(), nullable=True),
            sa.Column("imdb_id", sa.String(), nullable=True),
            sa.Column("tvmaze_id", sa.Integer(), nullable=True),
            sa.Column("anilist_id", sa.Integer(), nullable=True),
            sa.Column("mal_id", sa.Integer(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("tvdb_id", name="pk_canonicalseries"),
        )
        op.create_index(
            "ix_canonicalseries_title", "canonicalseries", ["title"], unique=False
        )
        op.create_index(
            "ix_canonicalseries_normalized_title",
            "canonicalseries",
            ["normalized_title"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalseries_tmdb_id", "canonicalseries", ["tmdb_id"], unique=False
        )
        op.create_index(
            "ix_canonicalseries_imdb_id", "canonicalseries", ["imdb_id"], unique=False
        )
        op.create_index(
            "ix_canonicalseries_tvmaze_id",
            "canonicalseries",
            ["tvmaze_id"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalseries_anilist_id",
            "canonicalseries",
            ["anilist_id"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalseries_mal_id", "canonicalseries", ["mal_id"], unique=False
        )
        op.create_index(
            "ix_canonicalseries_last_synced_at",
            "canonicalseries",
            ["last_synced_at"],
            unique=False,
        )

    if not inspector.has_table("canonicalseriesalias"):
        op.create_table(
            "canonicalseriesalias",
            sa.Column("tvdb_id", sa.Integer(), nullable=False),
            sa.Column("alias", sa.String(), nullable=False),
            sa.Column("normalized_alias", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("tvdb_id", "alias", name="pk_canonicalseriesalias"),
        )
        op.create_index(
            "ix_canonicalseriesalias_normalized_alias",
            "canonicalseriesalias",
            ["normalized_alias"],
            unique=False,
        )

    if not inspector.has_table("canonicalepisode"):
        op.create_table(
            "canonicalepisode",
            sa.Column("tvdb_id", sa.Integer(), nullable=False),
            sa.Column("season", sa.Integer(), nullable=False),
            sa.Column("episode", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("normalized_title", sa.String(), nullable=False),
            sa.Column("last_synced_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "tvdb_id", "season", "episode", name="pk_canonicalepisode"
            ),
        )
        op.create_index(
            "ix_canonicalepisode_title",
            "canonicalepisode",
            ["title"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalepisode_normalized_title",
            "canonicalepisode",
            ["normalized_title"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalepisode_last_synced_at",
            "canonicalepisode",
            ["last_synced_at"],
            unique=False,
        )

    if not inspector.has_table("canonicalmovie"):
        op.create_table(
            "canonicalmovie",
            sa.Column("tmdb_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("normalized_title", sa.String(), nullable=False),
            sa.Column("release_year", sa.Integer(), nullable=False),
            sa.Column("imdb_id", sa.String(), nullable=True),
            sa.Column("tvdb_id", sa.Integer(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("tmdb_id", name="pk_canonicalmovie"),
        )
        op.create_index(
            "ix_canonicalmovie_title", "canonicalmovie", ["title"], unique=False
        )
        op.create_index(
            "ix_canonicalmovie_normalized_title",
            "canonicalmovie",
            ["normalized_title"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalmovie_release_year",
            "canonicalmovie",
            ["release_year"],
            unique=False,
        )
        op.create_index(
            "ix_canonicalmovie_imdb_id", "canonicalmovie", ["imdb_id"], unique=False
        )
        op.create_index(
            "ix_canonicalmovie_tvdb_id", "canonicalmovie", ["tvdb_id"], unique=False
        )
        op.create_index(
            "ix_canonicalmovie_last_synced_at",
            "canonicalmovie",
            ["last_synced_at"],
            unique=False,
        )

    if not inspector.has_table("providerseriesmapping"):
        op.create_table(
            "providerseriesmapping",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("tvdb_id", sa.Integer(), nullable=False),
            sa.Column("confidence", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("rationale", sa.String(), nullable=True),
            sa.Column("last_verified_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider", "slug", "tvdb_id", name="pk_providerseriesmapping"
            ),
        )
        op.create_index(
            "ix_providerseriesmapping_confidence",
            "providerseriesmapping",
            ["confidence"],
            unique=False,
        )
        op.create_index(
            "ix_providerseriesmapping_source",
            "providerseriesmapping",
            ["source"],
            unique=False,
        )
        op.create_index(
            "ix_providerseriesmapping_last_verified_at",
            "providerseriesmapping",
            ["last_verified_at"],
            unique=False,
        )

    if not inspector.has_table("providerepisodemapping"):
        op.create_table(
            "providerepisodemapping",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("provider_season", sa.Integer(), nullable=False),
            sa.Column("provider_episode", sa.Integer(), nullable=False),
            sa.Column("tvdb_id", sa.Integer(), nullable=False),
            sa.Column("canonical_season", sa.Integer(), nullable=False),
            sa.Column("canonical_episode", sa.Integer(), nullable=False),
            sa.Column("confidence", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("rationale", sa.String(), nullable=True),
            sa.Column("last_verified_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider",
                "slug",
                "provider_season",
                "provider_episode",
                "tvdb_id",
                "canonical_season",
                "canonical_episode",
                name="pk_providerepisodemapping",
            ),
        )
        op.create_index(
            "ix_providerepisodemapping_confidence",
            "providerepisodemapping",
            ["confidence"],
            unique=False,
        )
        op.create_index(
            "ix_providerepisodemapping_source",
            "providerepisodemapping",
            ["source"],
            unique=False,
        )
        op.create_index(
            "ix_providerepisodemapping_last_verified_at",
            "providerepisodemapping",
            ["last_verified_at"],
            unique=False,
        )

    if not inspector.has_table("providermoviemapping"):
        op.create_table(
            "providermoviemapping",
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("tmdb_id", sa.Integer(), nullable=False),
            sa.Column("confidence", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("rationale", sa.String(), nullable=True),
            sa.Column("last_verified_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "provider", "slug", "tmdb_id", name="pk_providermoviemapping"
            ),
        )
        op.create_index(
            "ix_providermoviemapping_confidence",
            "providermoviemapping",
            ["confidence"],
            unique=False,
        )
        op.create_index(
            "ix_providermoviemapping_source",
            "providermoviemapping",
            ["source"],
            unique=False,
        )
        op.create_index(
            "ix_providermoviemapping_last_verified_at",
            "providermoviemapping",
            ["last_verified_at"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    table_indexes = {
        "providermoviemapping": [
            "ix_providermoviemapping_last_verified_at",
            "ix_providermoviemapping_source",
            "ix_providermoviemapping_confidence",
        ],
        "providerepisodemapping": [
            "ix_providerepisodemapping_last_verified_at",
            "ix_providerepisodemapping_source",
            "ix_providerepisodemapping_confidence",
        ],
        "providerseriesmapping": [
            "ix_providerseriesmapping_last_verified_at",
            "ix_providerseriesmapping_source",
            "ix_providerseriesmapping_confidence",
        ],
        "canonicalmovie": [
            "ix_canonicalmovie_last_synced_at",
            "ix_canonicalmovie_tvdb_id",
            "ix_canonicalmovie_imdb_id",
            "ix_canonicalmovie_release_year",
            "ix_canonicalmovie_normalized_title",
            "ix_canonicalmovie_title",
        ],
        "canonicalepisode": [
            "ix_canonicalepisode_last_synced_at",
            "ix_canonicalepisode_normalized_title",
            "ix_canonicalepisode_title",
        ],
        "canonicalseriesalias": ["ix_canonicalseriesalias_normalized_alias"],
        "canonicalseries": [
            "ix_canonicalseries_last_synced_at",
            "ix_canonicalseries_mal_id",
            "ix_canonicalseries_anilist_id",
            "ix_canonicalseries_tvmaze_id",
            "ix_canonicalseries_imdb_id",
            "ix_canonicalseries_tmdb_id",
            "ix_canonicalseries_normalized_title",
            "ix_canonicalseries_title",
        ],
        "providerepisodelanguage": [
            "ix_providerepisodelanguage_last_indexed_at",
            "ix_providerepisodelanguage_indexed_generation",
            "ix_providerepisodelanguage_normalized_language",
        ],
        "providercatalogepisode": [
            "ix_providercatalogepisode_last_indexed_at",
            "ix_providercatalogepisode_indexed_generation",
            "ix_providercatalogepisode_media_type_hint",
        ],
        "providercatalogalias": [
            "ix_providercatalogalias_last_indexed_at",
            "ix_providercatalogalias_indexed_generation",
            "ix_providercatalogalias_normalized_alias",
        ],
        "providercatalogtitle": [
            "ix_providercatalogtitle_last_indexed_at",
            "ix_providercatalogtitle_indexed_generation",
            "ix_providercatalogtitle_media_type_hint",
            "ix_providercatalogtitle_normalized_title",
            "ix_providercatalogtitle_title",
        ],
        "providertitleindexstate": [
            "ix_providertitleindexstate_updated_at",
            "ix_providertitleindexstate_last_success_at",
            "ix_providertitleindexstate_last_attempted_at",
        ],
        "providerindexstatus": [
            "ix_providerindexstatus_updated_at",
            "ix_providerindexstatus_bootstrap_completed",
            "ix_providerindexstatus_next_refresh_after",
            "ix_providerindexstatus_latest_success_at",
            "ix_providerindexstatus_latest_completed_at",
            "ix_providerindexstatus_latest_started_at",
            "ix_providerindexstatus_status",
        ],
    }
    for table, indexes in table_indexes.items():
        if not inspector.has_table(table):
            continue
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
