"""Tests for menu management endpoints."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.menus.models import MenuCategory
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


# ===================================================================
# Menu Items CRUD
# ===================================================================


@pytest.mark.asyncio
async def test_create_menu_item(manager_client: AsyncClient, db):
    """Manager can create a menu item."""
    caf = await create_test_cafeteria(db)
    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/menu-items/",
        json={
            "name": "Chicken Biryani",
            "category": "main_course",
            "price": 25000,
            "description": "Delicious biryani",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Chicken Biryani"
    assert data["category"] == "main_course"
    assert data["price"] == 25000
    assert data["cafeteria_id"] == caf.id
    assert data["is_available"] is True
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_menu_item_student_forbidden(student_client: AsyncClient, db):
    """Students cannot create menu items."""
    caf = await create_test_cafeteria(db)
    response = await student_client.post(
        f"/api/v1/cafeterias/{caf.id}/menu-items/",
        json={"name": "Test", "category": "snack", "price": 100},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_menu_items(manager_client: AsyncClient, db):
    """List menu items for a cafeteria (scoped access)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Item A", category=MenuCategory.MAIN_COURSE
    )
    await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Item B", category=MenuCategory.BEVERAGE
    )
    response = await manager_client.get(f"/api/v1/cafeterias/{caf.id}/menu-items/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_menu_items_filter_category(manager_client: AsyncClient, db):
    """Filter menu items by category."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Biryani", category=MenuCategory.MAIN_COURSE
    )
    await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Cola", category=MenuCategory.BEVERAGE
    )
    response = await manager_client.get(
        f"/api/v1/cafeterias/{caf.id}/menu-items/?category=beverage"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Cola"


@pytest.mark.asyncio
async def test_get_menu_item(manager_client: AsyncClient, db):
    """Get a specific menu item (scoped access)."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Seekh Kebab")
    response = await manager_client.get(f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Seekh Kebab"


@pytest.mark.asyncio
async def test_update_menu_item(manager_client: AsyncClient, db):
    """Manager can update a menu item."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Old Name")
    response = await manager_client.put(
        f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}",
        json={"name": "New Name", "price": 30000},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["price"] == 30000


@pytest.mark.asyncio
async def test_delete_menu_item_admin(admin_client: AsyncClient, db):
    """Admin can soft-delete a menu item."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    response = await admin_client.delete(f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_menu_item_manager_forbidden(manager_client: AsyncClient, db):
    """Managers cannot delete menu items (admin only)."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    response = await manager_client.delete(f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}")
    assert response.status_code == 403


# ===================================================================
# Daily Menus
# ===================================================================


@pytest.mark.asyncio
async def test_create_daily_menu(manager_client: AsyncClient, db):
    """Manager can create a daily menu draft."""
    caf = await create_test_cafeteria(db)
    today = date.today().isoformat()
    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/",
        json={"menu_date": today},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert data["menu_date"] == today
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_daily_menu_duplicate(manager_client: AsyncClient, db):
    """Cannot create two daily menus for the same cafeteria and date."""
    caf = await create_test_cafeteria(db)
    today = date.today()
    await create_test_daily_menu(db, cafeteria_id=caf.id, menu_date=today)
    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/",
        json={"menu_date": today.isoformat()},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_add_item_to_daily_menu(manager_client: AsyncClient, db):
    """Manager can add items to a daily menu draft."""
    caf = await create_test_cafeteria(db)
    menu = await create_test_daily_menu(db, cafeteria_id=caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    response = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/items",
        json={
            "menu_item_id": item.id,
            "special_price": 20000,
            "display_order": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["special_price"] == 20000


@pytest.mark.asyncio
async def test_publish_daily_menu(manager_client: AsyncClient, db):
    """Manager can publish a daily menu that has items."""
    caf = await create_test_cafeteria(db)
    menu = await create_test_daily_menu(db, cafeteria_id=caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    # Add an item first
    await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/items",
        json={"menu_item_id": item.id},
    )
    # Publish
    response = await manager_client.patch(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/publish",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] is not None


@pytest.mark.asyncio
async def test_publish_empty_menu_fails(manager_client: AsyncClient, db):
    """Cannot publish an empty daily menu."""
    caf = await create_test_cafeteria(db)
    menu = await create_test_daily_menu(db, cafeteria_id=caf.id)
    response = await manager_client.patch(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/publish",
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_remove_item_from_daily_menu(manager_client: AsyncClient, db):
    """Manager can remove items from a draft daily menu."""
    caf = await create_test_cafeteria(db)
    menu = await create_test_daily_menu(db, cafeteria_id=caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/items",
        json={"menu_item_id": item.id},
    )
    response = await manager_client.delete(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/items/{item.id}"
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0


@pytest.mark.asyncio
async def test_get_todays_menu(manager_client: AsyncClient, db):
    """Get today's published menu."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    menu = await create_test_daily_menu(db, cafeteria_id=caf.id, menu_date=date.today())
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/items",
        json={"menu_item_id": item.id},
    )
    await manager_client.patch(
        f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/publish",
    )
    response = await manager_client.get(f"/api/v1/cafeterias/{caf.id}/daily-menus/today")
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["status"] == "published"


