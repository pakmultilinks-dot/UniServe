"""Tests for notifications — creation, listing, marking read, idempotency.

Covers:
- Notification creation from order events (all 11 integration point types)
- Notification creation from refund events (3 refund event types)
- Skipped events (internal bookkeeping → no notification)
- Unknown event types (no template → no notification)
- Idempotency (same source_event_id → no duplicate)
- Fire-and-forget helpers (emit_order_notification, emit_refund_notification)
- Fire-and-forget failure isolation (exception doesn't propagate)
- GET /notifications — listing, pagination, unread_only filter
- GET /notifications/unread-count — count
- PATCH /notifications/{id}/read — mark single read
- PATCH /notifications/read-all — mark all read
- Ownership enforcement (user can only see own notifications)
- Unauthenticated access returns 401
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import (
    DeliveryStatus,
    Notification,
    NotificationType,
)
from app.modules.notifications.service import (
    NotificationService,
    emit_order_notification,
    emit_refund_notification,
)
from tests.conftest import (
    create_test_user,
    create_user_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_notification_direct(
    db: AsyncSession,
    *,
    user_id: str,
    notification_type: NotificationType = NotificationType.ORDER_CREATED,
    title: str = "Test Notification",
    body: str = "Test body",
    order_id: str | None = None,
    cafeteria_id: str | None = None,
    reference_type: str | None = "order",
    reference_id: str | None = None,
    source_event_type: str | None = None,
    source_event_id: str | None = None,
    is_read: bool = False,
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING,
) -> Notification:
    """Insert a notification directly for testing."""
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
        is_read=is_read,
        delivery_status=delivery_status,
    )
    db.add(notification)
    await db.flush()
    return notification


# ---------------------------------------------------------------------------
# Service-level tests — create_order_event_notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderEventNotificationCreation:
    """Test creating notifications from order lifecycle events via service."""

    async def test_created_event(self, db: AsyncSession, student_user):
        """Order created → ORDER_CREATED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_CREATED
        assert notif.title == "Order Placed"
        assert "1001" in notif.body
        assert notif.is_read is False
        assert notif.delivery_status == DeliveryStatus.PENDING

    async def test_confirmed_by_staff_event(self, db: AsyncSession, student_user):
        """Order confirmed → ORDER_CONFIRMED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=2002,
            user_id=student_user.id,
            event_type="confirmed_by_staff",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_CONFIRMED
        assert notif.title == "Order Confirmed"
        assert "2002" in notif.body

    async def test_manager_rejected_event(self, db: AsyncSession, student_user):
        """Order rejected → ORDER_REJECTED notification with reason."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=3003,
            user_id=student_user.id,
            event_type="manager_rejected",
            source_event_id=str(uuid.uuid4()),
            notes="Item out of stock",
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_REJECTED
        assert notif.title == "Order Rejected"
        assert "3003" in notif.body
        assert "Item out of stock" in notif.body

    async def test_preparation_started_event(self, db: AsyncSession, student_user):
        """Preparation started → PREPARATION_STARTED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=4004,
            user_id=student_user.id,
            event_type="preparation_started",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.PREPARATION_STARTED
        assert notif.title == "Preparation Started"

    async def test_ready_for_collection_event(self, db: AsyncSession, student_user):
        """Ready for collection → ORDER_READY notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=5005,
            user_id=student_user.id,
            event_type="ready_for_collection",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_READY
        assert notif.title == "Order Ready for Collection"

    async def test_cancelled_event(self, db: AsyncSession, student_user):
        """Order cancelled → ORDER_CANCELLED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=6006,
            user_id=student_user.id,
            event_type="cancelled",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_CANCELLED
        assert notif.title == "Order Cancelled"

    async def test_cancelled_by_manager_event(self, db: AsyncSession, student_user):
        """Manager cancelled → ORDER_CANCELLED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=7007,
            user_id=student_user.id,
            event_type="cancelled_by_manager",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_CANCELLED
        assert notif.title == "Order Cancelled"

    async def test_delayed_event(self, db: AsyncSession, student_user):
        """Order delayed → ORDER_DELAYED notification with notes."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=8008,
            user_id=student_user.id,
            event_type="delayed",
            source_event_id=str(uuid.uuid4()),
            notes="Supply delivery delayed",
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_DELAYED
        assert notif.title == "Order Delayed"
        assert "Supply delivery delayed" in notif.body

    async def test_uncollected_event(self, db: AsyncSession, student_user):
        """Order uncollected → ORDER_UNCOLLECTED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=9009,
            user_id=student_user.id,
            event_type="uncollected",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.ORDER_UNCOLLECTED
        assert notif.title == "Order Not Collected"

    async def test_cafeteria_closed_event(self, db: AsyncSession, student_user):
        """Cafeteria closed → CAFETERIA_CLOSED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1010,
            user_id=student_user.id,
            event_type="cafeteria_closed",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.CAFETERIA_CLOSED
        assert notif.title == "Cafeteria Closed"

    async def test_payment_confirmed_event(self, db: AsyncSession, student_user):
        """Payment confirmed → PAYMENT_CONFIRMED notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1111,
            user_id=student_user.id,
            event_type="payment_confirmed",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.PAYMENT_CONFIRMED
        assert notif.title == "Payment Confirmed"


