"""Phase 3 — Cafeteria & Menu Management tables.

Extends: cafeterias (description, phone, email, location, operating_hours, timezone, operational_status)
Creates: menu_items, daily_menus, daily_menu_items, menu_favorites, inventory_items, inventory_adjustments

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- New Enums (needed for op.add_column which doesn't auto-create) ----
    cafeteria_operational_status_enum = sa.Enum(
        "open",
        "closed",
        "closing_soon",
        "maintenance",
        name="cafeteria_operational_status",
    )
    cafeteria_operational_status_enum.create(op.get_bind(), checkfirst=True)

    # ---- Extend Cafeterias ----
    op.add_column(
        "cafeterias",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "cafeterias",
        sa.Column("phone", sa.String(20), nullable=True),
    )
    op.add_column(
        "cafeterias",
        sa.Column("email", sa.String(255), nullable=True),
    )
    op.add_column(
        "cafeterias",
        sa.Column("location", sa.Text(), nullable=True),
    )
    op.add_column(
        "cafeterias",
        sa.Column("operating_hours", sa.Text(), nullable=True),
    )
    op.add_column(
        "cafeterias",
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Karachi"),
    )
    op.add_column(
        "cafeterias",
        sa.Column(
            "operational_status",
            sa.Enum(
                "open", "closed", "closing_soon", "maintenance", name="cafeteria_operational_status"
            ),
            nullable=False,
            server_default="open",
        ),
    )
    op.create_index("idx_cafeteria_status", "cafeterias", ["operational_status"])

    # ---- Menu Items ----
    op.create_table(
        "menu_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "breakfast",
                "main_course",
                "side_dish",
                "dessert",
                "beverage",
                "snack",
                "salad",
                "soup",
                name="menu_category"
            ),
            nullable=False,
        ),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("dietary_info", sa.Text(), nullable=True),
        sa.Column("allergens", sa.Text(), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_menu_item_cafeteria", "menu_items", ["cafeteria_id"])
    op.create_index("idx_menu_item_category", "menu_items", ["category"])
    op.create_index("idx_menu_item_is_active", "menu_items", ["is_active"])

    # ---- Daily Menus ----
    op.create_table(
        "daily_menus",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("menu_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "archived", name="daily_menu_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("cafeteria_id", "menu_date", name="uq_daily_menu_cafeteria_date"),
    )
    op.create_index("idx_daily_menu_cafeteria", "daily_menus", ["cafeteria_id"])
    op.create_index("idx_daily_menu_date", "daily_menus", ["menu_date"])
    op.create_index("idx_daily_menu_status", "daily_menus", ["status"])

    # ---- Daily Menu Items (junction) ----
    op.create_table(
        "daily_menu_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "daily_menu_id",
            sa.String(36),
            sa.ForeignKey("daily_menus.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "menu_item_id",
            sa.String(36),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("special_price", sa.Integer(), nullable=True),
        sa.Column(
            "is_available_today", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("daily_menu_id", "menu_item_id", name="uq_daily_menu_item"),
    )
    op.create_index("idx_daily_menu_item_menu", "daily_menu_items", ["daily_menu_id"])
    op.create_index("idx_daily_menu_item_item", "daily_menu_items", ["menu_item_id"])

    # ---- Menu Favorites ----
    op.create_table(
        "menu_favorites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "menu_item_id",
            sa.String(36),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "menu_item_id", name="uq_menu_favorite"),
    )
    op.create_index("idx_menu_favorite_user", "menu_favorites", ["user_id"])
    op.create_index("idx_menu_favorite_item", "menu_favorites", ["menu_item_id"])

    # ---- Inventory Items ----
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "menu_item_id",
            sa.String(36),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "unit",
            sa.Enum("kg", "g", "L", "mL", "pcs", "portions", name="inventory_unit"),
            nullable=False,
        ),
        sa.Column("low_threshold", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("last_restocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_inventory_item_cafeteria", "inventory_items", ["cafeteria_id"])
    op.create_index("idx_inventory_item_menu_item", "inventory_items", ["menu_item_id"])

    # ---- Inventory Adjustments ----
    op.create_table(
        "inventory_adjustments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "inventory_item_id",
            sa.String(36),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("adjustment_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "adjusted_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_inventory_adj_item", "inventory_adjustments", ["inventory_item_id"])
    op.create_index("idx_inventory_adj_created", "inventory_adjustments", ["created_at"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("inventory_adjustments")
    op.drop_table("inventory_items")
    op.drop_table("menu_favorites")
    op.drop_table("daily_menu_items")
    op.drop_table("daily_menus")
    op.drop_table("menu_items")

    # Remove extended columns from cafeterias
    op.drop_index("idx_cafeteria_status", table_name="cafeterias")
    op.drop_column("cafeterias", "operational_status")
    op.drop_column("cafeterias", "timezone")
    op.drop_column("cafeterias", "operating_hours")
    op.drop_column("cafeterias", "location")
    op.drop_column("cafeterias", "email")
    op.drop_column("cafeterias", "phone")
    op.drop_column("cafeterias", "description")

    # Drop enums
    sa.Enum(name="inventory_unit").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="daily_menu_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="menu_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cafeteria_operational_status").drop(op.get_bind(), checkfirst=True)
