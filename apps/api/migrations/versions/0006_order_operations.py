"""Phase 6 — Order Operations & Fulfillment

Revision ID: 0006
Revises: 0005_payments_and_refunds
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===================================================================
    # orders table — new operational columns
    # ===================================================================
    op.add_column("orders", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("preparation_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("pickup_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("eta_minutes", sa.Integer, nullable=True))
    op.add_column("orders", sa.Column("collection_method", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("rejection_reason", sa.String(30), nullable=True))
    op.add_column("orders", sa.Column("rejection_note", sa.Text, nullable=True))
    op.add_column("orders", sa.Column("preparation_started", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # ===================================================================
    # users table — ordering suspension fields
    # ===================================================================
    op.add_column("users", sa.Column("ordering_suspended", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("ordering_suspended_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("ordering_suspension_reason", sa.Text, nullable=True))
    op.add_column("users", sa.Column("no_show_count", sa.Integer(), nullable=False, server_default=sa.text("0")))

    # ===================================================================
    # menu_items table — preparation time
    # ===================================================================
    op.add_column("menu_items", sa.Column("preparation_time_minutes", sa.Integer(), nullable=False, server_default=sa.text("15")))

    # ===================================================================
    # cafeterias table — preparation capacity
    # ===================================================================
    op.add_column("cafeterias", sa.Column("preparation_capacity", sa.Integer(), nullable=False, server_default=sa.text("10")))

    # ===================================================================
    # no_shows table
    # ===================================================================
    op.create_table(
        "no_shows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_noshow_user", "no_shows", ["user_id"])
    op.create_index("idx_noshow_cafeteria", "no_shows", ["cafeteria_id"])
    op.create_index("idx_noshow_created", "no_shows", ["created_at"])


def downgrade() -> None:
    op.drop_table("no_shows")
    op.drop_column("cafeterias", "preparation_capacity")
    op.drop_column("menu_items", "preparation_time_minutes")
    op.drop_column("users", "no_show_count")
    op.drop_column("users", "ordering_suspension_reason")
    op.drop_column("users", "ordering_suspended_until")
    op.drop_column("users", "ordering_suspended")
    op.drop_column("orders", "preparation_started")
    op.drop_column("orders", "rejection_note")
    op.drop_column("orders", "rejection_reason")
    op.drop_column("orders", "collection_method")
    op.drop_column("orders", "eta_minutes")
    op.drop_column("orders", "pickup_deadline")
    op.drop_column("orders", "ready_at")
    op.drop_column("orders", "preparation_started_at")
    op.drop_column("orders", "confirmed_at")