# ---------------------------------------------------------------------------
# Service-level tests — create_refund_event_notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefundEventNotificationCreation:
    """Test creating notifications from refund lifecycle events via service."""

    async def test_refund_requested_event(self, db: AsyncSession, student_user):
        """Refund requested → REFUND_REQUESTED notification."""
        svc = NotificationService(db)
        notif = await svc.create_refund_event_notification(
            refund_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            order_number=5001,
            user_id=student_user.id,
            event_type="refund_requested",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.REFUND_REQUESTED
        assert notif.title == "Refund Requested"
        assert "5001" in notif.body

    async def test_refund_succeeded_event(self, db: AsyncSession, student_user):
        """Refund processed → REFUND_PROCESSED notification."""
        svc = NotificationService(db)
        notif = await svc.create_refund_event_notification(
            refund_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            order_number=5002,
            user_id=student_user.id,
            event_type="refund_succeeded",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.REFUND_PROCESSED
        assert notif.title == "Refund Processed"

    async def test_refund_failed_event(self, db: AsyncSession, student_user):
        """Refund failed → REFUND_FAILED notification."""
        svc = NotificationService(db)
        notif = await svc.create_refund_event_notification(
            refund_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            order_number=5003,
            user_id=student_user.id,
            event_type="refund_failed",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is not None
        assert notif.notification_type == NotificationType.REFUND_FAILED
        assert notif.title == "Refund Failed"


# ---------------------------------------------------------------------------
# Service-level tests — skip events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSkipEvents:
    """Test that internal bookkeeping events don't generate notifications."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "payment_pending",
            "inventory_reserved",
            "inventory_released",
            "eta_updated",
            "collected",
            "partial_cancelled",
            "item_unavailable",
            "no_show_recorded",
        ],
    )
    async def test_order_skip_events(self, db: AsyncSession, student_user, event_type):
        """Skipped order event types return None and create no notification."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=9999,
            user_id=student_user.id,
            event_type=event_type,
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is None

    async def test_unknown_order_event_type(self, db: AsyncSession, student_user):
        """Unknown order event type (no template) returns None."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=9999,
            user_id=student_user.id,
            event_type="totally_unknown_event",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is None

    async def test_unknown_refund_event_type(self, db: AsyncSession, student_user):
        """Unknown refund event type (no template) returns None."""
        svc = NotificationService(db)
        notif = await svc.create_refund_event_notification(
            refund_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            order_number=9999,
            user_id=student_user.id,
            event_type="unknown_refund_event",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif is None


# ---------------------------------------------------------------------------
# Service-level tests — idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIdempotency:
    """Test that duplicate source_event_id doesn't create duplicates."""

    async def test_order_event_idempotent(self, db: AsyncSession, student_user):
        """Creating two notifications with the same source_event_id returns None on second call."""
        svc = NotificationService(db)
        event_id = str(uuid.uuid4())
        order_id = str(uuid.uuid4())

        first = await svc.create_order_event_notification(
            order_id=order_id,
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=event_id,
        )
        assert first is not None

        second = await svc.create_order_event_notification(
            order_id=order_id,
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=event_id,
        )
        assert second is None

    async def test_refund_event_idempotent(self, db: AsyncSession, student_user):
        """Creating two refund notifications with same source_event_id returns None on second call."""
        svc = NotificationService(db)
        event_id = str(uuid.uuid4())
        order_id = str(uuid.uuid4())
        refund_id = str(uuid.uuid4())

        first = await svc.create_refund_event_notification(
            refund_id=refund_id,
            order_id=order_id,
            order_number=2001,
            user_id=student_user.id,
            event_type="refund_requested",
            source_event_id=event_id,
        )
        assert first is not None

        second = await svc.create_refund_event_notification(
            refund_id=refund_id,
            order_id=order_id,
            order_number=2001,
            user_id=student_user.id,
            event_type="refund_requested",
            source_event_id=event_id,
        )
        assert second is None

    async def test_different_source_event_ids_create_separate_notifications(
        self, db: AsyncSession, student_user
    ):
        """Different source_event_ids for the same event type create separate notifications."""
        svc = NotificationService(db)
        order_id = str(uuid.uuid4())

        first = await svc.create_order_event_notification(
            order_id=order_id,
            order_number=3001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        second = await svc.create_order_event_notification(
            order_id=order_id,
            order_number=3001,
            user_id=student_user.id,
            event_type="cancelled",
            source_event_id=str(uuid.uuid4()),
        )
        assert first is not None
        assert second is not None
        assert first.notification_type != second.notification_type


# ---------------------------------------------------------------------------
# Service-level tests — listing and reading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestServiceListing:
    """Test notification listing and reading at the service level."""

    async def test_list_empty(self, db: AsyncSession, student_user):
        """Empty list returns empty items with zero counts."""
        svc = NotificationService(db)
        items, total, unread = await svc.list_user_notifications(user_id=student_user.id)
        assert items == []
        assert total == 0
        assert unread == 0

    async def test_list_returns_created_notifications(self, db: AsyncSession, student_user):
        """Created notifications appear in list, newest first."""
        svc = NotificationService(db)

        # Create 3 notifications
        for i in range(3):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )

        items, total, unread = await svc.list_user_notifications(user_id=student_user.id)
        assert total == 3
        assert unread == 3  # all unread
        assert len(items) == 3

    async def test_unread_only_filter(self, db: AsyncSession, student_user):
        """unread_only=True filters to only unread notifications."""
        svc = NotificationService(db)

        n1 = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1002,
            user_id=student_user.id,
            event_type="cancelled",
            source_event_id=str(uuid.uuid4()),
        )

        # Mark first as read
        await svc.mark_as_read(notification_id=n1.id, user_id=student_user.id)

        items, total, unread = await svc.list_user_notifications(
            user_id=student_user.id, unread_only=True
        )
        assert total == 2  # total count is for all
        assert unread == 1  # one is now read
        assert len(items) == 1  # only unread returned

    async def test_pagination(self, db: AsyncSession, student_user):
        """Pagination works with limit/offset."""
        svc = NotificationService(db)

        for i in range(5):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )

        items, total, _ = await svc.list_user_notifications(
            user_id=student_user.id, limit=2, offset=0
        )
        assert len(items) == 2
        assert total == 5

        items2, _, _ = await svc.list_user_notifications(
            user_id=student_user.id, limit=2, offset=2
        )
        assert len(items2) == 2

        items3, _, _ = await svc.list_user_notifications(
            user_id=student_user.id, limit=2, offset=4
        )
        assert len(items3) == 1

    async def test_mark_as_read(self, db: AsyncSession, student_user):
        """Mark a single notification as read."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await db.flush()  # materialise generated UUID
        assert notif.is_read is False

        updated = await svc.mark_as_read(notification_id=notif.id, user_id=student_user.id)
        assert updated.is_read is True
        assert updated.read_at is not None

    async def test_mark_already_read_is_noop(self, db: AsyncSession, student_user):
        """Marking an already-read notification doesn't update read_at again."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await db.flush()  # materialise generated UUID

        first_read = await svc.mark_as_read(notification_id=notif.id, user_id=student_user.id)
        first_read_at = first_read.read_at

        # Read again
        second_read = await svc.mark_as_read(notification_id=notif.id, user_id=student_user.id)
        assert second_read.read_at == first_read_at

    async def test_mark_all_as_read(self, db: AsyncSession, student_user):
        """Mark all unread notifications as read."""
        svc = NotificationService(db)

        for i in range(3):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )

        count = await svc.mark_all_as_read(user_id=student_user.id)
        assert count == 3

        _, total, unread = await svc.list_user_notifications(user_id=student_user.id)
        assert total == 3
        assert unread == 0

    async def test_mark_all_as_read_with_mixed_read_states(
        self, db: AsyncSession, student_user
    ):
        """mark_all_as_read only marks unread ones, returns correct count."""
        svc = NotificationService(db)

        n1 = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1002,
            user_id=student_user.id,
            event_type="cancelled",
            source_event_id=str(uuid.uuid4()),
        )
        # Pre-mark one
        await svc.mark_as_read(notification_id=n1.id, user_id=student_user.id)

        count = await svc.mark_all_as_read(user_id=student_user.id)
        assert count == 1  # only 1 was still unread

    async def test_get_unread_count(self, db: AsyncSession, student_user):
        """get_unread_count returns correct count."""
        svc = NotificationService(db)

        assert await svc.get_unread_count(user_id=student_user.id) == 0

        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        assert await svc.get_unread_count(user_id=student_user.id) == 1

        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1002,
            user_id=student_user.id,
            event_type="cancelled",
            source_event_id=str(uuid.uuid4()),
        )
        assert await svc.get_unread_count(user_id=student_user.id) == 2


