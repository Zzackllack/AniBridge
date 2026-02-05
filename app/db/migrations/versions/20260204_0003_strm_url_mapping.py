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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("strmurlmapping"):
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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table("strmurlmapping"):
        return
    op.drop_index("ix_strmurlmapping_updated_at", table_name="strmurlmapping")
    op.drop_index("ix_strmurlmapping_resolved_at", table_name="strmurlmapping")
    op.drop_table("strmurlmapping")
