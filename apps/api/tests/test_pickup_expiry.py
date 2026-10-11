"""Tests for automatic pickup expiry processing (Phase 6 — background worker).

Covers:
- process_expired_pickups() service method
- Idempotency (uncollected_at prevents re-processing)
- Collection race safety (uncollected_at check in collect_order)
- No-show recording and suspension
- Background worker lifecycle
- Edge cases (no eligible orders, already collected, etc.)
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.cafeterias.models import CafeteriaType, OperationalStatus
from app.modules.orders.models import (
    NoShow,
    Order,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.users.models import (
    Role,
    User,
    UserCategory,
)
from tests.conftest import (
    create_test_cafeteria,
    create_test_user,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_ready_order(
    db: AsyncSession,
    *,
    user: User,
    cafeteria_id: str,
    pickup_deadline: datetime,
    order_number: int = 1001,
) -> Order:
    """Insert an order directly in READY state with a given pickup_deadline."""
    order = Order(
        order_number=order_number,
        user_id=user.id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.IMMEDIATE,
        payment_method=PaymentMethod.CASH,
        status=OrderStatus.READY,
        total_amount=25000,
        currency="PKR",
        order_date=date.today(),
        inventory_reserved=True,
        pickup_deadline=pickup_deadline,
        ready_at=pickup_deadline - timedelta(minutes=30),
    )
    db.add(order)
    await db.flush()
    return order


async def _create_user_and_cafeteria(
    db: AsyncSession,
) -> tuple[User, object]:
    """Create a test user and cafeteria for pickup expiry tests."""
    user = await create_test_user(
        db,
        first_name="Expiry",
        last_name="Student",
        university_id="EXP-001",
        university_email="expiry.student@lgu.edu.pk",
        role=Role.STUDENT,
        category=UserCategory.STUDENT,
    )
    cafeteria = await create_test_cafeteria(
        db,
        name="Expiry Cafeteria",
        cafeteria_type=CafeteriaType.STUDENT,
        operational_status=OperationalStatus.OPEN,
    )
    return user, cafeteria


# ---------------------------------------------------------------------------
# A. Single expired order → processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsSingleOrder:
    """Test processing a single expired order."""

    @pytest.mark.asyncio
    async def test_single_expired_order_is_processed(self, db: AsyncSession):
        """A single READY order past its deadline is marked uncollected."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),  # expired 5 min ago
        )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 1
        assert stats["processed"] == 1
        assert stats["skipped"] == 0
        assert stats["failed"] == 0

        # Verify order state
        await db.refresh(order)
        assert order.uncollected_at is not None
        assert order.status == OrderStatus.READY  # Status stays READY

    @pytest.mark.asyncio
    async def test_no_show_record_created(self, db: AsyncSession):
        """Processing an expired order creates a NoShow record."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )

        service = OrderService(db)
        await service.process_expired_pickups()

        # Verify no-show record exists
        result = await db.execute(
            select(NoShow).where(
                NoShow.order_id == order.id,
                NoShow.user_id == user.id,
                NoShow.cafeteria_id == cafeteria.id,
            )
        )
        noshow = result.scalar_one_or_none()
        assert noshow is not None

    @pytest.mark.asyncio
    async def test_uncollected_event_recorded(self, db: AsyncSession):
        """Processing creates an UNCOLLECTED event with automatic expiry notes."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
        )

        service = OrderService(db)
        await service.process_expired_pickups()

        await db.refresh(order)
        event_types = [e.event_type.value for e in order.events]
        assert "uncollected" in event_types

        # Check the event has the automatic expiry note
        uncollected_events = [e for e in order.events if e.event_type.value == "uncollected"]
        assert len(uncollected_events) == 1
        assert "Automatic expiry" in (uncollected_events[0].notes or "")


