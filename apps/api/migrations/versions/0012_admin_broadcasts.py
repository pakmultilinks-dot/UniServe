"""Phase 50 — Admin broadcast records (admin_broadcasts table).

One row per sent University Admin broadcast. Recipient delivery is stored
as ordinary per-user rows in the existing ``notifications`` table
(notification_type=admin_announcement, reference_type='broadcast',
reference_id=<admin_broadcasts.id>) — this migration does NOT touch the
notifications table, its indexes, or read/unread behavior.

The unique index on idempotency_key mirrors the Payment.idempotency_key
convention: replayed requests are detected at the DB level and cannot
create duplicate broadcasts.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_broadcasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_by_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by_name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(50), nullable=False),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipient_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "idx_admin_broadcast_created_at", "admin_broadcasts", ["created_at"]
    )
    op.create_index(
        "idx_admin_broadcast_idempotency_key",
        "admin_broadcasts",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_admin_broadcast_idempotency_key", table_name="admin_broadcasts")
    op.drop_index("idx_admin_broadcast_created_at", table_name="admin_broadcasts")
    op.drop_table("admin_broadcasts")