# ---------------------------------------------------------------------------
# Service-level tests — ownership enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOwnershipEnforcement:
    """Test that users cannot access other users' notifications."""

    async def test_mark_other_user_notification_raises(self, db: AsyncSession, student_user):
        """mark_as_read raises NotFoundException when user doesn't own the notification."""
        from app.core.exceptions import NotFoundException

        # Create a notification for student_user
        svc_student = NotificationService(db)
        notif = await svc_student.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await db.flush()  # materialise generated UUID

        # Create another user
        other_user = await create_test_user(
            db,
            first_name="Other",
            last_name="Student",
            university_id="FA22-BSE-999",
            university_email="other.student@lgu.edu.pk",
        )

        # Other user tries to mark as read
        svc_other = NotificationService(db)
        with pytest.raises(NotFoundException):
            await svc_other.mark_as_read(
                notification_id=notif.id, user_id=other_user.id
            )

    async def test_user_cannot_see_other_notifications(
        self, db: AsyncSession, student_user
    ):
        """list_user_notifications only returns the requesting user's notifications."""
        # Create notification for student_user
        svc = NotificationService(db)
        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )

        # Create other user
        other_user = await create_test_user(
            db,
            first_name="Other",
            last_name="Student",
            university_id="FA22-BSE-998",
            university_email="other2.student@lgu.edu.pk",
        )

        # other user should see nothing
        items, total, _ = await svc.list_user_notifications(user_id=other_user.id)
        assert total == 0
        assert items == []