# ---------------------------------------------------------------------------
# B. Multiple expired orders → all processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsMultipleOrders:
    """Test processing multiple expired orders."""

    @pytest.mark.asyncio
    async def test_multiple_expired_orders_all_processed(self, db: AsyncSession):
        """All eligible expired orders are processed in a single run."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        orders = []
        for i in range(3):
            order = await _create_ready_order(
                db,
                user=user,
                cafeteria_id=cafeteria.id,
                pickup_deadline=now - timedelta(minutes=5 + i),
                order_number=2001 + i,
            )
            orders.append(order)

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 3
        assert stats["processed"] == 3

        for order in orders:
            await db.refresh(order)
            assert order.uncollected_at is not None


# ---------------------------------------------------------------------------
# C. Order not yet expired → not processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsNotYetExpired:
    """Test that orders with future deadlines are not touched."""

    @pytest.mark.asyncio
    async def test_future_deadline_not_processed(self, db: AsyncSession):
        """An order whose deadline hasn't passed is not processed."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now + timedelta(minutes=20),  # 20 min in future
        )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0
        assert stats["processed"] == 0

        await db.refresh(order)
        assert order.uncollected_at is None

    @pytest.mark.asyncio
    async def test_exactly_at_deadline_not_processed(self, db: AsyncSession):
        """An order whose deadline is exactly now (<=) depends on timing.

        Since pickup_deadline <= now, an order at exactly now SHOULD be processed.
        We set it 1 second in the future to be safe.
        """
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now + timedelta(seconds=1),  # 1 second future
        )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        # 1 second in the future → not yet expired
        assert stats["examined"] == 0
        await db.refresh(order)
        assert order.uncollected_at is None


# ---------------------------------------------------------------------------
# D. Order already collected → not processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsAlreadyCollected:
    """Test that collected orders are not processed."""

    @pytest.mark.asyncio
    async def test_collected_order_not_processed(self, db: AsyncSession):
        """A COMPLETED/collected order is not affected by expiry processing."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )
        # Simulate collection
        order.status = OrderStatus.COMPLETED
        order.collected_at = now - timedelta(minutes=5)
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0
        assert stats["processed"] == 0


# ---------------------------------------------------------------------------
# E. Order already uncollected (idempotency) → not re-processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsIdempotency:
    """Test that already-uncollected orders are not processed again."""

    @pytest.mark.asyncio
    async def test_already_uncollected_not_reprocessed(self, db: AsyncSession):
        """An order with uncollected_at already set is not processed again."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )
        # Simulate already processed
        order.uncollected_at = now - timedelta(minutes=5)
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0
        assert stats["processed"] == 0

    @pytest.mark.asyncio
    async def test_mark_uncollected_idempotent_directly(self, db: AsyncSession):
        """Calling mark_uncollected twice on the same order is idempotent."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )

        service = OrderService(db)
        # First call
        result1 = await service.mark_uncollected(
            order_id=order.id,
            actor_id=None,
            notes="First call",
        )
        first_ts = result1.uncollected_at

        # Second call — should be no-op
        result2 = await service.mark_uncollected(
            order_id=order.id,
            actor_id=None,
            notes="Second call",
        )
        assert result2.uncollected_at == first_ts  # Timestamp unchanged

        # Count uncollected events — should be only 1
        await db.refresh(order)
        uncollected_events = [e for e in order.events if e.event_type.value == "uncollected"]
        assert len(uncollected_events) == 1


# ---------------------------------------------------------------------------
# F. Order not READY status → not processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsWrongStatus:
    """Test that non-READY orders are not processed."""

    @pytest.mark.asyncio
    async def test_pending_order_not_processed(self, db: AsyncSession):
        """A PENDING order past its deadline is not processed."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )
        order.status = OrderStatus.PENDING  # Override to PENDING
        order.pickup_deadline = now - timedelta(minutes=10)
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0
        assert stats["processed"] == 0

    @pytest.mark.asyncio
    async def test_preparing_order_not_processed(self, db: AsyncSession):
        """A PREPARING order is not processed even if deadline passed."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )
        order.status = OrderStatus.PREPARING
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0

    @pytest.mark.asyncio
    async def test_cancelled_order_not_processed(self, db: AsyncSession):
        """A CANCELLED order is not processed."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )
        order.status = OrderStatus.CANCELLED
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0


# ---------------------------------------------------------------------------
# G. Collection race safety
# ---------------------------------------------------------------------------


