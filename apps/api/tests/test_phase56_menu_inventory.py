"""Phase 56 — Menu & Inventory Ergonomics tests.

Covers:
- Copy Previous Day's Menu (POST /daily-menus/copy): draft creation,
  junction metadata preservation, explicit 409 on occupied target,
  inactive-item skipping, RBAC, source immutability.
- Menu item DELETE (soft-delete): admin-only, is_active/is_available flip,
  historical junction + inventory rows remain.
- Inventory creation scope (wrong cafeteria, student, negative qty).
- Inactive cafeteria filtering (is_active query param + admin visibility).
- Dietary/allergen metadata roundtrip + survival through menu copy.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryItem
from app.modules.menus.models import (
    DailyMenu,
    DailyMenuItem,
    DailyMenuStatus,
    MenuItem,
)
from app.modules.orders.models import Order, OrderStatus, OrderType
from app.modules.users.models import Role, User
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
)


async def _get_manager_user(db: AsyncSession) -> User:
    """Fetch the manager user from the DB (created by conftest fixture)."""
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_MANAGER))
    return result.scalar_one()


def _days(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


# ===================================================================
# Copy Previous Day's Menu
# ===================================================================


@pytest.mark.asyncio
async def test_copy_daily_menu_creates_draft_with_metadata(admin_client: AsyncClient, db):
    """Admin copies a published source menu into a free target date.

    The copy must: (a) create a new DRAFT on the target date, (b) carry
    over junction metadata (special_price, display_order, notes,
    is_available_today), (c) leave the source menu untouched, and
    (d) surface dietary/allergen metadata via the copied items.
    """
    caf = await create_test_cafeteria(db)
    src_menu = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    item_a = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Copy Item A")
    item_b = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Copy Item B")
    db.add(
        DailyMenuItem(
            daily_menu_id=src_menu.id,
            menu_item_id=item_a.id,
            special_price=24500,
            is_available_today=True,
            display_order=2,
            notes="Phase 56 meta note",
        )
    )
    db.add(
        DailyMenuItem(
            daily_menu_id=src_menu.id,
            menu_item_id=item_b.id,
            special_price=None,
            is_available_today=False,
            display_order=0,
            notes=None,
        )
    )
    # Dietary/allergen metadata on item A (canonical JSON arrays).
    item_a.dietary_info = '["vegetarian","halal"]'
    item_a.allergens = '["milk","wheat"]'
    await db.flush()

    resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["menu_date"] == _days(1)
    assert data["status"] == "draft"
    assert len(data["items"]) == 2

    by_id = {i["menu_item_id"]: i for i in data["items"]}
    assert by_id[item_a.id]["special_price"] == 24500
    assert by_id[item_a.id]["display_order"] == 2
    assert by_id[item_a.id]["notes"] == "Phase 56 meta note"
    assert by_id[item_a.id]["is_available_today"] is True
    assert by_id[item_b.id]["special_price"] is None
    assert by_id[item_b.id]["is_available_today"] is False

    # Dietary/allergen metadata is served through the copied junction item.
    assert by_id[item_a.id]["menu_item"]["dietary_info"] == '["vegetarian","halal"]'
    assert by_id[item_a.id]["menu_item"]["allergens"] == '["milk","wheat"]'

    # Source menu untouched: still published, still exactly 2 items.
    src_rows = await db.execute(
        select(DailyMenuItem).where(DailyMenuItem.daily_menu_id == src_menu.id)
    )
    assert len(src_rows.scalars().all()) == 2
    src_status = await db.execute(select(DailyMenu).where(DailyMenu.id == src_menu.id))
    assert src_status.scalar_one().status == DailyMenuStatus.PUBLISHED


@pytest.mark.asyncio
async def test_copy_daily_menu_skips_inactive_items(admin_client: AsyncClient, db):
    """Inactive catalog items must not leak into the copied draft."""
    caf = await create_test_cafeteria(db)
    src_menu = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    active_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Active")
    inactive_item = await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Phase 56 Inactive", is_available=False
    )
    inactive_item.is_active = False
    db.add(DailyMenuItem(daily_menu_id=src_menu.id, menu_item_id=active_item.id))
    db.add(DailyMenuItem(daily_menu_id=src_menu.id, menu_item_id=inactive_item.id))
    await db.flush()

    resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["menu_item_id"] == active_item.id


@pytest.mark.asyncio
async def test_copy_daily_menu_target_published_conflict(admin_client: AsyncClient, db):
    """Copying onto a date with a PUBLISHED menu → explicit 409, no overwrite."""
    caf = await create_test_cafeteria(db)
    src = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    src_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Src")
    db.add(DailyMenuItem(daily_menu_id=src.id, menu_item_id=src_item.id))
    target = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=1),
        status=DailyMenuStatus.PUBLISHED,
    )
    target_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Target")
    db.add(DailyMenuItem(daily_menu_id=target.id, menu_item_id=target_item.id))
    await db.flush()

    resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 409, resp.text
    assert "PUBLISHED" in resp.json()["detail"]

    # Target menu unchanged — still published with its own single item.
    target_rows = await db.execute(
        select(DailyMenuItem).where(DailyMenuItem.daily_menu_id == target.id)
    )
    rows = target_rows.scalars().all()
    assert len(rows) == 1
    assert rows[0].menu_item_id == target_item.id


@pytest.mark.asyncio
async def test_copy_daily_menu_target_draft_conflict(admin_client: AsyncClient, db):
    """Copying onto a date with an existing DRAFT → explicit 409, no overwrite."""
    caf = await create_test_cafeteria(db)
    src = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    src_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Src2")
    db.add(DailyMenuItem(daily_menu_id=src.id, menu_item_id=src_item.id))
    await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=1),
        status=DailyMenuStatus.DRAFT,
    )
    await db.flush()

    resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 409, resp.text
    assert "DRAFT" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_copy_daily_menu_missing_source_404(admin_client: AsyncClient, db):
    """Copy from a date with no menu → 404 (explicit, not silent empty draft)."""
    caf = await create_test_cafeteria(db)
    resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-30), "target_date": _days(1)},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_copy_daily_menu_same_date_rejected(admin_client: AsyncClient, db):
    """Source == target → 400 validation error."""
    caf = await create_test_cafeteria(db)
    src = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    src_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Src3")
    db.add(DailyMenuItem(daily_menu_id=src.id, menu_item_id=src_item.id))
    await db.flush()

    resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(-1)},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_copy_daily_menu_manager_assigned_ok(manager_client: AsyncClient, db):
    """Manager assigned to the cafeteria can copy."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    src = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    src_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Src4")
    db.add(DailyMenuItem(daily_menu_id=src.id, menu_item_id=src_item.id))
    await db.flush()

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_copy_daily_menu_manager_unassigned_forbidden(manager_client: AsyncClient, db):
    """Manager not assigned to the cafeteria → 403 (write scope)."""
    caf = await create_test_cafeteria(db)
    src = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-1),
        status=DailyMenuStatus.PUBLISHED,
    )
    src_item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Src5")
    db.add(DailyMenuItem(daily_menu_id=src.id, menu_item_id=src_item.id))
    await db.flush()

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_copy_daily_menu_staff_forbidden(staff_client: AsyncClient, db):
    """Cafeteria staff cannot copy daily menus (manager/admin write scope)."""
    caf = await create_test_cafeteria(db)
    resp = await staff_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_copy_daily_menu_student_forbidden(student_client: AsyncClient, db):
    """Students cannot copy daily menus."""
    caf = await create_test_cafeteria(db)
    resp = await student_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/copy",
        json={"source_date": _days(-1), "target_date": _days(1)},
    )
    assert resp.status_code == 403, resp.text


