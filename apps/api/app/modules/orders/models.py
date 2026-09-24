"""Order domain models.

Defines orders, order items, order events, and collection tokens.
"""

import enum
import secrets
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# ---- Enums ----


class OrderStatus(str, enum.Enum):
    """Customer-facing order statuses."""

    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderType(str, enum.Enum):
    """Order delivery type."""

    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"


class PaymentMethod(str, enum.Enum):
    """Payment method.

    ONLINE is a boundary for future Phase 5 integration.
    """

    CASH = "cash"
    ONLINE = "online"


class OrderEventType(str, enum.Enum):
    """Internal order event types for audit trail."""

    CREATED = "created"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_CONFIRMED = "payment_confirmed"
    CONFIRMED_BY_STAFF = "confirmed_by_staff"
    MANAGER_REJECTED = "manager_rejected"
    PREPARATION_STARTED = "preparation_started"
    READY_FOR_COLLECTION = "ready_for_collection"
    COLLECTED = "collected"
    CANCELLED = "cancelled"
    CANCELLED_BY_MANAGER = "cancelled_by_manager"
    INVENTORY_RESERVED = "inventory_reserved"
    INVENTORY_RELEASED = "inventory_released"
    UNCOLLECTED = "uncollected"
    DELAYED = "delayed"
    ETA_UPDATED = "eta_updated"
    CAFETERIA_CLOSED = "cafeteria_closed"
    ITEM_UNAVAILABLE = "item_unavailable"
    PARTIAL_CANCELLED = "partial_cancelled"
    NO_SHOW_RECORDED = "no_show_recorded"


# ---- Order ----


class Order(Base):
    """A customer order.

    Each order belongs to one cafeteria and one user.
    Contains snapshot data sufficient to reconstruct the order
    independently of current menu item state.
    """

    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_order_user", "user_id"),
        Index("idx_order_cafeteria", "cafeteria_id"),
        Index("idx_order_status", "status"),
        Index("idx_order_number", "order_number"),
        Index("idx_order_date", "order_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, create_type=False), nullable=False
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, create_type=False), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, create_type=False), default=OrderStatus.PENDING, nullable=False
    )

    # Price snapshot (server-calculated, never from client)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)

    # Scheduling
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_collection_time: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Collection
    collection_token: Mapped[str] = mapped_column(
        String(64), default=lambda: secrets.token_hex(32), nullable=False, unique=True
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Inventory
    inventory_reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Operational timestamps
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preparation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Collection details
    collection_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Rejection
    rejection_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flags
    preparation_started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Note
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )
    events: Mapped[list["OrderEvent"]] = relationship(
        "OrderEvent", back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Order #{self.order_number} status={self.status.value}>"


# ---- Order Item (snapshot) ----


class OrderItem(Base):
    """A snapshot of a menu item at time of order.

    Preserves historical data: item name, unit price, quantity, subtotal.
    Never depends on the current MenuItem record.
    """

    __tablename__ = "order_items"
    __table_args__ = (Index("idx_order_item_order", "order_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True
    )

    # Historical snapshots
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem {self.item_name} x{self.quantity}>"


# ---- Order Event (audit trail) ----


class OrderEvent(Base):
    """Internal order event for audit and lifecycle tracking."""

    __tablename__ = "order_events"
    __table_args__ = (
        Index("idx_order_event_order", "order_id"),
        Index("idx_order_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[OrderEventType] = mapped_column(
        Enum(OrderEventType, create_type=False), nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="events")

    def __repr__(self) -> str:
        return f"<OrderEvent {self.event_type.value} order={self.order_id}>"


# ---- Order Number Sequence ----


class OrderNumberSequence(Base):
    """Global sequential order number allocator.

    Uses database-level atomic allocation to guarantee uniqueness
    and sequential ordering. Never reused.
    """

    __tablename__ = "order_number_sequence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<OrderNumberSequence last={self.last_number}>"


class OrderRejectionReason(str, enum.Enum):
    """Reasons for manager rejection of an order."""

    CAPACITY = "capacity"
    ITEM_UNAVAILABLE = "item_unavailable"
    CAFETERIA_ISSUE = "cafeteria_issue"
    OPERATIONAL_ISSUE = "operational_issue"
    OTHER = "other"


# ---- No-Show Tracking ----


class NoShow(Base):
    """Records a no-show event when an order goes uncollected past its pickup deadline.

    Used for suspension policy enforcement.
    """

    __tablename__ = "no_shows"
    __table_args__ = (
        Index("idx_noshow_user", "user_id"),
        Index("idx_noshow_cafeteria", "cafeteria_id"),
        Index("idx_noshow_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)

    def __repr__(self) -> str:
        return f"<NoShow user={self.user_id} order={self.order_id}>"