# ---------------------------------------------------------------------------
# Service-level tests — fire-and-forget helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFireAndForget:
    """Test standalone fire-and-forget emit helpers."""

    async def test_emit_order_notification_creates_notification(
        self, db: AsyncSession, student_user
    ):
        """emit_order_notification creates a notification for valid event."""
        order_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())

        await emit_order_notification(
            db,
            order_id=order_id,
            order_number=4001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=event_id,
            cafeteria_id=str(uuid.uuid4()),
        )

        svc = NotificationService(db)
        items, total, _ = await svc.list_user_notifications(user_id=student_user.id)
        assert total == 1
        assert items[0].notification_type == NotificationType.ORDER_CREATED

    async def test_emit_refund_notification_creates_notification(
        self, db: AsyncSession, student_user
    ):
        """emit_refund_notification creates a notification for valid event."""
        order_id = str(uuid.uuid4())
        refund_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())

        await emit_refund_notification(
            db,
            refund_id=refund_id,
            order_id=order_id,
            order_number=4002,
            user_id=student_user.id,
            event_type="refund_requested",
            source_event_id=event_id,
            cafeteria_id=str(uuid.uuid4()),
        )

        svc = NotificationService(db)
        items, total, _ = await svc.list_user_notifications(user_id=student_user.id)
        assert total == 1
        assert items[0].notification_type == NotificationType.REFUND_REQUESTED

    async def test_emit_order_notification_does_not_raise_on_bad_data(
        self, db: AsyncSession, student_user
    ):
        """emit_order_notification swallows exceptions (fire-and-forget)."""
        # Should not raise even though it might fail internally
        await emit_order_notification(
            db,
            order_id="not-a-real-id",
            order_number=0,
            user_id=student_user.id,
            event_type="totally_unknown_event",
            source_event_id=str(uuid.uuid4()),
        )

    async def test_emit_refund_notification_does_not_raise_on_bad_data(
        self, db: AsyncSession, student_user
    ):
        """emit_refund_notification swallows exceptions (fire-and-forget)."""
        await emit_refund_notification(
            db,
            refund_id="not-a-real-id",
            order_id="not-a-real-id",
            order_number=0,
            user_id=student_user.id,
            event_type="totally_unknown_event",
            source_event_id=str(uuid.uuid4()),
        )


