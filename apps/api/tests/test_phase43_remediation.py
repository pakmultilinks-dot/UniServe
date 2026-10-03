"""Phase 43 regression tests — closing the four Phase 42 acceptance defects.

Phase 42 (final real-world product acceptance) found:

- P1: menu items without an inventory record made checkout fail with a raw
  UUID; a clean user-facing error was required. (Backfill + clean errors.)
- P2-1: daily-menu special_price was displayed but ignored by cart/checkout
  — listed Rs 110 was charged Rs 120. (Effective-price resolution.)
- P2-2: revenue reporting returned Rs 0 because cash payments were never
  confirmed at completion. (Ledger lifecycle wiring + backfill.)
- P2-3: mobile login succeeded but never navigated into the app. (Fixed by
  route-group Redirect guards in the Expo layouts; no mobile test runner
  exists in this repo — verified via real UI journeys, documented in
  PHASE_43_PRODUCT_BUG_REMEDIATION.md.)

These tests pin the fixed behaviour. Existing tests are untouched.
"""

import re
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import Cafeteria, CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.inventory.service import backfill_missing_inventory_records
from app.modules.menus.models import DailyMenuStatus, DailyMenuItem, MenuCategory
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.payments.service import backfill_completed_cash_payments
from app.modules.users.models import Role
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
    future_collection_time,
)

# High module-local order-number counter (shared DB across the session).
_order_seq = 500000

# Dummy user id for directly-seeded orders (same convention as test_reports;
# SQLite tests do not enforce FKs on this column).
_DUMMY_USER_ID = "00000000-0000-0000-0000-0000000000ff"


def _next_order_number() -> int:
    global _order_seq
    _order_seq += 1
    return _order_seq


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


async def _setup_shoppable(
    db: AsyncSession,
    *,
    price: int = 25000,
    special_price: int | None = None,
    stock: int | None = 50,
    published_menu: bool = True,
    cafeteria_type: CafeteriaType = CafeteriaType.STUDENT,
) -> tuple[Cafeteria, object]:
    """Cafeteria + menu item (+ published daily menu, + inventory row)."""
    cafeteria = await create_test_cafeteria(
        db,
        name=f"Phase43 Cafeteria {uuid.uuid4().hex[:8]}",
        cafeteria_type=cafeteria_type,
        operational_status=OperationalStatus.OPEN,
    )
    item = await create_test_menu_item(
        db,
        cafeteria_id=cafeteria.id,
        name="Phase43 Special Item",
        category=MenuCategory.MAIN_COURSE,
        price=price,
    )
    if published_menu:
        daily_menu = await create_test_daily_menu(
            db,
            cafeteria_id=cafeteria.id,
            status=DailyMenuStatus.PUBLISHED,
        )
        db.add(
            DailyMenuItem(
                daily_menu_id=daily_menu.id,
                menu_item_id=item.id,
                special_price=special_price,
                is_available_today=True,
            )
        )
    if stock is not None:
        db.add(
            InventoryItem(
                cafeteria_id=cafeteria.id,
                menu_item_id=item.id,
                quantity=stock,
                unit=InventoryUnit.PIECES,
            )
        )
    await db.flush()
    return cafeteria, item


async def _assign_staff(db: AsyncSession, staff_user, cafeteria: Cafeteria) -> None:
    await assign_user_to_cafeteria(
        db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF
    )


async def _add_to_cart(
    student_client: AsyncClient, cafeteria_id: str, item_id: str, quantity: int = 2
):
    return await student_client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/items",
        json={"menu_item_id": item_id, "quantity": quantity},
    )


