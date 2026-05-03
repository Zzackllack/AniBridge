"""Add staged provider index status and title enrichment state

Revision ID: 20260429_0006
Revises: 20260429_0005
Create Date: 2026-04-29 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_0006"
down_revision = "20260429_0005"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("providerindexstatus"):
        with op.batch_alter_table("providerindexstatus") as batch_op:
            if not _has_column(inspector, "providerindexstatus", "active_stage"):
                batch_op.add_column(
                    sa.Column("active_stage", sa.String(), nullable=True)
                )
                batch_op.create_index(
                    "ix_providerindexstatus_active_stage",
                    ["active_stage"],
                    unique=False,
                )
            if not _has_column(inspector, "providerindexstatus", "title_index_status"):
                batch_op.add_column(
                    sa.Column(
                        "title_index_status",
                        sa.String(),
                        nullable=False,
                        server_default="pending",
                    )
                )
                batch_op.create_index(
                    "ix_providerindexstatus_title_index_status",
                    ["title_index_status"],
                    unique=False,
                )
            if not _has_column(
                inspector, "providerindexstatus", "title_index_ready_at"
            ):
                batch_op.add_column(
                    sa.Column("title_index_ready_at", sa.DateTime(), nullable=True)
                )
                batch_op.create_index(
                    "ix_providerindexstatus_title_index_ready_at",
                    ["title_index_ready_at"],
                    unique=False,
                )
            if not _has_column(
                inspector, "providerindexstatus", "title_index_next_retry_after"
            ):
                batch_op.add_column(
                    sa.Column(
                        "title_index_next_retry_after",
                        sa.DateTime(),
                        nullable=True,
                    )
                )
                batch_op.create_index(
                    "ix_providerindexstatus_title_index_next_retry_after",
                    ["title_index_next_retry_after"],
                    unique=False,
                )
            if not _has_column(
                inspector, "providerindexstatus", "detail_enrichment_status"
            ):
                batch_op.add_column(
                    sa.Column(
                        "detail_enrichment_status",
                        sa.String(),
                        nullable=False,
                        server_default="pending",
                    )
                )
                batch_op.create_index(
                    "ix_providerindexstatus_detail_enrichment_status",
                    ["detail_enrichment_status"],
                    unique=False,
                )
            if not _has_column(inspector, "providerindexstatus", "detail_ready_at"):
                batch_op.add_column(
                    sa.Column("detail_ready_at", sa.DateTime(), nullable=True)
                )
                batch_op.create_index(
                    "ix_providerindexstatus_detail_ready_at",
                    ["detail_ready_at"],
                    unique=False,
                )
            if not _has_column(
                inspector, "providerindexstatus", "detail_next_retry_after"
            ):
                batch_op.add_column(
                    sa.Column("detail_next_retry_after", sa.DateTime(), nullable=True)
                )
                batch_op.create_index(
                    "ix_providerindexstatus_detail_next_retry_after",
                    ["detail_next_retry_after"],
                    unique=False,
                )
            if not _has_column(
                inspector, "providerindexstatus", "canonical_enrichment_status"
            ):
                batch_op.add_column(
                    sa.Column(
                        "canonical_enrichment_status",
                        sa.String(),
                        nullable=False,
                        server_default="pending",
                    )
                )
                batch_op.create_index(
                    "ix_providerindexstatus_canonical_enrichment_status",
                    ["canonical_enrichment_status"],
                    unique=False,
                )
            if not _has_column(inspector, "providerindexstatus", "canonical_ready_at"):
                batch_op.add_column(
                    sa.Column("canonical_ready_at", sa.DateTime(), nullable=True)
                )
                batch_op.create_index(
                    "ix_providerindexstatus_canonical_ready_at",
                    ["canonical_ready_at"],
                    unique=False,
                )
            if not _has_column(
                inspector, "providerindexstatus", "canonical_next_retry_after"
            ):
                batch_op.add_column(
                    sa.Column(
                        "canonical_next_retry_after",
                        sa.DateTime(),
                        nullable=True,
                    )
                )
                batch_op.create_index(
                    "ix_providerindexstatus_canonical_next_retry_after",
                    ["canonical_next_retry_after"],
                    unique=False,
                )

    if inspector.has_table("providertitleindexstate"):
        with op.batch_alter_table("providertitleindexstate") as batch_op:
            staged_columns = [
                ("detail_status", sa.String(), "pending"),
                ("detail_last_attempted_at", sa.DateTime(), None),
                ("detail_last_success_at", sa.DateTime(), None),
                ("detail_next_retry_after", sa.DateTime(), None),
                ("detail_failure_count", sa.Integer(), 0),
                ("detail_last_error_summary", sa.String(), None),
                ("canonical_status", sa.String(), "pending"),
                ("canonical_last_attempted_at", sa.DateTime(), None),
                ("canonical_last_success_at", sa.DateTime(), None),
                ("canonical_next_retry_after", sa.DateTime(), None),
                ("canonical_failure_count", sa.Integer(), 0),
                ("canonical_last_error_summary", sa.String(), None),
            ]
            for name, column_type, default in staged_columns:
                if _has_column(inspector, "providertitleindexstate", name):
                    continue
                kwargs = {"nullable": True}
                if default is not None:
                    kwargs["server_default"] = str(default)
                    kwargs["nullable"] = False
                batch_op.add_column(sa.Column(name, column_type, **kwargs))
                if (
                    name.endswith("_status")
                    or name.endswith("_at")
                    or name.endswith("_retry_after")
                ):
                    batch_op.create_index(
                        f"ix_providertitleindexstate_{name}",
                        [name],
                        unique=False,
                    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    providerindexstatus_indexes = [
        "ix_providerindexstatus_canonical_next_retry_after",
        "ix_providerindexstatus_canonical_ready_at",
        "ix_providerindexstatus_canonical_enrichment_status",
        "ix_providerindexstatus_detail_next_retry_after",
        "ix_providerindexstatus_detail_ready_at",
        "ix_providerindexstatus_detail_enrichment_status",
        "ix_providerindexstatus_title_index_next_retry_after",
        "ix_providerindexstatus_title_index_ready_at",
        "ix_providerindexstatus_title_index_status",
        "ix_providerindexstatus_active_stage",
    ]
    providerindexstatus_columns = [
        "canonical_next_retry_after",
        "canonical_ready_at",
        "canonical_enrichment_status",
        "detail_next_retry_after",
        "detail_ready_at",
        "detail_enrichment_status",
        "title_index_next_retry_after",
        "title_index_ready_at",
        "title_index_status",
        "active_stage",
    ]
    if inspector.has_table("providerindexstatus"):
        existing_columns = {
            column["name"] for column in inspector.get_columns("providerindexstatus")
        }
        existing_indexes = {
            index["name"] for index in inspector.get_indexes("providerindexstatus")
        }
        with op.batch_alter_table("providerindexstatus") as batch_op:
            for index_name in providerindexstatus_indexes:
                if index_name in existing_indexes:
                    batch_op.drop_index(index_name)
            for column_name in providerindexstatus_columns:
                if column_name in existing_columns:
                    batch_op.drop_column(column_name)

    staged_columns = [
        "canonical_last_error_summary",
        "canonical_failure_count",
        "canonical_next_retry_after",
        "canonical_last_success_at",
        "canonical_last_attempted_at",
        "canonical_status",
        "detail_last_error_summary",
        "detail_failure_count",
        "detail_next_retry_after",
        "detail_last_success_at",
        "detail_last_attempted_at",
        "detail_status",
    ]
    if inspector.has_table("providertitleindexstate"):
        existing_columns = {
            column["name"]
            for column in inspector.get_columns("providertitleindexstate")
        }
        existing_indexes = {
            index["name"] for index in inspector.get_indexes("providertitleindexstate")
        }
        with op.batch_alter_table("providertitleindexstate") as batch_op:
            for column_name in staged_columns:
                index_name = f"ix_providertitleindexstate_{column_name}"
                if index_name in existing_indexes:
                    batch_op.drop_index(index_name)
                if column_name in existing_columns:
                    batch_op.drop_column(column_name)
