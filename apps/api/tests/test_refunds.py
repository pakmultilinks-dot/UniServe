"""Tests for refund processing — full/partial refunds, deadlines, authorization, invariants.

Covers:
- Refund creation (full and partial)
- Refund deadline enforcement (72-hour configurable)
- Over-refunding prevention
- Refund idempotency
- Refund authorization (admin, manager, staff, student, faculty)
- Manager cafeteria scope enforcement
- Multiple partial refunds
- Refund amount validation
- Payment status transitions (REFUNDED, PARTIALLY_REFUNDED)
- Refundable amount calculation
- Invalid refund reason rejection
- Refund API endpoints
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import (
    Order,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import (
    RefundEvent,
    RefundReason,
    RefundStatus,
)
from app.modules.refunds.processors.test_processor import TestRefundProcessor
from app.modules.refunds.service import REFUND_DEADLINE_HOURS, RefundService
from app.modules.users.models import Role
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_order_with_payment(
    db: AsyncSession,
    *,
    user_id: str,
    cafeteria_id: str,
    amount: int = 50000,
    payment_status: PaymentStatus = PaymentStatus.SUCCEEDED,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    order_status: OrderStatus = OrderStatus.PENDING,
    order_created_at: datetime | None = None,
):
    """Create an order + successful payment for refund tests.

    Returns (order, payment).
    """
    from datetime import date as date_type

    order = Order(
        order_number=9000 + int(uuid.uuid4().int % 1000),
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.IMMEDIATE,
        payment_method=payment_method,
        status=order_status,
        total_amount=amount,
        currency="PKR",
        order_date=date_type.today(),
        inventory_reserved=False,
    )
    if order_created_at:
        order.created_at = order_created_at
    db.add(order)
    await db.flush()

    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order.id,
        user_id=user_id,
        amount=amount,
        currency="PKR",
        status=payment_status,
        provider_name="test_provider",
        provider_reference=f"test_pay_{uuid.uuid4().hex[:12]}",
        idempotency_key=f"pay_{order.id}",
    )
    db.add(payment)
    await db.flush()

    return order, payment


# ---------------------------------------------------------------------------
# Refund Creation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefundCreation:
    """Test refund creation via service."""

    async def test_full_refund(self, student_user, db: AsyncSession):
        """Full refund for an order succeeds."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe1")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note="Changed my mind",
            requested_by_user_id=student_user.id,
            idempotency_key="refund_full_001",
        )

        assert refund.status == RefundStatus.PENDING
        assert refund.amount == 50000
        assert refund.reason == RefundReason.ORDER_CANCELLED
        assert refund.requested_by == student_user.id

    async def test_partial_refund(self, student_user, db: AsyncSession):
        """Partial refund creates a record for less than full amount."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe2")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=20000,
            reason="item_unavailable",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refund_partial_001",
        )

        assert refund.amount == 20000
        assert refund.reason == RefundReason.ITEM_UNAVAILABLE

    async def test_multiple_partial_refunds(self, student_user, db: AsyncSession):
        """Multiple partial refunds that don't exceed payment are allowed."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe3")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())

        r1 = await svc.create_refund(
            order_id=order.id,
            amount=15000,
            reason="item_unavailable",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refund_multi_001",
        )
        assert r1.status == RefundStatus.PENDING

        r2 = await svc.create_refund(
            order_id=order.id,
            amount=20000,
            reason="cafeteria_closed",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refund_multi_002",
        )
        assert r2.status == RefundStatus.PENDING

    async def test_over_refunding_blocked(self, student_user, db: AsyncSession):
        """Refund exceeding payment amount is blocked."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe4")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        with pytest.raises(Exception):
            await svc.create_refund(
                order_id=order.id,
                amount=99999,
                reason="order_cancelled",
                reason_note=None,
                requested_by_user_id=student_user.id,
                idempotency_key="refund_over_001",
            )

    async def test_refund_exceeding_remaining_blocked(self, student_user, db: AsyncSession):
        """After a partial refund, the next refund cannot exceed the remaining."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe5")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())

        # Process first refund of 30000
        r1 = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refund_exc_001",
        )
        r1.status = RefundStatus.SUCCEEDED
        await db.flush()

        # Now try to refund 25000 more (only 20000 remaining)
        with pytest.raises(Exception):
            await svc.create_refund(
                order_id=order.id,
                amount=25000,
                reason="order_cancelled",
                reason_note=None,
                requested_by_user_id=student_user.id,
                idempotency_key="refund_exc_002",
            )

    async def test_refund_idempotency(self, student_user, db: AsyncSession):
        """Same idempotency key returns existing refund."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe6")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())

        r1 = await svc.create_refund(
            order_id=order.id,
            amount=10000,
            reason="other",
            reason_note="test",
            requested_by_user_id=student_user.id,
            idempotency_key="refund_idemp_001",
        )
        r2 = await svc.create_refund(
            order_id=order.id,
            amount=10000,
            reason="other",
            reason_note="test",
            requested_by_user_id=student_user.id,
            idempotency_key="refund_idemp_001",
        )

        assert r1.id == r2.id

    async def test_refund_no_successful_payment_blocked(self, student_user, db: AsyncSession):
        """Refund for order without successful payment is blocked."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe7")
        order = Order(
            order_number=9500,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.PENDING,
            total_amount=50000,
            currency="PKR",
            order_date=datetime.now(UTC).date(),
            inventory_reserved=False,
        )
        db.add(order)
        await db.flush()

        svc = RefundService(db, TestRefundProcessor())
        with pytest.raises(Exception):
            await svc.create_refund(
                order_id=order.id,
                amount=50000,
                reason="order_cancelled",
                reason_note=None,
                requested_by_user_id=student_user.id,
                idempotency_key="refund_nopay_001",
            )

    async def test_refund_invalid_reason_rejected(self, student_user, db: AsyncSession):
        """Invalid refund reason string is rejected."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe8")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        with pytest.raises(Exception):
            await svc.create_refund(
                order_id=order.id,
                amount=10000,
                reason="totally_invalid_reason",
                reason_note=None,
                requested_by_user_id=student_user.id,
                idempotency_key="refund_badreason_001",
            )

    async def test_refund_deadline_enforced(self, student_user, db: AsyncSession):
        """Refund after deadline is blocked."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe9")
        order, payment = await _create_order_with_payment(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            amount=50000,
            order_created_at=datetime.now(UTC) - timedelta(hours=REFUND_DEADLINE_HOURS + 1),
        )

        svc = RefundService(db, TestRefundProcessor())
        with pytest.raises(Exception):
            await svc.create_refund(
                order_id=order.id,
                amount=50000,
                reason="order_cancelled",
                reason_note=None,
                requested_by_user_id=student_user.id,
                idempotency_key="refund_deadline_001",
            )

    async def test_refund_within_deadline_allowed(self, student_user, db: AsyncSession):
        """Refund within deadline is allowed."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe10")
        order, payment = await _create_order_with_payment(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            amount=50000,
            order_created_at=datetime.now(UTC) - timedelta(hours=1),
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refund_intime_001",
        )
        assert refund.status == RefundStatus.PENDING

    async def test_refund_creates_audit_event(self, student_user, db: AsyncSession):
        """Creating a refund creates a RefundEvent audit record."""
        cafeteria = await create_test_cafeteria(db, name="RefCafe11")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=10000,
            reason="other",
            reason_note="Missing item",
            requested_by_user_id=student_user.id,
            idempotency_key="refund_audit_001",
        )

        result = await db.execute(select(RefundEvent).where(RefundEvent.refund_id == refund.id))
        events = list(result.scalars().all())
        assert len(events) >= 1
        assert events[0].event_type == "refund_requested"


# ---------------------------------------------------------------------------
# Refund Processing Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefundProcessing:
    """Test refund processing by admin/manager."""

    async def test_admin_can_process_refund(self, admin_user, student_user, db: AsyncSession):
        """Admin can process any refund."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe1")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_admin_001",
        )

        processed = await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        assert processed.status == RefundStatus.SUCCEEDED
        assert processed.processed_by == admin_user.id
        assert processed.processed_at is not None
        assert processed.provider_reference is not None

    async def test_manager_can_process_assigned_cafeteria_refund(
        self, manager_user, student_user, db: AsyncSession
    ):
        """Manager can process refunds for their assigned cafeteria."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe2")
        await assign_user_to_cafeteria(db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER)

        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=30000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="item_unavailable",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_mgr_001",
        )

        processed = await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=manager_user.id,
            processor_role=Role.CAFETERIA_MANAGER,
        )

        assert processed.status == RefundStatus.SUCCEEDED

    async def test_manager_cannot_process_unassigned_cafeteria_refund(
        self, manager_user, student_user, db: AsyncSession
    ):
        """Manager cannot process refunds for a cafeteria they're not assigned to."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe3")
        # NOT assigning manager to cafeteria

        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=30000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_mgr_bad_001",
        )

        with pytest.raises(Exception):
            await svc.process_refund(
                refund_id=refund.id,
                processor_user_id=manager_user.id,
                processor_role=Role.CAFETERIA_MANAGER,
            )

    async def test_student_cannot_process_refund(self, student_user, db: AsyncSession):
        """Students cannot process refunds — only admin/manager."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe4")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=30000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_stu_001",
        )

        with pytest.raises(Exception):
            await svc.process_refund(
                refund_id=refund.id,
                processor_user_id=student_user.id,
                processor_role=Role.STUDENT,
            )

    async def test_staff_cannot_process_refund(self, staff_user, student_user, db: AsyncSession):
        """Cafeteria staff cannot process refunds."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe5")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=30000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_staff_001",
        )

        with pytest.raises(Exception):
            await svc.process_refund(
                refund_id=refund.id,
                processor_user_id=staff_user.id,
                processor_role=Role.CAFETERIA_STAFF,
            )

    async def test_faculty_cannot_process_refund(
        self, faculty_user, student_user, db: AsyncSession
    ):
        """Faculty cannot process refunds."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe6")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=30000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_fac_001",
        )

        with pytest.raises(Exception):
            await svc.process_refund(
                refund_id=refund.id,
                processor_user_id=faculty_user.id,
                processor_role=Role.FACULTY,
            )

    async def test_successful_refund_updates_payment_status_full(
        self, admin_user, student_user, db: AsyncSession
    ):
        """Full successful refund sets payment status to REFUNDED."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe7")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_full_001",
        )

        await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        await db.refresh(payment)
        assert payment.status == PaymentStatus.REFUNDED

    async def test_successful_refund_updates_payment_status_partial(
        self, admin_user, student_user, db: AsyncSession
    ):
        """Partial successful refund sets payment status to PARTIALLY_REFUNDED."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe8")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=20000,
            reason="item_unavailable",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_partial_001",
        )

        await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        await db.refresh(payment)
        assert payment.status == PaymentStatus.PARTIALLY_REFUNDED

    async def test_refund_processing_creates_audit_events(
        self, admin_user, student_user, db: AsyncSession
    ):
        """Processing a refund creates multiple RefundEvent records."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe9")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_audit_001",
        )

        await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        result = await db.execute(select(RefundEvent).where(RefundEvent.refund_id == refund.id))
        events = list(result.scalars().all())
        event_types = [e.event_type for e in events]
        assert "refund_requested" in event_types
        assert "refund_processing" in event_types
        assert "refund_succeeded" in event_types

    async def test_cannot_process_already_succeeded_refund(
        self, admin_user, student_user, db: AsyncSession
    ):
        """Cannot process a refund that already succeeded."""
        cafeteria = await create_test_cafeteria(db, name="ProcCafe10")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="proc_dup_001",
        )

        await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        with pytest.raises(Exception):
            await svc.process_refund(
                refund_id=refund.id,
                processor_user_id=admin_user.id,
                processor_role=Role.UNIVERSITY_ADMIN,
            )


