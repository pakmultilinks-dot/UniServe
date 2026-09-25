"""Tests for payment-preparation gate — online orders require succeeded payment.

Business rule: An online-paid order must not enter preparation unless its
payment has successfully completed.

Covers:
- Online order with succeeded payment → preparation allowed
- Online order with pending payment → preparation rejected
- Online order with failed payment → preparation rejected
- Online order with no payment record → preparation rejected
- Cash order regression → preparation allowed without payment
- Confirmed-but-unpaid online order → preparation still rejected
"""

import uuid
from datetime import date, datetime, UTC

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
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.users.models import Role, User, UserCategory
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
    create_test_user,
    create_user_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup_gate_test_data(db: AsyncSession):
    """Create cafeteria, menu item, inventory, daily menu for gate tests."""
    cafeteria = await create_test_cafeteria(
        db,
        name="Gate Test Cafeteria",
        cafeteria_type=CafeteriaType.STUDENT,
        operational_status=OperationalStatus.OPEN,
    )
    item = await create_test_menu_item(
        db,
        cafeteria_id=cafeteria.id,
        name="Burger",
        category=MenuCategory.MAIN_COURSE,
        price=10000,
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

    inv = InventoryItem(
        cafeteria_id=cafeteria.id,
        menu_item_id=item.id,
        quantity=50,
        unit=InventoryUnit.PIECES,
    )
    db.add(inv)
    await db.flush()

    return cafeteria, item


async def _create_order_in_db(
    db: AsyncSession,
    *,
    user_id: str,
    cafeteria_id: str,
    payment_method: PaymentMethod = PaymentMethod.ONLINE,
    status: OrderStatus = OrderStatus.PENDING,
    confirmed: bool = False,
) -> Order:
    """Create an order directly in DB for gate testing."""
    order = Order(
        order_number=int(uuid.uuid4().int % 90000) + 1000,
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.IMMEDIATE,
        payment_method=payment_method,
        status=status,
        total_amount=10000,
        currency="PKR",
        order_date=date.today(),
        inventory_reserved=False,
        confirmed_at=datetime.now(UTC) if confirmed else None,
    )
    db.add(order)
    await db.flush()
    return order


async def _create_payment_in_db(
    db: AsyncSession,
    *,
    order_id: str,
    user_id: str,
    status: PaymentStatus = PaymentStatus.PENDING,
    provider_reference: str | None = None,
) -> Payment:
    """Create a payment record directly in DB for gate testing."""
    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order_id,
        user_id=user_id,
        amount=10000,
        currency="PKR",
        status=status,
        provider_name="test_provider",
        provider_reference=provider_reference or f"test_pay_{uuid.uuid4().hex[:12]}",
        idempotency_key=f"idem_{order_id[:8]}_{uuid.uuid4().hex[:8]}",
    )
    db.add(payment)
    await db.flush()
    return payment


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPaymentPreparationGate:
    """Verify: online-paid orders cannot enter preparation without succeeded payment."""

    async def test_online_order_succeeded_payment_allows_preparation(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Online order with SUCCEEDED payment → preparation succeeds."""
        cafeteria, item = await _setup_gate_test_data(db)
        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
        )

        # Add to cart and checkout (online)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
        )
        assert resp.status_code == 201, resp.text

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "online", "order_type": "immediate"},
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # Initiate payment
        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": f"idem_{order_id}"},
        )
        assert resp.status_code in (200, 201), resp.text

        # Simulate payment success via DB
        result = await db.execute(
            select(Payment).where(Payment.order_id == order_id)
        )
        payment = result.scalar_one()
        payment.status = PaymentStatus.SUCCEEDED
        await db.flush()

        # Confirm order
        resp = await staff_client.post(
            f"/api/v1/orders/{order_id}/confirm",
            json={},
        )
        assert resp.status_code == 200, resp.text

        # Prepare order — should succeed
        resp = await staff_client.post(
            f"/api/v1/orders/{order_id}/prepare",
            json={},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "preparing"

    async def test_online_order_pending_payment_blocks_preparation(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Online order with PENDING payment → preparation rejected (400)."""
        cafeteria, item = await _setup_gate_test_data(db)
        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
        )

        # Add to cart and checkout (online)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
        )
        assert resp.status_code == 201, resp.text

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "online", "order_type": "immediate"},
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # Initiate payment (status = PENDING)
        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": f"idem_{order_id}"},
        )
        assert resp.status_code in (200, 201), resp.text

        # Confirm order (allowed before payment)
        resp = await staff_client.post(
            f"/api/v1/orders/{order_id}/confirm",
            json={},
        )
        assert resp.status_code == 200, resp.text

        # Prepare order — should be REJECTED
        resp = await staff_client.post(
            f"/api/v1/orders/{order_id}/prepare",
            json={},
        )
        assert resp.status_code == 400, resp.text
        data = resp.json()
        assert "pending" in data["detail"].lower() or "succeeded" in data["detail"].lower()

    async def test_online_order_failed_payment_blocks_preparation(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Online order with FAILED payment → preparation rejected (400)."""
        cafeteria, item = await _setup_gate_test_data(db)
        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
        )

        # Create order + confirmed + failed payment via DB helpers
        order = await _create_order_in_db(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            payment_method=PaymentMethod.ONLINE,
            confirmed=True,
        )
        await _create_payment_in_db(
            db,
            order_id=order.id,
            user_id=student_user.id,
            status=PaymentStatus.FAILED,
        )

        # Prepare order — should be REJECTED
        resp = await staff_client.post(
            f"/api/v1/orders/{order.id}/prepare",
            json={},
        )
        assert resp.status_code == 400, resp.text
        data = resp.json()
        assert "failed" in data["detail"].lower()

    async def test_online_order_no_payment_record_blocks_preparation(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Online order with NO payment record → preparation rejected (400)."""
        cafeteria, item = await _setup_gate_test_data(db)
        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
        )

        # Create order (online, confirmed, no payment)
        order = await _create_order_in_db(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            payment_method=PaymentMethod.ONLINE,
            confirmed=True,
        )
        # No payment record at all

        # Prepare order — should be REJECTED
        resp = await staff_client.post(
            f"/api/v1/orders/{order.id}/prepare",
            json={},
        )
        assert resp.status_code == 400, resp.text
        data = resp.json()
        assert "payment not found" in data["detail"].lower()

    async def test_cash_order_preparation_not_blocked(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cash order → preparation allowed without payment record."""
        cafeteria, item = await _setup_gate_test_data(db)
        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
        )

        # Add to cart and checkout (cash)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
        )
        assert resp.status_code == 201, resp.text

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "cash", "order_type": "immediate"},
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # Confirm order
        resp = await staff_client.post(
            f"/api/v1/orders/{order_id}/confirm",
            json={},
        )
        assert resp.status_code == 200, resp.text

        # Prepare order — should succeed (no payment check for cash)
        resp = await staff_client.post(
            f"/api/v1/orders/{order_id}/prepare",
            json={},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "preparing"

    async def test_confirmed_unpaid_online_order_still_blocked(
        self,
        staff_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Confirmed online order with PENDING payment still cannot prepare.

        This confirms that order confirmation does NOT bypass the payment gate.
        """
        cafeteria, item = await _setup_gate_test_data(db)
        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(
            db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
        )

        # Create order (online, confirmed, payment PENDING)
        order = await _create_order_in_db(
            db,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            payment_method=PaymentMethod.ONLINE,
            confirmed=True,
        )
        await _create_payment_in_db(
            db,
            order_id=order.id,
            user_id=student_user.id,
            status=PaymentStatus.PENDING,
        )

        # Prepare order — should be REJECTED even though confirmed
        resp = await staff_client.post(
            f"/api/v1/orders/{order.id}/prepare",
            json={},
        )
        assert resp.status_code == 400, resp.text
        data = resp.json()
        assert "pending" in data["detail"].lower() or "succeeded" in data["detail"].lower()