async def _checkout(
    student_client: AsyncClient,
    cafeteria_id: str,
    item_id: str,
    *,
    quantity: int = 2,
    payment_method: str = "cash",
    order_type: str = "immediate",
    extra: dict | None = None,
):
    """Add to cart + checkout; returns (add_resp, checkout_resp)."""
    add_resp = await _add_to_cart(student_client, cafeteria_id, item_id, quantity)
    body: dict = {"payment_method": payment_method, "order_type": order_type}
    if order_type == "scheduled":
        body["scheduled_collection_time"] = future_collection_time(45)
    if extra:
        body.update(extra)
    checkout_resp = await student_client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/checkout",
        json=body,
    )
    return add_resp, checkout_resp


async def _get_payment(db: AsyncSession, order_id: str) -> Payment | None:
    result = await db.execute(select(Payment).where(Payment.order_id == order_id))
    return result.scalar_one_or_none()


async def _assert_no_raw_uuid(payload_text: str) -> None:
    """No UUID-shaped identifiers may leak into customer-facing errors."""
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        payload_text,
        re.IGNORECASE,
    ), f"Raw UUID leaked to client: {payload_text}"


async def _complete_via_collect(staff_client: AsyncClient, order_id: str, order_number: int):
    r = await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
    assert r.status_code == 200, r.text
    r = await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
    assert r.status_code == 200, r.text
    r = await staff_client.put(f"/api/v1/orders/{order_id}/ready", json={})
    assert r.status_code == 200, r.text
    r = await staff_client.post("/api/v1/orders/collect", json={"order_number": order_number})
    assert r.status_code == 200, r.text
    return r.json()


async def _complete_via_status_transitions(staff_client: AsyncClient, order_id: str):
    r = await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
    assert r.status_code == 200, r.text
    for status in ("preparing", "ready", "completed"):
        r = await staff_client.put(
            f"/api/v1/orders/{order_id}/status", json={"status": status}
        )
        assert r.status_code == 200, r.text
    return r.json()


async def _seed_completed_cash_order(
    db: AsyncSession,
    cafeteria: Cafeteria,
    *,
    total_amount: int,
    payment: str = "pending",
    order_type: OrderType = OrderType.IMMEDIATE,
) -> Order:
    """Insert a COMPLETED cash order directly (ledger-backfill scenarios).

    payment: "pending" → PENDING cash row; "none" → no payment row;
             "succeeded" → SUCCEEDED cash row.
    """
    order = Order(
        order_number=_next_order_number(),
        user_id=_DUMMY_USER_ID,
        cafeteria_id=cafeteria.id,
        order_type=order_type,
        payment_method=PaymentMethod.CASH,
        status=OrderStatus.COMPLETED,
        total_amount=total_amount,
        currency="PKR",
        order_date=date.today(),
        collection_token=f"p43_{uuid.uuid4().hex[:16]}",
    )
    db.add(order)
    await db.flush()
    if payment != "none":
        db.add(
            Payment(
                id=str(uuid.uuid4()),
                order_id=order.id,
                user_id=_DUMMY_USER_ID,
                amount=total_amount,
                currency="PKR",
                status=(
                    PaymentStatus.SUCCEEDED
                    if payment == "succeeded"
                    else PaymentStatus.PENDING
                ),
                provider_name="cash",
                idempotency_key=f"cash_{order.id}",
            )
        )
        await db.flush()
    return order


# ===========================================================================
# P1 — inventory record missing: backfill + clean user-facing errors
# ===========================================================================


