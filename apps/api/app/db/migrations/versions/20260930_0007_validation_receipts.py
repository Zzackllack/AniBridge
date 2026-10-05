"""Version private snapshot admission receipts after validator fixes.

Revision ID: 20260930_0007
Revises: 20260929_0006
"""

from alembic import op
from app.catalog.state_schema import VALIDATION_STATEMENTS

revision = "20260930_0007"
down_revision = "20260929_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in VALIDATION_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Use a verified backup with matching catalog state")
