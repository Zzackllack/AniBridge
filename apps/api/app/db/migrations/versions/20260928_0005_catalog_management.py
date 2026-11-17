"""Persist management status versions and provider update outcomes.

Revision ID: 20260928_0005
Revises: 20260927_0004
"""

from alembic import op
from app.catalog.management_schema import STATEMENTS

revision = "20260928_0005"
down_revision = "20260927_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError(
        "Use a verified backup with matching catalog state; destructive downgrade is unsupported"
    )