@pytest.mark.asyncio
class TestP1InventoryBackfillAndCleanErrors:

    async def test_backfill_creates_missing_records_exactly_once(self, db: AsyncSession):
        cafeteria, item = await _setup_shoppable(db, stock=None)  # no inventory row
        # A second item that already HAS stock must remain untouched.
        _, item2 = await _setup_shoppable(db, price=15000, stock=7)

        summary = await backfill_missing_inventory_records(db)
        assert summary["records_created"] >= 1

        result = await db.execute(
            select(InventoryItem).where(InventoryItem.menu_item_id == item.id)
        )
        inv = result.scalar_one()
        assert inv.quantity == 0
        assert inv.unit == InventoryUnit.PORTIONS
        assert inv.low_threshold == 10
        assert inv.cafeteria_id == cafeteria.id

        # Idempotent — second run creates nothing new.
        before = (await db.execute(select(InventoryItem))).scalars().all()
        summary2 = await backfill_missing_inventory_records(db)
        after = (await db.execute(select(InventoryItem))).scalars().all()
        assert len(after) == len(before)
        assert summary2["records_created"] == 0

        # Existing stock untouched (no overwrite to zero).
        result2 = await db.execute(
            select(InventoryItem).where(InventoryItem.menu_item_id == item2.id)
        )
        assert result2.scalar_one().quantity == 7

    async def test_add_item_missing_inventory_clean_error_no_uuid(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, stock=None)

        resp = await _add_to_cart(student_client, cafeteria.id, item.id, 1)
        assert resp.status_code == 400
        assert "currently unavailable" in resp.text
        await _assert_no_raw_uuid(resp.text)

    async def test_add_item_zero_stock_clean_error_no_uuid(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, stock=0)

        resp = await _add_to_cart(student_client, cafeteria.id, item.id, 1)
        assert resp.status_code == 400
        assert "Insufficient inventory" in resp.text
        assert "available=0" in resp.text
        await _assert_no_raw_uuid(resp.text)

    async def test_checkout_missing_inventory_clean_error_no_uuid(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """The orders-side reservation path also fails cleanly (no UUID)."""
        cafeteria, item = await _setup_shoppable(db, stock=50)

        add_resp = await _add_to_cart(student_client, cafeteria.id, item.id, 1)
        assert add_resp.status_code == 201, add_resp.text

        # Remove the inventory row after the item entered the cart.
        result = await db.execute(
            select(InventoryItem).where(InventoryItem.menu_item_id == item.id)
        )
        inv = result.scalar_one()
        await db.delete(inv)
        await db.flush()

        checkout_resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "cash", "order_type": "immediate"},
        )
        assert checkout_resp.status_code == 400
        assert "currently unavailable" in checkout_resp.text
        await _assert_no_raw_uuid(checkout_resp.text)

    async def test_restock_makes_item_orderable_and_checkout_succeeds(
        self,
        student_client: AsyncClient,
        staff_client: AsyncClient,
        staff_user,
        db: AsyncSession,
    ):
        cafeteria, item = await _setup_shoppable(db, price=20000, stock=0)
        await _assign_staff(db, staff_user, cafeteria)

        # Zero stock → clean rejection.
        resp = await _add_to_cart(student_client, cafeteria.id, item.id, 2)
        assert resp.status_code == 400

        # Staff restocks via the real inventory API.
        result = await db.execute(
            select(InventoryItem).where(InventoryItem.menu_item_id == item.id)
        )
        inv_id = result.scalar_one().id
        restock = await staff_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/inventory/adjust",
            json={
                "inventory_item_id": inv_id,
                "adjustment_quantity": 10,
                "reason": "Phase43 restock",
            },
        )
        assert restock.status_code == 200, restock.text

        # Now orderable end-to-end.
        add_resp, checkout_resp = await _checkout(
            student_client, cafeteria.id, item.id, quantity=2
        )
        assert add_resp.status_code == 201, add_resp.text
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()
        assert order["total_amount"] == 40000

        result = await db.execute(
            select(InventoryItem).where(InventoryItem.menu_item_id == item.id)
        )
        assert result.scalar_one().quantity == 8


# ===========================================================================
# P2-1 — special price applied at cart + checkout (server-authoritative)
# ===========================================================================