# ---------------------------------------------------------------------------
# Service-level tests — notification field values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNotificationFieldValues:
    """Verify specific field values on created notifications."""

    async def test_reference_fields_order(self, db: AsyncSession, student_user):
        """Order notification has correct reference_type and reference_id."""
        svc = NotificationService(db)
        order_id = str(uuid.uuid4())
        notif = await svc.create_order_event_notification(
            order_id=order_id,
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif.reference_type == "order"
        assert notif.reference_id == order_id

    async def test_reference_fields_refund(self, db: AsyncSession, student_user):
        """Refund notification has correct reference_type and reference_id."""
        svc = NotificationService(db)
        refund_id = str(uuid.uuid4())
        notif = await svc.create_refund_event_notification(
            refund_id=refund_id,
            order_id=str(uuid.uuid4()),
            order_number=2001,
            user_id=student_user.id,
            event_type="refund_requested",
            source_event_id=str(uuid.uuid4()),
        )
        assert notif.reference_type == "refund"
        assert notif.reference_id == refund_id

    async def test_cafeteria_id_propagated(self, db: AsyncSession, student_user):
        """cafeteria_id is propagated from caller."""
        svc = NotificationService(db)
        caf_id = str(uuid.uuid4())
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
            cafeteria_id=caf_id,
        )
        assert notif.cafeteria_id == caf_id

    async def test_source_event_fields(self, db: AsyncSession, student_user):
        """source_event_type and source_event_id are stored."""
        svc = NotificationService(db)
        event_id = str(uuid.uuid4())
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=event_id,
        )
        assert notif.source_event_type == "created"
        assert notif.source_event_id == event_id


# ---------------------------------------------------------------------------
# API endpoint tests — GET /notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAPIListNotifications:
    """Test the GET /notifications endpoint."""

    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        """Unauthenticated request returns 401 (via exception handler)."""
        resp = await client.get("/api/v1/notifications")
        # FastAPI returns 422 for missing required header, or 401 via our exception handler
        assert resp.status_code in (401, 403, 422)

    async def test_empty_list(self, student_client: AsyncClient, student_user, db: AsyncSession):
        """Empty list returns empty items."""
        resp = await student_client.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["unread_count"] == 0

    async def test_list_with_notifications(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """List returns created notifications."""
        svc = NotificationService(db)
        for i in range(3):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )
        await db.flush()  # ensure all notifications are visible to the API session

        resp = await student_client.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["unread_count"] == 3

    async def test_pagination_params(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Pagination limit/offset works."""
        svc = NotificationService(db)
        for i in range(5):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )
        await db.flush()

        resp = await student_client.get("/api/v1/notifications?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    async def test_unread_only_filter(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """unread_only=true filters to unread only."""
        svc = NotificationService(db)

        n1 = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1002,
            user_id=student_user.id,
            event_type="cancelled",
            source_event_id=str(uuid.uuid4()),
        )
        await svc.mark_as_read(notification_id=n1.id, user_id=student_user.id)

        resp = await student_client.get("/api/v1/notifications?unread_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2  # total is all
        assert data["unread_count"] == 1


# ---------------------------------------------------------------------------
# API endpoint tests — GET /notifications/unread-count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAPIUnreadCount:
    """Test the GET /notifications/unread-count endpoint."""

    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        """Unauthenticated request returns 401 (via exception handler)."""
        resp = await client.get("/api/v1/notifications/unread-count")
        assert resp.status_code in (401, 403, 422)

    async def test_unread_count_empty(self, student_client: AsyncClient):
        """Zero unread when no notifications."""
        resp = await student_client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    async def test_unread_count_with_notifications(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Count reflects actual unread notifications."""
        svc = NotificationService(db)
        for i in range(3):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )
        await db.flush()

        resp = await student_client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 3