# ---------------------------------------------------------------------------
# Refundable Amount Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefundableAmount:
    """Test refundable amount calculation."""

    async def test_full_refundable_when_no_refunds(self, student_user, db: AsyncSession):
        """Refundable amount equals payment when no refunds exist."""
        cafeteria = await create_test_cafeteria(db, name="ReflCafe1")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        data = await svc.get_refundable_amount(order.id)

        assert data["paid_amount"] == 50000
        assert data["total_refunded"] == 0
        assert data["refundable_amount"] == 50000

    async def test_reduced_after_partial_refund(self, admin_user, student_user, db: AsyncSession):
        """Refundable amount decreases after a partial refund."""
        cafeteria = await create_test_cafeteria(db, name="ReflCafe2")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=15000,
            reason="item_unavailable",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refl_red_001",
        )
        await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        data = await svc.get_refundable_amount(order.id)
        assert data["total_refunded"] == 15000
        assert data["refundable_amount"] == 35000

    async def test_zero_refundable_when_fully_refunded(
        self, admin_user, student_user, db: AsyncSession
    ):
        """Refundable amount is 0 when fully refunded."""
        cafeteria = await create_test_cafeteria(db, name="ReflCafe3")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="refl_zero_001",
        )
        await svc.process_refund(
            refund_id=refund.id,
            processor_user_id=admin_user.id,
            processor_role=Role.UNIVERSITY_ADMIN,
        )

        data = await svc.get_refundable_amount(order.id)
        assert data["refundable_amount"] == 0


