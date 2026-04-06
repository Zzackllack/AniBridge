"""Initial schema

Revision ID: 20260203_0001
Revises:
Create Date: 2026-02-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260203_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("downloaded_bytes", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.Integer(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("eta", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("result_path", sa.String(), nullable=True),
        sa.Column("source_site", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_job_status", "job", ["status"], unique=False)
    op.create_index("ix_job_source_site", "job", ["source_site"], unique=False)
    op.create_index("ix_job_created_at", "job", ["created_at"], unique=False)
    op.create_index("ix_job_updated_at", "job", ["updated_at"], unique=False)

    op.create_table(
        "episodeavailability",
        sa.Column("slug", sa.String(), primary_key=True, nullable=False),
        sa.Column("season", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("episode", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("language", sa.String(), primary_key=True, nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("vcodec", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_episodeavailability_checked_at",
        "episodeavailability",
        ["checked_at"],
        unique=False,
    )

    op.create_table(
        "clienttask",
        sa.Column("hash", sa.String(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("episode", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("site", sa.String(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("save_path", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("added_on", sa.DateTime(), nullable=False),
        sa.Column("completion_on", sa.DateTime(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
    )
    op.create_index("ix_clienttask_added_on", "clienttask", ["added_on"], unique=False)
    op.create_index("ix_clienttask_job_id", "clienttask", ["job_id"], unique=False)
    op.create_index("ix_clienttask_site", "clienttask", ["site"], unique=False)
    op.create_index("ix_clienttask_state", "clienttask", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clienttask_state", table_name="clienttask")
    op.drop_index("ix_clienttask_site", table_name="clienttask")
    op.drop_index("ix_clienttask_job_id", table_name="clienttask")
    op.drop_index("ix_clienttask_added_on", table_name="clienttask")
    op.drop_table("clienttask")

    op.drop_index("ix_episodeavailability_checked_at", table_name="episodeavailability")
    op.drop_table("episodeavailability")

    op.drop_index("ix_job_updated_at", table_name="job")
    op.drop_index("ix_job_created_at", table_name="job")
    op.drop_index("ix_job_source_site", table_name="job")
    op.drop_index("ix_job_status", table_name="job")
    op.drop_table("job")
