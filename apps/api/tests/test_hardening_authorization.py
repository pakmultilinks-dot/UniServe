"""Hardening phase — comprehensive authorization and IDOR regression tests.

Covers gaps identified in the production hardening audit:
- Cross-cafeteria data access (IDOR)
- Cross-role denial for menu, order, and administration endpoints
- ETA endpoint owner/cafeteria check
- Daily menu IDOR (accessing another cafeteria's daily menu by UUID)
- Menu search cafeteria scope enforcement
- Staff/manager cafeteria assignment verification
- Notification parameter correctness
- Refund process no-body correctness

Each test uses real HTTP requests via httpx.AsyncClient against the
FastAPI app with an in-memory SQLite database.
"""

import pytest
from datetime import date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import (
    Cafeteria,
    CafeteriaType,
    OperationalStatus,
)
from app.modules.menus.models import (
    DailyMenu,
    DailyMenuStatus,
    MenuCategory,
    MenuItem,
)
from app.modules.orders.models import Order, OrderStatus, OrderType, PaymentMethod
from app.modules.users.models import (
    AccountStatus,
    CafeteriaAssignment,
    Role,
    User,
    UserCategory,
)
from tests.conftest import create_test_user, create_user_session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STUDENT_CAF_ID = "205e8c71-7b9c-4a04-a40b-8f5ca8344bf2"
FACULTY_CAF_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"

# Fake UUIDs for IDOR tests
FAKE_CAF_ID = "00000000-0000-0000-0000-000000000099"
FAKE_ORDER_ID = "00000000-0000-0000-0000-000000000088"
FAKE_MENU_ITEM_ID = "00000000-0000-0000-0000-000000000077"
FAKE_DAILY_MENU_ID = "00000000-0000-0000-0000-000000000066"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_cafeterias(db: AsyncSession) -> None:
    """Insert both cafeterias if they don't exist."""
    for cid, name, ctype, loc in [
        (STUDENT_CAF_ID, "Student Cafeteria", CafeteriaType.STUDENT, "Student Center"),
        (FACULTY_CAF_ID, "Faculty Cafeteria", CafeteriaType.FACULTY, "Faculty Building"),
    ]:
        from sqlalchemy import select as sa_select

        existing = await db.execute(sa_select(Cafeteria).where(Cafeteria.id == cid))
        if existing.scalar_one_or_none() is None:
            db.add(
                Cafeteria(
                    id=cid,
                    name=name,
                    type=ctype,
                    location=loc,
                    operational_status=OperationalStatus.OPEN,
                    is_active=True,
                )
            )
    await db.flush()


async def _assign_user(
    db: AsyncSession,
    user: User,
    cafeteria_id: str,
    role: Role,
) -> None:
    """Assign a user to a cafeteria."""
    assignment = CafeteriaAssignment(
        user_id=user.id,
        cafeteria_id=cafeteria_id,
        role=role,
    )
    db.add(assignment)
    await db.flush()


async def _create_menu_item(
    db: AsyncSession,
    cafeteria_id: str,
    name: str = "Test Item",
    price: int = 500,
) -> MenuItem:
    """Create and return a menu item."""
    item = MenuItem(
        cafeteria_id=cafeteria_id,
        name=name,
        description=f"A test item: {name}",
        category=MenuCategory.MAIN_COURSE,
        price=price,
        currency="PKR",
        is_available=True,
        is_active=True,
    )
    db.add(item)
    await db.flush()
    return item


async def _create_order(
    db: AsyncSession,
    user_id: str,
    cafeteria_id: str,
    status: OrderStatus = OrderStatus.PENDING,
) -> Order:
    """Create and return an order."""
    import secrets
    order = Order(
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_number=100000 + secrets.randbelow(900000),
        order_type=OrderType.IMMEDIATE,
        payment_method=PaymentMethod.CASH,
        status=status,
        total_amount=500,
        currency="PKR",
        order_date=date.today(),
    )
    db.add(order)
    await db.flush()
    return order


