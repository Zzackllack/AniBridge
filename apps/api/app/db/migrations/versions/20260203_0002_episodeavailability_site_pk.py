"""Add site column to episodeavailability primary key

Revision ID: 20260203_0002
Revises: 20260203_0001
Create Date: 2026-02-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260203_0002"
down_revision = "20260203_0001"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    cols = conn.exec_driver_sql(f"PRAGMA table_info('{table}')").fetchall()
    return any(col[1] == column for col in cols)


def upgrade() -> None:
    conn = op.get_bind()
    table_present = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='episodeavailability'"
    ).fetchone()
    if not table_present:
        return

    if _has_column(conn, "episodeavailability", "site"):
        return

    conn.exec_driver_sql(
        """
        CREATE TABLE episodeavailability_new (
            slug TEXT NOT NULL,
            season INTEGER NOT NULL,
            episode INTEGER NOT NULL,
            language TEXT NOT NULL,
            site TEXT NOT NULL DEFAULT 'aniworld.to',
            available BOOLEAN NOT NULL,
            height INTEGER,
            vcodec TEXT,
            provider TEXT,
            checked_at DATETIME NOT NULL,
            extra JSON,
            PRIMARY KEY (slug, season, episode, language, site)
        )
        """
    )
    conn.exec_driver_sql(
        """
        INSERT INTO episodeavailability_new (
            slug, season, episode, language, site,
            available, height, vcodec, provider, checked_at, extra
        )
        SELECT
            slug, season, episode, language,
            'aniworld.to' AS site,
            available, height, vcodec, provider, checked_at, extra
        FROM episodeavailability
        """
    )
    conn.exec_driver_sql("DROP TABLE episodeavailability")
    conn.exec_driver_sql(
        "ALTER TABLE episodeavailability_new RENAME TO episodeavailability"
    )
    conn.exec_driver_sql(
        "CREATE INDEX ix_episodeavailability_checked_at ON episodeavailability(checked_at)"
    )


def downgrade() -> None:
    conn = op.get_bind()
    table_present = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='episodeavailability'"
    ).fetchone()
    if not table_present:
        return

    if not _has_column(conn, "episodeavailability", "site"):
        return

    conn.exec_driver_sql(
        """
        CREATE TABLE episodeavailability_old (
            slug TEXT NOT NULL,
            season INTEGER NOT NULL,
            episode INTEGER NOT NULL,
            language TEXT NOT NULL,
            available BOOLEAN NOT NULL,
            height INTEGER,
            vcodec TEXT,
            provider TEXT,
            checked_at DATETIME NOT NULL,
            extra JSON,
            PRIMARY KEY (slug, season, episode, language)
        )
        """
    )
    conn.exec_driver_sql(
        """
        INSERT INTO episodeavailability_old (
            slug, season, episode, language,
            available, height, vcodec, provider, checked_at, extra
        )
        SELECT
            slug, season, episode, language,
            available, height, vcodec, provider, checked_at, extra
        FROM episodeavailability
        """
    )
    conn.exec_driver_sql("DROP TABLE episodeavailability")
    conn.exec_driver_sql(
        "ALTER TABLE episodeavailability_old RENAME TO episodeavailability"
    )
    conn.exec_driver_sql(
        "CREATE INDEX ix_episodeavailability_checked_at ON episodeavailability(checked_at)"
    )
