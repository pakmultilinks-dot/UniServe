"""Inventory domain models.

Tracks ingredient/supply quantities for menu items and supports manual adjustments.
"""

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.users.models import User

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, StrEnum

# ---- Inventory Unit ----


class InventoryUnit(str, enum.Enum):
    """Units of measurement for inventory items."""

    KG = "kg"
    GRAMS = "g"
    LITERS = "L"
    MILLILITERS = "mL"
    PIECES = "pcs"
    PORTIONS = "portions"


# ---- Inventory Item ----


class InventoryItem(Base):
    """Tracks inventory for a menu item within a cafeteria.

    Each menu item has exactly one inventory record per cafeteria.
    """

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index("idx_inventory_item_cafeteria", "cafeteria_id"),
        Index("idx_inventory_item_menu_item", "menu_item_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit: Mapped[InventoryUnit] = mapped_column(
        StrEnum(InventoryUnit, name="inventory_unit", create_type=False), nullable=False
    )
    low_threshold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_restocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    adjustments: Mapped[list["InventoryAdjustment"]] = relationship(
        "InventoryAdjustment", back_populates="inventory_item", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<InventoryItem {self.menu_item_id} qty={self.quantity} {self.unit.value}>"


# ---- Inventory Adjustment ----


class InventoryAdjustment(Base):
    """Manual inventory adjustment record.

    Records every change to inventory quantities with reason and operator.
    """

    __tablename__ = "inventory_adjustments"
    __table_args__ = (
        Index("idx_inventory_adj_item", "inventory_item_id"),
        Index("idx_inventory_adj_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventory_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    adjustment_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # positive = restock, negative = usage
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjusted_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="adjustments"
    )
    adjuster: Mapped[Optional["User"]] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return f"<InventoryAdjustment item={self.inventory_item_id} qty={self.adjustment_quantity}>"