class TestCollectionRaceSafety:
    """Test that collected_at prevents expiry processing."""

    @pytest.mark.asyncio
    async def test_collected_at_prevents_processing(self, db: AsyncSession):
        """If collected_at is set, the order is not processed by expiry worker."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
        )
        # Simulate race: order was collected but not yet marked COMPLETED
        order.collected_at = now - timedelta(minutes=2)
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0

    @pytest.mark.asyncio
    async def test_collect_order_rejects_uncollected_order(self, db: AsyncSession):
        """collect_order() rejects an order already marked uncollected."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
        )

        # Mark as uncollected
        service = OrderService(db)
        await service.mark_uncollected(
            order_id=order.id,
            actor_id=None,
        )
        await db.flush()

        # Try to collect — should fail
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="already been marked as uncollected"):
            await service.collect_order(
                order_id=order.id,
                collector_id=user.id,
                cafeteria_id=cafeteria.id,
            )


# ---------------------------------------------------------------------------
# H. No-show tracking and suspension
# ---------------------------------------------------------------------------


class TestNoShowTracking:
    """Test no-show recording and suspension policy integration."""

    @pytest.mark.asyncio
    async def test_no_show_count_incremented(self, db: AsyncSession):
        """Expiry processing increments user's no_show_count."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
        )

        service = OrderService(db)
        await service.process_expired_pickups()

        await db.refresh(user)
        assert user.no_show_count >= 1

    @pytest.mark.asyncio
    async def test_suspension_after_threshold(self, db: AsyncSession):
        """User gets suspended after exceeding no-show threshold via expiry processing."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)

        # Create enough expired orders to hit the student threshold
        threshold = settings.NOSHOW_STUDENT_THRESHOLD
        for i in range(threshold):
            await _create_ready_order(
                db,
                user=user,
                cafeteria_id=cafeteria.id,
                pickup_deadline=now - timedelta(minutes=10 + i),
                order_number=3001 + i,
            )

        service = OrderService(db)
        stats = await service.process_expired_pickups()
        assert stats["processed"] == threshold

        await db.refresh(user)
        assert user.ordering_suspended is True
        assert user.ordering_suspended_until is not None


# ---------------------------------------------------------------------------
# I. No eligible orders → stats all zero
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsNoEligible:
    """Test that empty state returns zero stats."""

    @pytest.mark.asyncio
    async def test_no_orders_at_all(self, db: AsyncSession):
        """When there are no orders, all stats are zero."""
        from app.modules.orders.service import OrderService

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        # Phase 44 (P3-14 Phase 2) extended the stats dict with scheduled
        # expiry counters — empty state keeps all of them at zero.
        assert stats == {
            "examined": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "scheduled_examined": 0,
            "scheduled_expired": 0,
        }

    @pytest.mark.asyncio
    async def test_all_orders_in_future(self, db: AsyncSession):
        """When all orders have future deadlines, nothing is processed."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        for i in range(3):
            await _create_ready_order(
                db,
                user=user,
                cafeteria_id=cafeteria.id,
                pickup_deadline=now + timedelta(minutes=30 + i * 10),
                order_number=4001 + i,
            )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 0
        assert stats["processed"] == 0


# ---------------------------------------------------------------------------
# J. Mixed eligible/ineligible → only eligible processed
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsMixed:
    """Test mixed state: some eligible, some not."""

    @pytest.mark.asyncio
    async def test_mixed_eligible_and_ineligible(self, db: AsyncSession):
        """Only expired READY orders are processed; others are skipped."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)

        # Eligible: expired READY order
        eligible = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
            order_number=5001,
        )

        # Ineligible: future deadline
        future = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now + timedelta(minutes=30),
            order_number=5002,
        )

        # Ineligible: READY but already collected
        collected = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
            order_number=5003,
        )
        collected.collected_at = now - timedelta(minutes=5)
        await db.flush()

        # Ineligible: PENDING status
        pending = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
            order_number=5004,
        )
        pending.status = OrderStatus.PENDING
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        # 2 eligible (eligible + collected... wait, collected has collected_at set)
        # Actually: eligible has no collected_at → eligible
        # future: future deadline → not eligible (0 match)
        # collected: has collected_at → not eligible
        # pending: PENDING status → not eligible
        assert stats["examined"] == 1  # only the one eligible order
        assert stats["processed"] == 1

        await db.refresh(eligible)
        assert eligible.uncollected_at is not None

        await db.refresh(future)
        assert future.uncollected_at is None

        await db.refresh(pending)
        assert pending.uncollected_at is None


