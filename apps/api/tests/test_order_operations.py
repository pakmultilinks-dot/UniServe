"""Tests for Phase 6 — Order Operations & Fulfillment.

Covers:
- Order confirmation by manager/staff
- Order rejection by manager
- Preparation lifecycle (start, ready, delay, uncollected)
- ETA calculation
- Partial item cancellation
- Cafeteria sudden closure
- No-show tracking and suspension
- Pickup deadline enforcement
- Authorization enforcement
- Edge cases and error paths
"""

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus, MenuCategory
from app.modules.orders.models import (
    NoShow,
    Order,
    OrderStatus,
    OrderType,
)
from app.modules.users.models import AccountStatus, Role, User, UserCategory
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
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
    cafeteria_name: str = "Test Cafeteria",
):
    """Create common test data for order tests.

    Returns: (cafeteria, menu_item, daily_menu)
    """
    cafeteria = await create_test_cafeteria(
        db,
        name=cafeteria_name,
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
):
    """Checkout the cart via API."""
    resp = await client.post(
        f"/api/v1/cafeterias/{cafeteria_id}/cart/checkout",
        json={"payment_method": payment_method, "order_type": order_type},
    )
    return resp


async def _create_and_checkout_order(
    client: AsyncClient,
    db: AsyncSession,
    *,
    student_user: User,
    staff_user: User,
    manager_user: User,
) -> tuple:
    """Create a complete order and return (cafeteria, item, order_data).

    Also assigns staff/manager to cafeteria and sets up inventory.
    """
    cafeteria, item, _ = await _setup_order_test_data(db)

    # Assign manager and staff to cafeteria
    await assign_user_to_cafeteria(db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER)
    await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF)

    # Add item and checkout
    await _add_cart_item(client, cafeteria.id, item.id, quantity=2)
    resp = await _checkout(client, cafeteria.id, payment_method="cash")
    assert resp.status_code == 201, resp.text
    order_data = resp.json()

    return cafeteria, item, order_data


