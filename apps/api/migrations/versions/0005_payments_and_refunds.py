"""Phase 5 — Payments & Refunds

Revision ID: 0005
Revises: 0004_cart_and_order_system
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004_cart_and_order_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===================================================================
    # payments table
    # ===================================================================
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("provider_metadata_json", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_payment_order_id", "payments", ["order_id"])
    op.create_index("idx_payment_user_id", "payments", ["user_id"])
    op.create_index("idx_payment_status", "payments", ["status"])
    op.create_index(
        "idx_payment_idempotency_key", "payments", ["idempotency_key"], unique=True
    )
    op.create_index(
        "idx_payment_provider_reference",
        "payments",
        ["provider_reference"],
        unique=True,
        postgresql_where=sa.text("provider_reference IS NOT NULL"),
    )

    # ===================================================================
    # payment_attempts table
    # ===================================================================
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "payment_id",
            sa.String(36),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("provider_response_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_payment_attempt_payment_id", "payment_attempts", ["payment_id"])

    # ===================================================================
    # webhook_events table
    # ===================================================================
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_webhook_provider_event_id",
        "webhook_events",
        ["provider_event_id"],
        unique=True,
    )

    # ===================================================================
    # refunds table
    # ===================================================================
    op.create_table(
        "refunds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.String(36),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column(
            "requested_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "processed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_refund_order_id", "refunds", ["order_id"])
    op.create_index("idx_refund_payment_id", "refunds", ["payment_id"])
    op.create_index("idx_refund_user_id", "refunds", ["user_id"])
    op.create_index("idx_refund_status", "refunds", ["status"])
    op.create_index(
        "idx_refund_idempotency_key", "refunds", ["idempotency_key"], unique=True
    )

    # ===================================================================
    # refund_events table
    # ===================================================================
    op.create_table(
        "refund_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "refund_id",
            sa.String(36),
            sa.ForeignKey("refunds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column(
            "actor_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_refund_event_refund_id", "refund_events", ["refund_id"])


def downgrade() -> None:
    op.drop_table("refund_events")
    op.drop_table("refunds")
    op.drop_table("webhook_events")
    op.drop_table("payment_attempts")
    op.drop_table("payments")
