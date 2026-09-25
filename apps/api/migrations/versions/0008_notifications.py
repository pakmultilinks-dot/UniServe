"""Phase 6 — Notifications table

Revision ID: 0008
Revises: 0007_auto_pickup_expiry
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("source_event_type", sa.String(50), nullable=True),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes
    op.create_index("idx_notification_user_id", "notifications", ["user_id"])
    op.create_index(
        "idx_notification_user_read",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        "idx_notification_created_at",
        "notifications",
        ["created_at"],
    )
    op.create_index(
        "idx_notification_source_event",
        "notifications",
        ["source_event_type", "source_event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("notifications")
