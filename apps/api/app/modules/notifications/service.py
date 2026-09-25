"""Notification service — business logic for creating and managing notifications.

Handles:
- Creating notifications from order lifecycle events (fire-and-forget)
- Creating notifications from refund events
- Listing, reading, and marking notifications
- Idempotent creation via source_event dedup
- Title/body templates for each notification type
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.notifications.models import (
    DeliveryStatus,
    Notification,
    NotificationType,
)

logger = structlog.get_logger(__name__)


# ====================================================================
# Standalone fire-and-forget helpers
# ====================================================================

async def emit_order_notification(
    db: AsyncSession,
    *,
    order_id: str,
    order_number: int,
    user_id: str,
    event_type: str,
    source_event_id: str | None = None,
    notes: str | None = None,
    cafeteria_id: str | None = None,
) -> None:
    """Fire-and-forget: create a notification for an order event.

    Called from OrderService / PaymentService after an OrderEvent is created.
    Wrapped in try/except — notification failure never propagates to the caller.
    """
    try:
        svc = NotificationService(db)
        await svc.create_order_event_notification(
            order_id=order_id,
            order_number=order_number,
            user_id=user_id,
            event_type=event_type,
            source_event_id=source_event_id,
            notes=notes,
            cafeteria_id=cafeteria_id,
        )
    except Exception:
        logger.warning(
            "order_notification_failed",
            order_id=order_id,
            event_type=event_type,
        )


async def emit_refund_notification(
    db: AsyncSession,
    *,
    refund_id: str,
    order_id: str,
    order_number: int,
    user_id: str,
    event_type: str,
    source_event_id: str | None = None,
    cafeteria_id: str | None = None,
) -> None:
    """Fire-and-forget: create a notification for a refund event.

    Called from RefundService after a RefundEvent is created.
    Wrapped in try/except — notification failure never propagates to the caller.
    """
    try:
        svc = NotificationService(db)
        await svc.create_refund_event_notification(
            refund_id=refund_id,
            order_id=order_id,
            order_number=order_number,
            user_id=user_id,
            event_type=event_type,
            source_event_id=source_event_id,
            cafeteria_id=cafeteria_id,
        )
    except Exception:
        logger.warning(
            "refund_notification_failed",
            refund_id=refund_id,
            event_type=event_type,
        )

# ====================================================================
# Notification templates — maps event types to human-readable titles/bodies
# ====================================================================

_ORDER_NOTIFICATION_TEMPLATES: dict[str, tuple[str, str]] = {
    # (title_template, body_template) — {order_number} and {notes} are filled at runtime
    "created": (
        "Order Placed",
        "Your order #{order_number} has been placed successfully.",
    ),
    "confirmed_by_staff": (
        "Order Confirmed",
        "Your order #{order_number} has been confirmed and will be prepared soon.",
    ),
    "manager_rejected": (
        "Order Rejected",
        "Your order #{order_number} has been rejected. {reason}",
    ),
    "preparation_started": (
        "Preparation Started",
        "Your order #{order_number} is now being prepared.",
    ),
    "ready_for_collection": (
        "Order Ready for Collection",
        "Your order #{order_number} is ready for collection! Please collect it before the deadline.",
    ),
    "cancelled": (
        "Order Cancelled",
        "Your order #{order_number} has been cancelled.",
    ),
    "cancelled_by_manager": (
        "Order Cancelled",
        "Your order #{order_number} has been cancelled by the cafeteria manager.",
    ),
    "delayed": (
        "Order Delayed",
        "Your order #{order_number} has been delayed. {notes}",
    ),
    "uncollected": (
        "Order Not Collected",
        "Your order #{order_number} was not collected before the deadline and has been marked as uncollected.",
    ),
    "cafeteria_closed": (
        "Cafeteria Closed",
        "The cafeteria has been closed unexpectedly. Your order #{order_number} has been cancelled.",
    ),
    "payment_confirmed": (
        "Payment Confirmed",
        "Payment for order #{order_number} has been confirmed. Your order will be prepared shortly.",
    ),
}

_REFUND_NOTIFICATION_TEMPLATES: dict[str, tuple[str, str]] = {
    "refund_requested": (
        "Refund Requested",
        "A refund request for your order #{order_number} has been submitted and is under review.",
    ),
    "refund_succeeded": (
        "Refund Processed",
        "Your refund for order #{order_number} has been processed successfully.",
    ),
    "refund_failed": (
        "Refund Failed",
        "Your refund request for order #{order_number} could not be processed. Please contact support.",
    ),
}

# Event types that should NOT generate notifications (internal bookkeeping)
_SKIP_NOTIFICATION_EVENTS = frozenset(
    {
        "payment_pending",
        "inventory_reserved",
        "inventory_released",
        "eta_updated",
        "collected",
        "partial_cancelled",
        "item_unavailable",
        "no_show_recorded",
    }
)


class NotificationService:
    """Service for notification operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ====================================================================
    # Create notification from an order event (fire-and-forget)
    # ====================================================================

    async def create_order_event_notification(
        self,
        *,
        order_id: str,
        order_number: int,
        user_id: str,
        event_type: str,
        source_event_id: str | None = None,
        notes: str | None = None,
        cafeteria_id: str | None = None,
    ) -> Notification | None:
        """Create a notification for an order event.

        Returns the created Notification, or None if:
        - The event type does not warrant a notification
        - A notification with the same source_event_id already exists (idempotent)

        This method MUST be called inside the caller's transaction. It should
        never be wrapped in its own transaction — failure isolation is handled
        by the caller's try/except.
        """
        # Skip internal bookkeeping events
        if event_type in _SKIP_NOTIFICATION_EVENTS:
            return None

        # Look up template
        template = _ORDER_NOTIFICATION_TEMPLATES.get(event_type)
        if template is None:
            logger.warning(
                "notification_no_template",
                event_type=event_type,
            )
            return None

        title_template, body_template = template

        # Build body — fill in order_number and optional notes
        reason_text = ""
        if event_type in ("manager_rejected", "delayed") and notes:
            reason_text = notes
        title = title_template
        body = body_template.format(
            order_number=order_number,
            notes=reason_text,
            reason=reason_text,
        )

        return await self._create_notification(
            user_id=user_id,
            notification_type=self._event_type_to_notification_type(event_type),
            title=title,
            body=body,
            order_id=order_id,
            cafeteria_id=cafeteria_id,
            reference_type="order",
            reference_id=order_id,
            source_event_type=event_type,
            source_event_id=source_event_id,
        )

    # ====================================================================
    # Create notification from a refund event (fire-and-forget)
    # ====================================================================

    async def create_refund_event_notification(
        self,
        *,
        refund_id: str,
        order_id: str,
        order_number: int,
        user_id: str,
        event_type: str,
        source_event_id: str | None = None,
        cafeteria_id: str | None = None,
    ) -> Notification | None:
        """Create a notification for a refund event.

        Returns the created Notification, or None if:
        - The event type does not warrant a notification
        - A notification with the same source_event_id already exists (idempotent)
        """
        template = _REFUND_NOTIFICATION_TEMPLATES.get(event_type)
        if template is None:
            return None

        title_template, body_template = template
        title = title_template
        body = body_template.format(order_number=order_number)

        return await self._create_notification(
            user_id=user_id,
            notification_type=self._refund_event_type_to_notification_type(event_type),
            title=title,
            body=body,
            order_id=order_id,
            cafeteria_id=cafeteria_id,
            reference_type="refund",
            reference_id=refund_id,
            source_event_type=event_type,
            source_event_id=source_event_id,
        )

    # ====================================================================
    # Read operations
    # ====================================================================

    async def list_user_notifications(
        self,
        *,
        user_id: str,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Notification], int, int]:
        """List notifications for a user.

        Returns: (notifications, total_count, unread_count)
        """
        base_query = select(Notification).where(Notification.user_id == user_id)

        # Total count
        total_q = select(func.count()).select_from(
            base_query.subquery()
        )
        total_result = await self.db.execute(total_q)
        total = total_result.scalar() or 0

        # Unread count
        unread_q = select(func.count()).select_from(
            base_query.where(Notification.is_read == False).subquery()  # noqa: E712
        )
        unread_result = await self.db.execute(unread_q)
        unread_count = unread_result.scalar() or 0

        # Fetch notifications
        query = base_query.order_by(Notification.created_at.desc())
        if unread_only:
            query = query.where(Notification.is_read == False)  # noqa: E712
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        notifications = list(result.scalars().all())

        return notifications, total, unread_count

    async def get_unread_count(self, *, user_id: str) -> int:
        """Get count of unread notifications for a user."""
        result = await self.db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        return result.scalar() or 0

    # ====================================================================
    # Write operations (mark as read)
    # ====================================================================

    async def mark_as_read(
        self,
        *,
        notification_id: str,
        user_id: str,
    ) -> Notification:
        """Mark a single notification as read.

        Verifies ownership. Returns the updated notification.
        """
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise NotFoundException("Notification", notification_id)

        if notification.user_id != user_id:
            raise NotFoundException("Notification", notification_id)

        if not notification.is_read:
            from datetime import UTC, datetime

            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await self.db.flush()

        return notification

    async def mark_all_as_read(self, *, user_id: str) -> int:
        """Mark all unread notifications as read for a user.

        Returns the count of notifications marked.
        """
        from datetime import UTC, datetime

        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()
        return result.rowcount  # type: ignore[return-value]

    # ====================================================================
    # Private helpers
    # ====================================================================

    async def _create_notification(
        self,
        *,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        order_id: str | None = None,
        cafeteria_id: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        source_event_type: str | None = None,
        source_event_id: str | None = None,
    ) -> Notification | None:
        """Core notification creation with idempotency check."""
        # Idempotency: skip if a notification with this source event already exists
        if source_event_id is not None and source_event_type is not None:
            existing = await self.db.execute(
                select(Notification).where(
                    Notification.source_event_type == source_event_type,
                    Notification.source_event_id == source_event_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.debug(
                    "notification_already_exists",
                    source_event_type=source_event_type,
                    source_event_id=source_event_id,
                )
                return None

        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            order_id=order_id,
            cafeteria_id=cafeteria_id,
            reference_type=reference_type,
            reference_id=reference_id,
            source_event_type=source_event_type,
            source_event_id=source_event_id,
            is_read=False,
            delivery_status=DeliveryStatus.PENDING,
        )
        self.db.add(notification)
        # Note: caller is responsible for flush/commit
        return notification

    @staticmethod
    def _event_type_to_notification_type(event_type: str) -> NotificationType:
        """Map an OrderEventType string to a NotificationType."""
        mapping = {
            "created": NotificationType.ORDER_CREATED,
            "confirmed_by_staff": NotificationType.ORDER_CONFIRMED,
            "manager_rejected": NotificationType.ORDER_REJECTED,
            "preparation_started": NotificationType.PREPARATION_STARTED,
            "ready_for_collection": NotificationType.ORDER_READY,
            "cancelled": NotificationType.ORDER_CANCELLED,
            "cancelled_by_manager": NotificationType.ORDER_CANCELLED,
            "delayed": NotificationType.ORDER_DELAYED,
            "uncollected": NotificationType.ORDER_UNCOLLECTED,
            "cafeteria_closed": NotificationType.CAFETERIA_CLOSED,
            "payment_confirmed": NotificationType.PAYMENT_CONFIRMED,
        }
        return mapping[event_type]

    @staticmethod
    def _refund_event_type_to_notification_type(event_type: str) -> NotificationType:
        """Map a RefundEvent type string to a NotificationType."""
        mapping = {
            "refund_requested": NotificationType.REFUND_REQUESTED,
            "refund_succeeded": NotificationType.REFUND_PROCESSED,
            "refund_failed": NotificationType.REFUND_FAILED,
        }
        return mapping[event_type]
