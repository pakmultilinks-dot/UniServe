"""Tests for order management — checkout, lifecycle, cancellation, collection.

Covers:
- Checkout flow (cart → order)
- Order numbering (sequential, globally unique)
- Order retrieval (by ID, number, token)
- Order listing (user, cafeteria)
- Status transitions (pending → preparing → ready → completed)
- Cancellation rules (user before deadline, manager anytime)
- Collection via order number or QR token
- Inventory reservation (cash immediate, scheduled at preparation)
- Inventory release on cancellation
- Authorization (student/faculty scope, manager/staff write scope)
- Edge cases (empty cart, wrong cafeteria, double cancel, etc.)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus, MenuCategory
from app.modules.users.models import Role, User, UserCategory
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
    create_test_user,
    create_user_session,
    future_collection_time,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup_order_test_data(
    db: AsyncSession,
    *,
    with_inventory: bool = True,
    cafeteria_type: CafeteriaType = CafeteriaType.STUDENT,
    inventory_qty: int = 50,
):
    """Create common test data for order tests.

    Returns: (cafeteria, menu_item, daily_menu)
    """
    cafeteria = await create_test_cafeteria(
        db,
        name="Test Cafeteria",
        cafeteria_type=cafeteria_type,
        operational_status=OperationalStatus.OPEN,
    )
    item = await create_test_menu_item(
        db,
        cafeteria_id=cafeteria.id,
        name="Chicken Biryani",
        category=MenuCategory.MAIN_COURSE,
        price=25000,
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

    if with_inventory:
        inv = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item.id,
            quantity=inventory_qty,
            unit=InventoryUnit.PIECES,
        )
        db.add(inv)
        await db.flush()

    return cafeteria, item, daily_menu


async def _add_cart_item(
    client: AsyncClient,
    cafeteria_id: str,
    menu_item_id: str,
    quantity: int = 2,
):
    """Add an item to the cart via API."""
    resp = await client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/items",
        json={"menu_item_id": menu_item_id, "quantity": quantity},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _checkout(
    client: AsyncClient,
    cafeteria_id: str,
    *,
    payment_method: str = "cash",
    order_type: str = "immediate",
    note: str | None = None,
):
    """Checkout the cart via API."""
    body: dict = {"payment_method": payment_method, "order_type": order_type}
    if note:
        body["note"] = note
    resp = await client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/checkout",
        json=body,
    )
    return resp


# ---------------------------------------------------------------------------
# Checkout Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckout:
    """Test the checkout flow: cart → order."""

    async def test_checkout_creates_order(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Checkout with a valid cart creates an order with correct totals."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=3)

        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["order_type"] == "immediate"
        assert data["payment_method"] == "cash"
        assert data["status"] == "pending"
        assert data["total_amount"] == 75000  # 3 * 25000
        assert data["inventory_reserved"] is True
        assert len(data["items"]) == 1
        assert data["items"][0]["item_name"] == "Chicken Biryani"
        assert data["items"][0]["quantity"] == 3
        assert data["items"][0]["unit_price"] == 25000

    async def test_checkout_empty_cart_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot checkout an empty cart."""
        cafeteria, _, _ = await _setup_order_test_data(db)

        resp = await _checkout(student_client, cafeteria.id)
        assert resp.status_code == 400

    async def test_checkout_idempotency_returns_existing_order(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Retrying checkout with the same key does not create another order."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)

        body = {
            "payment_method": "cash",
            "order_type": "immediate",
            "idempotency_key": "checkout-retry-test",
        }
        first = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json=body,
        )
        second = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json=body,
        )

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["order_number"] == first.json()["order_number"]

    async def test_checkout_preserves_order_number(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Each order gets a sequential order number."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp1 = await _checkout(student_client, cafeteria.id)
        assert resp1.status_code == 201
        num1 = resp1.json()["order_number"]

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp2 = await _checkout(student_client, cafeteria.id)
        assert resp2.status_code == 201
        num2 = resp2.json()["order_number"]

        assert num2 == num1 + 1

    async def test_checkout_expires_cart(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """After checkout, the old cart is expired and a new empty cart is created."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)

        # Capture the cart_id before checkout
        cart_resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        old_cart_id = cart_resp.json()["id"]

        await _checkout(student_client, cafeteria.id)

        # The old cart should be expired — verify in DB
        from app.modules.carts.models import Cart as CartModel

        old_cart = await db.get(CartModel, old_cart_id)
        assert old_cart is not None
        assert old_cart.status.value == "expired"

        # GET /cart creates a new active cart (or returns existing active)
        new_cart_resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        assert new_cart_resp.json()["status"] == "active"
        assert new_cart_resp.json()["id"] != old_cart_id

    async def test_checkout_releases_inventory_for_cash(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cash immediate order reserves inventory."""
        cafeteria, item, _ = await _setup_order_test_data(db, inventory_qty=10)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=5)
        await _checkout(student_client, cafeteria.id)

        # Check inventory was reduced
        inv_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = inv_result.scalar_one()
        assert inv.quantity == 5  # 10 - 5

    async def test_checkout_online_does_not_reserve_inventory(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Online payment order does NOT reserve inventory (Phase 5 boundary)."""
        cafeteria, item, _ = await _setup_order_test_data(db, inventory_qty=10)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=5)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        assert resp.status_code == 201
        assert resp.json()["inventory_reserved"] is False

        # Inventory should still be full
        inv_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = inv_result.scalar_one()
        assert inv.quantity == 10

    async def test_checkout_cafeteria_closed_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot checkout if cafeteria is closed."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        cafeteria.operational_status = OperationalStatus.CLOSED
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id)
        assert resp.status_code == 400

    async def test_checkout_no_published_menu_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot checkout if no published menu for today."""
        cafeteria, item, daily_menu = await _setup_order_test_data(db)

        # Revert menu to draft
        daily_menu.status = DailyMenuStatus.DRAFT
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id)
        assert resp.status_code == 400

    async def test_checkout_scheduled_requires_time(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Scheduled order requires a collection time."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={"payment_method": "cash", "order_type": "scheduled"},
        )
        assert resp.status_code == 400

    async def test_checkout_scheduled_does_not_reserve_inventory(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Scheduled order does NOT reserve inventory at checkout."""
        cafeteria, item, _ = await _setup_order_test_data(db, inventory_qty=10)
        cafeteria.closing_time = "23:59"
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=5)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={
                "payment_method": "cash",
                "order_type": "scheduled",
                "scheduled_collection_time": future_collection_time(),
            },
        )
        assert resp.status_code == 201
        assert resp.json()["inventory_reserved"] is False

    async def test_checkout_scheduled_rejects_past_time(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Scheduled order rejects a collection time that is already past."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)

        # Use "00:00" which is always in the past (even at midnight edge,
        # the check is utc_collection <= now, so exactly midnight is also rejected).
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={
                "payment_method": "cash",
                "order_type": "scheduled",
                "scheduled_collection_time": "00:00",
            },
        )
        assert resp.status_code == 400

    async def test_checkout_scheduled_rejects_after_closing(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Scheduled order rejects collection time after cafeteria closing."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        # Set cafeteria closing time to 17:00
        cafeteria.closing_time = "17:00"
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={
                "payment_method": "cash",
                "order_type": "scheduled",
                "scheduled_collection_time": "23:00",
            },
        )
        assert resp.status_code == 400

    async def test_checkout_server_authoritative_price(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Order uses server-side price, not client-supplied."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=2)
        resp = await _checkout(student_client, cafeteria.id)
        assert resp.status_code == 201

        # Even if we tried to manipulate, the server uses price_snapshot
        order_data = resp.json()
        assert order_data["total_amount"] == 50000  # server-calculated


# ---------------------------------------------------------------------------
# Order Retrieval Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderRetrieval:
    """Test order retrieval by ID, number, token, and listing."""

    async def test_get_order_by_id(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await student_client.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id

    async def test_get_order_by_number(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_number = checkout_resp.json()["order_number"]

        resp = await student_client.get(f"/api/v1/orders/by-number/{order_number}")
        assert resp.status_code == 200
        assert resp.json()["order_number"] == order_number

    async def test_get_order_by_number_other_user_forbidden(
        self, student_client: AsyncClient, faculty_client: AsyncClient, db: AsyncSession
    ):
        """User cannot view another user's order by order number (IDOR prevention)."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_number = checkout_resp.json()["order_number"]

        # Faculty user (different user) tries to access student's order
        resp = await faculty_client.get(f"/api/v1/orders/by-number/{order_number}")
        assert resp.status_code == 403

    async def test_list_user_orders(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)

        # Create 3 orders
        for _ in range(3):
            await _add_cart_item(student_client, cafeteria.id, item.id)
            await _checkout(student_client, cafeteria.id)

        resp = await student_client.get("/api/v1/orders/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["orders"]) == 3

    async def test_list_orders_filter_by_status(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        assert checkout_resp.status_code == 201

        resp = await student_client.get("/api/v1/orders/?status=pending")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = await student_client.get("/api/v1/orders/?status=completed")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Order Detail IDOR Security Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderDetailIDOR:
    """Security regression tests for GET /orders/{order_id} IDOR fix.

    Verifies that an authenticated user cannot access another user's order
    by guessing or knowing the order UUID.
    """

    async def test_owner_can_access_own_order(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Test A — Order owner can access their own order."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await student_client.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id

    async def test_different_student_cannot_access_order(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """Test B — A different student cannot access another user's order."""

        # Student A creates an order
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Student B (different user) — build a clean client
        student_b = await create_test_user(
            db,
            first_name="Other",
            last_name="Student",
            university_id="FA22-BSE-999",
            university_email="other.student@lgu.edu.pk",
            role=Role.STUDENT,
        )
        _, token_b, _ = await create_user_session(db, student_b)
        client_b = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_b}"},
        )

        resp = await client_b.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 403
        await client_b.aclose()

    async def test_different_faculty_cannot_access_order(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """Test C — A different faculty user cannot access another user's order."""

        # Student creates an order
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Faculty user (different user)
        faculty = await create_test_user(
            db,
            first_name="Dr.",
            last_name="Other",
            university_id="FAC-9999",
            university_email="other.faculty@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        _, token_faculty, _ = await create_user_session(db, faculty)
        client_faculty = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_faculty}"},
        )

        resp = await client_faculty.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 403
        await client_faculty.aclose()

    async def test_cross_cafeteria_manager_cannot_access_order(
        self, student_client: AsyncClient, manager_user: User, db: AsyncSession
    ):
        """Test D — Manager assigned to a different cafeteria cannot access order."""

        # Order in cafeteria A
        cafeteria_a, item_a, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria_a.id, item_a.id)
        checkout_resp = await _checkout(student_client, cafeteria_a.id)
        order_id = checkout_resp.json()["id"]

        # Manager B assigned to cafeteria B (different cafeteria)
        cafeteria_b = await create_test_cafeteria(
            db, name="Cafeteria B", cafeteria_type=CafeteriaType.STUDENT
        )
        await assign_user_to_cafeteria(db, manager_user.id, cafeteria_b.id, Role.CAFETERIA_MANAGER)
        _, token_mgr, _ = await create_user_session(db, manager_user)
        client_mgr = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_mgr}"},
        )

        resp = await client_mgr.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 403
        await client_mgr.aclose()

    async def test_correct_manager_can_access_order(
        self, student_client: AsyncClient, manager_user: User, db: AsyncSession
    ):
        """Test E — Manager assigned to the order's cafeteria can access it."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        await assign_user_to_cafeteria(db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        _, token_mgr, _ = await create_user_session(db, manager_user)
        client_mgr = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_mgr}"},
        )
        resp = await client_mgr.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id
        await client_mgr.aclose()

    async def test_correct_staff_can_access_order(
        self, student_client: AsyncClient, staff_user: User, db: AsyncSession
    ):
        """Test F — Staff assigned to the order's cafeteria can access it."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        _, token_staff, _ = await create_user_session(db, staff_user)
        client_staff = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_staff}"},
        )
        resp = await client_staff.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id
        await client_staff.aclose()

    async def test_university_admin_can_access_any_order(
        self, student_client: AsyncClient, admin_user: User, db: AsyncSession
    ):
        """Test G — University Admin can access any order."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        _, token_admin, _ = await create_user_session(db, admin_user)
        client_admin = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        resp = await client_admin.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id
        await client_admin.aclose()

    async def test_unauthenticated_blocked(
        self, student_client: AsyncClient, client: AsyncClient, db: AsyncSession
    ):
        """Test H — Unauthenticated request is denied."""
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Use the raw unauthenticated client directly (no Authorization header)
        resp = await client.get(f"/api/v1/orders/{order_id}")
        # Without auth header: 422 (validation) or 401/403 (auth rejection)
        assert resp.status_code in (401, 403, 422)

    async def test_nonexistent_order_returns_not_found(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """Test I — Nonexistent order returns 404."""
        resp = await student_client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    async def test_idor_uuid_substitution_attack(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        """Test J — Primary IDOR attack: User B requests User A's order UUID."""

        # User A creates an order
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_a_id = checkout_resp.json()["id"]

        # User B authenticates and tries to access User A's order by UUID
        user_b = await create_test_user(
            db,
            first_name="Attacker",
            last_name="User",
            university_id="ATTACK-001",
            university_email="attacker@lgu.edu.pk",
            role=Role.STUDENT,
        )
        _, token_b, _ = await create_user_session(db, user_b)
        client_b = AsyncClient(
            transport=student_client._transport,
            base_url=str(student_client.base_url),
            headers={"Authorization": f"Bearer {token_b}"},
        )

        resp = await client_b.get(f"/api/v1/orders/{order_a_id}")
        assert resp.status_code == 403
        # Verify no sensitive order data is returned
        assert "total_amount" not in resp.json()
        assert "items" not in resp.json()
        await client_b.aclose()