# ===================================================================
# Menu Item DELETE (soft-delete, admin only)
# ===================================================================


@pytest.mark.asyncio
async def test_delete_menu_item_soft_deletes(admin_client: AsyncClient, db):
    """Admin delete soft-deletes: item flips inactive/unavailable, stays in DB.

    Historical references (daily_menu_items junction rows, inventory rows)
    must remain — delete never hard-deletes and never rewrites history.
    """
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Delete Me")
    menu = await create_test_daily_menu(
        db,
        cafeteria_id=caf.id,
        menu_date=date.today() + timedelta(days=-2),
        status=DailyMenuStatus.PUBLISHED,
    )
    db.add(DailyMenuItem(daily_menu_id=menu.id, menu_item_id=item.id))
    db.add(
        InventoryItem(
            cafeteria_id=caf.id,
            menu_item_id=item.id,
            quantity=25,
            unit="portions",
            low_threshold=10,
        )
    )
    await db.flush()
    item_id = item.id
    menu_id = menu.id

    resp = await admin_client.delete(f"/api/v1/cafeterias/{caf.id}/menu-items/{item_id}")
    assert resp.status_code == 204, resp.text

    # Row remains (soft delete), flipped inactive + unavailable.
    # populate_existing: the app session mutated the row; the test session's
    # identity map must be refreshed (Phase 55 lesson).
    row = (
        await db.execute(
            select(MenuItem)
            .where(MenuItem.id == item_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row.is_active is False
    assert row.is_available is False

    # Junction + inventory rows remain intact.
    jrows = (
        await db.execute(select(DailyMenuItem).where(DailyMenuItem.daily_menu_id == menu_id))
    ).scalars().all()
    assert len(jrows) == 1
    assert jrows[0].menu_item_id == item_id
    inv_rows = (
        await db.execute(select(InventoryItem).where(InventoryItem.menu_item_id == item_id))
    ).scalars().all()
    assert len(inv_rows) == 1

    # Item no longer listed as active catalog content via API.
    resp = await admin_client.get(f"/api/v1/cafeterias/{caf.id}/menu-items/")
    assert resp.status_code == 200
    listed = [i["id"] for i in resp.json()["items"] if i.get("is_active")]
    assert item_id not in listed


@pytest.mark.asyncio
async def test_delete_menu_item_manager_forbidden(manager_client: AsyncClient, db):
    """Menu item DELETE is admin-only (RequireRole UNIVERSITY_ADMIN)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Keep")
    await db.flush()

    resp = await manager_client.delete(f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}")
    assert resp.status_code == 403, resp.text

    row = (await db.execute(select(MenuItem).where(MenuItem.id == item.id))).scalar_one()
    assert row.is_active is True


@pytest.mark.asyncio
async def test_delete_menu_item_student_forbidden(student_client: AsyncClient, db):
    """Students cannot delete menu items."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Keep2")
    await db.flush()

    resp = await student_client.delete(f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}")
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_delete_menu_item_not_found(admin_client: AsyncClient, db):
    """Deleting a nonexistent menu item → 404."""
    caf = await create_test_cafeteria(db)
    resp = await admin_client.delete(
        f"/api/v1/cafeterias/{caf.id}/menu-items/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


# ===================================================================
# Inventory creation — scope & validation
# ===================================================================


@pytest.mark.asyncio
async def test_inventory_create_wrong_cafeteria_forbidden(manager_client: AsyncClient, db):
    """Manager assigned to A cannot create inventory in A for B's menu item.

    The router verifies the menu item belongs to the path cafeteria → 403.
    """
    caf_a = await create_test_cafeteria(db, name="Phase 56 Caf A")
    caf_b = await create_test_cafeteria(db, name="Phase 56 Caf B")
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf_a.id)
    foreign_item = await create_test_menu_item(
        db, cafeteria_id=caf_b.id, name="Phase 56 Foreign"
    )
    await db.flush()

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf_a.id}/inventory/",
        json={"menu_item_id": foreign_item.id, "quantity": 5, "unit": "portions"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_inventory_create_negative_quantity_422(manager_client: AsyncClient, db):
    """Negative quantity → 422 (pydantic ge=0)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Qty")
    await db.flush()

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/",
        json={"menu_item_id": item.id, "quantity": -5, "unit": "portions"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_inventory_create_student_forbidden(student_client: AsyncClient, db):
    """Students cannot create inventory records."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Stud")
    await db.flush()

    resp = await student_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/",
        json={"menu_item_id": item.id, "quantity": 5, "unit": "portions"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_inventory_create_manager_ok_with_valid_record(
    manager_client: AsyncClient, db
):
    """Manager (assigned) can create an inventory record — UI path works."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Phase 56 Inv")
    await db.flush()

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/inventory/",
        json={
            "menu_item_id": item.id,
            "quantity": 42,
            "unit": "portions",
            "low_threshold": 8,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["quantity"] == 42
    assert data["unit"] == "portions"
    assert data["low_threshold"] == 8
    assert data["is_low"] is False


# ===================================================================
# Inactive cafeteria filtering
# ===================================================================


@pytest.mark.asyncio
async def test_cafeterias_is_active_filter_excludes_inactive(admin_client: AsyncClient, db):
    """GET /cafeterias?is_active=true excludes inactive cafeterias."""
    active = await create_test_cafeteria(db, name="Phase 56 Active Caf", is_active=True)
    await create_test_cafeteria(db, name="Phase 56 Inactive Caf", is_active=False)
    await db.flush()

    resp = await admin_client.get("/api/v1/cafeterias/?is_active=true")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    ids = [c["id"] for c in data["cafeterias"]]
    assert active.id in ids
    assert all(c["is_active"] for c in data["cafeterias"])


@pytest.mark.asyncio
async def test_cafeterias_default_returns_all_for_admin(admin_client: AsyncClient, db):
    """Unfiltered GET /cafeterias (admin) still returns inactive cafeterias."""
    active = await create_test_cafeteria(db, name="Phase 56 Active2", is_active=True)
    inactive = await create_test_cafeteria(db, name="Phase 56 Inactive2", is_active=False)
    await db.flush()

    resp = await admin_client.get("/api/v1/cafeterias/")
    assert resp.status_code == 200, resp.text
    ids = [c["id"] for c in resp.json()["cafeterias"]]
    assert active.id in ids
    assert inactive.id in ids


@pytest.mark.asyncio
async def test_inactive_cafeteria_admin_visibility_preserved(admin_client: AsyncClient, db):
    """Admin can still view + update an inactive cafeteria (management)."""
    caf = await create_test_cafeteria(db, name="Phase 56 Inactive3", is_active=False)
    await db.flush()

    resp = await admin_client.get(f"/api/v1/cafeterias/{caf.id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False

    resp = await admin_client.put(
        f"/api/v1/cafeterias/{caf.id}",
        json={"description": "Phase 56 inactive probe — admin-managed"},
    )
    assert resp.status_code == 200, resp.text
    assert "Phase 56 inactive probe" in resp.json()["description"]


@pytest.mark.asyncio
async def test_historical_records_survive_inactive_cafeteria(
    admin_client: AsyncClient, db, student_user: User
):
    """Historical records for an inactive cafeteria remain intact + visible.

    The cafeteria is made inactive AFTER an order exists; detail view and
    the order row must keep working for admin historical visibility.
    """
    caf = await create_test_cafeteria(db, name="Phase 56 Hist Caf")
    order = Order(
        cafeteria_id=caf.id,
        user_id=student_user.id,
        order_number=900056,
        order_type=OrderType.IMMEDIATE,
        payment_method="cash",
        status=OrderStatus.COMPLETED,
        total_amount=10000,
        order_date=date.today(),
    )
    db.add(order)
    await db.flush()
    order_id = order.id

    # Deactivate AFTER the historical record exists.
    caf.is_active = False
    await db.flush()

    # Cafeteria detail still works for admin.
    resp = await admin_client.get(f"/api/v1/cafeterias/{caf.id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # The historical order row is untouched.
    order_row = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one()
    assert order_row.status == OrderStatus.COMPLETED


# ===================================================================
# Dietary / allergen metadata
# ===================================================================


@pytest.mark.asyncio
async def test_menu_item_dietary_allergen_roundtrip(manager_client: AsyncClient, db):
    """Create + update menu items with dietary/allergen JSON; API serves them."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)

    resp = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/menu-items/",
        json={
            "name": "Phase 56 Dietary Item",
            "category": "salad",
            "price": 30000,
            "dietary_info": '["vegetarian","gluten_free"]',
            "allergens": '["milk"]',
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["dietary_info"] == '["vegetarian","gluten_free"]'
    assert data["allergens"] == '["milk"]'

    resp = await manager_client.put(
        f"/api/v1/cafeterias/{caf.id}/menu-items/{data['id']}",
        json={"dietary_info": '["vegan"]', "allergens": '["peanuts","soy"]'},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dietary_info"] == '["vegan"]'
    assert data["allergens"] == '["peanuts","soy"]'
