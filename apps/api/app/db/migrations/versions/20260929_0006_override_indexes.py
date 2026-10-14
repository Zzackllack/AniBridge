"""Index local corrections and bounded idempotency cleanup.

Revision ID: 20260929_0006
Revises: 20260928_0005
"""

from alembic import op
from app.catalog.override_indexes import STATEMENTS

revision = "20260929_0006"
down_revision = "20260928_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Use a verified backup with matching catalog state")
