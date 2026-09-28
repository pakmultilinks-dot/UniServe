"""Add server-side checkout idempotency keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("checkout_idempotency_key", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_order_checkout_idempotency_key", "orders", ["checkout_idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_order_checkout_idempotency_key", "orders", type_="unique")
    op.drop_column("orders", "checkout_idempotency_key")