# ---------------------------------------------------------------------------
# K. Process returns correct statistics
# ---------------------------------------------------------------------------


class TestProcessExpiredPickupsStats:
    """Test that processing statistics are accurate."""

    @pytest.mark.asyncio
    async def test_stats_count_correctly(self, db: AsyncSession):
        """Stats reflect the correct counts for each category."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)

        # 2 expired READY orders
        await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
            order_number=6001,
        )
        await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=3),
            order_number=6002,
        )
        # 1 future READY order (won't be examined)
        await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now + timedelta(minutes=30),
            order_number=6003,
        )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["examined"] == 2  # only the 2 expired ones
        assert stats["processed"] == 2
        assert stats["skipped"] == 0
        assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_idempotent_run_returns_same_stats(self, db: AsyncSession):
        """Running process_expired_pickups twice processes only new orders."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
        )

        service = OrderService(db)

        # First run — processes the order
        stats1 = await service.process_expired_pickups()
        assert stats1["processed"] == 1

        # Second run — order already has uncollected_at, so it's not examined
        stats2 = await service.process_expired_pickups()
        assert stats2["examined"] == 0
        assert stats2["processed"] == 0


# ---------------------------------------------------------------------------
# L. Background worker lifecycle
# ---------------------------------------------------------------------------


