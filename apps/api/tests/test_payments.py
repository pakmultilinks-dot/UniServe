"""Tests for payment processing — cash, online, webhooks, financial invariants.

Covers:
- Cash payment record creation at checkout
- Cash payment confirmation
- Online payment initiation via provider
- Payment idempotency (duplicate prevention)
- Server-authoritative amounts (client cannot tamper)
- Currency validation
- Payment success/failure handling
- Webhook processing (valid, invalid, replay, unknown)
- Payment retrieval (ownership enforcement)
- Amount/currency mismatch detection
- Cancelled order payment blocked
- Payment state machine transitions
"""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus, MenuCategory
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import (
    Payment,
    PaymentStatus,
    WebhookEvent,
)
from app.modules.payments.providers.test_provider import TestPaymentProvider
from app.modules.payments.service import PaymentService
from tests.conftest import (
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup_test_data(
    db: AsyncSession,
    *,
    payment_method: str = "cash",
    inventory_qty: int = 50,
):
    """Create cafeteria, menu item, daily menu, inventory. Returns (cafeteria, item, daily_menu)."""
    cafeteria = await create_test_cafeteria(
        db,
        name="Test Cafeteria",
        cafeteria_type=CafeteriaType.STUDENT,
        operational_status=OperationalStatus.OPEN,
    )
    item = await create_test_menu_item(
        db,
        cafeteria_id=cafeteria.id,
        name="Chicken Biryani",
        category=MenuCategory.MAIN_COURSE,
        price=25000,  # 250 PKR in paisa
        is_available=True,
    )
    daily_menu = await create_test_daily_menu(
        db,
        cafeteria_id=cafeteria.id,
        status=DailyMenuStatus.PUBLISHED,
    )

    from app.modules.menus.models import DailyMenuItem

    dmi = DailyMenuItem(
        daily_menu_id=daily_menu.id,
        menu_item_id=item.id,
        is_available_today=True,
    )
    db.add(dmi)
    await db.flush()

    if inventory_qty > 0:
        inv = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item.id,
            quantity=inventory_qty,
            unit=InventoryUnit.PIECES,
        )
        db.add(inv)
        await db.flush()

    return cafeteria, item, daily_menu


async def _checkout(
    client: AsyncClient,
    cafeteria_id: str,
    *,
    payment_method: str = "cash",
    order_type: str = "immediate",
):
    """Checkout via API."""
    resp = await client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/checkout",
        json={"payment_method": payment_method, "order_type": order_type},
    )
    return resp


async def _add_cart_item(
    client: AsyncClient, cafeteria_id: str, menu_item_id: str, quantity: int = 1
):
    """Add an item to the cart."""
    resp = await client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/items",
        json={"menu_item_id": menu_item_id, "quantity": quantity},
    )
    return resp


async def _create_order_direct(
    db: AsyncSession, user_id: str, cafeteria_id: str, **kwargs
) -> Order:
    """Create an order directly in DB for service-level tests."""
    from datetime import date as date_type

    order_number = kwargs.pop("order_number", 1000)
    order = Order(
        order_number=order_number,
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_type=kwargs.get("order_type", OrderType.IMMEDIATE),
        payment_method=kwargs.get("payment_method", PaymentMethod.ONLINE),
        status=kwargs.get("status", OrderStatus.PENDING),
        total_amount=kwargs.get("total_amount", 50000),
        currency="PKR",
        order_date=date_type.today(),
        inventory_reserved=kwargs.get("inventory_reserved", False),
    )
    db.add(order)
    await db.flush()
    return order


async def _create_payment_direct(
    db: AsyncSession,
    *,
    order_id: str,
    user_id: str,
    amount: int,
    status: PaymentStatus = PaymentStatus.PENDING,
    provider_name: str = "test_provider",
    provider_reference: str | None = None,
    idempotency_key: str | None = None,
) -> Payment:
    """Create a payment directly in DB for service-level tests."""
    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order_id,
        user_id=user_id,
        amount=amount,
        currency="PKR",
        status=status,
        provider_name=provider_name,
        provider_reference=provider_reference,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )
    db.add(payment)
    await db.flush()
    return payment