@pytest.mark.asyncio
class TestP21SpecialPriceApplied:

    async def test_cart_uses_special_price(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, price=12000, special_price=11000)

        resp = await _add_to_cart(student_client, cafeteria.id, item.id, 1)
        assert resp.status_code == 201, resp.text
        assert resp.json()["price_snapshot"] == 11000

    async def test_checkout_charges_special_price(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, price=12000, special_price=11000)

        _, checkout_resp = await _checkout(student_client, cafeteria.id, item.id, quantity=2)
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()
        assert order["total_amount"] == 22000  # 11000 × 2, NOT 24000
        assert len(order["items"]) == 1
        assert order["items"][0]["unit_price"] == 11000
        assert order["items"][0]["subtotal"] == 22000

    async def test_without_special_price_base_price_unchanged(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, price=12000, special_price=None)

        add_resp, checkout_resp = await _checkout(
            student_client, cafeteria.id, item.id, quantity=2
        )
        assert add_resp.status_code == 201
        assert add_resp.json()["price_snapshot"] == 12000
        assert checkout_resp.status_code == 201
        order = checkout_resp.json()
        assert order["total_amount"] == 24000
        assert order["items"][0]["unit_price"] == 12000

    async def test_add_to_cart_without_published_menu_falls_back_to_base_price(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """No published menu for today → cart falls back to the base price.

        (Checkout itself is gated by the pre-existing published-menu rule, so
        the fallback is exercised at the cart layer where it is reachable.)
        """
        cafeteria, item = await _setup_shoppable(
            db, price=12000, special_price=11000, published_menu=False
        )

        add_resp = await _add_to_cart(student_client, cafeteria.id, item.id, 1)
        assert add_resp.status_code == 201, add_resp.text
        assert add_resp.json()["price_snapshot"] == 12000

    async def test_client_cannot_tamper_price(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, price=12000, special_price=11000)

        _, checkout_resp = await _checkout(
            student_client,
            cafeteria.id,
            item.id,
            quantity=2,
            extra={"price": 1, "total_amount": 1, "unit_price": 1},
        )
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()
        # Server-authoritative: client-sent price fields are ignored.
        assert order["total_amount"] == 22000
        assert order["items"][0]["unit_price"] == 11000

    async def test_order_total_matches_sum_of_items(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        from app.modules.menus.models import DailyMenuItem

        cafeteria, item_a = await _setup_shoppable(db, price=10000, special_price=9000)
        item_b = await create_test_menu_item(
            db, cafeteria_id=cafeteria.id, name="No Special", price=5000
        )
        daily = (
            await db.execute(
                select(DailyMenuItem).where(DailyMenuItem.menu_item_id == item_a.id)
            )
        ).scalars().first()
        db.add(
            DailyMenuItem(
                daily_menu_id=daily.daily_menu_id,
                menu_item_id=item_b.id,
                special_price=None,
                is_available_today=True,
            )
        )
        inv = (
            await db.execute(
                select(InventoryItem).where(InventoryItem.menu_item_id == item_a.id)
            )
        ).scalar_one()
        db.add(
            InventoryItem(
                cafeteria_id=cafeteria.id,
                menu_item_id=item_b.id,
                quantity=inv.quantity,
                unit=InventoryUnit.PIECES,
            )
        )
        await db.flush()

        r = await _add_to_cart(student_client, cafeteria.id, item_a.id, 2)
        assert r.status_code == 201
        r = await _add_to_cart(student_client, cafeteria.id, item_b.id, 1)
        assert r.status_code == 201

        checkout_resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "cash", "order_type": "immediate"},
        )
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()
        # 9000×2 + 5000×1 = 23000
        assert order["total_amount"] == 23000
        assert sum(i["subtotal"] for i in order["items"]) == order["total_amount"]


# ===========================================================================
# P2-2 — cash revenue ledger: confirmed at completion, backfilled, counted
# ===========================================================================


