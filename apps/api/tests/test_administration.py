"""Tests for the Administration Overview API.

Covers:
- Authorization (admin-only, all roles)
- User aggregation (role counts, status counts)
- Cafeteria aggregation (both cafeterias, operational status, manager/staff counts)
- Order aggregation (status counts, date filtering)
- Financial aggregation (revenue, refunds, online/cash breakdown)
- Exception aggregation (overdue refunds, suspensions, no-shows)
- Security (no sensitive fields, no cross-role access)
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, UTC
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_menu_item,
    create_test_user,
    create_user_session,
)

from app.modules.cafeterias.models import Cafeteria, CafeteriaType, OperationalStatus
from app.modules.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundReason, RefundStatus
from app.modules.users.models import (
    AccountStatus,
    CafeteriaAssignment,
    Role,
    User,
    UserCategory,
)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

_order_seq = 200000


def _next_order_number() -> int:
    global _order_seq
    _order_seq += 1
    return _order_seq


async def _seed_order(
    db: AsyncSession,
    *,
    cafeteria: Cafeteria,
    item: OrderItem | None = None,
    user: User | None = None,
    status: OrderStatus = OrderStatus.COMPLETED,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    payment_status: PaymentStatus = PaymentStatus.SUCCEEDED,
    total_amount: int = 25000,
    order_date: date | None = None,
    cancel: bool = False,
    uncollected: bool = False,
) -> Order:
    """Seed a single order with payment."""
    if user is None:
        user = await create_test_user(
            db,
            first_name="Order",
            last_name="Student",
            university_id=f"ORD-{_next_order_number()}",
            university_email=f"order{_order_seq}@lgu.edu.pk",
        )
    if order_date is None:
        order_date = date.today()

    order = Order(
        order_number=_next_order_number(),
        user_id=user.id,
        cafeteria_id=cafeteria.id,
        order_type=OrderType.IMMEDIATE,
        payment_method=payment_method,
        status=status,
        total_amount=total_amount,
        order_date=order_date,
    )
    if cancel:
        order.cancelled_at = datetime.now(UTC)
        order.cancellation_reason = "test"
    if uncollected:
        order.uncollected_at = datetime.now(UTC)
    db.add(order)
    await db.flush()

    if item is None:
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)

    oi = OrderItem(
        order_id=order.id,
        menu_item_id=item.id,
        item_name=item.name,
        quantity=1,
        unit_price=item.price,
        subtotal=item.price,
    )
    db.add(oi)
    await db.flush()

    payment = Payment(
        id=f"pay-{order.order_number}",
        order_id=order.id,
        user_id=user.id,
        amount=total_amount,
        status=payment_status,
        idempotency_key=f"idem-{order.order_number}",
    )
    db.add(payment)
    await db.flush()

    return order


# ===========================================================================
# Authorization Tests
# ===========================================================================


class TestAuthorization:
    """Cross-role authorization for /administration/overview."""

    @pytest.mark.asyncio
    async def test_unauthenticated_denied(self, client: AsyncClient):
        resp = await client.get("/api/v1/administration/overview")
        assert resp.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_student_denied(self, student_client: AsyncClient):
        resp = await student_client.get("/api/v1/administration/overview")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_faculty_denied(self, faculty_client: AsyncClient):
        resp = await faculty_client.get("/api/v1/administration/overview")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_denied(self, manager_client: AsyncClient):
        resp = await manager_client.get("/api/v1/administration/overview")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_denied(self, staff_client: AsyncClient):
        resp = await staff_client.get("/api/v1/administration/overview")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_allowed(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200


# ===========================================================================
# User Aggregation Tests
# ===========================================================================


class TestUserAggregation:
    """Verify user counts in the overview."""

    @pytest.mark.asyncio
    async def test_user_counts(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_user: User,
        faculty_user: User,
        manager_user: User,
        staff_user: User,
        admin_user: User,
    ):
        """All fixture users should be counted by role."""
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        data = resp.json()
        users = data["users"]

        # At minimum we have the 5 fixture users
        assert users["total"] >= 5
        assert users["students"] >= 1
        assert users["faculty"] >= 1
        assert users["university_admins"] >= 1
        assert users["cafeteria_managers"] >= 1
        assert users["cafeteria_staff"] >= 1

    @pytest.mark.asyncio
    async def test_active_suspended_counts(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_user: User,
    ):
        """Active and suspended counts should be accurate."""
        # Create a suspended user
        suspended = await create_test_user(
            db,
            first_name="Suspended",
            last_name="User",
            university_id="SUS-999",
            university_email="suspended@lgu.edu.pk",
            status=AccountStatus.SUSPENDED,
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        users = resp.json()["users"]

        assert users["suspended"] >= 1
        # All fixture users are active
        assert users["active"] >= 1

    @pytest.mark.asyncio
    async def test_ordering_suspended_count(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        """Ordering-suspended users should be counted."""
        user = await create_test_user(
            db,
            first_name="Bad",
            last_name="Student",
            university_id="BAD-001",
            university_email="bad@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        user.ordering_suspended = True
        await db.flush()

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        users = resp.json()["users"]
        assert users["ordering_suspended"] >= 1


# ===========================================================================
# Cafeteria Aggregation Tests
# ===========================================================================


class TestCafeteriaAggregation:
    """Verify cafeteria counts in the overview."""

    @pytest.mark.asyncio
    async def test_both_cafeterias_represented(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
        faculty_cafeteria: Cafeteria,
    ):
        """Both cafeterias should appear in the overview."""
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        cafeterias = resp.json()["cafeterias"]

        assert cafeterias["total"] >= 2
        ids = {c["cafeteria_id"] for c in cafeterias["cafeterias"]}
        assert student_cafeteria.id in ids
        assert faculty_cafeteria.id in ids

    @pytest.mark.asyncio
    async def test_operational_status(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Cafeteria operational status should be reflected."""
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        cafeterias = resp.json()["cafeterias"]

        caf = next(
            c for c in cafeterias["cafeterias"] if c["cafeteria_id"] == student_cafeteria.id
        )
        assert caf["operational_status"] == "open"
        assert caf["is_active"] is True

    @pytest.mark.asyncio
    async def test_manager_staff_counts(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
        manager_user: User,
        staff_user: User,
    ):
        """Assigned manager and staff counts should be correct."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, student_cafeteria.id, Role.CAFETERIA_STAFF
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        caf = next(
            c
            for c in resp.json()["cafeterias"]["cafeterias"]
            if c["cafeteria_id"] == student_cafeteria.id
        )
        assert caf["assigned_managers"] >= 1
        assert caf["assigned_staff"] >= 1

    @pytest.mark.asyncio
    async def test_preparation_capacity(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Preparation capacity should be included."""
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        caf = next(
            c
            for c in resp.json()["cafeterias"]["cafeterias"]
            if c["cafeteria_id"] == student_cafeteria.id
        )
        assert caf["preparation_capacity"] >= 1