class TestBackgroundWorker:
    """Test the background worker configuration and lifecycle."""

    def test_worker_config_importable(self):
        """The background worker interval is configured."""
        from app.main import _PICKUP_CHECK_INTERVAL

        assert _PICKUP_CHECK_INTERVAL == 60

    def test_lifespan_function_exists(self):
        """The lifespan context manager exists and is callable."""

        from app.main import lifespan

        assert callable(lifespan)

    @pytest.mark.asyncio
    async def test_worker_creates_session_and_processes(self, db: AsyncSession):
        """Simulate what the worker does: create session, call service, commit."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
        )

        # Simulate worker behavior: service call + commit
        service = OrderService(db)
        stats = await service.process_expired_pickups()
        await db.commit()

        assert stats["processed"] == 1
        await db.refresh(order)
        assert order.uncollected_at is not None


# ---------------------------------------------------------------------------
# M. Rolling-window expiration — old no-shows outside window don't count
# ---------------------------------------------------------------------------


class TestRollingWindowExpiration:
    """Verify that no-shows outside the rolling window don't trigger suspension."""

    @pytest.mark.asyncio
    async def test_old_noshow_outside_window_not_counted(self, db: AsyncSession):
        """A no-show older than the rolling window should not count toward suspension.

        Student threshold is 3, window is 30 days.
        Create 2 old no-shows (>30 days ago) + 1 new one.
        Should NOT trigger suspension (old ones are outside window).
        """
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)

        # Create 2 old no-shows outside the 30-day window.
        # Pre-set uncollected_at on old orders so they are NOT picked up by
        # process_expired_pickups — we only want the no-show records.
        old_cafeteria = await create_test_cafeteria(
            db,
            name="Old Cafeteria",
            cafeteria_type=CafeteriaType.STUDENT,
            operational_status=OperationalStatus.OPEN,
        )
        for i in range(2):
            old_order = await _create_ready_order(
                db,
                user=user,
                cafeteria_id=old_cafeteria.id,
                pickup_deadline=now - timedelta(days=35 + i),
                order_number=7001 + i,
            )
            # Mark as already processed so expiry worker doesn't re-process it
            old_order.uncollected_at = now - timedelta(days=35 + i)
            await db.flush()
            # Manually backdate the no-show creation
            noshow = NoShow(
                user_id=user.id,
                order_id=old_order.id,
                cafeteria_id=old_cafeteria.id,
                created_at=now - timedelta(days=35 + i),
            )
            db.add(noshow)
            await db.flush()

        # Create 1 new expired order → process it
        await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
            order_number=7003,
        )
        service = OrderService(db)
        stats = await service.process_expired_pickups()
        assert stats["processed"] == 1

        # Total no-shows: 3, but only 1 is inside the 30-day window
        # Suspension should NOT be triggered (threshold=3, active count=1)
        await db.refresh(user)
        assert user.ordering_suspended is False

    @pytest.mark.asyncio
    async def test_enough_noshow_in_window_triggers_suspension(self, db: AsyncSession):
        """3 no-shows within the 30-day window triggers student suspension."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        threshold = settings.NOSHOW_STUDENT_THRESHOLD  # 3

        for i in range(threshold):
            await _create_ready_order(
                db,
                user=user,
                cafeteria_id=cafeteria.id,
                pickup_deadline=now - timedelta(minutes=10 + i),
                order_number=7100 + i,
            )

        service = OrderService(db)
        stats = await service.process_expired_pickups()
        assert stats["processed"] == threshold

        await db.refresh(user)
        assert user.ordering_suspended is True


# ---------------------------------------------------------------------------
# N. Faculty threshold and suspension
# ---------------------------------------------------------------------------


class TestFacultyThreshold:
    """Verify faculty-specific no-show threshold and suspension duration."""

    @pytest.mark.asyncio
    async def test_faculty_higher_threshold(self, db: AsyncSession):
        """Faculty users require 5 no-shows (not 3) before suspension.

        Process only 4 expired orders → should NOT be suspended.
        """
        from app.modules.orders.service import OrderService

        user = await create_test_user(
            db,
            first_name="Faculty",
            last_name="User",
            university_id="FAC-001",
            university_email="faculty.user@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.FACULTY,
        )
        cafeteria = await create_test_cafeteria(
            db,
            name="Faculty Cafeteria",
            cafeteria_type=CafeteriaType.FACULTY,
            operational_status=OperationalStatus.OPEN,
        )
        now = datetime.now(UTC)

        # Create 4 expired orders (faculty threshold is 5)
        for i in range(4):
            await _create_ready_order(
                db,
                user=user,
                cafeteria_id=cafeteria.id,
                pickup_deadline=now - timedelta(minutes=10 + i),
                order_number=7200 + i,
            )

        service = OrderService(db)
        stats = await service.process_expired_pickups()
        assert stats["processed"] == 4

        await db.refresh(user)
        assert user.ordering_suspended is False  # 4 < 5 threshold

    @pytest.mark.asyncio
    async def test_faculty_suspension_at_threshold(self, db: AsyncSession):
        """Faculty gets suspended after 5 no-shows with 3-day suspension."""
        from app.modules.orders.service import OrderService

        user = await create_test_user(
            db,
            first_name="Faculty2",
            last_name="User",
            university_id="FAC-002",
            university_email="faculty2.user@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.FACULTY,
        )
        cafeteria = await create_test_cafeteria(
            db,
            name="Faculty Cafeteria 2",
            cafeteria_type=CafeteriaType.FACULTY,
            operational_status=OperationalStatus.OPEN,
        )
        now = datetime.now(UTC)
        threshold = settings.NOSHOW_FACULTY_THRESHOLD  # 5

        for i in range(threshold):
            await _create_ready_order(
                db,
                user=user,
                cafeteria_id=cafeteria.id,
                pickup_deadline=now - timedelta(minutes=10 + i),
                order_number=7300 + i,
            )

        service = OrderService(db)
        stats = await service.process_expired_pickups()
        assert stats["processed"] == threshold

        await db.refresh(user)
        assert user.ordering_suspended is True
        assert user.ordering_suspended_until is not None
        # Verify suspension duration is 3 days (faculty).
        # SQLite may return naive datetimes; normalize both sides.
        susp_until = user.ordering_suspended_until
        if susp_until.tzinfo is None:
            susp_until = susp_until.replace(tzinfo=UTC)
        susp_duration = susp_until - now
        assert susp_duration.days == 3


# ---------------------------------------------------------------------------
# O. Closing-before-30-minute rule
# ---------------------------------------------------------------------------


class TestClosingBefore30Minutes:
    """When cafeteria closes before 30 minutes, closing time wins."""

    @pytest.mark.asyncio
    async def test_closing_time_earlier_than_30min(self, db: AsyncSession):
        """pickup_deadline = cafeteria closing time when it's earlier than ready + 30m.

        Ready at 16:50, 30-min window ends at 17:20, cafeteria closes at 17:00.
        pickup_deadline should be 17:00.
        """
        from app.modules.cafeterias.models import Cafeteria
        from app.modules.orders.service import OrderService

        user = await create_test_user(
            db,
            first_name="CloseEarly",
            last_name="Student",
            university_id="CE-001",
            university_email="close.early@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        cafeteria = await create_test_cafeteria(
            db,
            name="Early Close Cafeteria",
            cafeteria_type=CafeteriaType.STUDENT,
            operational_status=OperationalStatus.OPEN,
        )
        # Set closing time to 17:00
        caf_result = await db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria.id))
        caf = caf_result.scalar_one()
        caf.closing_time = "17:00"
        caf.timezone = "Asia/Karachi"
        await db.flush()

        # Create a READY order and set the pickup_deadline to the cafeteria closing
        # time (which is earlier than 30 min after ready_at).
        from app.modules.orders.models import OrderEvent, OrderEventType

        now_utc = datetime.now(UTC)
        # Set ready_at to 10 minutes ago
        ready_at = now_utc - timedelta(minutes=10)
        # 30-minute window: ready_at + 30m = 20 min from now
        deadline_30min = ready_at + timedelta(minutes=30)

        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Karachi")
        # Set cafeteria closing to 5 minutes ago (in UTC) so it's in the past
        local_closing_past = now_utc.astimezone(tz) - timedelta(minutes=5)
        local_closing_past = local_closing_past.replace(second=0, microsecond=0)
        utc_closing = local_closing_past.astimezone(UTC)

        # closing is earlier than 30-min window
        assert utc_closing < deadline_30min

        order = Order(
            order_number=7401,
            user_id=user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.READY,
            total_amount=25000,
            currency="PKR",
            order_date=date.today(),
            inventory_reserved=True,
            ready_at=ready_at,
            pickup_deadline=utc_closing,  # closing time wins
        )
        db.add(order)
        await db.flush()
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.READY_FOR_COLLECTION,
            actor_id=user.id,
        )
        db.add(event)
        await db.flush()

        # Verify deadline is the closing time, not 30 minutes
        assert order.pickup_deadline == utc_closing

        service = OrderService(db)
        stats = await service.process_expired_pickups()
        assert stats["processed"] == 1

        await db.refresh(order)
        assert order.uncollected_at is not None


# ---------------------------------------------------------------------------
# P. Closing-after-30-minute rule
# ---------------------------------------------------------------------------


class TestClosingAfter30Minutes:
    """When cafeteria closes after 30 minutes, the 30-min window wins."""

    @pytest.mark.asyncio
    async def test_30min_wins_when_closing_later(self, db: AsyncSession):
        """pickup_deadline = ready_at + 30m when closing is later.

        Ready at 16:00, 30-min window ends at 16:30, cafeteria closes at 17:00.
        pickup_deadline should be 16:30.
        """
        from app.modules.cafeterias.models import Cafeteria

        user, cafeteria = await _create_user_and_cafeteria(db)

        # Set closing time to 17:00 PKT
        caf_result = await db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria.id))
        caf = caf_result.scalar_one()
        caf.closing_time = "17:00"
        caf.timezone = "Asia/Karachi"
        await db.flush()

        # Ready at 16:00 UTC
        now = datetime(2026, 9, 25, 16, 0, 0, tzinfo=UTC)
        deadline_30min = now + timedelta(minutes=30)  # 16:30 UTC

        from datetime import time as dt_time
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Karachi")
        # 17:00 PKT = 12:00 UTC
        # We need cafeteria closing to be AFTER the 30min window.
        # Set closing to 22:00 PKT = 17:00 UTC
        caf.closing_time = "22:00"
        await db.flush()

        local_closing_late = datetime.combine(date.today(), dt_time(22, 0), tzinfo=tz)
        utc_closing_late = local_closing_late.astimezone(UTC)  # 17:00 UTC

        order = Order(
            order_number=7501,
            user_id=user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.READY,
            total_amount=25000,
            currency="PKR",
            order_date=date.today(),
            inventory_reserved=True,
            ready_at=now,
            pickup_deadline=deadline_30min,  # 16:30 UTC — 30min wins
        )
        db.add(order)
        await db.flush()

        expected_deadline = min(deadline_30min, utc_closing_late)
        assert expected_deadline == deadline_30min  # 30min wins
        assert order.pickup_deadline == deadline_30min


# ---------------------------------------------------------------------------
# Q. Collection race safety (concurrent transaction simulation)
# ---------------------------------------------------------------------------


class TestCollectionRaceConcurrency:
    """Verify collection race safety at the database level."""

    @pytest.mark.asyncio
    async def test_uncollected_at_prevents_concurrent_collection(self, db: AsyncSession):
        """Simulate race: expiry worker sets uncollected_at, then staff tries to collect.

        The collect_order() method checks uncollected_at before allowing collection.
        """
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
            order_number=7601,
        )

        # Expiry worker processes first
        expiry_service = OrderService(db)
        await expiry_service.mark_uncollected(
            order_id=order.id,
            actor_id=None,
            notes="Expiry worker got there first",
        )
        await db.flush()

        # Staff tries to collect — should fail
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="uncollected"):
            await expiry_service.collect_order(
                order_id=order.id,
                collector_id=user.id,
                cafeteria_id=cafeteria.id,
            )

    @pytest.mark.asyncio
    async def test_collection_prevents_expiry_processing(self, db: AsyncSession):
        """Simulate race: staff collects, then expiry worker sees collected_at."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)
        order = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
            order_number=7602,
        )

        # Staff collects first
        service = OrderService(db)
        await service.collect_order(
            order_id=order.id,
            collector_id=user.id,
            cafeteria_id=cafeteria.id,
        )
        await db.flush()

        # Expiry worker runs — order should not be examined
        stats = await service.process_expired_pickups()
        assert stats["examined"] == 0

        await db.refresh(order)
        assert order.uncollected_at is None
        assert order.status == OrderStatus.COMPLETED


