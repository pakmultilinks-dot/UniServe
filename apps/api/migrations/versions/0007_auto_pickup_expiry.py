"""Phase 6 — Auto pickup expiry columns

Revision ID: 0007
Revises: 0006_order_operations
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # orders table — uncollected_at timestamp for auto-expiry tracking
    op.add_column(
        "orders",
        sa.Column("uncollected_at", sa.DateTime(timezone=True), nullable=True),
    )

    # cafeterias table — closing_time for earlier-of pickup deadline rule
    op.add_column(
        "cafeterias",
        sa.Column("closing_time", sa.String(5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cafeterias", "closing_time")
    op.drop_column("orders", "uncollected_at")