@pytest.mark.asyncio
class TestP22CashRevenueLedger:

    async def test_collect_confirms_cash_payment_and_counts_revenue(
        self,
        student_client: AsyncClient,
        staff_client: AsyncClient,
        staff_user,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        cafeteria, item = await _setup_shoppable(db, price=20000)
        await _assign_staff(db, staff_user, cafeteria)

        _, checkout_resp = await _checkout(student_client, cafeteria.id, item.id, quantity=2)
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()
        assert order["total_amount"] == 40000

        # Before completion the PENDING payment must NOT count as revenue.
        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_revenue"] == 0

        await _complete_via_collect(staff_client, order["id"], order["order_number"])

        payment = await _get_payment(db, order["id"])
        assert payment is not None
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.amount == 40000
        assert payment.provider_name == "cash"

        resp = await admin_client.get("/api/v1/reports/sales")
        data = resp.json()
        assert data["summary"]["total_revenue"] == 40000
        assert data["summary"]["total_orders"] == 1
        assert data["summary"]["net_revenue"] == 40000

    async def test_status_transition_completed_confirms_cash_payment(
        self,
        student_client: AsyncClient,
        staff_client: AsyncClient,
        staff_user,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        cafeteria, item = await _setup_shoppable(db, price=15000)
        await _assign_staff(db, staff_user, cafeteria)

        _, checkout_resp = await _checkout(student_client, cafeteria.id, item.id, quantity=1)
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()

        await _complete_via_status_transitions(staff_client, order["id"])

        payment = await _get_payment(db, order["id"])
        assert payment is not None
        assert payment.status == PaymentStatus.SUCCEEDED

        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.json()["summary"]["total_revenue"] == 15000

    async def test_scheduled_cash_order_completion_creates_ledger_row(
        self,
        student_client: AsyncClient,
        staff_client: AsyncClient,
        staff_user,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        cafeteria, item = await _setup_shoppable(db, price=18000)
        await _assign_staff(db, staff_user, cafeteria)

        _, checkout_resp = await _checkout(
            student_client, cafeteria.id, item.id, quantity=1, order_type="scheduled"
        )
        assert checkout_resp.status_code == 201, checkout_resp.text
        order = checkout_resp.json()
        assert order["order_type"] == "scheduled"

        # Scheduled cash orders have NO payment row at checkout.
        assert await _get_payment(db, order["id"]) is None

        await _complete_via_status_transitions(staff_client, order["id"])

        payment = await _get_payment(db, order["id"])
        assert payment is not None
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.amount == 18000

        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.json()["summary"]["total_revenue"] == 18000

    async def test_pending_cash_order_not_counted(
        self, student_client: AsyncClient, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, price=20000)
        _, checkout_resp = await _checkout(student_client, cafeteria.id, item.id)
        assert checkout_resp.status_code == 201

        resp = await admin_client.get("/api/v1/reports/sales")
        data = resp.json()
        assert data["summary"]["total_revenue"] == 0
        assert data["summary"]["total_orders"] == 0

    async def test_cancelled_cash_order_not_counted(
        self, student_client: AsyncClient, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria, item = await _setup_shoppable(db, price=20000)
        _, checkout_resp = await _checkout(student_client, cafeteria.id, item.id)
        assert checkout_resp.status_code == 201
        order = checkout_resp.json()

        r = await student_client.post(
            f"/api/v1/orders/{order['id']}/cancel", json={"reason": "changed mind"}
        )
        assert r.status_code == 200, r.text

        resp = await admin_client.get("/api/v1/reports/sales")
        data = resp.json()
        assert data["summary"]["total_revenue"] == 0
        assert data["summary"]["total_orders"] == 0

    async def test_cafeteria_scope_after_completion(
        self,
        student_client: AsyncClient,
        staff_client: AsyncClient,
        staff_user,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        caf_a, item_a = await _setup_shoppable(db, price=20000)
        caf_b, _ = await _setup_shoppable(
            db, price=99000, cafeteria_type=CafeteriaType.FACULTY
        )
        await _assign_staff(db, staff_user, caf_a)

        _, checkout_resp = await _checkout(student_client, caf_a.id, item_a.id, quantity=1)
        assert checkout_resp.status_code == 201
        order = checkout_resp.json()
        await _complete_via_collect(staff_client, order["id"], order["order_number"])

        resp_a = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_a.id}")
        assert resp_a.json()["summary"]["total_revenue"] == 20000

        resp_b = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_b.id}")
        assert resp_b.json()["summary"]["total_revenue"] == 0

    async def test_backfill_confirms_pending_and_creates_missing(self, db: AsyncSession):
        cafeteria, _ = await _setup_shoppable(db)

        pending_order = await _seed_completed_cash_order(
            db, cafeteria, total_amount=16000, payment="pending"
        )
        missing_order = await _seed_completed_cash_order(
            db,
            cafeteria,
            total_amount=45000,
            payment="none",
            order_type=OrderType.SCHEDULED,
        )
        untouched_order = await _seed_completed_cash_order(
            db, cafeteria, total_amount=99000, payment="succeeded"
        )
        # A PENDING (not completed) cash order must NOT be touched.
        pending_open = Order(
            order_number=_next_order_number(),
            user_id=_DUMMY_USER_ID,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.PENDING,
            total_amount=77000,
            currency="PKR",
            order_date=date.today(),
            collection_token=f"p43_{uuid.uuid4().hex[:16]}",
        )
        db.add(pending_open)
        await db.flush()
        db.add(
            Payment(
                id=str(uuid.uuid4()),
                order_id=pending_open.id,
                user_id=_DUMMY_USER_ID,
                amount=77000,
                currency="PKR",
                status=PaymentStatus.PENDING,
                provider_name="cash",
                idempotency_key=f"cash_{pending_open.id}",
            )
        )
        await db.flush()

        summary = await backfill_completed_cash_payments(db)
        assert summary["payments_confirmed"] == 1
        assert summary["payments_created"] == 1

        p1 = await _get_payment(db, pending_order.id)
        assert p1.status == PaymentStatus.SUCCEEDED and p1.amount == 16000
        p2 = await _get_payment(db, missing_order.id)
        assert p2 is not None
        assert p2.status == PaymentStatus.SUCCEEDED
        assert p2.amount == 45000
        assert p2.provider_name == "cash"
        assert p2.idempotency_key == f"cash_{missing_order.id}"
        p3 = await _get_payment(db, untouched_order.id)
        assert p3.status == PaymentStatus.SUCCEEDED and p3.amount == 99000
        p4 = await _get_payment(db, pending_open.id)
        assert p4.status == PaymentStatus.PENDING  # not completed → untouched

        # Idempotent — second run changes nothing.
        summary2 = await backfill_completed_cash_payments(db)
        assert summary2["payments_confirmed"] == 0
        assert summary2["payments_created"] == 0

    async def test_backfill_leaves_non_cash_and_failed_untouched(self, db: AsyncSession):
        cafeteria, _ = await _setup_shoppable(db)

        _cash_done = await _seed_completed_cash_order(db, cafeteria, total_amount=10000)
        online_done = Order(
            order_number=_next_order_number(),
            user_id=_DUMMY_USER_ID,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.ONLINE,
            status=OrderStatus.COMPLETED,
            total_amount=20000,
            currency="PKR",
            order_date=date.today(),
            collection_token=f"p43_{uuid.uuid4().hex[:16]}",
        )
        db.add(online_done)
        await db.flush()
        db.add(
            Payment(
                id=str(uuid.uuid4()),
                order_id=online_done.id,
                user_id=_DUMMY_USER_ID,
                amount=20000,
                currency="PKR",
                status=PaymentStatus.FAILED,
                provider_name="test",
                idempotency_key=f"online_{online_done.id}",
            )
        )
        await db.flush()

        summary = await backfill_completed_cash_payments(db)
        assert summary["payments_confirmed"] == 1  # only the cash PENDING row
        assert summary["payments_created"] == 0

        online_payment = await _get_payment(db, online_done.id)
        assert online_payment.status == PaymentStatus.FAILED  # untouched