# ---------------------------------------------------------------------------
# Order Cancellation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderCancellation:
    """Test cancellation rules and inventory release."""

    async def test_user_cancel_pending_order(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json={"reason": "Changed my mind"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["cancellation_reason"] == "Changed my mind"
        assert data["cancelled_at"] is not None

    async def test_cancel_releases_inventory(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db, inventory_qty=10)
        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=5)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Inventory should be reduced
        inv_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = inv_result.scalar_one()
        assert inv.quantity == 5

        # Cancel the order
        await student_client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json={"reason": "Test"},
        )

        # Inventory should be restored
        await db.refresh(inv)
        assert inv.quantity == 10

    async def test_cancel_already_cancelled_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        await student_client.post(f"/api/v1/orders/{order_id}/cancel", json={})
        resp = await student_client.post(f"/api/v1/orders/{order_id}/cancel", json={})
        assert resp.status_code == 400

    async def test_cancel_non_pending_fails_for_user(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
        staff_client,
        staff_user,
    ):
        """User cannot cancel order that is already preparing."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Manager confirms, then starts preparation
        await manager_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )

        # User tries to cancel — should fail
        resp = await student_client.post(f"/api/v1/orders/{order_id}/cancel", json={})
        assert resp.status_code == 400

    async def test_user_cancel_wrong_order_fails(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        faculty_client,
        faculty_user,
    ):
        """User cannot cancel another user's order."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        # Faculty user places order (faculty can access both)
        await _add_cart_item(faculty_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(faculty_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Student tries to cancel — should fail
        resp = await student_client.post(f"/api/v1/orders/{order_id}/cancel", json={})
        assert resp.status_code == 400

    async def test_manager_cancel_any_order(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Manager can cancel any order in their cafeteria."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()
        cafeteria.closing_time = "23:59"
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await manager_client.post(
            f"/api/v1/orders/{order_id}/manager-cancel",
            json={"reason": "Cafeteria closing early"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["cancellation_reason"] == "Cafeteria closing early"


# ---------------------------------------------------------------------------
# Status Transition Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStatusTransitions:
    """Test order status lifecycle transitions."""

    async def test_full_lifecycle(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Test: pending → preparing → ready → completed."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]
        assert checkout_resp.json()["status"] == "pending"

        # pending → preparing (confirmation required first)
        resp = await manager_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        assert resp.status_code == 200
        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "preparing"

        # preparing → ready
        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ready"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

        # ready → completed
        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    async def test_invalid_transition_fails(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Cannot skip status steps (e.g., pending → ready)."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ready"},
        )
        assert resp.status_code == 400

    async def test_staff_can_update_status(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        staff_client,
        staff_user,
    ):
        """Staff members can update order status."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        resp = await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 200

    async def test_unauthorized_user_cannot_update_status(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
    ):
        """Students cannot update order status."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await student_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Collection Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCollection:
    """Test order collection via staff/manager action."""

    async def test_collect_ready_order(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        staff_client,
        staff_user,
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]
        order_number = checkout_resp.json()["order_number"]

        # Move to ready (confirm required before preparation)
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ready"},
        )

        # Collect via order number
        resp = await staff_client.post(
            "/api/v1/orders/collect",
            json={"order_number": order_number},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["collected_at"] is not None

    async def test_collect_already_collected_fails(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        staff_client,
        staff_user,
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        # Move to ready + complete (confirm required before preparation)
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ready"},
        )
        await staff_client.post(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "completed"},
        )

        # Actually collect via collect endpoint first
        resp = await staff_client.post(
            "/api/v1/orders/collect",
            json={"order_number": checkout_resp.json()["order_number"]},
        )
        assert resp.status_code == 200

        # Try to collect again
        resp2 = await staff_client.post(
            "/api/v1/orders/collect",
            json={"order_number": checkout_resp.json()["order_number"]},
        )
        assert resp2.status_code == 400

    async def test_collect_non_ready_fails(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        staff_client,
        staff_user,
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_number = checkout_resp.json()["order_number"]

        # Try to collect a pending order
        resp = await staff_client.post(
            "/api/v1/orders/collect",
            json={"order_number": order_number},
        )
        assert resp.status_code == 400

    async def test_student_cannot_collect(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        staff_client,
        staff_user,
    ):
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)

        # Move to ready (confirm required before preparation)
        order_id = checkout_resp.json()["id"]
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        await staff_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ready"},
        )

        # Student tries to collect — should fail (not staff/manager)
        resp = await student_client.post(
            "/api/v1/orders/collect",
            json={"order_number": checkout_resp.json()["order_number"]},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Inventory Reservation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInventoryReservation:
    """Test inventory reservation and release logic."""

    async def test_scheduled_inventory_reserved_at_preparation(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Scheduled order reserves inventory when preparation starts."""
        cafeteria, item, _ = await _setup_order_test_data(db, inventory_qty=10)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=5)
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={
                "payment_method": "cash",
                "order_type": "scheduled",
                "scheduled_collection_time": future_collection_time(),
            },
        )
        assert resp.status_code == 201
        order_id = resp.json()["id"]

        # Inventory should still be full
        inv_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = inv_result.scalar_one()
        assert inv.quantity == 10

        # Start preparation (confirm required first)
        await manager_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )

        # Now inventory should be reduced
        await db.refresh(inv)
        assert inv.quantity == 5

    async def test_inventory_insufficient_at_checkout(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Checkout should fail if inventory became insufficient after cart was filled."""
        cafeteria, item, _ = await _setup_order_test_data(db, inventory_qty=10)

        # Add items to cart (within inventory)
        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=5)

        # Now reduce inventory below what's in the cart
        from app.modules.inventory.models import InventoryItem

        inv_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = inv_result.scalar_one()
        inv.quantity = 2
        await db.flush()

        resp = await _checkout(student_client, cafeteria.id)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Authorization Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthorization:
    """Test cafeteria scope and role-based authorization."""

    async def test_faculty_can_access_student_cafeteria(
        self, faculty_client: AsyncClient, faculty_user, db: AsyncSession
    ):
        """Faculty can access both student and faculty cafeterias."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await _add_cart_item(faculty_client, cafeteria.id, item.id)
        resp = await _checkout(faculty_client, cafeteria.id)
        assert resp.status_code == 201

    async def test_student_cannot_access_faculty_cafeteria(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(
            db, name="Faculty Canteen", cafeteria_type=CafeteriaType.FACULTY
        )

        resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        assert resp.status_code == 403

    async def test_manager_cannot_update_unassigned_cafeteria_order(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Manager can only manage orders in their assigned cafeteria."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        # Manager is NOT assigned to this cafeteria

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Phase 27: Non-Payment Release Readiness — Regression Tests
# ===========================================================================


@pytest.mark.asyncio
class TestScheduledCancellationTimezone:
    """Phase 27 fix: the cancellation deadline uses cafeteria-local time.

    scheduled_collection_time is cafeteria-local (checkout validation uses
    ZoneInfo(cafeteria.timezone)). The deadline check must interpret it the
    same way — previously it treated HH:MM as UTC, shifting the deadline by
    the cafeteria's UTC offset (5 hours for PKT).
    """

    async def test_deadline_past_in_local_time_rejected(self, db: AsyncSession):
        """A collection time already past in cafeteria-local time must reject."""
        from datetime import datetime as dt
        from datetime import timedelta

        from app.core.exceptions import ValidationError
        from app.modules.orders.models import Order
        from app.modules.orders.service import OrderService

        from zoneinfo import ZoneInfo

        caf = await create_test_cafeteria(db, name="TZ Cafeteria Midway")
        caf.timezone = "Pacific/Midway"  # UTC-11
        await db.flush()

        # Collection is 2 hours ahead in UTC = 9 hours behind in Midway local
        # time. Derive the date/time from the local datetime directly — the
        # local clock may roll back to the previous calendar day.
        local_now = dt.now(ZoneInfo("Pacific/Midway"))
        past_local = local_now - timedelta(hours=9)
        collection = past_local.strftime("%H:%M")
        local_date = past_local.date()

        order = Order(
            cafeteria_id=caf.id,
            order_number="TZTEST-0001",
            order_date=local_date,
            scheduled_collection_time=collection,
        )

        service = OrderService(db)
        with pytest.raises(ValidationError):
            await service._check_scheduled_cancellation_deadline(order)

    async def test_future_local_time_allows_cancellation(self, db: AsyncSession):
        """A collection time still future in cafeteria-local time must pass."""
        from datetime import datetime as dt
        from datetime import timedelta

        from app.modules.orders.models import Order
        from app.modules.orders.service import OrderService

        from zoneinfo import ZoneInfo

        caf = await create_test_cafeteria(db, name="TZ Cafeteria Karachi")
        caf.timezone = "Asia/Karachi"  # UTC+5
        await db.flush()

        # 8 hours ahead in UTC = 13 hours ahead in PKT — well within deadline.
        # Derive from the local datetime so the date rolls correctly.
        local_now = dt.now(ZoneInfo("Asia/Karachi"))
        future_local = local_now + timedelta(hours=13)
        collection = future_local.strftime("%H:%M")
        local_date = future_local.date()

        order = Order(
            cafeteria_id=caf.id,
            order_number="TZTEST-0002",
            order_date=local_date,
            scheduled_collection_time=collection,
        )

        service = OrderService(db)
        # Must NOT raise — collection time is future in cafeteria-local time.
        await service._check_scheduled_cancellation_deadline(order)


@pytest.mark.asyncio
class TestUpdateStatusBusinessGates:
    """Phase 27 fix: PUT /orders/{id}/status enforces the same gates as /prepare."""

    async def test_preparing_requires_confirmation(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Generic status endpoint cannot start preparation on unconfirmed order."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(student_client, cafeteria.id)
        order_id = checkout_resp.json()["id"]

        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower()

    async def test_online_order_unpaid_blocked_from_generic_status(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Online order without succeeded payment cannot enter preparing via PUT."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(
            student_client, cafeteria.id, payment_method="online"
        )
        order_id = checkout_resp.json()["id"]

        # Confirm first (confirmation gate passes), payment still unpaid.
        await manager_client.post(f"/api/v1/orders/{order_id}/confirm", json={})

        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 400
        assert "payment" in resp.json()["detail"].lower()

    async def test_online_order_succeeded_payment_allows_generic_status(
        self,
        student_client: AsyncClient,
        student_user,
        db: AsyncSession,
        manager_client,
        manager_user,
    ):
        """Control: online order with succeeded payment can enter preparing via PUT."""
        from app.modules.payments.models import Payment, PaymentStatus

        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(
            db, manager_user.id, cafeteria.id, role=Role.CAFETERIA_MANAGER
        )
        await db.flush()

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(
            student_client, cafeteria.id, payment_method="online"
        )
        order_id = checkout_resp.json()["id"]

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": f"idem_{order_id}"},
        )
        assert resp.status_code in (200, 201), resp.text

        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()
        payment.status = PaymentStatus.SUCCEEDED
        await db.flush()

        await manager_client.post(f"/api/v1/orders/{order_id}/confirm", json={})

        resp = await manager_client.put(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "preparing"
