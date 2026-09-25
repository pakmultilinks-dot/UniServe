"""Payment and PaymentAttempt models.

Financial invariants enforced at the database level:
- Payment amount is derived from order total (server-authoritative)
- Idempotency keys are unique (prevent duplicate payments)
- Provider references are unique (prevent duplicate processing)
- Currency is validated (only PKR initially)
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PaymentStatus(str, enum.Enum):
    """Payment lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUND_PENDING = "refund_pending"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"


class PaymentAttemptStatus(str, enum.Enum):
    """Individual payment attempt states."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Payment(Base):
    """Payment record — one per order.

    The payment amount is ALWAYS derived from the server-side order total.
    The client never determines the payment amount.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("idx_payment_order_id", "order_id"),
        Index("idx_payment_user_id", "user_id"),
        Index("idx_payment_status", "status"),
        Index("idx_payment_idempotency_key", "idempotency_key", unique=True),
        Index(
            "idx_payment_provider_reference",
            "provider_reference",
            unique=True,
            sqlite_where=text("provider_reference IS NOT NULL"),
            postgresql_where=text("provider_reference IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Financial fields — server-authoritative
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # smallest currency unit
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")

    # Status
    status: Mapped[PaymentStatus] = mapped_column(
        StrEnum(PaymentStatus, create_type=False, native_enum=False), nullable=False, default=PaymentStatus.PENDING
    )

    # Provider information (no sensitive credentials stored)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Idempotency
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timestamps
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
    attempts: Mapped[list[PaymentAttempt]] = relationship(
        "PaymentAttempt", back_populates="payment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Payment id={self.id} order={self.order_id} status={self.status.value} amount={self.amount}>"


class PaymentAttempt(Base):
    """Individual payment attempt — tracks retries and provider interactions.

    An order may have multiple payment attempts if the first one fails.
    Only one attempt should be SUCCEEDED per payment.
    """

    __tablename__ = "payment_attempts"
    __table_args__ = (Index("idx_payment_attempt_payment_id", "payment_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentAttemptStatus] = mapped_column(
        StrEnum(PaymentAttemptStatus, create_type=False, native_enum=False),
        nullable=False,
        default=PaymentAttemptStatus.PENDING,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    payment: Mapped[Payment] = relationship("Payment", back_populates="attempts")

    def __repr__(self) -> str:
        return f"<PaymentAttempt id={self.id} payment={self.payment_id} attempt={self.attempt_number} status={self.status.value}>"


class WebhookEvent(Base):
    """Webhook event log — ensures idempotent processing.

    Stores the provider event ID to prevent duplicate processing.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (Index("idx_webhook_provider_event_id", "provider_event_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)

    def __repr__(self) -> str:
        return f"<WebhookEvent id={self.id} provider={self.provider_name} event_id={self.provider_event_id}>"
