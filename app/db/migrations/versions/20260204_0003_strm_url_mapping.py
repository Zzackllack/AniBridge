"""Add STRM URL mapping table

Revision ID: 20260204_0003
Revises: 20260203_0002
Create Date: 2026-02-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260204_0003"
down_revision = "20260203_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create the `strmurlmapping` table and its indexes if the table does not already exist.

    Creates a table named `strmurlmapping` with columns:
    - `site` (String, not null)
    - `slug` (String, not null)
    - `season` (Integer, not null)
    - `episode` (Integer, not null)
    - `language` (String, not null)
    - `provider` (String, not null)
    - `resolved_url` (String, not null)
    - `provider_used` (String, nullable)
    - `resolved_headers` (JSON, nullable)
    - `resolved_at` (DateTime, not null)
    - `updated_at` (DateTime, not null)

    Establishes a composite primary key on (`site`, `slug`, `season`, `episode`, `language`, `provider`) named `pk_strmurlmapping`, and creates non-unique indexes `ix_strmurlmapping_resolved_at` on `resolved_at` and `ix_strmurlmapping_updated_at` on `updated_at`.
    """
    conn = op.get_bind()
    table_present = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='strmurlmapping'"
    ).fetchone()
    if table_present:
        return
    op.create_table(
        "strmurlmapping",
        sa.Column("site", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("episode", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("resolved_url", sa.String(), nullable=False),
        sa.Column("provider_used", sa.String(), nullable=True),
        sa.Column("resolved_headers", sa.JSON(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint(
            "site",
            "slug",
            "season",
            "episode",
            "language",
            "provider",
            name="pk_strmurlmapping",
        ),
    )
    op.create_index(
        "ix_strmurlmapping_resolved_at",
        "strmurlmapping",
        ["resolved_at"],
        unique=False,
    )
    op.create_index(
        "ix_strmurlmapping_updated_at",
        "strmurlmapping",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """
    Downgrades the database schema by removing the strmurlmapping table and its indexes if present.

    Performs a presence check and, if the table exists, drops the indexes `ix_strmurlmapping_updated_at`
    and `ix_strmurlmapping_resolved_at` and then drops the `strmurlmapping` table. No action is taken
    if the table does not exist.
    """
    conn = op.get_bind()
    table_present = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='strmurlmapping'"
    ).fetchone()
    if not table_present:
        return
    op.drop_index("ix_strmurlmapping_updated_at", table_name="strmurlmapping")
    op.drop_index("ix_strmurlmapping_resolved_at", table_name="strmurlmapping")
    op.drop_table("strmurlmapping")