@pytest.mark.asyncio
async def test_get_todays_menu_none_published(manager_client: AsyncClient, db):
    """Returns null if no menu is published for today."""
    caf = await create_test_cafeteria(db)
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    response = await manager_client.get(f"/api/v1/cafeterias/{caf.id}/daily-menus/today")
    assert response.status_code == 200
    assert response.json() is None


# ===================================================================
# Favorites
# ===================================================================


@pytest.mark.asyncio
async def test_add_favorite(student_client: AsyncClient, db):
    """Student can add a menu item to favorites."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    response = await student_client.post(
        "/api/v1/favorites/",
        json={"menu_item_id": item.id},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["menu_item_id"] == item.id


@pytest.mark.asyncio
async def test_add_favorite_duplicate(student_client: AsyncClient, db):
    """Cannot add the same item to favorites twice."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    await student_client.post("/api/v1/favorites/", json={"menu_item_id": item.id})
    response = await student_client.post("/api/v1/favorites/", json={"menu_item_id": item.id})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_favorites(student_client: AsyncClient, db):
    """List user's favorites."""
    caf = await create_test_cafeteria(db)
    item1 = await create_test_menu_item(db, cafeteria_id=caf.id, name="Item 1")
    item2 = await create_test_menu_item(db, cafeteria_id=caf.id, name="Item 2")
    await student_client.post("/api/v1/favorites/", json={"menu_item_id": item1.id})
    await student_client.post("/api/v1/favorites/", json={"menu_item_id": item2.id})
    response = await student_client.get("/api/v1/favorites/")
    assert response.status_code == 200
    assert response.json()["total"] == 2


@pytest.mark.asyncio
async def test_remove_favorite(student_client: AsyncClient, db):
    """Remove an item from favorites."""
    caf = await create_test_cafeteria(db)
    item = await create_test_menu_item(db, cafeteria_id=caf.id)
    await student_client.post("/api/v1/favorites/", json={"menu_item_id": item.id})
    response = await student_client.delete(f"/api/v1/favorites/{item.id}")
    assert response.status_code == 204
    # Verify removed
    list_response = await student_client.get("/api/v1/favorites/")
    assert list_response.json()["total"] == 0


# ===================================================================
# Menu Search
# ===================================================================


@pytest.mark.asyncio
async def test_search_menu_items(student_client: AsyncClient, db):
    """Search menu items by name."""
    caf = await create_test_cafeteria(db)
    await create_test_menu_item(db, cafeteria_id=caf.id, name="Chicken Biryani")
    await create_test_menu_item(db, cafeteria_id=caf.id, name="Beef Biryani")
    await create_test_menu_item(db, cafeteria_id=caf.id, name="Cola")
    response = await student_client.get("/api/v1/menu-search/?search=Biryani")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_search_menu_items_by_category(student_client: AsyncClient, db):
    """Search menu items by category."""
    caf = await create_test_cafeteria(db)
    await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Biryani", category=MenuCategory.MAIN_COURSE
    )
    await create_test_menu_item(
        db, cafeteria_id=caf.id, name="Cola", category=MenuCategory.BEVERAGE
    )
    response = await student_client.get("/api/v1/menu-search/?category=beverage")
    assert response.status_code == 200
    assert response.json()["total"] == 1