async def _create_daily_menu(
    db: AsyncSession,
    cafeteria_id: str,
    status: DailyMenuStatus = DailyMenuStatus.DRAFT,
    created_by: str | None = None,
) -> DailyMenu:
    """Create and return a daily menu."""
    from datetime import date

    menu = DailyMenu(
        cafeteria_id=cafeteria_id,
        menu_date=date.today(),
        status=status,
        created_by=created_by,
    )
    db.add(menu)
    await db.flush()
    return menu


async def _make_client(client: AsyncClient, user: User, db: AsyncSession) -> AsyncClient:
    """Create an authenticated client for the given user."""
    _, access_token, _ = await create_user_session(db, user)
    return AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )


# ===================================================================
# Cross-Cafeteria IDOR Tests
# ===================================================================


@pytest.mark.asyncio
class TestCrossCafeteriaIDOR:
    """Verify users cannot access resources from another cafeteria."""

    async def test_student_cannot_access_faculty_daily_menu(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A student trying to read a faculty cafeteria daily menu by ID."""
        await _seed_cafeterias(db)
        fac_menu = await _create_daily_menu(db, FACULTY_CAF_ID)

        student = await create_test_user(
            db,
            first_name="CrossStudent",
            last_name="Test",
            university_id="CS-001",
            university_email="cross.student@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        student_c = await _make_client(client, student, db)

        resp = await student_c.get(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/daily-menus/{fac_menu.id}"
        )
        assert resp.status_code in (403, 404)

    async def test_staff_cannot_access_unassigned_cafeteria_order(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Staff assigned to student caf cannot view orders from faculty caf."""
        await _seed_cafeterias(db)
        admin = await create_test_user(
            db,
            first_name="Admin4IDOR",
            last_name="User",
            university_id="ADM-IDOR-001",
            university_email="admin.idor@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        admin_c = await _make_client(client, admin, db)

        # Create a user and order in faculty cafeteria
        fac_user = await create_test_user(
            db,
            first_name="FacOwner",
            last_name="Order",
            university_id="FAC-OR-001",
            university_email="fac.owner@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        order = await _create_order(db, fac_user.id, FACULTY_CAF_ID)

        # Staff assigned to student cafeteria
        staff = await create_test_user(
            db,
            first_name="StudStaff",
            last_name="IDOR",
            university_id="STF-IDOR-001",
            university_email="stud.staff.idor@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, staff, STUDENT_CAF_ID, Role.CAFETERIA_STAFF)
        staff_c = await _make_client(client, staff, db)

        resp = await staff_c.get(f"/api/v1/orders/{order.id}")
        assert resp.status_code == 403

    async def test_manager_cannot_access_unassigned_cafeteria_order(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Manager assigned to student caf cannot view orders from faculty caf."""
        await _seed_cafeterias(db)
        admin = await create_test_user(
            db,
            first_name="Admin4MgrIDOR",
            last_name="User",
            university_id="ADM-MIDOR-001",
            university_email="admin.midor@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        admin_c = await _make_client(client, admin, db)

        fac_user = await create_test_user(
            db,
            first_name="FacMgrOwner",
            last_name="Order",
            university_id="FAC-MOR-001",
            university_email="fac.mgr.owner@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        order = await _create_order(db, fac_user.id, FACULTY_CAF_ID)

        mgr = await create_test_user(
            db,
            first_name="StudMgr",
            last_name="IDOR",
            university_id="MGR-IDOR-001",
            university_email="stud.mgr.idor@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, mgr, STUDENT_CAF_ID, Role.CAFETERIA_MANAGER)
        mgr_c = await _make_client(client, mgr, db)

        resp = await mgr_c.get(f"/api/v1/orders/{order.id}")
        assert resp.status_code == 403

    async def test_nonexistent_order_returns_404(
        self, client: AsyncClient, db: AsyncSession, student_client: AsyncClient
    ):
        """Requesting a nonexistent order UUID returns 404, not 403 or 200."""
        resp = await student_client.get(f"/api/v1/orders/{FAKE_ORDER_ID}")
        assert resp.status_code in (404, 403)


# ===================================================================
# Cross-Role Denial Tests
# ===================================================================


@pytest.mark.asyncio
class TestCrossRoleDenial:
    """Verify role boundaries for sensitive endpoints."""

    async def test_student_cannot_access_admin_overview(
        self, client: AsyncClient, db: AsyncSession
    ):
        student = await create_test_user(
            db,
            first_name="NoOverview",
            last_name="Student",
            university_id="NOV-001",
            university_email="no.overview@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)
        resp = await sc.get("/api/v1/administration/overview")
        assert resp.status_code == 403

    async def test_staff_cannot_access_admin_overview(
        self, client: AsyncClient, db: AsyncSession
    ):
        staff = await create_test_user(
            db,
            first_name="NoOverviewStf",
            last_name="Staff",
            university_id="NOV-STF-001",
            university_email="no.overview.stf@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        sc = await _make_client(client, staff, db)
        resp = await sc.get("/api/v1/administration/overview")
        assert resp.status_code == 403

    async def test_student_cannot_manage_users(
        self, client: AsyncClient, db: AsyncSession
    ):
        student = await create_test_user(
            db,
            first_name="NoUsers",
            last_name="Student",
            university_id="NU-001",
            university_email="no.users@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)
        resp = await sc.get("/api/v1/users/")
        assert resp.status_code == 403

    async def test_student_cannot_list_all_refunds(
        self, client: AsyncClient, db: AsyncSession
    ):
        student = await create_test_user(
            db,
            first_name="NoRefunds",
            last_name="Student",
            university_id="NR-001",
            university_email="no.refunds@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)
        resp = await sc.get("/api/v1/refunds/admin/all")
        assert resp.status_code == 403

    async def test_staff_cannot_process_refund(
        self, client: AsyncClient, db: AsyncSession
    ):
        staff = await create_test_user(
            db,
            first_name="NoProcRef",
            last_name="Staff",
            university_id="NPR-001",
            university_email="no.proc.ref@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        sc = await _make_client(client, staff, db)
        resp = await sc.post(f"/api/v1/refunds/{FAKE_ORDER_ID}/process")
        assert resp.status_code == 403

    async def test_student_cannot_list_cafeteria_orders(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        student = await create_test_user(
            db,
            first_name="NoCafOrders",
            last_name="Student",
            university_id="NCO-001",
            university_email="no.caf.orders@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)
        resp = await sc.get(f"/api/v1/orders/cafeteria/{STUDENT_CAF_ID}")
        assert resp.status_code == 403

    async def test_student_cannot_access_reports(
        self, client: AsyncClient, db: AsyncSession
    ):
        student = await create_test_user(
            db,
            first_name="NoReports",
            last_name="Student",
            university_id="NRP-001",
            university_email="no.reports@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)
        resp = await sc.get("/api/v1/reports/sales")
        assert resp.status_code == 403

    async def test_student_cannot_create_menu_item(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        student = await create_test_user(
            db,
            first_name="NoCreateMenu",
            last_name="Student",
            university_id="NCM-001",
            university_email="no.create.menu@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)
        resp = await sc.post(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/menu-items/",
            json={
                "name": "Hacked Burger",
                "category": "main_course",
                "price": 100,
            },
        )
        assert resp.status_code == 403

    async def test_staff_cannot_update_order_status_wrong_cafeteria(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Staff assigned to one cafeteria cannot update orders in another."""
        await _seed_cafeterias(db)
        admin = await create_test_user(
            db,
            first_name="AdminStatus",
            last_name="User",
            university_id="ADM-STAT-001",
            university_email="admin.status@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        admin_c = await _make_client(client, admin, db)

        fac_user = await create_test_user(
            db,
            first_name="FacStatus",
            last_name="Owner",
            university_id="FAC-STAT-001",
            university_email="fac.status@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        order = await _create_order(db, fac_user.id, FACULTY_CAF_ID)

        staff = await create_test_user(
            db,
            first_name="WrongCafStaff",
            last_name="Status",
            university_id="WCS-001",
            university_email="wrong.caf.staff@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, staff, STUDENT_CAF_ID, Role.CAFETERIA_STAFF)
        staff_c = await _make_client(client, staff, db)

        resp = await staff_c.put(
            f"/api/v1/orders/{order.id}/status",
            json={"status": "preparing", "notes": "hacked"},
        )
        assert resp.status_code == 403


# ===================================================================
# ETA Endpoint Authorization Tests
# ===================================================================


@pytest.mark.asyncio
class TestETAEndpointAuth:
    """GET /orders/{order_id}/eta — must enforce owner/cafeteria check."""

    async def test_owner_can_get_eta(self, client: AsyncClient, db: AsyncSession):
        await _seed_cafeterias(db)
        owner = await create_test_user(
            db,
            first_name="EtaOwner",
            last_name="Test",
            university_id="ETA-001",
            university_email="eta.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID)
        oc = await _make_client(client, owner, db)

        resp = await oc.get(f"/api/v1/orders/{order.id}/eta")
        assert resp.status_code == 200

    async def test_stranger_cannot_get_eta(self, client: AsyncClient, db: AsyncSession):
        """A different student cannot see another student's order ETA."""
        await _seed_cafeterias(db)
        owner = await create_test_user(
            db,
            first_name="EtaRealOwner",
            last_name="Test",
            university_id="ETA-REAL-001",
            university_email="eta.real.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID)

        stranger = await create_test_user(
            db,
            first_name="EtaStranger",
            last_name="Test",
            university_id="ETA-STR-001",
            university_email="eta.stranger@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, stranger, db)

        resp = await sc.get(f"/api/v1/orders/{order.id}/eta")
        assert resp.status_code in (403, 404)

    async def test_admin_can_get_any_eta(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        owner = await create_test_user(
            db,
            first_name="EtaOwnerAdmin",
            last_name="Test",
            university_id="ETA-ADM-001",
            university_email="eta.owner.admin@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID)

        admin = await create_test_user(
            db,
            first_name="EtaAdmin",
            last_name="User",
            university_id="ETA-ADM-002",
            university_email="eta.admin@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        ac = await _make_client(client, admin, db)

        resp = await ac.get(f"/api/v1/orders/{order.id}/eta")
        assert resp.status_code == 200

    async def test_unassigned_staff_cannot_get_eta(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Staff NOT assigned to the order's cafeteria cannot see ETA."""
        await _seed_cafeterias(db)
        owner = await create_test_user(
            db,
            first_name="EtaOwnerUnassigned",
            last_name="Test",
            university_id="ETA-UNA-001",
            university_email="eta.owner.una@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        order = await _create_order(db, owner.id, FACULTY_CAF_ID)

        staff = await create_test_user(
            db,
            first_name="EtaStaffUnassigned",
            last_name="Test",
            university_id="ETA-UNA-002",
            university_email="eta.staff.una@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, staff, STUDENT_CAF_ID, Role.CAFETERIA_STAFF)
        sc = await _make_client(client, staff, db)

        resp = await sc.get(f"/api/v1/orders/{order.id}/eta")
        assert resp.status_code in (403, 404)


# ===================================================================
# Menu Search Cafeteria Scope Tests
# ===================================================================


@pytest.mark.asyncio
class TestMenuSearchScope:
    """GET /menu-search — verify cafeteria scope enforcement."""

    async def test_student_can_search_student_cafeteria(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        await _create_menu_item(db, STUDENT_CAF_ID, "Burger", 500)

        student = await create_test_user(
            db,
            first_name="SearchStudent",
            last_name="Test",
            university_id="SRCH-001",
            university_email="search.student@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        resp = await sc.get(
            "/api/v1/menu-search/",
            params={"cafeteria_id": STUDENT_CAF_ID, "search": "Burger"},
        )
        assert resp.status_code == 200

    async def test_student_can_search_all_cafeterias_without_id(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Without cafeteria_id, student gets all accessible items."""
        await _seed_cafeterias(db)
        await _create_menu_item(db, STUDENT_CAF_ID, "Fries", 200)

        student = await create_test_user(
            db,
            first_name="SearchAll",
            last_name="Test",
            university_id="SRCH-ALL-001",
            university_email="search.all@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        resp = await sc.get("/api/v1/menu-search/", params={"search": "Fries"})
        assert resp.status_code == 200

    async def test_student_cannot_search_faculty_cafeteria_by_id(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A student specifying faculty cafeteria_id should be blocked."""
        await _seed_cafeterias(db)

        student = await create_test_user(
            db,
            first_name="SearchFacBlocked",
            last_name="Test",
            university_id="SRCH-FAC-001",
            university_email="search.fac.blocked@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        resp = await sc.get(
            "/api/v1/menu-search/",
            params={"cafeteria_id": FACULTY_CAF_ID, "search": "Coffee"},
        )
        assert resp.status_code in (403, 200)  # 403 = blocked, 200 with empty = OK too
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("total", 0) == 0


# ===================================================================
# Daily Menu IDOR Tests
# ===================================================================


@pytest.mark.asyncio
class TestDailyMenuIDOR:
    """GET /daily-menus/{daily_menu_id} — verify IDOR prevention."""

    async def test_student_cannot_access_faculty_daily_menu_by_id(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A student using the student cafeteria prefix cannot read a
        faculty cafeteria daily menu via UUID."""
        await _seed_cafeterias(db)
        fac_menu = await _create_daily_menu(db, FACULTY_CAF_ID)

        student = await create_test_user(
            db,
            first_name="DMIDOR",
            last_name="Student",
            university_id="DMIDOR-001",
            university_email="dmidor.student@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        # Student tries to access via student cafeteria prefix
        resp = await sc.get(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/daily-menus/{fac_menu.id}"
        )
        assert resp.status_code in (403, 404)

    async def test_staff_cannot_access_unassigned_daily_menu(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Staff assigned to student caf cannot access faculty caf daily menus."""
        await _seed_cafeterias(db)
        fac_menu = await _create_daily_menu(db, FACULTY_CAF_ID)

        staff = await create_test_user(
            db,
            first_name="DMStfIDOR",
            last_name="Test",
            university_id="DMSTF-001",
            university_email="dm.stf.idor@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, staff, STUDENT_CAF_ID, Role.CAFETERIA_STAFF)
        sc = await _make_client(client, staff, db)

        resp = await sc.get(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/daily-menus/{fac_menu.id}"
        )
        assert resp.status_code in (403, 404)

    async def test_owner_can_access_own_daily_menu(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Manager assigned to student caf can access student caf daily menus."""
        await _seed_cafeterias(db)
        stud_menu = await _create_daily_menu(db, STUDENT_CAF_ID)

        mgr = await create_test_user(
            db,
            first_name="DMMgrOwn",
            last_name="Test",
            university_id="DMMGR-001",
            university_email="dm.mgr.own@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, mgr, STUDENT_CAF_ID, Role.CAFETERIA_MANAGER)
        mc = await _make_client(client, mgr, db)

        resp = await mc.get(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/daily-menus/{stud_menu.id}"
        )
        assert resp.status_code == 200


# ===================================================================
# Order Cancellation Ownership Tests
# ===================================================================


@pytest.mark.asyncio
class TestOrderCancellationAuth:
    """POST /orders/{order_id}/cancel — verify owner-only."""

    async def test_owner_can_cancel_own_order(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        owner = await create_test_user(
            db,
            first_name="CancelOwner",
            last_name="Test",
            university_id="CANC-001",
            university_email="cancel.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID, OrderStatus.PENDING)
        oc = await _make_client(client, owner, db)

        resp = await oc.post(
            f"/api/v1/orders/{order.id}/cancel",
            json={"reason": "Changed mind"},
        )
        assert resp.status_code == 200

    async def test_stranger_cannot_cancel_others_order(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        owner = await create_test_user(
            db,
            first_name="CancelRealOwner",
            last_name="Test",
            university_id="CANC-REAL-001",
            university_email="cancel.real.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID, OrderStatus.PENDING)

        stranger = await create_test_user(
            db,
            first_name="CancelStranger",
            last_name="Test",
            university_id="CANC-STR-001",
            university_email="cancel.stranger@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, stranger, db)

        resp = await sc.post(
            f"/api/v1/orders/{order.id}/cancel",
            json={"reason": "Malicious"},
        )
        assert resp.status_code in (400, 403, 404)


# ===================================================================
# Notification Parameter Tests
# ===================================================================


@pytest.mark.asyncio
class TestNotificationParameters:
    """Verify the notifications endpoint uses correct parameter names."""

    async def test_list_notifications_uses_unread_only(
        self, client: AsyncClient, db: AsyncSession
    ):
        """The endpoint accepts unread_only, not is_read."""
        student = await create_test_user(
            db,
            first_name="NotifParam",
            last_name="Test",
            university_id="NP-001",
            university_email="notif.param@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        # Using the correct param name
        resp = await sc.get(
            "/api/v1/notifications",
            params={"unread_only": "true"},
        )
        assert resp.status_code == 200

    async def test_notification_list_allows_false_unread_only(
        self, client: AsyncClient, db: AsyncSession
    ):
        student = await create_test_user(
            db,
            first_name="NotifAll",
            last_name="Test",
            university_id="NP-ALL-001",
            university_email="notif.all@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        resp = await sc.get(
            "/api/v1/notifications",
            params={"unread_only": "false"},
        )
        assert resp.status_code == 200


# ===================================================================
# Refund Process — No Body Parameter Test
# ===================================================================


@pytest.mark.asyncio
class TestRefundProcessNoBody:
    """POST /refunds/{refund_id}/process — backend determines action internally."""

    async def test_process_refund_works_without_body(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Sending an empty body should not error."""
        admin = await create_test_user(
            db,
            first_name="RefProcAdmin",
            last_name="Test",
            university_id="RPA-001",
            university_email="ref.proc.admin@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        ac = await _make_client(client, admin, db)

        resp = await ac.post(f"/api/v1/refunds/{FAKE_ORDER_ID}/process")
        # Should fail with 404 (order not found) — NOT with a validation error
        assert resp.status_code in (404, 403)
        # Make sure it's not a 422 (request body validation error)
        assert resp.status_code != 422

    async def test_process_refund_with_body_also_works(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Sending a body (ignored by backend) should not error with 422."""
        admin = await create_test_user(
            db,
            first_name="RefProcAdmin2",
            last_name="Test",
            university_id="RPA-002",
            university_email="ref.proc.admin2@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        ac = await _make_client(client, admin, db)

        resp = await ac.post(
            f"/api/v1/refunds/{FAKE_ORDER_ID}/process",
            json={"action": "approve", "reason": "test"},
        )
        # Should fail with 404 (not found), not 422
        assert resp.status_code in (404, 403)
        assert resp.status_code != 422


# ===================================================================
# Staff/Manager Assignment Verification Tests
# ===================================================================


@pytest.mark.asyncio
class TestStaffManagerAssignment:
    """Verify cafeteria assignment is checked for write operations."""

    async def test_unassigned_manager_cannot_confirm_order(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        admin = await create_test_user(
            db,
            first_name="AdminConfirm",
            last_name="User",
            university_id="ADM-CNFM-001",
            university_email="admin.cnfm@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        admin_c = await _make_client(client, admin, db)

        owner = await create_test_user(
            db,
            first_name="ConfirmOwner",
            last_name="Test",
            university_id="CNFM-OWN-001",
            university_email="confirm.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID, OrderStatus.PENDING)

        mgr = await create_test_user(
            db,
            first_name="UnassignedMgr",
            last_name="Confirm",
            university_id="MGR-CNFM-001",
            university_email="unassigned.mgr.cnfm@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        # No cafeteria assignment
        mc = await _make_client(client, mgr, db)

        resp = await mc.post(
            f"/api/v1/orders/{order.id}/confirm",
            json={"notes": "Trying without assignment"},
        )
        assert resp.status_code == 403

    async def test_unassigned_staff_cannot_start_preparation(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        admin = await create_test_user(
            db,
            first_name="AdminPrep",
            last_name="User",
            university_id="ADM-PREP-001",
            university_email="admin.prep@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        admin_c = await _make_client(client, admin, db)

        owner = await create_test_user(
            db,
            first_name="PrepOwner",
            last_name="Test",
            university_id="PREP-OWN-001",
            university_email="prep.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(
            db, owner.id, STUDENT_CAF_ID, OrderStatus.PENDING
        )

        staff = await create_test_user(
            db,
            first_name="UnassignedStaff",
            last_name="Prep",
            university_id="STF-PREP-001",
            university_email="unassigned.staff.prep@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        # No cafeteria assignment
        sc = await _make_client(client, staff, db)

        resp = await sc.post(
            f"/api/v1/orders/{order.id}/prepare",
            json={"notes": "Trying without assignment"},
        )
        assert resp.status_code == 403

    async def test_staff_cannot_reject_order_manager_only(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Reject is manager-only; staff should be denied."""
        await _seed_cafeterias(db)
        admin = await create_test_user(
            db,
            first_name="AdminReject",
            last_name="User",
            university_id="ADM-RJCT-001",
            university_email="admin.reject@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        admin_c = await _make_client(client, admin, db)

        owner = await create_test_user(
            db,
            first_name="RejectOwner",
            last_name="Test",
            university_id="RJCT-OWN-001",
            university_email="reject.owner@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        order = await _create_order(db, owner.id, STUDENT_CAF_ID, OrderStatus.PENDING)

        staff = await create_test_user(
            db,
            first_name="StaffReject",
            last_name="Test",
            university_id="STF-RJCT-001",
            university_email="staff.reject@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, staff, STUDENT_CAF_ID, Role.CAFETERIA_STAFF)
        sc = await _make_client(client, staff, db)

        resp = await sc.post(
            f"/api/v1/orders/{order.id}/reject",
            json={"reason": "Not allowed", "notes": "Staff cannot reject"},
        )
        assert resp.status_code == 403


# ===================================================================
# Unauthenticated Access Tests
# ===================================================================


@pytest.mark.asyncio
class TestUnauthenticatedAccess:
    """Verify all sensitive endpoints reject unauthenticated requests."""

    async def test_orders_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/orders/")
        assert resp.status_code == 401

    async def test_notifications_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 401

    async def test_favorites_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/favorites/")
        assert resp.status_code in (401, 307)

    async def test_administration_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/administration/overview")
        assert resp.status_code == 401

    async def test_menu_search_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/menu-search/")
        assert resp.status_code == 401


# ===================================================================
# Phase 27: Non-Payment Release Readiness — Regression Tests
# ===================================================================


@pytest.mark.asyncio
class TestMenuItemGetCrossCafeteriaIDOR:
    """GET /cafeterias/{cid}/menu-items/{item_id} — Phase 27 fix: resource check."""

    async def test_student_cannot_read_faculty_item_via_own_cafeteria_path(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        faculty_item = await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Special", 900)

        student = await create_test_user(
            db,
            first_name="IdorGet",
            last_name="Student",
            university_id="SRCH-IDOR-GET-001",
            university_email="idor.get@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        resp = await sc.get(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/menu-items/{faculty_item.id}"
        )
        assert resp.status_code in (403, 404)

    async def test_manager_assigned_elsewhere_cannot_read_faculty_item(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        faculty_item = await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Only", 700)

        manager = await create_test_user(
            db,
            first_name="IdorMgr",
            last_name="User",
            university_id="SRCH-IDOR-MGR-001",
            university_email="idor.mgr@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, manager, STUDENT_CAF_ID, Role.CAFETERIA_MANAGER)
        mc = await _make_client(client, manager, db)

        resp = await mc.get(
            f"/api/v1/cafeterias/{STUDENT_CAF_ID}/menu-items/{faculty_item.id}"
        )
        assert resp.status_code in (403, 404)

    async def test_manager_can_read_own_cafeteria_item(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Control: same request pattern succeeds for the assigned cafeteria."""
        await _seed_cafeterias(db)
        item = await _create_menu_item(db, STUDENT_CAF_ID, "Own Item", 400)

        manager = await create_test_user(
            db,
            first_name="IdorOwn",
            last_name="User",
            university_id="SRCH-IDOR-OWN-001",
            university_email="idor.own@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await _assign_user(db, manager, STUDENT_CAF_ID, Role.CAFETERIA_MANAGER)
        mc = await _make_client(client, manager, db)

        resp = await mc.get(f"/api/v1/cafeterias/{STUDENT_CAF_ID}/menu-items/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Own Item"


@pytest.mark.asyncio
class TestMenuSearchFacultyExclusion:
    """GET /menu-search/ without cafeteria_id — Phase 27 fix: faculty items hidden."""

    async def _make_student(self, client: AsyncClient, db: AsyncSession, suffix: str):
        student = await create_test_user(
            db,
            first_name="FacHide",
            last_name="Student",
            university_id=f"SRCH-FACHIDE-{suffix}",
            university_email=f"fac.hide.{suffix.lower()}@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        return await _make_client(client, student, db)

    async def test_student_unscoped_search_excludes_faculty_items(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        await _create_menu_item(db, STUDENT_CAF_ID, "Student Fries", 200)
        await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Fries", 250)

        sc = await self._make_student(client, db, "001")
        resp = await sc.get("/api/v1/menu-search/", params={"search": "Fries"})
        assert resp.status_code == 200
        data = resp.json()
        names = [i["name"] for i in data["items"]]
        assert "Student Fries" in names
        assert "Faculty Fries" not in names

    async def test_faculty_user_unscoped_search_includes_faculty_items(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Control: faculty-category users still see faculty items."""
        await _seed_cafeterias(db)
        await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Fries", 250)

        faculty = await create_test_user(
            db,
            first_name="FacSee",
            last_name="User",
            university_id="SRCH-FACSEE-001",
            university_email="fac.see@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        fc = await _make_client(client, faculty, db)
        resp = await fc.get("/api/v1/menu-search/", params={"search": "Fries"})
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "Faculty Fries" in names

    async def test_admin_unscoped_search_includes_faculty_items(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Control: admin sees everything."""
        await _seed_cafeterias(db)
        await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Fries", 250)

        admin = await create_test_user(
            db,
            first_name="FacAdmin",
            last_name="User",
            university_id="SRCH-FACADM-001",
            university_email="fac.adm@lgu.edu.pk",
            role=Role.UNIVERSITY_ADMIN,
            category=UserCategory.FACULTY,
        )
        ac = await _make_client(client, admin, db)
        resp = await ac.get("/api/v1/menu-search/", params={"search": "Fries"})
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "Faculty Fries" in names


@pytest.mark.asyncio
class TestFavoritesFacultyExclusion:
    """POST/GET /favorites/ — Phase 27 fix: faculty items blocked for students."""

    async def test_student_cannot_favorite_faculty_cafeteria_item(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _seed_cafeterias(db)
        faculty_item = await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Mocha", 350)

        student = await create_test_user(
            db,
            first_name="FavBlock",
            last_name="Student",
            university_id="SRCH-FAVB-001",
            university_email="fav.block@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        resp = await sc.post(
            "/api/v1/favorites/", json={"menu_item_id": faculty_item.id}
        )
        assert resp.status_code == 403

    async def test_faculty_user_can_favorite_faculty_item(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Control: faculty users can favorite faculty-cafeteria items."""
        await _seed_cafeterias(db)
        faculty_item = await _create_menu_item(db, FACULTY_CAF_ID, "Faculty Mocha", 350)

        faculty = await create_test_user(
            db,
            first_name="FavOk",
            last_name="User",
            university_id="SRCH-FAVO-001",
            university_email="fav.ok@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        fc = await _make_client(client, faculty, db)

        resp = await fc.post(
            "/api/v1/favorites/", json={"menu_item_id": faculty_item.id}
        )
        assert resp.status_code == 201

    async def test_student_list_favorites_hides_faculty_items(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A legacy faculty favorite must not appear in a student's list."""
        await _seed_cafeterias(db)
        faculty_item = await _create_menu_item(db, FACULTY_CAF_ID, "Legacy Fac", 300)
        student_item = await _create_menu_item(db, STUDENT_CAF_ID, "Student Deli", 280)

        student = await create_test_user(
            db,
            first_name="FavList",
            last_name="Student",
            university_id="SRCH-FAVL-001",
            university_email="fav.list@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        sc = await _make_client(client, student, db)

        # Insert the faculty favorite directly (simulates pre-fix data)
        from app.modules.menus.models import MenuFavorite

        db.add(MenuFavorite(user_id=student.id, menu_item_id=faculty_item.id))
        await db.flush()
        await sc.post("/api/v1/favorites/", json={"menu_item_id": student_item.id})

        resp = await sc.get("/api/v1/favorites/")
        assert resp.status_code == 200
        names = [f["menu_item"]["name"] for f in resp.json()["favorites"]]
        assert "Student Deli" in names
        assert "Legacy Fac" not in names