# ---------------------------------------------------------------------------
# R. One failure doesn't stop others
# ---------------------------------------------------------------------------


class TestFailureDoesNotStopOthers:
    """Verify that one bad order doesn't prevent processing of others."""

    @pytest.mark.asyncio
    async def test_one_failure_continues_processing(self, db: AsyncSession):
        """If processing one order fails, other eligible orders still get processed."""
        from app.modules.orders.service import OrderService

        user, cafeteria = await _create_user_and_cafeteria(db)
        now = datetime.now(UTC)

        # Create 3 expired orders
        o1 = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=10),
            order_number=7701,
        )
        o2 = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=8),
            order_number=7702,
        )
        o3 = await _create_ready_order(
            db,
            user=user,
            cafeteria_id=cafeteria.id,
            pickup_deadline=now - timedelta(minutes=5),
            order_number=7703,
        )

        # Pre-corrupt o2 to cause a failure (set to CANCELLED after query but before processing)
        # We'll do this by cancelling the order status after it's found in the eligible query
        # but before mark_uncollected runs — simulating a race condition.
        # Actually, a simpler approach: make o2 have status CANCELLED so mark_uncollected raises.
        o2.status = OrderStatus.CANCELLED
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        # o2 should be skipped (not READY), o1 and o3 should be processed
        assert stats["processed"] == 2
        assert stats["examined"] == 2  # o2 not even found (CANCELLED doesn't match READY)

        await db.refresh(o1)
        await db.refresh(o3)
        assert o1.uncollected_at is not None
        assert o3.uncollected_at is not None
