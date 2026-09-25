"""Regression tests for Phase 6 bug fixes.

Covers:
- WebhookEvent.processed_at timezone-aware datetime storage
- Refund.processed_at timezone-aware datetime storage
- Partial cancel returns updated order items (db.refresh fix)
"""

from datetime import UTC, date, datetime, timedelta
import time

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus, MenuCategory
from app.modules.orders.models import Order, OrderStatus, OrderType, PaymentMethod
from app.modules.payments.models import Payment, PaymentStatus, WebhookEvent
from app.modules.refunds.models import Refund, RefundStatus
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup_test_data(db: AsyncSession):
    """Create cafeteria, two menu items, daily menu, inventory."""
    cafeteria = await create_test_cafeteria(
        db,
        name="Regression Cafe",
        cafeteria_type=CafeteriaType.STUDENT,
        operational_status=OperationalStatus.OPEN,
    )
    item1 = await create_test_menu_item(
        db,
        cafeteria_id=cafeteria.id,
        name="Burger",
        category=MenuCategory.MAIN_COURSE,
        price=10000,
        is_available=True,
    )
    item2 = await create_test_menu_item(
        db,
        cafeteria_id=cafeteria.id,
        name="Fries",
        category=MenuCategory.SIDE_DISH,
        price=5000,
        is_available=True,
    )
    daily_menu = await create_test_daily_menu(
        db,
        cafeteria_id=cafeteria.id,
        status=DailyMenuStatus.DRAFT,
    )

    from app.modules.menus.models import DailyMenuItem

    for mi in [item1, item2]:
        dmi = DailyMenuItem(
            daily_menu_id=daily_menu.id,
            menu_item_id=mi.id,
            is_available_today=True,
        )
        db.add(dmi)
    await db.flush()

    daily_menu.status = DailyMenuStatus.PUBLISHED
    await db.flush()

    inv1 = InventoryItem(
        cafeteria_id=cafeteria.id,
        menu_item_id=item1.id,
        quantity=50,
        unit=InventoryUnit.PIECES,
    )
    inv2 = InventoryItem(
        cafeteria_id=cafeteria.id,
        menu_item_id=item2.id,
        quantity=50,
        unit=InventoryUnit.PIECES,
    )
    db.add(inv1)
    db.add(inv2)
    await db.flush()

    return cafeteria, item1, item2, daily_menu


async def _create_order_with_items(db: AsyncSession, user_id, cafeteria_id, item_ids):
    """Create an order with multiple items via service-level DB operations."""
    from app.modules.orders.models import OrderItem

    total = 0
    order = Order(
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.IMMEDIATE,
        payment_method=PaymentMethod.ONLINE,
        status=OrderStatus.PENDING,
        total_amount=0,
        currency="PKR",
        order_number=int(time.time() * 1000),
        order_date=date.today(),
    )
    db.add(order)
    await db.flush()

    for mid in item_ids:
        item = await db.execute(
            select(InventoryItem.menu_item_id).where(InventoryItem.menu_item_id == mid)
        )
        menu_item_id = item.scalar()
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=mid,
            item_name=f"Item {mid[:8]}",
            unit_price=10000,
            quantity=1,
            subtotal=10000,
            currency="PKR",
        )
        db.add(order_item)
        total += 10000
    order.total_amount = total
    await db.flush()
    return order


