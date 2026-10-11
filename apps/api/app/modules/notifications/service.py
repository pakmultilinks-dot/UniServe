"""Notification service — business logic for creating and managing notifications.

Handles:
- Creating notifications from order lifecycle events (fire-and-forget)
- Creating notifications from refund events
- Listing, reading, and marking notifications
- Idempotent creation via source_event dedup
- Title/body templates for each notification type
- Phase 50 — Admin broadcast (in-app announcements to supported audiences)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select, update

from app.core.exceptions import NotFoundException, ValidationError
from app.modules.notifications.models import (
    AdminBroadcast,
    DeliveryStatus,
    Notification,
    NotificationType,
)
from app.modules.notifications.schemas import BroadcastAudience

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
    "refund_rejected": (
        "Refund Rejected",
        "Your refund request for order #{order_number} has been rejected. Please contact support for details.",
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
        return result.rowcount  # type: ignore[attr-defined]

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
            "refund_rejected": NotificationType.REFUND_REJECTED,
        }
        return mapping[event_type]


# ====================================================================
# Phase 50 — Admin broadcast
# ====================================================================


class BroadcastService:
    """University Admin broadcast (in-app announcement) workflow.

    Reuses NotificationService._create_notification for per-recipient
    persistence — no parallel notification write path. Broadcast
    idempotency follows the Payment.idempotency_key convention: a unique
    key on AdminBroadcast prevents accidental duplicate sends, and a
    replay returns the original broadcast without creating new rows.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._notifications = NotificationService(db)

    async def _resolve_recipient_ids(
        self,
        audience: BroadcastAudience,
        cafeteria_id: str | None,
    ) -> list[str]:
        """Resolve active, non-deleted recipient user ids for an audience."""
        from app.modules.cafeterias.models import Cafeteria
        from app.modules.users.models import AccountStatus, CafeteriaAssignment, Role, User

        base = select(User.id).where(
            User.status == AccountStatus.ACTIVE,
            User.deleted_at.is_(None),
        )

        role_map = {
            BroadcastAudience.STUDENTS: Role.STUDENT,
            BroadcastAudience.FACULTY: Role.FACULTY,
            BroadcastAudience.CAFETERIA_STAFF: Role.CAFETERIA_STAFF,
            BroadcastAudience.CAFETERIA_MANAGERS: Role.CAFETERIA_MANAGER,
            BroadcastAudience.UNIVERSITY_ADMINS: Role.UNIVERSITY_ADMIN,
        }

        if audience == BroadcastAudience.ALL_USERS:
            query = base
        elif audience in role_map:
            query = base.where(User.role == role_map[audience])
        elif audience == BroadcastAudience.CAFETERIA:
            if not cafeteria_id:
                raise ValidationError(
                    "cafeteria_id is required when audience is 'cafeteria'"
                )
            cafeteria = (
                await self.db.execute(
                    select(Cafeteria).where(Cafeteria.id == cafeteria_id)
                )
            ).scalar_one_or_none()
            if cafeteria is None:
                raise NotFoundException("Cafeteria", cafeteria_id)
            query = base.where(
                User.id.in_(
                    select(CafeteriaAssignment.user_id).where(
                        CafeteriaAssignment.cafeteria_id == cafeteria_id
                    )
                )
            )
        else:
            # Defensive — pydantic rejects unknown audiences first.
            raise ValidationError(f"Unsupported audience: {audience}")

        result = await self.db.execute(query.order_by(User.id))
        return list(result.scalars().all())

    async def count_audience(
        self,
        *,
        audience: BroadcastAudience,
        cafeteria_id: str | None = None,
    ) -> int:
        """Count active recipients an audience resolves to (preview support)."""
        recipient_ids = await self._resolve_recipient_ids(audience, cafeteria_id)
        return len(recipient_ids)

    async def create_broadcast(
        self,
        *,
        title: str,
        message: str,
        audience: BroadcastAudience,
        cafeteria_id: str | None,
        idempotency_key: str,
        created_by,
    ) -> tuple[AdminBroadcast, bool]:
        """Create and persist an Admin broadcast + per-recipient notifications.

        Returns (broadcast, duplicate). duplicate=True means this key was
        already sent — the original broadcast is returned untouched.
        Nothing is persisted unless recipient resolution succeeds and the
        transaction commits (get_db commits on request success).
        """
        title = title.strip()
        message = message.strip()
        if not title:
            raise ValidationError("Broadcast title cannot be empty")
        if not message:
            raise ValidationError("Broadcast message cannot be empty")

        if audience == BroadcastAudience.CAFETERIA and not cafeteria_id:
            raise ValidationError("cafeteria_id is required when audience is 'cafeteria'")
        if audience != BroadcastAudience.CAFETERIA and cafeteria_id:
            raise ValidationError(
                "cafeteria_id is only supported when audience is 'cafeteria'"
            )

        # Idempotency — payments convention: replay returns the original.
        existing = (
            await self.db.execute(
                select(AdminBroadcast).where(
                    AdminBroadcast.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.debug(
                "broadcast_idempotent_replay",
                broadcast_id=existing.id,
                idempotency_key=idempotency_key,
            )
            return existing, True

        recipient_ids = await self._resolve_recipient_ids(audience, cafeteria_id)
        if not recipient_ids:
            raise ValidationError(
                f"Audience '{audience.value}' has no active recipients — nothing sent"
            )

        created_by_name = (
            f"{created_by.first_name} {created_by.last_name}".strip()
            if created_by is not None
            else "Unknown"
        )
        # Explicit id (Payment-creation pattern) — recipient rows below need
        # reference_id BEFORE the flush that assigns column defaults.
        broadcast_id = str(uuid.uuid4())
        broadcast = AdminBroadcast(
            id=broadcast_id,
            created_by_id=getattr(created_by, "id", None),
            created_by_name=created_by_name,
            title=title,
            message=message,
            audience=audience.value,
            cafeteria_id=cafeteria_id,
            recipient_count=len(recipient_ids),
            idempotency_key=idempotency_key,
        )
        self.db.add(broadcast)

        for user_id in recipient_ids:
            await self._notifications._create_notification(
                user_id=user_id,
                notification_type=NotificationType.ADMIN_ANNOUNCEMENT,
                title=title,
                body=message,
                cafeteria_id=cafeteria_id,
                reference_type="broadcast",
                reference_id=broadcast_id,
                source_event_type="admin_broadcast",
                source_event_id=None,
            )

        await self.db.flush()
        logger.info(
            "broadcast_created",
            broadcast_id=broadcast.id,
            audience=audience.value,
            recipient_count=broadcast.recipient_count,
            created_by_id=broadcast.created_by_id,
        )
        return broadcast, False

    async def list_broadcasts(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AdminBroadcast], int]:
        """Broadcast history — newest first, with total count."""
        total_result = await self.db.execute(
            select(func.count()).select_from(AdminBroadcast)
        )
        total = total_result.scalar() or 0

        result = await self.db.execute(
            select(AdminBroadcast)
            .order_by(AdminBroadcast.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