# ---------------------------------------------------------------------------
# Refund API Endpoint Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefundAPI:
    """Test refund API endpoints via HTTP client."""

    async def test_request_refund(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """POST /refunds with order_id and body creates a refund."""
        cafeteria = await create_test_cafeteria(db, name="APICafe1")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        resp = await student_client.post(
            "/api/v1/refunds",
            params={"order_id": order.id},
            json={
                "amount": 50000,
                "reason": "order_cancelled",
                "reason_note": "Changed mind",
                "idempotency_key": "api_refund_001",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["amount"] == 50000
        assert data["status"] == "pending"

    async def test_request_refund_not_own_order_forbidden(
        self, student_client: AsyncClient, student_user, faculty_user, db: AsyncSession
    ):
        """User cannot request refund for another user's order."""
        cafeteria = await create_test_cafeteria(db, name="APICafe2")
        order, payment = await _create_order_with_payment(
            db, user_id=faculty_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        resp = await student_client.post(
            "/api/v1/refunds",
            params={"order_id": order.id},
            json={
                "amount": 50000,
                "reason": "order_cancelled",
                "idempotency_key": "api_refund_bad_001",
            },
        )
        assert resp.status_code in (403, 401)

    async def test_list_order_refunds(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """GET /refunds/order/{order_id} lists refunds for an order."""
        cafeteria = await create_test_cafeteria(db, name="APICafe3")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        # Create refund first
        svc = RefundService(db, TestRefundProcessor())
        await svc.create_refund(
            order_id=order.id,
            amount=10000,
            reason="item_unavailable",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="api_list_001",
        )

        resp = await student_client.get(f"/api/v1/refunds/order/{order.id}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_refundable_amount(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """GET /refunds/refundable/{order_id} returns refundable info."""
        cafeteria = await create_test_cafeteria(db, name="APICafe4")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        resp = await student_client.get(f"/api/v1/refunds/refundable/{order.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["paid_amount"] == 50000
        assert data["refundable_amount"] == 50000

    async def test_admin_list_all_refunds(
        self, admin_client: AsyncClient, admin_user, student_user, db: AsyncSession
    ):
        """GET /refunds/admin/all requires admin role."""
        cafeteria = await create_test_cafeteria(db, name="APICafe5")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="api_admin_001",
        )

        resp = await admin_client.get("/api/v1/refunds/admin/all")
        assert resp.status_code == 200

    async def test_student_cannot_list_all_refunds(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """Students cannot access admin refund list."""
        resp = await student_client.get("/api/v1/refunds/admin/all")
        assert resp.status_code in (403, 401)

    async def test_process_refund_endpoint(
        self, admin_client: AsyncClient, admin_user, student_user, db: AsyncSession
    ):
        """POST /refunds/{refund_id}/process requires admin/manager role."""
        cafeteria = await create_test_cafeteria(db, name="APICafe6")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="api_process_001",
        )

        resp = await admin_client.post(f"/api/v1/refunds/{refund.id}/process")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "succeeded"

    async def test_student_cannot_process_refund(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Students cannot process refunds."""
        cafeteria = await create_test_cafeteria(db, name="APICafe7")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, amount=50000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="api_stu_proc_001",
        )

        resp = await student_client.post(f"/api/v1/refunds/{refund.id}/process")
        assert resp.status_code in (403, 401)
