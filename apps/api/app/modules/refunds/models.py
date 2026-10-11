"""Refund and RefundEvent models.

Financial invariants:
- Total refunds for an order cannot exceed the paid amount
- Refund amounts are validated server-side
- Every refund state change is audited via RefundEvent
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

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

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RefundStatus(str, enum.Enum):
    """Refund lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # Phase 51 — admin rejection resolution state
    REJECTED = "rejected"


class RefundReason(str, enum.Enum):
    """Structured refund reasons."""

    ORDER_CANCELLED = "order_cancelled"
    ITEM_UNAVAILABLE = "item_unavailable"
    PAYMENT_ERROR = "payment_error"
    DUPLICATE_PAYMENT = "duplicate_payment"
    CAFETERIA_CLOSED = "cafeteria_closed"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Refund(Base):
    """Refund record — linked to an order and its payment.

    Enforces:
    - refund amount ≤ (paid amount - already refunded amount)
    - refund belongs to exactly one payment and one order
    """

    __tablename__ = "refunds"
    __table_args__ = (
        Index("idx_refund_order_id", "order_id"),
        Index("idx_refund_payment_id", "payment_id"),
        Index("idx_refund_user_id", "user_id"),
        Index("idx_refund_status", "status"),
        Index("idx_refund_idempotency_key", "idempotency_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Financial fields
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")

    # Status
    status: Mapped[RefundStatus] = mapped_column(
        StrEnum(RefundStatus, create_type=False, native_enum=False), nullable=False, default=RefundStatus.PENDING
    )

    # Reason
    reason: Mapped[RefundReason] = mapped_column(
        StrEnum(RefundReason, create_type=False, native_enum=False), nullable=False
    )
    reason_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 51 — admin rejection reason (set only when status == REJECTED)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Authorization
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    processed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Provider information
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Idempotency
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    events: Mapped[list[RefundEvent]] = relationship(
        "RefundEvent", back_populates="refund", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Refund id={self.id} order={self.order_id} status={self.status.value} amount={self.amount}>"


class RefundEvent(Base):
    """Refund audit event — tracks every state change on a refund."""

    __tablename__ = "refund_events"
    __table_args__ = (Index("idx_refund_event_refund_id", "refund_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    refund_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    refund: Mapped[Refund] = relationship("Refund", back_populates="events")

    def __repr__(self) -> str:
        return f"<RefundEvent id={self.id} refund={self.refund_id} type={self.event_type}>"
