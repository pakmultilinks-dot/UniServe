"""Phase 51 — refund rejection resolution column.

Adds ``rejection_reason`` to the refunds table so an admin/manager
rejection is fully auditable (who rejected it, when, and why).

Scope justification (Phase 51 spec):
- This is the minimal change enabling a real admin rejection workflow.
- No existing column stores the admin's rejection reason — ``reason`` and
  ``reason_note`` belong to the requester's original request, not to the
  admin's decision.
- RefundStatus gains the ``rejected`` member WITHOUT a migration: the
  status column is a String column (StrEnum with native_enum=False), so
  existing rows are unaffected and the new member needs no DDL.
- RefundEvent already exists and records ``refund_rejected`` events
  without any schema change.

Reversible: dropping the column restores the previous schema.
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refunds", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("refunds", "rejection_reason")
