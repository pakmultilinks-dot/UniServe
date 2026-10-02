"""Tests for inventory management endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.users.models import Role, User
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_menu_item,
)


async def _get_manager_user(db: AsyncSession) -> User:
    """Fetch the manager user from the DB."""
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_MANAGER))
    return result.scalar_one()


async def _get_staff_user(db: AsyncSession) -> User:
    """Fetch the staff user from the DB."""
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_STAFF))
    return result.scalar_one()


# ===================================================================
# Create Inventory Item
# ===================================================================


@pytest.mark.asyncio
async def test_create_inventory_item(manager_client: AsyncClient, db):
    """Manager can create an inventory item."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu_item = await create_test_menu_item(db, cafeteria_id=caf.id)
    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/",
        json={
            "menu_item_id": menu_item.id,
            "quantity": 100,
            "unit": "portions",
            "low_threshold": 20,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == 100
    assert data["unit"] == "portions"
    assert data["low_threshold"] == 20
    assert data["is_low"] is False


@pytest.mark.asyncio
async def test_create_inventory_item_staff_forbidden(staff_client: AsyncClient, db):
    """Staff cannot create inventory items."""
    caf = await create_test_cafeteria(db)
    menu_item = await create_test_menu_item(db, cafeteria_id=caf.id)
    response = await staff_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/",
        json={
            "menu_item_id": menu_item.id,
            "quantity": 50,
            "unit": "kg",
        },
    )
    assert response.status_code == 403


# ===================================================================
# List Inventory Items
# ===================================================================


@pytest.mark.asyncio
async def test_list_inventory_items(manager_client: AsyncClient, db):
    """List inventory items for a cafeteria (scoped access)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu_item1 = await create_test_menu_item(db, cafeteria_id=caf.id, name="Item 1")
    menu_item2 = await create_test_menu_item(db, cafeteria_id=caf.id, name="Item 2")
    # Create inventory items directly
    inv1 = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item1.id,
        quantity=50,
        unit=InventoryUnit.PORTIONS,
        low_threshold=10,
    )
    inv2 = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item2.id,
        quantity=5,
        unit=InventoryUnit.KG,
        low_threshold=10,
    )
    db.add(inv1)
    db.add(inv2)
    await db.flush()

    response = await manager_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


# ===================================================================
# Adjust Inventory
# ===================================================================


@pytest.mark.asyncio
async def test_adjust_inventory_restock(manager_client: AsyncClient, db):
    """Staff can restock inventory."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu_item = await create_test_menu_item(db, cafeteria_id=caf.id)
    inv = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item.id,
        quantity=10,
        unit=InventoryUnit.PORTIONS,
        low_threshold=20,
    )
    db.add(inv)
    await db.flush()

    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
        json={
            "inventory_item_id": inv.id,
            "adjustment_quantity": 50,
            "reason": "Weekly restock",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["adjustment_quantity"] == 50
    assert data["reason"] == "Weekly restock"


@pytest.mark.asyncio
async def test_adjust_inventory_consumption(manager_client: AsyncClient, db):
    """Staff can record inventory consumption."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu_item = await create_test_menu_item(db, cafeteria_id=caf.id)
    inv = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item.id,
        quantity=100,
        unit=InventoryUnit.PORTIONS,
        low_threshold=10,
    )
    db.add(inv)
    await db.flush()

    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
        json={
            "inventory_item_id": inv.id,
            "adjustment_quantity": -30,
            "reason": "Lunch service",
        },
    )
    assert response.status_code == 200
    assert response.json()["adjustment_quantity"] == -30


@pytest.mark.asyncio
async def test_adjust_inventory_below_zero_fails(manager_client: AsyncClient, db):
    """Cannot reduce inventory below zero."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu_item = await create_test_menu_item(db, cafeteria_id=caf.id)
    inv = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item.id,
        quantity=10,
        unit=InventoryUnit.PORTIONS,
        low_threshold=5,
    )
    db.add(inv)
    await db.flush()

    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
        json={
            "inventory_item_id": inv.id,
            "adjustment_quantity": -20,
            "reason": "Over-consumption",
        },
    )
    assert response.status_code == 400


# ===================================================================
# Low Stock
# ===================================================================


