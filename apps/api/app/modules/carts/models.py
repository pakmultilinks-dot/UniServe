"""Cart domain models.

Persistent shopping carts scoped per user per cafeteria.
Enforces one active cart per user per cafeteria at the database level.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, StrEnum

if TYPE_CHECKING:
    from app.modules.menus.models import MenuItem


class CartStatus(str, enum.Enum):
    """Cart lifecycle status."""

    ACTIVE = "active"
    EXPIRED = "expired"


class Cart(Base):
    """A user's shopping cart for a specific cafeteria.

    Invariants:
    - One active cart per user per cafeteria (unique constraint on user_id + cafeteria_id).
    - Cart expires when the cafeteria closes for the day.
    """

    __tablename__ = "carts"
    __table_args__ = (
        Index(
            "uq_active_cart_user_cafeteria",
            "user_id",
            "cafeteria_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("idx_cart_user", "user_id"),
        Index("idx_cart_cafeteria", "cafeteria_id"),
        Index("idx_cart_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[CartStatus] = mapped_column(
        StrEnum(CartStatus, create_type=False, native_enum=False), default=CartStatus.ACTIVE, nullable=False
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
    items: Mapped[list[CartItem]] = relationship(
        "CartItem", back_populates="cart", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Cart user={self.user_id} cafeteria={self.cafeteria_id} status={self.status.value}>"
        )


class CartItem(Base):
    """A line item in a shopping cart.

    Stores the price snapshot at time of addition.
    The price_snapshot preserves the menu item's price when added to the cart.
    """

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "menu_item_id", name="uq_cart_item_menu_item"),
        Index("idx_cart_item_cart", "cart_id"),
        Index("idx_cart_item_menu_item", "menu_item_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cart_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
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
    cart: Mapped[Cart] = relationship("Cart", back_populates="items")
    menu_item: Mapped[MenuItem] = relationship("MenuItem")

    def __repr__(self) -> str:
        return f"<CartItem cart={self.cart_id} item={self.menu_item_id} qty={self.quantity}>"
