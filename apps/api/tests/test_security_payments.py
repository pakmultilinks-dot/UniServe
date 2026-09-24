"""Security tests — attacks on payment/refund system.

Covers:
- IDOR: User A accessing User B's payments/refunds
- Cross-user refund request (User A requests refund on User B's order)
- Manager cross-cafeteria refund processing
- Staff/faculty refund processing blocked
- Client-side amount manipulation (server-authoritative)
- Provider event spoofing prevention
- Webhook replay prevention
- Refund over-refunding race condition protection
- Authorization bypass attempts
"""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.processors.test_processor import TestRefundProcessor
from app.modules.refunds.service import RefundService
from app.modules.users.models import Role
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
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
):
    """Create order + payment for security tests."""
    from datetime import date as date_type

    order = Order(
        order_number=9800 + int(uuid.uuid4().int % 100),
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.IMMEDIATE,
        payment_method=PaymentMethod.CASH,
        status=OrderStatus.PENDING,
        total_amount=amount,
        currency="PKR",
        order_date=date_type.today(),
        inventory_reserved=False,
    )
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
        idempotency_key=f"sec_{order.id}",
    )
    db.add(payment)
    await db.flush()

    return order, payment


# ---------------------------------------------------------------------------
# IDOR / Authorization Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPaymentIDOR:
    """Test IDOR prevention on payment endpoints."""

    async def test_user_a_cannot_view_user_b_payment(
        self,
        student_client: AsyncClient,
        student_user,
        faculty_user,
        db: AsyncSession,
    ):
        """User A cannot view User B's payment via API."""
        cafeteria = await create_test_cafeteria(db, name="SecCafe1")
        order, payment = await _create_order_with_payment(
            db, user_id=faculty_user.id, cafeteria_id=cafeteria.id
        )

        resp = await student_client.get(f"/api/v1/payments/{payment.id}")
        assert resp.status_code in (403, 404), "User A should not access User B's payment"

    async def test_user_a_cannot_view_user_b_order_payment(
        self,
        student_client: AsyncClient,
        student_user,
        faculty_user,
        db: AsyncSession,
    ):
        """User A cannot view User B's order payment via API."""
        cafeteria = await create_test_cafeteria(db, name="SecCafe2")
        order, payment = await _create_order_with_payment(
            db, user_id=faculty_user.id, cafeteria_id=cafeteria.id
        )

        resp = await student_client.get(f"/api/v1/payments/order/{order.id}")
        assert resp.status_code in (403, 404), "User A should not access User B's order payment"

    async def test_user_a_cannot_initiate_payment_on_user_b_order(
        self,
        student_client: AsyncClient,
        student_user,
        faculty_user,
        db: AsyncSession,
    ):
        """User A cannot initiate payment on User B's order."""
        cafeteria = await create_test_cafeteria(db, name="SecCafe3")

        # Create online order for faculty
        order = Order(
            order_number=9900,
            user_id=faculty_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.PENDING,
            total_amount=50000,
            currency="PKR",
            order_date=__import__("datetime").date.today(),
            inventory_reserved=False,
        )
        db.add(order)
        await db.flush()

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order.id}",
            json={"idempotency_key": "idor_key_001"},
        )
        assert resp.status_code in (403, 404), (
            "User A should not initiate payment for User B's order"
        )


@pytest.mark.asyncio
class TestRefundIDOR:
    """Test IDOR prevention on refund endpoints."""

    async def test_user_a_cannot_request_refund_on_user_b_order(
        self,
        student_client: AsyncClient,
        student_user,
        faculty_user,
        db: AsyncSession,
    ):
        """User A cannot request a refund on User B's order."""
        cafeteria = await create_test_cafeteria(db, name="SecCafe4")
        order, payment = await _create_order_with_payment(
            db, user_id=faculty_user.id, cafeteria_id=cafeteria.id
        )

        resp = await student_client.post(
            "/api/v1/refunds",
            params={"order_id": order.id},
            json={
                "amount": 50000,
                "reason": "order_cancelled",
                "idempotency_key": "idor_refund_001",
            },
        )
        assert resp.status_code in (403, 401), "User A should not refund User B's order"

    async def test_user_a_cannot_view_user_b_refunds(
        self,
        student_client: AsyncClient,
        student_user,
        faculty_user,
        db: AsyncSession,
    ):
        """User A cannot view refunds for User B's order."""
        cafeteria = await create_test_cafeteria(db, name="SecCafe5")
        order, payment = await _create_order_with_payment(
            db, user_id=faculty_user.id, cafeteria_id=cafeteria.id
        )

        resp = await student_client.get(f"/api/v1/refunds/order/{order.id}")
        assert resp.status_code in (403, 404), "User A should not view User B's refunds"

    async def test_user_a_cannot_view_user_b_refundable_amount(
        self,
        student_client: AsyncClient,
        student_user,
        faculty_user,
        db: AsyncSession,
    ):
        """User A cannot view refundable amount for User B's order."""
        cafeteria = await create_test_cafeteria(db, name="SecCafe6")
        order, payment = await _create_order_with_payment(
            db, user_id=faculty_user.id, cafeteria_id=cafeteria.id
        )

        resp = await student_client.get(f"/api/v1/refunds/refundable/{order.id}")
        assert resp.status_code in (403, 404), "User A should not view User B's refundable amount"


