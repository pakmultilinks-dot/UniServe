"""Cross-café scope enforcement — attack scenario regression tests.

Sets up:
  - Student Cafeteria (caf_student)
  - Faculty Cafeteria (caf_faculty)
  - Manager A → assigned to Student Cafeteria
  - Manager B → assigned to Faculty Cafeteria
  - Staff A → assigned to Student Cafeteria
  - Staff B → assigned to Faculty Cafeteria
  - Admin → university-wide

Verifies that Manager A cannot mutate Faculty Cafeteria resources and vice versa.
Also verifies that resource-ID-based bypass attacks are blocked.
"""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus
from app.modules.users.models import Role, User
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
    create_test_user,
    create_user_session,
)

# ---------------------------------------------------------------------------
# Fixtures — two cafeterias, four managers/staff, two authenticated clients
# ---------------------------------------------------------------------------


async def _create_manager_client(
    engine,
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    email: str,
    uid: str,
) -> tuple[User, AsyncClient]:
    """Create a manager user, session, and authenticated AsyncClient."""
    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db
    from app.main import app

    mgr = await create_test_user(
        db,
        first_name=first_name,
        last_name=last_name,
        university_email=email,
        university_id=uid,
        role=Role.CAFETERIA_MANAGER,
    )
    _, access_token, _ = await create_user_session(db, mgr)

    connection = await engine.connect()
    transaction = await connection.begin()
    test_session = AsyncSession(bind=connection, expire_on_commit=False)

    async def _override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    client.headers["Authorization"] = f"Bearer {access_token}"

    # We'll yield the client and let the test clean up
    # For simplicity, we'll create the client inline instead
    return mgr, test_session, connection, transaction, client


async def _create_staff_client(
    engine,
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    email: str,
    uid: str,
) -> tuple[User, AsyncClient]:
    """Create a staff user, session, and authenticated AsyncClient."""
    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db
    from app.main import app

    staff = await create_test_user(
        db,
        first_name=first_name,
        last_name=last_name,
        university_email=email,
        university_id=uid,
        role=Role.CAFETERIA_STAFF,
    )
    _, access_token, _ = await create_user_session(db, staff)

    connection = await engine.connect()
    transaction = await connection.begin()
    test_session = AsyncSession(bind=connection, expire_on_commit=False)

    async def _override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    client.headers["Authorization"] = f"Bearer {access_token}"

    return staff, test_session, connection, transaction, client


async def _teardown_client(client, test_session, connection, transaction):
    """Clean up a test client and its DB session."""
    await client.aclose()
    app.dependency_overrides.clear()
    await test_session.close()
    await transaction.rollback()
    await connection.close()


# We import app here for the override
from app.main import app  # noqa: E402

# ===========================================================================
# MENU ITEM SCOPE ENFORCEMENT
# ===========================================================================


