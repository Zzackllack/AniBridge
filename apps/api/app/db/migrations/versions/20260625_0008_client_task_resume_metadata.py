"""Store download metadata required to resume paused client tasks.

Revision ID: 20260625_0008
Revises: 20260430_0007
Create Date: 2026-06-25 03:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260625_0008"
down_revision = "20260430_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {
        column["name"] for column in inspector.get_columns("clienttask")
    }
    with op.batch_alter_table("clienttask") as batch_op:
        if "provider" not in existing_columns:
            batch_op.add_column(sa.Column("provider", sa.String(), nullable=True))
        if "mode" not in existing_columns:
            batch_op.add_column(sa.Column("mode", sa.String(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {
        column["name"] for column in inspector.get_columns("clienttask")
    }
    with op.batch_alter_table("clienttask") as batch_op:
        if "mode" in existing_columns:
            batch_op.drop_column("mode")
        if "provider" in existing_columns:
            batch_op.drop_column("provider")