# ---------------------------------------------------------------------------
# Order Confirmation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderConfirmation:
    """Test order confirmation by manager/staff."""

    async def test_confirm_order_success(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Staff can confirm a pending order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={"notes": "Confirmed for preparation"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "pending"  # Status stays PENDING
        assert data["confirmed_at"] is not None

    async def test_confirm_order_already_confirmed_fails(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cannot confirm an order twice."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={},
        )
        assert resp.status_code == 200

        # Try again
        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={},
        )
        assert resp.status_code == 400

    async def test_confirm_wrong_status_fails(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cannot confirm an order that is not PENDING."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        # Confirm
        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={},
        )
        assert resp.status_code == 200

        # Start preparation
        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/prepare",
            json={},
        )
        assert resp.status_code == 200

        # Try to confirm now
        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={},
        )
        assert resp.status_code == 400

    async def test_confirm_unauthorized_fails(
        self,
        student_client: AsyncClient,
        db: AsyncSession,
        student_user: User,
        staff_user: User,
        manager_user: User,
    ):
        """Students cannot confirm orders."""
        cafeteria, item, _ = await _setup_order_test_data(db)

        await assign_user_to_cafeteria(db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER)
        await assign_user_to_cafeteria(db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF)

        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=1)
        resp = await _checkout(student_client, cafeteria.id)
        order_data = resp.json()

        resp = await student_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Order Rejection Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderRejection:
    """Test order rejection by manager."""

    async def test_reject_order_success(
        self,
        manager_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Manager can reject a pending order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await manager_client.post(
            f"/api/v1/orders/{order_data['id']}/reject",
            json={"reason": "capacity", "notes": "Kitchen overloaded"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["rejection_reason"] == "capacity"
        assert data["rejection_note"] == "Kitchen overloaded"

    async def test_reject_order_releases_inventory(
        self,
        manager_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Rejecting an order releases reserved inventory."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        # Check inventory before rejection
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = result.scalar_one()
        assert inv.quantity == 48  # 50 - 2 reserved

        resp = await manager_client.post(
            f"/api/v1/orders/{order_data['id']}/reject",
            json={"reason": "item_unavailable"},
        )
        assert resp.status_code == 200

        # Check inventory restored
        await db.refresh(inv)
        assert inv.quantity == 50

    async def test_reject_wrong_status_fails(
        self,
        manager_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cannot reject a non-pending order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        # Confirm + prepare
        await manager_client.post(f"/api/v1/orders/{order_data['id']}/confirm", json={})
        await manager_client.post(f"/api/v1/orders/{order_data['id']}/prepare", json={})

        resp = await manager_client.post(
            f"/api/v1/orders/{order_data['id']}/reject",
            json={"reason": "capacity"},
        )
        assert resp.status_code == 400

    async def test_reject_invalid_reason_fails(
        self,
        manager_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Rejecting with an invalid reason fails."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await manager_client.post(
            f"/api/v1/orders/{order_data['id']}/reject",
            json={"reason": "invalid_reason"},
        )
        assert resp.status_code == 400

    async def test_staff_cannot_reject(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Staff cannot reject orders (manager only)."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/reject",
            json={"reason": "capacity"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Preparation Lifecycle Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPreparationLifecycle:
    """Test the full preparation lifecycle: confirm → prepare → ready → collect."""

    async def test_start_preparation_requires_confirmation(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cannot start preparation without confirmation."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/prepare",
            json={},
        )
        assert resp.status_code == 400

    async def test_full_lifecycle(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Full lifecycle: confirm → prepare → ready → collect."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        # Confirm
        resp = await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        assert resp.status_code == 200
        assert resp.json()["confirmed_at"] is not None

        # Start preparation
        resp = await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "preparing"
        assert data["preparation_started_at"] is not None
        assert data["eta_minutes"] is not None
        assert data["eta_minutes"] >= 5

        # Mark ready
        resp = await staff_client.put(f"/api/v1/orders/{order_id}/ready", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["ready_at"] is not None
        assert data["pickup_deadline"] is not None

        # Collect
        resp = await staff_client.post(
            "/api/v1/orders/collect",
            json={"order_number": order_data["order_number"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["collected_at"] is not None

    async def test_ready_after_closing_never_gets_past_pickup_deadline(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Completing a 10 PM order at an 8 PM cafeteria cannot expire it immediately."""
        cafeteria, _, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]
        # Midnight belongs to the current cafeteria-local date and is already
        # over at practically every time of day. The exceptional behavior must
        # use the configured full pickup window, not yesterday's close.
        cafeteria.closing_time = "00:00"
        await db.flush()
        assert (await staff_client.post(
            f"/api/v1/orders/{order_id}/confirm", json={}
        )).status_code == 200
        assert (await staff_client.post(
            f"/api/v1/orders/{order_id}/prepare", json={}
        )).status_code == 200
        response = await staff_client.put(
            f"/api/v1/orders/{order_id}/ready", json={}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        ready_at = datetime.fromisoformat(data["ready_at"].replace("Z", "+00:00"))
        deadline = datetime.fromisoformat(data["pickup_deadline"].replace("Z", "+00:00"))
        assert deadline > ready_at
        from app.core.config import settings
        assert (deadline - ready_at).total_seconds() <= settings.PICKUP_WINDOW_MINUTES * 60

        # Both student/mobile endpoints must see the same server status and
        # the in-app Ready notification after staff acts on the web queue.
        student_view = await student_client.get(f"/api/v1/orders/{order_id}")
        assert student_view.status_code == 200
        assert student_view.json()["status"] == "ready"

        notifications = await student_client.get("/api/v1/notifications")
        assert notifications.status_code == 200
        assert any(
            n["notification_type"] == "order_ready" and n["order_id"] == order_id
            for n in notifications.json()["items"]
        )

    async def test_prepare_sets_eta(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Starting preparation calculates an ETA."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        resp = await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
        assert resp.status_code == 200
        assert resp.json()["eta_minutes"] >= 5

    async def test_delay_order(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Staff can delay an order and ETA updates."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        # Confirm + prepare
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        resp = await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
        original_eta = resp.json()["eta_minutes"]

        # Delay
        resp = await staff_client.put(
            f"/api/v1/orders/{order_id}/delay",
            json={"additional_minutes": 15, "notes": "Supplier delay"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["eta_minutes"] == original_eta + 15

    async def test_delay_ready_order_extends_deadline(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Delaying a READY order extends the pickup deadline."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        # Full lifecycle to READY
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
        resp = await staff_client.put(f"/api/v1/orders/{order_id}/ready", json={})
        original_deadline = resp.json()["pickup_deadline"]

        # Delay
        resp = await staff_client.put(
            f"/api/v1/orders/{order_id}/delay",
            json={"additional_minutes": 10},
        )
        assert resp.status_code == 200
        new_deadline = resp.json()["pickup_deadline"]
        assert new_deadline > original_deadline

    async def test_delay_invalid_range_fails(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Delay must be 1-120 minutes."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})

        resp = await staff_client.put(
            f"/api/v1/orders/{order_id}/delay",
            json={"additional_minutes": 0},
        )
        assert resp.status_code == 422

        resp = await staff_client.put(
            f"/api/v1/orders/{order_id}/delay",
            json={"additional_minutes": 200},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# ETA Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestETA:
    """Test ETA calculation endpoint."""

    async def test_get_eta(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Get ETA for a pending order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await student_client.get(f"/api/v1/orders/{order_data['id']}/eta")
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_id"] == order_data["id"]
        assert data["eta_minutes"] >= 5


# ---------------------------------------------------------------------------
# Partial Item Cancellation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPartialCancellation:
    """Test partial item cancellation."""

    async def test_partial_cancel_pending_order(
        self,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """User can cancel items from a pending order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        item_id = order_data["items"][0]["id"]

        resp = await student_client.post(
            f"/api/v1/orders/{order_data['id']}/partial-cancel",
            json={"item_id": item_id, "reason": "Changed my mind"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # All items cancelled → order cancelled
        assert data["status"] == "cancelled"

    async def test_partial_cancel_wrong_status_fails(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cannot cancel items from a non-pending order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        # Confirm + prepare
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})

        item_id = order_data["items"][0]["id"]
        resp = await student_client.post(
            f"/api/v1/orders/{order_id}/partial-cancel",
            json={"item_id": item_id},
        )
        assert resp.status_code == 400

    async def test_partial_cancel_nonexistent_item_fails(
        self,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Cannot cancel a nonexistent item."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await student_client.post(
            f"/api/v1/orders/{order_data['id']}/partial-cancel",
            json={"item_id": "nonexistent-item-id"},
        )
        assert resp.status_code == 404

    async def test_partial_cancel_wrong_user_fails(
        self,
        faculty_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        faculty_user: User,
        db: AsyncSession,
    ):
        """User cannot cancel items from another user's order."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        item_id = order_data["items"][0]["id"]
        resp = await faculty_client.post(
            f"/api/v1/orders/{order_data['id']}/partial-cancel",
            json={"item_id": item_id},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cafeteria Sudden Closure Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCafeteriaClosure:
    """Test cafeteria sudden closure cancelling affected orders."""

    async def test_close_cafeteria_cancels_pending_orders(
        self,
        manager_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Closing a cafeteria cancels all PENDING and PREPARING orders."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await manager_client.post(
            f"/api/v1/orders/cafeteria/{cafeteria.id}/close",
            json={"notes": "Emergency maintenance"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] >= 1

        # Verify order was cancelled
        cancel_event_found = False
        for order in data["orders"]:
            if order["status"] == "cancelled":
                cancel_event_found = True
        assert cancel_event_found

    async def test_close_cafeteria_updates_status(
        self,
        manager_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Closing a cafeteria sets its operational status to CLOSED."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await manager_client.post(
            f"/api/v1/orders/cafeteria/{cafeteria.id}/close",
            json={},
        )
        assert resp.status_code == 200

        # Verify cafeteria status
        await db.refresh(cafeteria)
        assert cafeteria.operational_status == OperationalStatus.CLOSED

    async def test_staff_cannot_close_cafeteria(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Staff cannot close a cafeteria (manager only)."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await staff_client.post(
            f"/api/v1/orders/cafeteria/{cafeteria.id}/close",
            json={},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# No-Show Tracking Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNoShow:
    """Test no-show tracking and suspension."""

    async def test_mark_uncollected_records_noshow(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Marking an order uncollected records a no-show event."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )
        order_id = order_data["id"]

        # Confirm → prepare → ready
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
        await staff_client.put(f"/api/v1/orders/{order_id}/ready", json={})

        # Get the actual order from DB to call service directly
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one()

        from app.modules.orders.noshow import record_no_show

        await record_no_show(
            db=db,
            user_id=order.user_id,
            order_id=order.id,
            cafeteria_id=order.cafeteria_id,
        )

        # Verify no-show was recorded
        noshow_result = await db.execute(select(NoShow).where(NoShow.order_id == order_id))
        noshow = noshow_result.scalar_one_or_none()
        assert noshow is not None

    async def test_suspension_after_threshold(
        self,
        db: AsyncSession,
    ):
        """User gets suspended after exceeding no-show threshold."""

        from app.core.config import settings
        from app.modules.orders.noshow import record_no_show

        user = User(
            first_name="NoShow",
            last_name="User",
            university_id="NS-001",
            university_email="noshow@lgu.edu.pk",
            category=UserCategory.STUDENT,
            role=Role.STUDENT,
            status=AccountStatus.ACTIVE,
            email_verified=True,
        )
        db.add(user)
        await db.flush()

        cafeteria = await create_test_cafeteria(
            db,
            name="NoShow Cafeteria",
            cafeteria_type=CafeteriaType.STUDENT,
        )

        # Create fake orders and record no-shows up to threshold
        for i in range(settings.NOSHOW_STUDENT_THRESHOLD):
            order = Order(
                order_number=9000 + i,
                user_id=user.id,
                cafeteria_id=cafeteria.id,
                order_type=OrderType.IMMEDIATE,
                payment_method="cash",
                status=OrderStatus.READY,
                total_amount=10000,
                currency="PKR",
                order_date=date.today(),
                inventory_reserved=False,
            )
            db.add(order)
            await db.flush()

            await record_no_show(
                db=db,
                user_id=user.id,
                order_id=order.id,
                cafeteria_id=cafeteria.id,
            )

        # User should now be suspended
        await db.refresh(user)
        assert user.ordering_suspended is True
        assert user.ordering_suspended_until is not None

    async def test_check_suspension_expired(
        self,
        db: AsyncSession,
    ):
        """Expired suspensions are automatically cleared."""
        from datetime import timedelta

        from app.modules.orders.noshow import check_suspension

        user = User(
            first_name="Expired",
            last_name="Suspension",
            university_id="ES-001",
            university_email="expired@lgu.edu.pk",
            category=UserCategory.STUDENT,
            role=Role.STUDENT,
            status=AccountStatus.ACTIVE,
            email_verified=True,
            ordering_suspended=True,
            ordering_suspended_until=datetime.now(UTC) - timedelta(days=1),
        )
        db.add(user)
        await db.flush()

        # Check — should auto-expire
        is_suspended = await check_suspension(db=db, user_id=user.id)
        assert is_suspended is False

        await db.refresh(user)
        assert user.ordering_suspended is False


# ---------------------------------------------------------------------------
# Authorization Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPhase6Authorization:
    """Test authorization enforcement for Phase 6 endpoints."""

    async def test_student_cannot_reject(
        self,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Students cannot reject orders."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await student_client.post(
            f"/api/v1/orders/{order_data['id']}/reject",
            json={"reason": "capacity"},
        )
        assert resp.status_code == 403

    async def test_student_cannot_start_preparation(
        self,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Students cannot start preparation."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await student_client.post(
            f"/api/v1/orders/{order_data['id']}/prepare",
            json={},
        )
        assert resp.status_code == 403

    async def test_student_cannot_mark_ready(
        self,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Students cannot mark orders as ready."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        resp = await student_client.put(
            f"/api/v1/orders/{order_data['id']}/ready",
            json={},
        )
        assert resp.status_code == 403

    async def test_unassigned_staff_cannot_operate(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Staff not assigned to the cafeteria cannot operate on its orders."""
        cafeteria, item, _ = await _setup_order_test_data(db, cafeteria_name="Other Cafeteria")

        # Don't assign staff to this cafeteria
        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=1)
        resp = await _checkout(student_client, cafeteria.id)
        order_data = resp.json()

        resp = await staff_client.post(
            f"/api/v1/orders/{order_data['id']}/confirm",
            json={},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Scheduled-time helper regression (CI around 23:58 Asia/Karachi)
# ---------------------------------------------------------------------------


def test_scheduled_time_helper_never_returns_an_expired_last_minute_slot(monkeypatch):
    """A late-night run skips impossible same-day scenarios, not a fake 23:58."""
    import tests.conftest as helpers
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    original_datetime = datetime

    class FrozenEndOfDay(original_datetime):
        @classmethod
        def now(cls, tz=None):
            local = original_datetime(2026, 10, 22, 23, 58, tzinfo=ZoneInfo("Asia/Karachi"))
            return local.astimezone(tz) if tz is not None else local.replace(tzinfo=None)

    monkeypatch.setattr(helpers, "datetime", FrozenEndOfDay)
    with pytest.raises(pytest.skip.Exception, match="No future same-day"):
        helpers.future_collection_time(30)


# ---------------------------------------------------------------------------
# Scheduled Order + Inventory Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestScheduledOrderPrep:
    """Test scheduled order inventory reservation at preparation start."""

    async def test_scheduled_order_inventory_reserved_at_prep(
        self,
        staff_client: AsyncClient,
        student_client: AsyncClient,
        student_user: User,
        staff_user: User,
        manager_user: User,
        db: AsyncSession,
    ):
        """Scheduled orders reserve inventory when preparation starts, not at checkout."""
        cafeteria, item, order_data = await _create_and_checkout_order(
            student_client,
            db,
            student_user=student_user,
            staff_user=staff_user,
            manager_user=manager_user,
        )

        # Check inventory NOT reserved at checkout for scheduled
        # First verify: immediate cash order reserves inventory
        assert order_data["inventory_reserved"] is True

        # Now test scheduled order
        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=1)
        cafeteria.closing_time = "23:59"
        await db.flush()
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/checkout",
            json={
                "payment_method": "cash",
                "order_type": "scheduled",
                "scheduled_collection_time": future_collection_time(),
            },
        )
        assert resp.status_code == 201, resp.text
        sched_order = resp.json()
        assert sched_order["inventory_reserved"] is False

        # Confirm + prepare → inventory should be reserved
        order_id = sched_order["id"]
        await staff_client.post(f"/api/v1/orders/{order_id}/confirm", json={})
        resp = await staff_client.post(f"/api/v1/orders/{order_id}/prepare", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["inventory_reserved"] is True
