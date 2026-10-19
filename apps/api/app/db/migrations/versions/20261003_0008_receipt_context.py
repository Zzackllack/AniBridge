"""Bind retained admission receipts to origin and trusted keys.

Revision ID: 20261003_0008
Revises: 20260930_0007
"""

from alembic import op
from app.catalog.state_schema import RECEIPT_STATEMENTS

revision = "20261003_0008"
down_revision = "20260930_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in RECEIPT_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Use a verified backup with matching catalog state")