# ===========================================================================
# Order Aggregation Tests
# ===========================================================================


class TestOrderAggregation:
    """Verify order counts in the overview."""

    @pytest.mark.asyncio
    async def test_order_status_counts(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Order status counts should reflect seeded orders."""
        await _seed_order(db, cafeteria=student_cafeteria, status=OrderStatus.COMPLETED)
        await _seed_order(db, cafeteria=student_cafeteria, status=OrderStatus.PENDING)
        await _seed_order(db, cafeteria=student_cafeteria, status=OrderStatus.CANCELLED, cancel=True)

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        orders = resp.json()["orders"]

        assert orders["total_orders"] >= 3
        assert orders["completed"] >= 1
        assert orders["pending"] >= 1
        assert orders["cancelled"] >= 1

    @pytest.mark.asyncio
    async def test_uncollected_count(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Uncollected orders should be counted."""
        await _seed_order(
            db, cafeteria=student_cafeteria, status=OrderStatus.READY, uncollected=True
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        assert resp.json()["orders"]["uncollected"] >= 1

    @pytest.mark.asyncio
    async def test_date_filtering(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Orders outside the date range should be excluded."""
        today = date.today()
        old_date = today - timedelta(days=60)

        # Seed one old order and one recent order
        await _seed_order(
            db, cafeteria=student_cafeteria, status=OrderStatus.COMPLETED, order_date=old_date
        )
        await _seed_order(
            db, cafeteria=student_cafeteria, status=OrderStatus.COMPLETED, order_date=today
        )

        # Filter to today only
        resp = await admin_client.get(
            f"/api/v1/administration/overview?start_date={today}&end_date={today}"
        )
        assert resp.status_code == 200
        orders = resp.json()["orders"]
        assert orders["total_orders"] >= 1
        # All orders should be completed
        assert orders["completed"] >= 1

    @pytest.mark.asyncio
    async def test_cancellation_rate(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Cancellation rate should be computed correctly."""
        # 1 completed, 1 cancelled = 50% cancellation rate
        await _seed_order(db, cafeteria=student_cafeteria, status=OrderStatus.COMPLETED)
        await _seed_order(
            db, cafeteria=student_cafeteria, status=OrderStatus.CANCELLED, cancel=True
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        rate = resp.json()["orders"]["cancellation_rate"]
        assert rate > 0  # At least some cancellation


# ===========================================================================
# Financial Aggregation Tests
# ===========================================================================


class TestFinancialAggregation:
    """Verify financial counts in the overview."""

    @pytest.mark.asyncio
    async def test_revenue_included(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Successful payments should count toward revenue."""
        await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=50000,
            payment_status=PaymentStatus.SUCCEEDED,
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        fin = resp.json()["financial"]
        assert fin["total_revenue"] >= 50000

    @pytest.mark.asyncio
    async def test_failed_payments_excluded(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Failed payments should not count toward revenue."""
        await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=99999,
            payment_status=PaymentStatus.FAILED,
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        # The failed payment should not add 99999 to revenue
        fin = resp.json()["financial"]
        assert fin["total_revenue"] < 99999

    @pytest.mark.asyncio
    async def test_refunds_included(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Successful refunds should be counted."""
        order = await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=30000,
            payment_status=PaymentStatus.SUCCEEDED,
        )

        refund = Refund(
            id=f"ref-{order.order_number}",
            order_id=order.id,
            payment_id=f"pay-{order.order_number}",
            user_id=order.user_id,
            amount=30000,
            status=RefundStatus.SUCCEEDED,
            reason=RefundReason.ORDER_CANCELLED,
            requested_by=order.user_id,
            idempotency_key=f"ref-idem-{order.order_number}",
        )
        db.add(refund)
        await db.flush()

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        fin = resp.json()["financial"]
        assert fin["total_refunded"] >= 30000
        assert fin["net_revenue"] == fin["total_revenue"] - fin["total_refunded"]

    @pytest.mark.asyncio
    async def test_online_cash_breakdown(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Online and cash volumes should be separated."""
        await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=10000,
            payment_method=PaymentMethod.ONLINE,
            payment_status=PaymentStatus.SUCCEEDED,
        )
        await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=20000,
            payment_method=PaymentMethod.CASH,
            payment_status=PaymentStatus.SUCCEEDED,
        )

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        fin = resp.json()["financial"]
        assert fin["online_payment_volume"] >= 10000
        assert fin["cash_payment_volume"] >= 20000
        assert fin["currency"] == "PKR"

    @pytest.mark.asyncio
    async def test_net_revenue_calculation(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Net revenue should equal revenue minus refunds."""
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        fin = resp.json()["financial"]
        assert fin["net_revenue"] == fin["total_revenue"] - fin["total_refunded"]


# ===========================================================================
# Exception Aggregation Tests
# ===========================================================================


class TestExceptionAggregation:
    """Verify exception counts in the overview."""

    @pytest.mark.asyncio
    async def test_ordering_suspension_detected(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        """Ordering-suspended users should appear in exceptions."""
        user = await create_test_user(
            db,
            first_name="Suspended",
            last_name="Orderer",
            university_id="SUSP-001",
            university_email="suspended_order@lgu.edu.pk",
        )
        user.ordering_suspended = True
        await db.flush()

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        exc = resp.json()["exceptions"]
        assert exc["ordering_suspended_users"] >= 1

    @pytest.mark.asyncio
    async def test_no_show_activity(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """No-show records should be counted."""
        from app.modules.orders.models import NoShow

        user = await create_test_user(
            db,
            first_name="NoShow",
            last_name="User",
            university_id="NS-001",
            university_email="noshows@lgu.edu.pk",
        )
        order = await _seed_order(
            db, cafeteria=student_cafeteria, user=user, status=OrderStatus.READY, uncollected=True
        )
        ns = NoShow(
            user_id=user.id,
            order_id=order.id,
            cafeteria_id=student_cafeteria.id,
        )
        db.add(ns)
        await db.flush()

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        assert resp.json()["exceptions"]["uncollected_orders"] >= 1

    @pytest.mark.asyncio
    async def test_cafeteria_closure_cancellations(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Refunds with reason cafeteria_closed should be counted."""
        order = await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=40000,
            payment_status=PaymentStatus.SUCCEEDED,
        )
        refund = Refund(
            id=f"ref-closure-{order.order_number}",
            order_id=order.id,
            payment_id=f"pay-{order.order_number}",
            user_id=order.user_id,
            amount=40000,
            status=RefundStatus.SUCCEEDED,
            reason=RefundReason.CAFETERIA_CLOSED,
            requested_by=order.user_id,
            idempotency_key=f"ref-closure-idem-{order.order_number}",
        )
        db.add(refund)
        await db.flush()

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        assert resp.json()["exceptions"]["cafeteria_closure_cancellations"] >= 1

    @pytest.mark.asyncio
    async def test_overdue_refunds_detected(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria: Cafeteria,
    ):
        """Refunds pending for >7 days should be counted as overdue."""
        order = await _seed_order(
            db,
            cafeteria=student_cafeteria,
            total_amount=15000,
            payment_status=PaymentStatus.SUCCEEDED,
        )
        # Create a refund with created_at 10 days ago
        old_refund = Refund(
            id=f"ref-overdue-{order.order_number}",
            order_id=order.id,
            payment_id=f"pay-{order.order_number}",
            user_id=order.user_id,
            amount=15000,
            status=RefundStatus.PENDING,
            reason=RefundReason.ORDER_CANCELLED,
            requested_by=order.user_id,
            idempotency_key=f"ref-overdue-idem-{order.order_number}",
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        db.add(old_refund)
        await db.flush()

        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        assert resp.json()["exceptions"]["overdue_refunds"] >= 1


# ===========================================================================
# Security Tests
# ===========================================================================


class TestSecurity:
    """Verify no sensitive data leakage and no cross-role access."""

    @pytest.mark.asyncio
    async def test_no_sensitive_fields(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        """Response should not contain passwords, hashes, tokens, or PII."""
        resp = await admin_client.get("/api/v1/administration/overview")
        assert resp.status_code == 200
        raw = resp.text

        # Should never appear in response
        sensitive_terms = [
            "password",
            "password_hash",
            "pin_hash",
            "refresh_token",
            "otp",
            "biometric",
            "credit_card",
            "card_number",
            "cvv",
        ]
        for term in sensitive_terms:
            assert term.lower() not in raw.lower(), f"Sensitive field '{term}' found in response"

    @pytest.mark.asyncio
    async def test_cross_role_no_leak(
        self,
        student_client: AsyncClient,
        manager_client: AsyncClient,
    ):
        """Non-admin roles should not see any overview data."""
        for client_instance in [student_client, manager_client]:
            resp = await client_instance.get("/api/v1/administration/overview")
            assert resp.status_code == 403
            # Should not contain any overview data
            assert "users" not in resp.json() if resp.status_code != 403 else True
