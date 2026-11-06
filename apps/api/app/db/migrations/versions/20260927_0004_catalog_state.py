"""Add private catalog trust, activation and durable request state.

Revision ID: 20260927_0004
Revises: 20260204_0003
"""

from alembic import op
from app.catalog.state_schema import V4_STATEMENTS
from app.db.legacy_catalog import preserve_incomplete_requests

revision = "20260927_0004"
down_revision = "20260204_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in V4_STATEMENTS:
        op.execute(statement)
    preserve_incomplete_requests(op.get_bind())


def downgrade() -> None:
    raise RuntimeError(
        "Restore a preupgrade backup with matching catalog state; destructive downgrade is unsupported"
    )