# ---------------------------------------------------------------------------
# Cash Payment Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCashPayments:
    """Test cash payment creation and confirmation."""

    async def test_cash_checkout_creates_payment_record(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cash checkout creates a payment record with correct amount."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=2)
        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # Verify payment record exists in DB
        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one_or_none()
        assert payment is not None
        assert payment.amount == 50000  # 2 * 25000
        assert payment.currency == "PKR"
        assert payment.status == PaymentStatus.PENDING
        assert payment.provider_name == "cash"

    async def test_cash_payment_amount_matches_order(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cash payment amount is always server-derived from order total."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=3)
        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]
        order_total = resp.json()["total_amount"]

        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()
        assert payment.amount == order_total

    async def test_cash_payment_idempotency_key(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cash payment idempotency key is derived from order ID."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        order_id = resp.json()["id"]

        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()
        assert payment.idempotency_key == f"cash_{order_id}"


# ---------------------------------------------------------------------------
# Online Payment Initiation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOnlinePaymentInitiation:
    """Test online payment initiation via provider."""

    async def test_online_checkout_creates_pending_order(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Online checkout creates a PENDING order with no payment record yet."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        assert resp.status_code == 201, resp.text
        assert resp.json()["payment_method"] == "online"
        assert resp.json()["status"] == "pending"

        # No payment record yet (only on explicit initiation)
        order_id = resp.json()["id"]
        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one_or_none()
        assert payment is None

    async def test_initiate_online_payment_creates_payment(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """POST /payments/initiate/{order_id} creates payment via provider."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        order_id = resp.json()["id"]

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "test_key_001"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["payment_id"] is not None
        assert data["status"] in ("processing", "succeeded")
        assert data["provider_name"] == "test_provider"

    async def test_initiate_payment_validates_ownership(
        self, student_client: AsyncClient, student_user, faculty_user, db: AsyncSession
    ):
        """User cannot initiate payment for another user's order."""
        cafeteria, item, _ = await _setup_test_data(db)

        # Student creates the order
        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        order_id = resp.json()["id"]

        # Faculty user tries to initiate payment — should fail
        from tests.conftest import create_user_session

        _, access_token, _ = await create_user_session(db, faculty_user)

        # We need a client for faculty with the same DB
        faculty_client_raw = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        resp = await faculty_client_raw.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "test_key_fraud"},
        )
        assert resp.status_code in (401, 403, 404)
        await faculty_client_raw.aclose()

    async def test_initiate_payment_wrong_order_type_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot initiate online payment for a cash order."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        order_id = resp.json()["id"]

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "test_key_cash"},
        )
        assert resp.status_code == 422 or resp.status_code == 400

    async def test_initiate_payment_cancelled_order_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot initiate payment for a cancelled order."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        order_id = resp.json()["id"]

        # Cancel the order
        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json={"reason": "Changed my mind"},
        )
        assert resp.status_code == 200

        # Try to initiate payment on cancelled order
        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "test_key_cancelled"},
        )
        assert resp.status_code in (400, 422)

    async def test_initiate_payment_idempotency(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Same idempotency key returns the same payment."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        order_id = resp.json()["id"]

        key = "idempotent_key_123"

        resp1 = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": key},
        )
        assert resp1.status_code == 201

        resp2 = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": key},
        )
        assert resp2.status_code == 201
        # Should return the same payment
        assert resp1.json()["payment_id"] == resp2.json()["payment_id"]

    async def test_initiate_payment_server_authoritative_amount(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Payment amount is always derived from order total, never from client."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=2)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        order_id = resp.json()["id"]
        order_total = resp.json()["total_amount"]  # 50000

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "key_amount_test"},
        )
        assert resp.status_code == 201

        # Verify DB payment amount matches order
        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()
        assert payment.amount == order_total