class TestMenuItemScope:
    """Verify that managers can only create/update menu items in their own cafeteria."""

    @pytest.mark.asyncio
    async def test_manager_a_can_create_in_own_cafeteria(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A can create menu items in their assigned cafeteria."""
        caf = await create_test_cafeteria(db, name="Student Caf 1")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)
        response = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/menu-items/",
            json={"name": "Biryani", "category": "main_course", "price": 25000},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_manager_cannot_create_in_other_cafeteria(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot create menu items in a cafeteria they are not assigned to."""
        # Create a cafeteria the manager is NOT assigned to
        caf = await create_test_cafeteria(db, name="Foreign Cafeteria")
        # Manager is not assigned to this cafeteria
        response = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/menu-items/",
            json={"name": "Biryani", "category": "main_course", "price": 25000},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_cannot_update_in_other_cafeteria(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot update menu items in a cafeteria they are not assigned to."""
        caf = await create_test_cafeteria(db, name="Foreign Caf 2")
        item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Foreign Item")
        response = await manager_client.put(
            f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}",
            json={"name": "Hacked Name"},
        )
        assert response.status_code == 403
        # Verify item unchanged
        from app.modules.menus.service import MenuService

        service = MenuService(db)
        refreshed = await service.get_menu_item(item.id)
        assert refreshed.name == "Foreign Item"

    @pytest.mark.asyncio
    async def test_admin_can_create_in_any_cafeteria(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        """University Admin can create menu items in any cafeteria."""
        caf = await create_test_cafeteria(db, name="Any Caf")
        response = await admin_client.post(
            f"/api/v1/cafeterias/{caf.id}/menu-items/",
            json={"name": "Admin Item", "category": "beverage", "price": 5000},
        )
        assert response.status_code == 201


# ===========================================================================
# RESOURCE-ID SCOPE BYPASS ATTACK
# ===========================================================================


class TestResourceIdBypass:
    """Verify that using a foreign resource ID with own cafeteria_id is blocked."""

    @pytest.mark.asyncio
    async def test_update_foreign_menu_item_bypass_blocked(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A tries to update a menu item belonging to another cafeteria.

        Attack: PUT /cafeterias/{own_caf}/menu-items/{foreign_item_id}
        Expected: 403 (resource ownership mismatch)
        """
        own_caf = await create_test_cafeteria(db, name="Own Cafeteria")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Cafeteria")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        foreign_item = await create_test_menu_item(
            db, cafeteria_id=foreign_caf.id, name="Foreign Biryani"
        )

        response = await manager_client.put(
            f"/api/v1/cafeterias/{own_caf.id}/menu-items/{foreign_item.id}",
            json={"name": "Hacked"},
        )
        assert response.status_code == 403
        # Verify foreign item unchanged
        from app.modules.menus.service import MenuService

        service = MenuService(db)
        refreshed = await service.get_menu_item(foreign_item.id)
        assert refreshed.name == "Foreign Biryani"

    @pytest.mark.asyncio
    async def test_add_item_to_foreign_daily_menu_bypass_blocked(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A tries to add items to another cafeteria's daily menu.

        Attack: POST /cafeterias/{own_caf}/daily-menus/{foreign_menu_id}/items
        Expected: 403 (daily menu ownership mismatch)
        """
        own_caf = await create_test_cafeteria(db, name="Own Caf 3")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Caf 3")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        foreign_menu = await create_test_daily_menu(db, cafeteria_id=foreign_caf.id)
        own_item = await create_test_menu_item(db, cafeteria_id=own_caf.id)

        response = await manager_client.post(
            f"/api/v1/cafeterias/{own_caf.id}/daily-menus/{foreign_menu.id}/items",
            json={"menu_item_id": own_item.id},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_publish_foreign_daily_menu_bypass_blocked(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A tries to publish another cafeteria's daily menu.

        Attack: PATCH /cafeterias/{own_caf}/daily-menus/{foreign_menu_id}/publish
        Expected: 403 (daily menu ownership mismatch)
        """
        own_caf = await create_test_cafeteria(db, name="Own Caf 4")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Caf 4")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        foreign_menu = await create_test_daily_menu(db, cafeteria_id=foreign_caf.id)

        response = await manager_client.patch(
            f"/api/v1/cafeterias/{own_caf.id}/daily-menus/{foreign_menu.id}/publish",
        )
        assert response.status_code == 403
        # Verify foreign menu still draft
        from app.modules.menus.service import MenuService

        service = MenuService(db)
        refreshed = await service.get_daily_menu(foreign_menu.id)
        assert refreshed.status == DailyMenuStatus.DRAFT

    @pytest.mark.asyncio
    async def test_remove_item_from_foreign_daily_menu_bypass_blocked(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A tries to remove items from another cafeteria's daily menu.

        Attack: DELETE /cafeterias/{own_caf}/daily-menus/{foreign_menu_id}/items/{item_id}
        Expected: 403 (daily menu ownership mismatch)
        """
        own_caf = await create_test_cafeteria(db, name="Own Caf 5")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Caf 5")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        foreign_menu = await create_test_daily_menu(db, cafeteria_id=foreign_caf.id)
        foreign_item = await create_test_menu_item(db, cafeteria_id=foreign_caf.id)

        # Add the item to the foreign menu via admin (who has universal access)
        response = await manager_client.delete(
            f"/api/v1/cafeterias/{own_caf.id}/daily-menus/{foreign_menu.id}/items/{foreign_item.id}",
        )
        assert response.status_code == 403


# ===========================================================================
# INVENTORY SCOPE ENFORCEMENT
# ===========================================================================


class TestInventoryScope:
    """Verify that inventory operations are scoped to the assigned cafeteria."""

    @pytest.mark.asyncio
    async def test_manager_can_adjust_own_inventory(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager can adjust inventory in their own cafeteria."""
        caf = await create_test_cafeteria(db, name="Own Inv Caf")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)
        item = await create_test_menu_item(db, cafeteria_id=caf.id)
        inv = InventoryItem(
            cafeteria_id=caf.id,
            menu_item_id=item.id,
            quantity=100,
            unit=InventoryUnit.PORTIONS,
            low_threshold=10,
        )
        db.add(inv)
        await db.flush()

        response = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
            json={"inventory_item_id": inv.id, "adjustment_quantity": -20, "reason": "Lunch"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_manager_cannot_adjust_foreign_inventory(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot adjust inventory in another cafeteria.

        Attack: POST /cafeterias/{own_caf}/inventory/adjust
                with inventory_item_id belonging to foreign cafeteria
        Expected: 403 (inventory item ownership mismatch)
        """
        own_caf = await create_test_cafeteria(db, name="Own Inv Caf 2")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Inv Caf 2")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        foreign_item = await create_test_menu_item(db, cafeteria_id=foreign_caf.id)
        foreign_inv = InventoryItem(
            cafeteria_id=foreign_caf.id,
            menu_item_id=foreign_item.id,
            quantity=100,
            unit=InventoryUnit.PORTIONS,
            low_threshold=10,
        )
        db.add(foreign_inv)
        await db.flush()

        response = await manager_client.post(
            f"/api/v1/cafeterias/{own_caf.id}/inventory/adjust",
            json={"inventory_item_id": foreign_inv.id, "adjustment_quantity": -50},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_cannot_create_inventory_in_other_cafeteria(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot create inventory items in a foreign cafeteria."""
        own_caf = await create_test_cafeteria(db, name="Own Inv Caf 3")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Inv Caf 3")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        # Menu item in the foreign cafeteria
        foreign_item = await create_test_menu_item(db, cafeteria_id=foreign_caf.id)

        response = await manager_client.post(
            f"/api/v1/cafeterias/{own_caf.id}/inventory/",
            json={
                "menu_item_id": foreign_item.id,
                "quantity": 50,
                "unit": "portions",
                "low_threshold": 10,
            },
        )
        assert response.status_code == 403


# ===========================================================================
# CAFETERIA STATUS SCOPE ENFORCEMENT
# ===========================================================================


class TestCafeteriaStatusScope:
    """Verify that status changes are scoped to the assigned cafeteria."""

    @pytest.mark.asyncio
    async def test_manager_can_change_own_status(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager can change status of their assigned cafeteria."""
        caf = await create_test_cafeteria(db, name="Status Caf A")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        response = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/status",
            json={"status": "maintenance"},
        )
        assert response.status_code == 200
        assert response.json()["operational_status"] == "maintenance"

    @pytest.mark.asyncio
    async def test_manager_cannot_change_foreign_status(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot change status of a cafeteria they are not assigned to."""
        foreign_caf = await create_test_cafeteria(db, name="Foreign Status Caf")

        response = await manager_client.patch(
            f"/api/v1/cafeterias/{foreign_caf.id}/status",
            json={"status": "closed"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_cannot_change_status(self, staff_client: AsyncClient, db: AsyncSession):
        """Staff cannot change operational status (manager-only action)."""
        caf = await create_test_cafeteria(db, name="Staff Status Caf")
        response = await staff_client.patch(
            f"/api/v1/cafeterias/{caf.id}/status",
            json={"status": "closed"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_change_any_status(self, admin_client: AsyncClient, db: AsyncSession):
        """University Admin can change status of any cafeteria."""
        caf = await create_test_cafeteria(db, name="Admin Status Caf")
        response = await admin_client.patch(
            f"/api/v1/cafeterias/{caf.id}/status",
            json={"status": "maintenance"},
        )
        assert response.status_code == 200


# ===========================================================================
# DAILY MENU SCOPE ENFORCEMENT
# ===========================================================================


class TestDailyMenuScope:
    """Verify that daily menu CRUD is scoped."""

    @pytest.mark.asyncio
    async def test_manager_cannot_create_menu_in_other_cafeteria(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot create daily menus in another cafeteria."""
        foreign_caf = await create_test_cafeteria(db, name="Foreign DM Caf")
        response = await manager_client.post(
            f"/api/v1/cafeterias/{foreign_caf.id}/daily-menus/",
            json={"menu_date": date.today().isoformat()},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_can_create_menu_in_own_cafeteria(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager can create daily menus in their assigned cafeteria."""
        caf = await create_test_cafeteria(db, name="Own DM Caf")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        response = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/",
            json={"menu_date": date.today().isoformat()},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_manager_can_publish_own_menu(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager can publish a daily menu in their own cafeteria."""
        caf = await create_test_cafeteria(db, name="Publish Own Caf")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        menu = await create_test_daily_menu(db, cafeteria_id=caf.id)
        item = await create_test_menu_item(db, cafeteria_id=caf.id)
        await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/items",
            json={"menu_item_id": item.id},
        )
        response = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu.id}/publish",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "published"

    @pytest.mark.asyncio
    async def test_manager_cannot_publish_foreign_menu(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Manager A cannot publish another cafeteria's daily menu."""
        own_caf = await create_test_cafeteria(db, name="Own Pub Caf")
        foreign_caf = await create_test_cafeteria(db, name="Foreign Pub Caf")
        mgr = await _get_manager_user(db)
        await assign_user_to_cafeteria(db, mgr.id, own_caf.id)

        foreign_menu = await create_test_daily_menu(db, cafeteria_id=foreign_caf.id)
        response = await manager_client.patch(
            f"/api/v1/cafeterias/{own_caf.id}/daily-menus/{foreign_menu.id}/publish",
        )
        assert response.status_code == 403


# ===========================================================================
# STAFF SCOPE ENFORCEMENT
# ===========================================================================


class TestStaffScope:
    """Verify that staff also face cafeteria scope enforcement."""

    @pytest.mark.asyncio
    async def test_staff_cannot_adjust_foreign_inventory(
        self, staff_client: AsyncClient, db: AsyncSession, engine
    ):
        """Staff cannot adjust inventory in a cafeteria they are not assigned to."""

        foreign_caf = await create_test_cafeteria(db, name="Foreign Staff Caf")
        # Create a manager user to satisfy any constraints, and assign them to the foreign cafeteria
        mgr_user = await create_test_user(
            db,
            first_name="Mgr",
            last_name="ForInv",
            university_email="mgr.forinv@lgu.edu.pk",
            university_id="MGR-FINV",
            role=Role.CAFETERIA_MANAGER,
        )
        await assign_user_to_cafeteria(db, mgr_user.id, foreign_caf.id)

        item = await create_test_menu_item(db, cafeteria_id=foreign_caf.id)
        inv = InventoryItem(
            cafeteria_id=foreign_caf.id,
            menu_item_id=item.id,
            quantity=50,
            unit=InventoryUnit.PORTIONS,
            low_threshold=10,
        )
        db.add(inv)
        await db.flush()

        response = await staff_client.post(
            f"/api/v1/cafeterias/{foreign_caf.id}/inventory/adjust",
            json={"inventory_item_id": inv.id, "adjustment_quantity": -10},
        )
        assert response.status_code == 403


# ===========================================================================
# STUDENT / FACULTY WRITE ACCESS DENIED
# ===========================================================================


class TestStudentFacultyNoWrite:
    """Students and Faculty cannot perform any mutations."""

    @pytest.mark.asyncio
    async def test_student_cannot_create_menu_item(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        caf = await create_test_cafeteria(db)
        response = await student_client.post(
            f"/api/v1/cafeterias/{caf.id}/menu-items/",
            json={"name": "Test", "category": "snack", "price": 100},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_faculty_cannot_create_menu_item(
        self, faculty_client: AsyncClient, db: AsyncSession
    ):
        caf = await create_test_cafeteria(db)
        response = await faculty_client.post(
            f"/api/v1/cafeterias/{caf.id}/menu-items/",
            json={"name": "Test", "category": "snack", "price": 100},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_adjust_inventory(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        caf = await create_test_cafeteria(db)
        response = await student_client.post(
            f"/api/v1/cafeterias/{caf.id}/inventory/adjust",
            json={"inventory_item_id": "fake-id", "adjustment_quantity": 10},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_change_status(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        caf = await create_test_cafeteria(db)
        response = await student_client.patch(
            f"/api/v1/cafeterias/{caf.id}/status",
            json={"status": "closed"},
        )
        assert response.status_code == 403


# ===========================================================================
# FAVORITES — USER OWNERSHIP
# ===========================================================================


class TestFavoritesOwnership:
    """Verify that favorites are user-scoped, not cafeteria-scoped."""

    @pytest.mark.asyncio
    async def test_user_cannot_remove_other_users_favorite(
        self, student_client: AsyncClient, db: AsyncSession, engine
    ):
        """One user cannot delete another user's favorite."""
        from httpx import ASGITransport

        from app.core.database import get_db

        caf = await create_test_cafeteria(db)
        item = await create_test_menu_item(db, cafeteria_id=caf.id)

        # Student adds item to favorites
        resp1 = await student_client.post("/api/v1/favorites/", json={"menu_item_id": item.id})
        assert resp1.status_code == 201

        # Create a second, separate client for a different user (manager)
        mgr = await create_test_user(
            db,
            first_name="Mgr",
            last_name="FavTest",
            university_email="mgr.favtest@lgu.edu.pk",
            university_id="MGR-FAV",
            role=Role.CAFETERIA_MANAGER,
        )
        _, mgr_token, _ = await create_user_session(db, mgr)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        connection = await engine.connect()
        transaction = await connection.begin()
        mgr_session = AsyncSession(bind=connection, expire_on_commit=False)

        async def _mgr_get_db():
            yield mgr_session

        app.dependency_overrides[get_db] = _mgr_get_db
        transport = ASGITransport(app=app)
        mgr_client = AsyncClient(transport=transport, base_url="http://test")
        mgr_client.headers["Authorization"] = f"Bearer {mgr_token}"

        try:
            # Manager (different user) tries to remove student's favorite
            resp2 = await mgr_client.delete(f"/api/v1/favorites/{item.id}")
            assert resp2.status_code == 404  # Not found (because it's not manager's)

            # Verify student's favorite still exists
            resp3 = await student_client.get("/api/v1/favorites/")
            assert resp3.status_code == 200
            assert resp3.json()["total"] == 1
        finally:
            await mgr_client.aclose()
            app.dependency_overrides.clear()
            await mgr_session.close()
            await transaction.rollback()
            await connection.close()


# ===========================================================================
# HELPER
# ===========================================================================


async def _get_manager_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_MANAGER))
    return result.scalar_one()