@pytest.mark.asyncio
async def test_low_stock_items(manager_client: AsyncClient, db):
    """Get low-stock items (scoped access)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu_item1 = await create_test_menu_item(db, cafeteria_id=caf.id, name="Item 1")
    menu_item2 = await create_test_menu_item(db, cafeteria_id=caf.id, name="Item 2")
    inv1 = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item1.id,
        quantity=5,
        unit=InventoryUnit.PORTIONS,
        low_threshold=10,
    )
    inv2 = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item2.id,
        quantity=100,
        unit=InventoryUnit.PORTIONS,
        low_threshold=10,
    )
    db.add(inv1)
    db.add(inv2)
    await db.flush()

    response = await manager_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/low-stock")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["quantity"] == 5


# ===========================================================================
# Phase 27: Non-Payment Release Readiness — Adjustment Locking Regression
# ===========================================================================


@pytest.mark.asyncio
async def test_adjust_inventory_not_found(manager_client: AsyncClient, db):
    """Refactored locked-select path raises NotFound for a missing item."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
        json={
            "inventory_item_id": "00000000-0000-0000-0000-000000000002",
            "adjustment_quantity": 5,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_adjust_inventory_sequential_accumulation(manager_client: AsyncClient, db):
    """Two sequential adjustments accumulate exactly (read-modify-write path)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    await db.flush()
    menu_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Lock Test Item")

    inv = InventoryItem(
        cafeteria_id=caf.id,
        menu_item_id=menu_item.id,
        quantity=10,
        unit=InventoryUnit.PIECES,
        low_threshold=5,
    )
    db.add(inv)
    await db.flush()

    for qty in (7, -4):
        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
            json={"inventory_item_id": inv.id, "adjustment_quantity": qty},
        )
        assert resp.status_code == 200, resp.text

    result = await db.execute(select(InventoryItem).where(InventoryItem.id == inv.id))
    final = result.scalar_one()
    await db.refresh(final)  # adjustments committed in a separate session
    assert final.quantity == 13  # 10 + 7 - 4


# ===========================================================================
# Phase 38: Inventory read authorization (BUG 2 hardening)
# ===========================================================================


@pytest.mark.asyncio
class TestInventoryReadAuthorization:
    """Inventory GET endpoints expose internal stock data to staff/manager/admin only.

    Phase 37 found students/faculty receiving HTTP 200 with inventory
    quantities from the GET endpoints (visibility scope instead of the
    management scope used by writes and the inventory reports module).
    """

    async def _seed_inventory(self, db: AsyncSession, manager_user: User):
        """Create a cafeteria with one inventory item; assign its manager."""
        caf = await create_test_cafeteria(db)
        await assign_user_to_cafeteria(db, manager_user.id, caf.id)
        menu_item = await create_test_menu_item(db, cafeteria_id=caf.id)
        inv = InventoryItem(
            cafeteria_id=caf.id,
            menu_item_id=menu_item.id,
            quantity=42,
            unit=InventoryUnit.PORTIONS,
            low_threshold=10,
        )
        db.add(inv)
        await db.flush()
        return caf, inv

    async def test_student_cannot_list_inventory(
        self, student_client: AsyncClient, db, manager_user: User
    ):
        caf, _ = await self._seed_inventory(db, manager_user)
        resp = await student_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/")
        assert resp.status_code == 403
        assert "quantity" not in resp.text

    async def test_faculty_cannot_list_inventory(
        self, faculty_client: AsyncClient, db, manager_user: User
    ):
        caf, _ = await self._seed_inventory(db, manager_user)
        resp = await faculty_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/")
        assert resp.status_code == 403
        assert "quantity" not in resp.text

    async def test_student_cannot_list_low_stock(
        self, student_client: AsyncClient, db, manager_user: User
    ):
        caf, _ = await self._seed_inventory(db, manager_user)
        resp = await student_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/low-stock")
        assert resp.status_code == 403

    async def test_staff_assigned_can_list_inventory(
        self, staff_client: AsyncClient, db, staff_user: User, manager_user: User
    ):
        caf, inv = await self._seed_inventory(db, manager_user)
        await assign_user_to_cafeteria(db, staff_user.id, caf.id, role=Role.CAFETERIA_STAFF)
        await db.flush()

        resp = await staff_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["quantity"] == 42

        resp = await staff_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/low-stock")
        assert resp.status_code == 200  # item is not low (42 > 10) — access is what matters

    async def test_unassigned_staff_cannot_list_inventory(
        self, staff_client: AsyncClient, db, manager_user: User
    ):
        """Cafeteria isolation: staff without an assignment are denied reads."""
        caf, _ = await self._seed_inventory(db, manager_user)
        # staff_user exists but is deliberately NOT assigned to this cafeteria
        resp = await staff_client.get(f"/api/v1/cafeterias/{caf.id}/inventory/")
        assert resp.status_code == 403

    async def test_manager_cannot_list_foreign_inventory(
        self, manager_client: AsyncClient, db, manager_user: User
    ):
        """Cafeteria isolation: a manager cannot read another cafeteria's stock."""
        caf, _ = await self._seed_inventory(db, manager_user)  # manager assigned here
        other = await create_test_cafeteria(db, name="Other Canteen")
        resp = await manager_client.get(f"/api/v1/cafeterias/{other.id}/inventory/")
        assert resp.status_code == 403

    async def test_menu_availability_remains_visible_to_students(
        self, student_client: AsyncClient, db
    ):
        """Ordering surface keeps its intentional public availability signal.

        MenuItem responses expose only the availability boolean — never
        stock quantities — so customer ordering behavior is unaffected by
        the inventory-read restriction.
        """
        caf = await create_test_cafeteria(db)
        await create_test_menu_item(db, cafeteria_id=caf.id, is_available=True)

        resp = await student_client.get(f"/api/v1/cafeterias/{caf.id}/menu-items/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["is_available"] is True
        assert "quantity" not in data["items"][0]