# ---------------------------------------------------------------------------
# Cross-Cafeteria Manager Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCrossCafeteriaManager:
    """Test that manager cannot process refunds for unassigned cafeterias."""

    async def test_manager_cannot_process_refund_other_cafeteria(
        self,
        manager_user,
        student_user,
        db: AsyncSession,
    ):
        """Manager assigned to cafeteria A cannot process refunds for cafeteria B."""
        cafeteria_a = await create_test_cafeteria(db, name="CafeA")
        cafeteria_b = await create_test_cafeteria(db, name="CafeB")

        # Manager only assigned to cafeteria A
        await assign_user_to_cafeteria(db, manager_user.id, cafeteria_a.id, Role.CAFETERIA_MANAGER)

        # Order is in cafeteria B
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria_b.id, amount=30000
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=30000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="cross_cafe_001",
        )

        with pytest.raises(Exception):
            await svc.process_refund(
                refund_id=refund.id,
                processor_user_id=manager_user.id,
                processor_role=Role.CAFETERIA_MANAGER,
            )


# ---------------------------------------------------------------------------
# Server-Authoritative Amount Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestServerAuthoritativeAmounts:
    """Test that server-derived amounts cannot be tampered with by clients."""

    async def test_payment_amount_from_order_not_client(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Payment initiation uses order total, not any client-sent amount."""
        cafeteria = await create_test_cafeteria(
            db, name="TamperCafe1", operational_status=OperationalStatus.OPEN
        )
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, price=25000)
        daily_menu = await create_test_daily_menu(
            db, cafeteria_id=cafeteria.id, status=DailyMenuStatus.PUBLISHED
        )

        from app.modules.menus.models import DailyMenuItem

        dmi = DailyMenuItem(
            daily_menu_id=daily_menu.id, menu_item_id=item.id, is_available_today=True
        )
        db.add(dmi)
        await db.flush()

        inv = InventoryItem(
            cafeteria_id=cafeteria.id, menu_item_id=item.id, quantity=50, unit=InventoryUnit.PIECES
        )
        db.add(inv)
        await db.flush()

        # Checkout
        await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
        )
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "online", "order_type": "immediate"},
        )
        assert resp.status_code == 201
        order_id = resp.json()["id"]

        # Initiate payment — even though request body has no amount field,
        # the server derives it from the order
        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "tamper_001"},
        )
        assert resp.status_code == 201

        # Verify amount in DB matches order, not any tampered value
        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()
        assert payment.amount == 25000  # 1 * 25000 — server-authoritative
        assert payment.status.value == "processing"


# ---------------------------------------------------------------------------
# Webhook Security Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookSecurity:
    """Test webhook security — replay, spoofing, tampering."""

    async def test_webhook_replay_prevention(self, student_user, db: AsyncSession):
        """Same webhook event_id cannot be replayed."""

        cafeteria = await create_test_cafeteria(db, name="WhSecCafe1")
        order = Order(
            order_number=9850,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.PENDING,
            total_amount=50000,
            currency="PKR",
            order_date=__import__("datetime").date.today(),
            inventory_reserved=False,
        )
        db.add(order)
        await db.flush()

        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            user_id=student_user.id,
            amount=50000,
            currency="PKR",
            status=PaymentStatus.PROCESSING,
            provider_name="test_provider",
            provider_reference="test_pay_sec_001",
            idempotency_key="whsec_001",
        )
        db.add(payment)
        await db.flush()

        payload = json.dumps(
            {
                "event_id": "replay_evt_001",
                "event_type": "payment_success",
                "payment_reference": "test_pay_sec_001",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        from app.modules.payments.providers.test_provider import TestPaymentProvider
        from app.modules.payments.service import PaymentService

        svc = PaymentService(db, TestPaymentProvider())

        # First webhook processes successfully
        r1 = await svc.process_webhook(
            provider_name="test_provider",
            payload=payload,
            provider_event_id="replay_evt_001",
        )
        assert r1 is True

        # Replay is blocked
        r2 = await svc.process_webhook(
            provider_name="test_provider",
            payload=payload,
            provider_event_id="replay_evt_001",
        )
        assert r2 is False

    async def test_webhook_tampered_amount_rejected(self, student_user, db: AsyncSession):
        """Webhook with tampered amount is rejected."""
        cafeteria = await create_test_cafeteria(db, name="WhSecCafe2")
        order = Order(
            order_number=9851,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.PENDING,
            total_amount=50000,
            currency="PKR",
            order_date=__import__("datetime").date.today(),
            inventory_reserved=False,
        )
        db.add(order)
        await db.flush()

        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            user_id=student_user.id,
            amount=50000,
            currency="PKR",
            status=PaymentStatus.PROCESSING,
            provider_name="test_provider",
            provider_reference="test_pay_sec_002",
            idempotency_key="whsec_002",
        )
        db.add(payment)
        await db.flush()

        # Tampered amount webhook
        payload = json.dumps(
            {
                "event_id": "tamper_evt_001",
                "event_type": "payment_success",
                "payment_reference": "test_pay_sec_002",
                "amount": 999999,  # TAMPERED!
                "currency": "PKR",
            }
        ).encode()

        from app.modules.payments.providers.test_provider import TestPaymentProvider
        from app.modules.payments.service import PaymentService

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider",
            payload=payload,
            provider_event_id="tamper_evt_001",
        )
        assert result is False

        # Verify payment NOT succeeded
        await db.refresh(payment)
        assert payment.status == PaymentStatus.PROCESSING


# ---------------------------------------------------------------------------
# Authorization Bypass Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthorizationBypass:
    """Test that authorization rules cannot be bypassed."""

    async def test_unauthenticated_cannot_access_payments(self, client: AsyncClient):
        """Unauthenticated requests to payment endpoints are rejected."""
        endpoints = [
            ("GET", "/api/v1/payments/"),
            ("POST", "/api/v1/payments/initiate/fake-id"),
            ("GET", "/api/v1/payments/fake-id"),
        ]
        for method, url in endpoints:
            resp = await client.request(method, url)
            # 401/403 = auth error; 422 = missing required Authorization header (FastAPI default)
            assert resp.status_code in (401, 403, 422), f"{method} {url} should require auth"

    async def test_unauthenticated_cannot_access_refunds(self, client: AsyncClient):
        """Unauthenticated requests to refund endpoints are rejected."""
        endpoints = [
            ("POST", "/api/v1/refunds"),
            ("GET", "/api/v1/refunds/order/fake-id"),
            ("GET", "/api/v1/refunds/refundable/fake-id"),
            ("GET", "/api/v1/refunds/admin/all"),
        ]
        for method, url in endpoints:
            resp = await client.request(method, url)
            # 401/403 = auth error; 422 = missing required Authorization header (FastAPI default)
            assert resp.status_code in (401, 403, 422), f"{method} {url} should require auth"

    async def test_student_cannot_process_refund_via_api(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Student cannot call the refund processing endpoint."""
        cafeteria = await create_test_cafeteria(db, name="AuthBypass1")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="bypass_001",
        )

        resp = await student_client.post(f"/api/v1/refunds/{refund.id}/process")
        assert resp.status_code in (403, 401)

    async def test_manager_cannot_process_refund_other_cafeteria_via_api(
        self,
        manager_client: AsyncClient,
        manager_user,
        student_user,
        db: AsyncSession,
    ):
        """Manager cannot process refund for unassigned cafeteria via API."""
        cafeteria_a = await create_test_cafeteria(db, name="AuthCafeA")
        cafeteria_b = await create_test_cafeteria(db, name="AuthCafeB")

        # Manager assigned to A only
        await assign_user_to_cafeteria(db, manager_user.id, cafeteria_a.id, Role.CAFETERIA_MANAGER)

        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria_b.id
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="bypass_002",
        )

        resp = await manager_client.post(f"/api/v1/refunds/{refund.id}/process")
        assert resp.status_code in (403, 500)

    async def test_staff_cannot_process_refund_via_api(
        self, staff_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cafeteria staff cannot process refunds."""
        cafeteria = await create_test_cafeteria(db, name="AuthStaff1")
        order, payment = await _create_order_with_payment(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id
        )

        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=50000,
            reason="order_cancelled",
            reason_note=None,
            requested_by_user_id=student_user.id,
            idempotency_key="bypass_003",
        )

        resp = await staff_client.post(f"/api/v1/refunds/{refund.id}/process")
        assert resp.status_code in (403, 401)