# ---------------------------------------------------------------------------
# Test class: Timezone-aware processed_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTimezoneAwareProcessedAt:
    """Regression: processed_at columns must use DateTime(timezone=True)."""

    async def test_webhook_event_processed_at_tz_aware(self, db: AsyncSession):
        """WebhookEvent.processed_at stores timezone-aware datetime correctly."""
        now_utc = datetime.now(UTC)
        event = WebhookEvent(
            provider_name="test_provider",
            provider_event_id="regression_evt_001",
            payload_json='{"test": true}',
            processed=True,
            processed_at=now_utc,
        )
        db.add(event)
        await db.flush()

        result = await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == "regression_evt_001")
        )
        fetched = result.scalar_one()
        assert fetched.processed_at is not None
        assert fetched.processed_at.tzinfo is not None
        assert fetched.processed_at.tzinfo == UTC

    async def test_webhook_event_processed_at_none(self, db: AsyncSession):
        """WebhookEvent.processed_at can be None (not yet processed)."""
        event = WebhookEvent(
            provider_name="test_provider",
            provider_event_id="regression_evt_002",
            payload_json='{"test": true}',
            processed=False,
            processed_at=None,
        )
        db.add(event)
        await db.flush()

        result = await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == "regression_evt_002")
        )
        fetched = result.scalar_one()
        assert fetched.processed_at is None

    async def test_refund_processed_at_tz_aware(self, student_user, db: AsyncSession):
        """Refund.processed_at stores timezone-aware datetime correctly."""
        cafeteria = await create_test_cafeteria(db, name="RegCafe1")

        order = Order(
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.PENDING,
            total_amount=10000,
            currency="PKR",
            order_number=int(time.time() * 1000),
            order_date=date.today(),
        )
        db.add(order)
        await db.flush()

        payment = Payment(
            id=f"reg_pay_{int(time.time() * 1000)}",
            order_id=order.id,
            user_id=student_user.id,
            amount=10000,
            currency="PKR",
            status=PaymentStatus.SUCCEEDED,
            provider_name="test_provider",
            provider_reference="test_pay_reg_001",
            idempotency_key="reg_pay_idem_001",
        )
        db.add(payment)
        await db.flush()

        now_utc = datetime.now(UTC)
        refund = Refund(
            id=f"reg_ref_{int(time.time() * 1000)}",
            order_id=order.id,
            payment_id=payment.id,
            user_id=student_user.id,
            amount=10000,
            currency="PKR",
            status=RefundStatus.SUCCEEDED,
            reason="order_cancelled",
            requested_by=student_user.id,
            processed_by=student_user.id,
            provider_reference="test_ref_reg_001",
            idempotency_key="reg_refund_001",
            processed_at=now_utc,
        )
        db.add(refund)
        await db.flush()

        result = await db.execute(
            select(Refund).where(Refund.idempotency_key == "reg_refund_001")
        )
        fetched = result.scalar_one()
        assert fetched.processed_at is not None
        assert fetched.processed_at.tzinfo is not None
        assert fetched.processed_at.tzinfo == UTC

    async def test_refund_processed_at_none(self, student_user, db: AsyncSession):
        """Refund.processed_at can be None (pending)."""
        cafeteria = await create_test_cafeteria(db, name="RegCafe2")
        order = Order(
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.PENDING,
            total_amount=10000,
            currency="PKR",
            order_number=int(time.time() * 1000),
            order_date=date.today(),
        )
        db.add(order)
        await db.flush()

        payment = Payment(
            id=f"reg_pay_{int(time.time() * 1000)}",
            order_id=order.id,
            user_id=student_user.id,
            amount=10000,
            currency="PKR",
            status=PaymentStatus.SUCCEEDED,
            provider_name="test_provider",
            provider_reference="test_pay_reg_002",
            idempotency_key="reg_pay_idem_002",
        )
        db.add(payment)
        await db.flush()

        refund = Refund(
            id=f"reg_ref_{int(time.time() * 1000)}",
            order_id=order.id,
            payment_id=payment.id,
            user_id=student_user.id,
            amount=10000,
            currency="PKR",
            status=RefundStatus.PENDING,
            reason="order_cancelled",
            requested_by=student_user.id,
            idempotency_key="reg_refund_002",
            processed_at=None,
        )
        db.add(refund)
        await db.flush()

        result = await db.execute(
            select(Refund).where(Refund.idempotency_key == "reg_refund_002")
        )
        fetched = result.scalar_one()
        assert fetched.processed_at is None


# ---------------------------------------------------------------------------
# Test class: Partial cancel returns correct items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPartialCancelItemsRefresh:
    """Regression: partial_item_cancel must return updated order.items.

    Before fix, the API returned stale order.items after deleting an item
    because the SQLAlchemy relationship was not refreshed.
    """

    async def test_partial_cancel_returns_correct_item_count(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
    ):
        """After partial cancel, order.items should have count-1 items."""
        cafeteria, item1, item2, _ = await _setup_test_data(db)

        # Add both items to cart
        for item in [item1, item2]:
            resp = await student_client.post(
                f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
                json={"menu_item_id": item.id, "quantity": 1},
            )
            assert resp.status_code == 201, resp.text

        # Checkout
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "online", "order_type": "immediate"},
        )
        assert resp.status_code == 201, resp.text
        order = resp.json()
        order_id = order["id"]
        assert len(order["items"]) == 2

        # Cancel one item
        target_item_id = order["items"][0]["id"]
        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/partial-cancel",
            json={"item_id": target_item_id, "reason": "Changed my mind"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # CRITICAL REGRESSION: items count must reflect the cancelled item
        assert len(data["items"]) == 1, (
            f"Expected 1 remaining item after partial cancel, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] != target_item_id

    async def test_partial_cancel_all_items_cancels_order(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
    ):
        """Cancelling all items via sequential partial cancels should cancel the order."""
        cafeteria, item1, item2, _ = await _setup_test_data(db)

        for item in [item1, item2]:
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
        order = resp.json()
        order_id = order["id"]

        # Cancel first item
        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/partial-cancel",
            json={"item_id": order["items"][0]["id"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) == 1

        # Cancel second (last) item → order should be CANCELLED
        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/partial-cancel",
            json={"item_id": order["items"][1]["id"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == OrderStatus.CANCELLED.value
        assert len(data["items"]) == 0

    async def test_partial_cancel_total_recalculated(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
    ):
        """After partial cancel, total_amount should exclude cancelled item."""
        cafeteria, item1, item2, _ = await _setup_test_data(db)

        for item in [item1, item2]:
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
        order = resp.json()
        order_id = order["id"]
        original_total = order["total_amount"]

        # Cancel one item
        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/partial-cancel",
            json={"item_id": order["items"][0]["id"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_amount"] < original_total
        # With items at 10000 each, cancelling one should halve the total
        assert data["total_amount"] == original_total - 10000
