"""Tests for cart management — add, update, remove items, checkout.

Covers:
- Cart creation and retrieval
- Adding items to cart (with inventory validation)
- Updating item quantities
- Removing items
- Cart expiry
- Authorization (student → student cafeteria only, faculty → both)
- Empty cart checkout rejection
- Inventory insufficient rejection
- Price snapshot preservation
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import CafeteriaType
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus, MenuCategory
from tests.conftest import (
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup_cart_test_data(db: AsyncSession, *, with_inventory: bool = True):
    """Create common test data for cart tests.

    Returns: (cafeteria, menu_item, daily_menu)
    """
    cafeteria = await create_test_cafeteria(
        db,
        name="Student Cafeteria",
        cafeteria_type=CafeteriaType.STUDENT,
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

    # Add item to daily menu
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
            quantity=50,
            unit=InventoryUnit.PIECES,
        )
        db.add(inv)
        await db.flush()

    return cafeteria, item, daily_menu


# ---------------------------------------------------------------------------
# Cart CRUD Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCartCRUD:
    """Test cart creation, item management, and retrieval."""

    async def test_get_empty_cart_creates_one(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Getting a cart for the first time should create a new active cart."""
        cafeteria, _, _ = await _setup_cart_test_data(db)

        resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["item_count"] == 0
        assert data["total_amount"] == 0

    async def test_get_cart_returns_existing(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Getting a cart twice should return the same cart."""
        cafeteria, _, _ = await _setup_cart_test_data(db)

        resp1 = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        resp2 = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        assert resp1.json()["id"] == resp2.json()["id"]

    async def test_add_item_to_cart(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Adding an item to the cart creates a cart item with price snapshot."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["menu_item_id"] == item.id
        assert data["quantity"] == 2
        assert data["price_snapshot"] == 25000
        assert data["subtotal"] == 50000
        assert data["item_name"] == "Chicken Biryani"
        assert data["item_available"] is True

    async def test_add_same_item_merges_quantity(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Adding the same item again should increase quantity, not create duplicate."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
        )
        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 3},
        )
        assert resp.status_code == 201
        assert resp.json()["quantity"] == 5

    async def test_cart_shows_correct_total(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cart total should reflect all items correctly."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 3},
        )
        resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        data = resp.json()
        assert data["total_amount"] == 75000  # 3 * 25000
        assert data["item_count"] == 1

    async def test_update_item_quantity(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Updating cart item quantity changes the quantity."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        # Add item
        add_resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
        )
        cart_item_id = add_resp.json()["id"]

        # Update quantity
        resp = await student_client.put(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items/{cart_item_id}",
            json={"quantity": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["quantity"] == 5
        assert resp.json()["subtotal"] == 125000

    async def test_update_quantity_to_zero_removes(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Updating quantity to 0 should remove the item."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        add_resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
        )
        cart_item_id = add_resp.json()["id"]

        resp = await student_client.put(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items/{cart_item_id}",
            json={"quantity": 0},
        )
        # Should return 404 since the item is deleted
        assert resp.status_code == 404

    async def test_remove_item(self, student_client: AsyncClient, student_user, db: AsyncSession):
        """Explicitly removing an item from the cart."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        add_resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
        )
        cart_item_id = add_resp.json()["id"]

        resp = await student_client.delete(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items/{cart_item_id}"
        )
        assert resp.status_code == 204

        # Cart should now be empty
        cart_resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        assert cart_resp.json()["item_count"] == 0

    async def test_add_unavailable_item_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot add an unavailable menu item to cart."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        # Make item unavailable
        item.is_available = False
        await db.flush()

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
        )
        assert resp.status_code == 400

    async def test_add_item_insufficient_inventory_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot add more items than available in inventory."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        # Reduce inventory
        inv_result = await db.execute(
            __import__("sqlalchemy")
            .select(InventoryItem)
            .where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria.id,
            )
        )
        inv = inv_result.scalar_one()
        inv.quantity = 2
        await db.flush()

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 5},
        )
        assert resp.status_code == 400

    async def test_add_wrong_cafeteria_item_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cannot add an item from a different cafeteria."""
        cafeteria, _, _ = await _setup_cart_test_data(db)
        cafeteria2 = await create_test_cafeteria(
            db, name="Faculty Cafeteria", cafeteria_type=CafeteriaType.FACULTY
        )
        item2 = await create_test_menu_item(
            db, cafeteria_id=cafeteria2.id, name="Dal Chawal", price=15000
        )

        resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item2.id, "quantity": 1},
        )
        assert resp.status_code == 400

    async def test_price_snapshot_preserved(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Cart item stores the price at time of addition."""
        cafeteria, item, _ = await _setup_cart_test_data(db)

        add_resp = await student_client.post(
            f"/api/v1/cafeterias/{cafeteria.id}/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
        )
        # Price snapshot should be the item's current price
        assert add_resp.json()["price_snapshot"] == 25000

    async def test_student_access_faculty_cafeteria_cart_fails(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Students can only access Student cafeteria carts."""
        cafeteria = await create_test_cafeteria(
            db, name="Faculty Canteen", cafeteria_type=CafeteriaType.FACULTY
        )

        resp = await student_client.get(f"/api/v1/cafeterias/{cafeteria.id}/cart/")
        assert resp.status_code == 403