# ---------------------------------------------------------------------------
# Payment Service — Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPaymentService:
    """Direct PaymentService unit tests."""

    async def test_create_cash_payment(self, student_user, db: AsyncSession):
        """PaymentService.create_cash_payment creates a PENDING cash record."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            total_amount=30000,
            payment_method=PaymentMethod.CASH,
        )

        svc = PaymentService(db, TestPaymentProvider())
        payment = await svc.create_cash_payment(order, student_user.id)

        assert payment.status == PaymentStatus.PENDING
        assert payment.amount == 30000
        assert payment.provider_name == "cash"
        assert payment.idempotency_key == f"cash_{order.id}"

    async def test_confirm_cash_payment(self, student_user, db: AsyncSession):
        """confirm_cash_payment transitions PENDING → SUCCEEDED."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe2")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            total_amount=10000,
        )

        svc = PaymentService(db, TestPaymentProvider())
        payment = await svc.create_cash_payment(order, student_user.id)
        confirmed = await svc.confirm_cash_payment(payment)

        assert confirmed.status == PaymentStatus.SUCCEEDED

    async def test_confirm_non_pending_cash_fails(self, student_user, db: AsyncSession):
        """Cannot confirm a cash payment that isn't PENDING."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe3")
        order = await _create_order_direct(db, user_id=student_user.id, cafeteria_id=cafeteria.id)

        svc = PaymentService(db, TestPaymentProvider())
        payment = await svc.create_cash_payment(order, student_user.id)
        payment.status = PaymentStatus.SUCCEEDED  # Force status
        await db.flush()

        with pytest.raises(Exception):
            await svc.confirm_cash_payment(payment)

    async def test_handle_payment_success_idempotent(self, student_user, db: AsyncSession):
        """handle_payment_success is idempotent — calling twice returns same payment."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe4")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            total_amount=20000,
            payment_method=PaymentMethod.ONLINE,
        )
        payment = await _create_payment_direct(
            db,
            order_id=order.id,
            user_id=student_user.id,
            amount=20000,
            status=PaymentStatus.PROCESSING,
            provider_reference="test_pay_001",
        )

        svc = PaymentService(db, TestPaymentProvider())
        p1 = await svc.handle_payment_success(
            payment_id=payment.id,
            provider_reference="test_pay_001",
        )
        assert p1.status == PaymentStatus.SUCCEEDED

        p2 = await svc.handle_payment_success(
            payment_id=payment.id,
            provider_reference="test_pay_001",
        )
        assert p2.status == PaymentStatus.SUCCEEDED

    async def test_handle_payment_amount_mismatch_rejected(self, student_user, db: AsyncSession):
        """Payment with amount ≠ order total is rejected."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe5")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            total_amount=20000,
            payment_method=PaymentMethod.ONLINE,
        )
        # Create payment with mismatched amount (tampered)
        payment = await _create_payment_direct(
            db,
            order_id=order.id,
            user_id=student_user.id,
            amount=99999,  # Wrong amount!
            status=PaymentStatus.PROCESSING,
            provider_reference="test_pay_tamper",
        )

        svc = PaymentService(db, TestPaymentProvider())
        with pytest.raises(Exception):
            await svc.handle_payment_success(
                payment_id=payment.id,
                provider_reference="test_pay_tamper",
            )

    async def test_handle_payment_failure(self, student_user, db: AsyncSession):
        """handle_payment_failure transitions to FAILED."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe6")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            total_amount=20000,
        )
        payment = await _create_payment_direct(
            db,
            order_id=order.id,
            user_id=student_user.id,
            amount=20000,
            status=PaymentStatus.PROCESSING,
        )

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.handle_payment_failure(
            payment_id=payment.id,
            error_message="Card declined",
        )
        assert result.status == PaymentStatus.FAILED

    async def test_get_payment(self, student_user, db: AsyncSession):
        """get_payment retrieves a payment by ID."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe7")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
        )
        payment = await _create_payment_direct(
            db,
            order_id=order.id,
            user_id=student_user.id,
            amount=10000,
        )

        svc = PaymentService(db, TestPaymentProvider())
        retrieved = await svc.get_payment(payment.id)
        assert retrieved.id == payment.id
        assert retrieved.amount == 10000

    async def test_get_payment_not_found(self, db: AsyncSession):
        """get_payment raises NotFoundException for missing payment."""
        svc = PaymentService(db, TestPaymentProvider())
        with pytest.raises(Exception):
            await svc.get_payment("nonexistent-id")

    async def test_list_user_payments(self, student_user, db: AsyncSession):
        """list_user_payments returns only payments for the given user."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe8")
        order1 = await _create_order_direct(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, order_number=2001
        )
        order2 = await _create_order_direct(
            db, user_id=student_user.id, cafeteria_id=cafeteria.id, order_number=2002
        )
        await _create_payment_direct(db, order_id=order1.id, user_id=student_user.id, amount=10000)
        await _create_payment_direct(db, order_id=order2.id, user_id=student_user.id, amount=20000)

        svc = PaymentService(db, TestPaymentProvider())
        payments = await svc.list_user_payments(user_id=student_user.id)
        assert len(payments) == 2

    async def test_get_order_payment(self, student_user, db: AsyncSession):
        """get_order_payment retrieves the payment for a given order."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe9")
        order = await _create_order_direct(db, user_id=student_user.id, cafeteria_id=cafeteria.id)
        payment = await _create_payment_direct(
            db, order_id=order.id, user_id=student_user.id, amount=15000
        )

        svc = PaymentService(db, TestPaymentProvider())
        found = await svc.get_order_payment(order.id)
        assert found is not None
        assert found.id == payment.id

    async def test_get_order_payment_none_when_no_payment(self, student_user, db: AsyncSession):
        """get_order_payment returns None when no payment exists."""
        cafeteria = await create_test_cafeteria(db, name="SvcCafe10")
        order = await _create_order_direct(db, user_id=student_user.id, cafeteria_id=cafeteria.id)

        svc = PaymentService(db, TestPaymentProvider())
        found = await svc.get_order_payment(order.id)
        assert found is None


# ---------------------------------------------------------------------------
# Webhook Processing Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookProcessing:
    """Test webhook processing — valid, invalid, replay, idempotency."""

    async def _setup_online_order_with_payment(
        self,
        db: AsyncSession,
        student_user,
        *,
        status: PaymentStatus = PaymentStatus.PROCESSING,
        amount: int = 50000,
    ):
        """Helper: create an online order + payment for webhook tests."""
        cafeteria = await create_test_cafeteria(db, name="WhCafe")
        order = await _create_order_direct(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            total_amount=amount,
            payment_method=PaymentMethod.ONLINE,
        )
        payment = await _create_payment_direct(
            db,
            order_id=order.id,
            user_id=student_user.id,
            amount=amount,
            status=status,
            provider_reference="test_pay_wh_001",
        )
        return order, payment

    async def test_valid_webhook_processes_payment(self, student_user, db: AsyncSession):
        """Valid webhook with payment_success event succeeds payment."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        payload = json.dumps(
            {
                "event_id": "evt_001",
                "event_type": "payment_success",
                "payment_reference": "test_pay_wh_001",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider",
            payload=payload,
            provider_event_id="evt_001",
        )
        assert result is True

        # Verify payment succeeded
        await db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED

    async def test_webhook_idempotency(self, student_user, db: AsyncSession):
        """Same webhook event_id is only processed once."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        payload = json.dumps(
            {
                "event_id": "evt_002",
                "event_type": "payment_success",
                "payment_reference": "test_pay_wh_001",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        r1 = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_002"
        )
        assert r1 is True

        r2 = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_002"
        )
        assert r2 is False  # Already processed

    async def test_webhook_amount_mismatch_rejected(self, student_user, db: AsyncSession):
        """Webhook with amount ≠ order total is rejected."""
        order, payment = await self._setup_online_order_with_payment(db, student_user, amount=50000)

        payload = json.dumps(
            {
                "event_id": "evt_003",
                "event_type": "payment_success",
                "payment_reference": "test_pay_wh_001",
                "amount": 100000,  # Tampered amount!
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_003"
        )
        assert result is False

        # Payment should still be PROCESSING
        await db.refresh(payment)
        assert payment.status == PaymentStatus.PROCESSING

    async def test_webhook_currency_mismatch_rejected(self, student_user, db: AsyncSession):
        """Webhook with wrong currency is rejected."""
        order, payment = await self._setup_online_order_with_payment(db, student_user, amount=50000)

        payload = json.dumps(
            {
                "event_id": "evt_004",
                "event_type": "payment_success",
                "payment_reference": "test_pay_wh_001",
                "amount": 50000,
                "currency": "USD",  # Wrong currency!
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_004"
        )
        assert result is False

    async def test_webhook_unknown_payment_reference(self, student_user, db: AsyncSession):
        """Webhook with unknown payment reference is rejected."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        payload = json.dumps(
            {
                "event_id": "evt_005",
                "event_type": "payment_success",
                "payment_reference": "unknown_reference",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_005"
        )
        assert result is False

    async def test_webhook_failure_event(self, student_user, db: AsyncSession):
        """Webhook with payment_failed event marks payment as FAILED."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        payload = json.dumps(
            {
                "event_id": "evt_006",
                "event_type": "payment_failed",
                "payment_reference": "test_pay_wh_001",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_006"
        )
        assert result is True

        await db.refresh(payment)
        assert payment.status == PaymentStatus.FAILED

    async def test_webhook_invalid_payload_rejected(self, student_user, db: AsyncSession):
        """Invalid JSON payload is rejected."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider",
            payload=b"not valid json {{{",
            provider_event_id="evt_007",
        )
        assert result is False

    async def test_webhook_logs_unprocessed_event(self, student_user, db: AsyncSession):
        """Failed webhooks are logged as WebhookEvents for auditing."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        payload = json.dumps(
            {
                "event_id": "evt_008",
                "event_type": "payment_success",
                "payment_reference": "unknown_ref",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_008"
        )

        # Verify webhook event logged
        result = await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == "evt_008")
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.processed is False

    async def test_webhook_already_successful_is_idempotent(self, student_user, db: AsyncSession):
        """Webhook for an already-succeeded payment is handled gracefully."""
        order, payment = await self._setup_online_order_with_payment(
            db, student_user, status=PaymentStatus.SUCCEEDED
        )

        payload = json.dumps(
            {
                "event_id": "evt_009",
                "event_type": "payment_success",
                "payment_reference": "test_pay_wh_001",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        result = await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_009"
        )
        assert result is True  # Still returns True (processed)

    async def test_webhook_creates_webhook_event_record(self, student_user, db: AsyncSession):
        """Processed webhooks are stored as WebhookEvent records."""
        order, payment = await self._setup_online_order_with_payment(db, student_user)

        payload = json.dumps(
            {
                "event_id": "evt_010",
                "event_type": "payment_success",
                "payment_reference": "test_pay_wh_001",
                "amount": 50000,
                "currency": "PKR",
            }
        ).encode()

        svc = PaymentService(db, TestPaymentProvider())
        await svc.process_webhook(
            provider_name="test_provider", payload=payload, provider_event_id="evt_010"
        )

        result = await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == "evt_010")
        )
        event = result.scalar_one()
        assert event.processed is True
        assert event.provider_name == "test_provider"


# ---------------------------------------------------------------------------
# Payment API Endpoint Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPaymentAPI:
    """Test payment API endpoints via HTTP client."""

    async def test_list_payments_empty(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """List payments when user has none returns empty."""
        resp = await student_client.get("/api/v1/payments/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["payments"] == []

    async def test_list_payments_after_checkout(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """List payments returns cash payment after checkout."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        await _checkout(student_client, cafeteria.id, payment_method="cash")

        resp = await student_client.get("/api/v1/payments/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_payment_by_id(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Get payment by ID returns payment details."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        await _checkout(student_client, cafeteria.id, payment_method="cash")

        # Get payment from DB
        result = await db.execute(select(Payment).limit(1))
        payment = result.scalar_one()

        resp = await student_client.get(f"/api/v1/payments/{payment.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == payment.id

    async def test_get_payment_not_owner_forbidden(
        self, student_client: AsyncClient, student_user, faculty_user, db: AsyncSession
    ):
        """User cannot view another user's payment."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        await _checkout(student_client, cafeteria.id, payment_method="cash")

        result = await db.execute(select(Payment).limit(1))
        payment = result.scalar_one()

        # Faculty tries to access student's payment
        from tests.conftest import create_user_session

        _, access_token, _ = await create_user_session(db, faculty_user)
        faculty_client_raw = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp = await faculty_client_raw.get(f"/api/v1/payments/{payment.id}")
        assert resp.status_code in (403, 404)
        await faculty_client_raw.aclose()

    async def test_get_order_payment(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """GET /payments/order/{order_id} returns the order's payment."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        order_id = checkout_resp.json()["id"]

        resp = await student_client.get(f"/api/v1/payments/order/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["order_id"] == order_id

    async def test_webhook_endpoint(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """POST /payments/webhook/{provider_name} accepts webhook payload."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        order_id = checkout_resp.json()["id"]

        # Initiate payment
        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "wh_key_001"},
        )
        assert resp.status_code == 201

        # Send webhook — need to look up the actual payment's provider_reference
        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()

        payload = json.dumps(
            {
                "event_id": "api_evt_001",
                "event_type": "payment_success",
                "payment_reference": payment.provider_reference,
                "amount": checkout_resp.json()["total_amount"],
                "currency": "PKR",
            }
        ).encode()

        resp = await student_client.post(
            "/api/v1/payments/webhook/test_provider",
            content=payload,
            headers={"Content-Type": "application/json", "x-event-id": "api_evt_001"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_unauthenticated_list_payments_fails(self, client: AsyncClient):
        """Unauthenticated request to list payments fails."""
        resp = await client.get("/api/v1/payments/")
        assert resp.status_code in (401, 403, 422)

    async def test_initiate_payment_nonexistent_order(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """Initiate payment for nonexistent order returns 404."""
        resp = await student_client.post(
            "/api/v1/payments/initiate/nonexistent-order-id",
            json={"idempotency_key": "key_404"},
        )
        assert resp.status_code in (404, 422)
