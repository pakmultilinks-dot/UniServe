"""Notification models — durable in-app notification records.

Provides:
- NotificationType enum — maps to order lifecycle events
- DeliveryStatus enum — tracks delivery state (foundation for push)
- Notification model — per-user, per-event durable records with idempotency
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, StrEnum


class NotificationType(str, enum.Enum):
    """Notification types mapped to domain events."""

    ORDER_CREATED = "order_created"
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_REJECTED = "order_rejected"
    PREPARATION_STARTED = "preparation_started"
    ORDER_READY = "order_ready"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_DELAYED = "order_delayed"
    ORDER_UNCOLLECTED = "order_uncollected"
    CAFETERIA_CLOSED = "cafeteria_closed"
    PAYMENT_CONFIRMED = "payment_confirmed"
    REFUND_REQUESTED = "refund_requested"
    REFUND_PROCESSED = "refund_processed"
    REFUND_FAILED = "refund_failed"


class DeliveryStatus(str, enum.Enum):
    """Delivery state of a notification.

    PENDING → DELIVERED for in-app reads.
    FAILED for external push failures (future).
    """

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class Notification(Base):
    """Durable in-app notification record.

    Created fire-and-forget alongside OrderEvent / RefundEvent creation.
    Idempotent via (source_event_type, source_event_id) unique pair.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notification_user_id", "user_id"),
        Index("idx_notification_user_read", "user_id", "is_read"),
        Index("idx_notification_created_at", "created_at"),
        Index(
            "idx_notification_source_event",
            "source_event_type",
            "source_event_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        StrEnum(NotificationType, create_type=False, native_enum=False), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    cafeteria_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="SET NULL"), nullable=True
    )
    reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "order", "refund"
    reference_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )  # order_id, refund_id
    source_event_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # OrderEventType / RefundEvent value
    source_event_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )  # OrderEvent.id for dedup
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        StrEnum(DeliveryStatus, create_type=False, native_enum=False),
        default=DeliveryStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Notification {self.notification_type.value} "
            f"user={self.user_id} read={self.is_read}>"
        )