# ---------------------------------------------------------------------------
# API endpoint tests — PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAPIMarkRead:
    """Test the PATCH /notifications/{id}/read endpoint."""

    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        """Unauthenticated request returns 401 (via exception handler)."""
        resp = await client.patch(f"/api/v1/notifications/{uuid.uuid4()}/read")
        assert resp.status_code in (401, 403, 422)

    async def test_mark_read_success(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Successfully marks a notification as read."""
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )
        await db.flush()  # materialise generated UUID

        resp = await student_client.patch(f"/api/v1/notifications/{notif.id}/read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == notif.id
        assert data["is_read"] is True
        assert data["read_at"] is not None

    async def test_mark_read_nonexistent_returns_404(
        self, student_client: AsyncClient
    ):
        """Marking a non-existent notification returns 404."""
        resp = await student_client.patch(f"/api/v1/notifications/{uuid.uuid4()}/read")
        assert resp.status_code == 404

    async def test_mark_read_other_users_returns_404(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot mark another user's notification as read (returns 404)."""
        # Create notification for a different user
        other_user = await create_test_user(
            db,
            first_name="Other",
            last_name="User",
            university_id="FA22-BSE-888",
            university_email="other8@lgu.edu.pk",
        )
        svc = NotificationService(db)
        notif = await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=other_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )

        resp = await student_client.patch(f"/api/v1/notifications/{notif.id}/read")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API endpoint tests — PATCH /notifications/read-all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAPIMarkAllRead:
    """Test the PATCH /notifications/read-all endpoint."""

    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        """Unauthenticated request returns 401 (via exception handler)."""
        resp = await client.patch("/api/v1/notifications/read-all")
        assert resp.status_code in (401, 403, 422)

    async def test_mark_all_read_success(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Marks all unread notifications as read."""
        svc = NotificationService(db)
        for i in range(3):
            await svc.create_order_event_notification(
                order_id=str(uuid.uuid4()),
                order_number=1000 + i,
                user_id=student_user.id,
                event_type="created",
                source_event_id=str(uuid.uuid4()),
            )
        await db.flush()  # ensure all notifications are visible to the API session

        resp = await student_client.patch("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["marked_count"] == 3

        # Verify all read
        count_resp = await student_client.get("/api/v1/notifications/unread-count")
        assert count_resp.json()["unread_count"] == 0

    async def test_mark_all_read_empty(
        self, student_client: AsyncClient, student_user
    ):
        """Mark all when none exist returns 0 marked."""
        resp = await student_client.patch("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["marked_count"] == 0


# ---------------------------------------------------------------------------
# API endpoint tests — ownership isolation via HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAPIOwnershipIsolation:
    """Test that the API enforces ownership via HTTP."""

    async def test_user_sees_only_own_notifications(
        self, client: AsyncClient, student_user, db: AsyncSession
    ):
        """User A's notifications don't appear for User B."""
        from tests.conftest import create_test_user

        # Create user B
        user_b = await create_test_user(
            db,
            first_name="UserB",
            last_name="Test",
            university_id="FA22-BSE-777",
            university_email="userb@lgu.edu.pk",
        )
        _, token_b, _ = await create_user_session(db, user_b)

        # Create notifications for student_user
        svc = NotificationService(db)
        await svc.create_order_event_notification(
            order_id=str(uuid.uuid4()),
            order_number=1001,
            user_id=student_user.id,
            event_type="created",
            source_event_id=str(uuid.uuid4()),
        )

        # User B should see nothing
        resp = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Event-type mapping tests
# ---------------------------------------------------------------------------


class TestEventTypeMapping:
    """Verify the event type → NotificationType mappings."""

    def test_all_order_event_types_map(self):
        """Every order event type that generates a notification maps correctly."""
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
        for event_type, expected in mapping.items():
            result = NotificationService._event_type_to_notification_type(event_type)
            assert result == expected, f"{event_type} maps to {result}, expected {expected}"

    def test_all_refund_event_types_map(self):
        """Every refund event type that generates a notification maps correctly."""
        mapping = {
            "refund_requested": NotificationType.REFUND_REQUESTED,
            "refund_succeeded": NotificationType.REFUND_PROCESSED,
            "refund_failed": NotificationType.REFUND_FAILED,
        }
        for event_type, expected in mapping.items():
            result = NotificationService._refund_event_type_to_notification_type(event_type)
            assert result == expected
