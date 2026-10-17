"""Phase 49 — Admin Reports & Analytics backend tests (A–M).

Covers the admin-console reporting experience built on the existing reports
module, including the Phase 49 additive fields:
- SalesSummary.online_payment_volume / cash_payment_volume (paisa)
- CafeteriaSalesRow.completed_orders / cancelled_orders

Test mapping (mission A–M):
  A — admin can access reports endpoints
  B — manager restricted to permitted scope
  C — student / faculty / staff denied
  D — today date filter
  E — 7-day date filter
  F — custom date range
  G — all-cafeterias aggregate equals sum of per-cafeteria data
  H — specific cafeteria returns only its data
  I — invalid/unauthorized cafeteria cannot bypass access control
  J — order totals correct
  K — revenue totals correct
  L — payment breakdown correct (counts + new volume fields)
  M — top-item data correct

Test DB has no seed data — every test creates its own cafeterias, users,
orders, items, payments, and refunds within the test.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import AsyncClient

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.cafeterias.models import Cafeteria
    from app.modules.menus.models import MenuItem
    from app.modules.users.models import User

from app.modules.cafeterias.models import CafeteriaType
from app.modules.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundReason, RefundStatus
from app.modules.users.models import Role, UserCategory
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_menu_item,
    create_test_user,
    create_user_session,
)

_order_seq_counter = 910000
_P49_USER = "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_order(
    db: AsyncSession,
    *,
    cafeteria: Cafeteria,
    days_ago: int = 0,
    status: OrderStatus = OrderStatus.COMPLETED,
    method: PaymentMethod = PaymentMethod.CASH,
    total: int = 25000,
    pay_status: PaymentStatus = PaymentStatus.SUCCEEDED,
    order_type: OrderType = OrderType.IMMEDIATE,
    item: MenuItem | None = None,
    quantity: int = 1,
) -> Order:
    """Create an order (+payment, optional item) for report testing."""
    global _order_seq_counter
    order = Order(
        cafeteria_id=cafeteria.id,
        order_number=_order_seq_counter,
        user_id=_P49_USER,
        order_type=order_type,
        payment_method=method,
        status=status,
        total_amount=total,
        currency="PKR",
        order_date=date.today() - timedelta(days=days_ago),
        collection_token=f"p49_{_uuid.uuid4().hex}",
    )
    _order_seq_counter += 1
    db.add(order)
    await db.flush()

    if item is not None:
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=item.id,
                item_name=item.name,
                unit_price=item.price,
                quantity=quantity,
                subtotal=item.price * quantity,
                currency="PKR",
            )
        )

    db.add(
        Payment(
            id=f"pay_{order.id}"[:36],
            order_id=order.id,
            user_id=_P49_USER,
            amount=total,
            currency="PKR",
            status=pay_status,
            idempotency_key=f"p49pay_{order.id}"[:255],
        )
    )
    await db.flush()
    return order


async def _seed_refund(
    db: AsyncSession,
    *,
    order: Order,
    amount: int,
    status: RefundStatus = RefundStatus.SUCCEEDED,
) -> Refund:
    refund = Refund(
        id=str(_uuid.uuid4()),
        order_id=order.id,
        payment_id=f"pay_{order.id}"[:36],
        user_id=_P49_USER,
        amount=amount,
        currency="PKR",
        status=status,
        reason=RefundReason.ORDER_CANCELLED,
        requested_by=_P49_USER,
        idempotency_key=f"p49ref_{_uuid.uuid4().hex}"[:255],
    )
    db.add(refund)
    await db.flush()
    return refund


async def _auth_client(client: AsyncClient, user: User, db: AsyncSession) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return new_client


def _d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------
# Shared fixtures — two cafeterias with known data
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def caf_a(db: AsyncSession) -> Cafeteria:
    return await create_test_cafeteria(db, name="P49 Cafeteria A", cafeteria_type=CafeteriaType.STUDENT)


@pytest_asyncio.fixture
async def caf_b(db: AsyncSession) -> Cafeteria:
    return await create_test_cafeteria(db, name="P49 Cafeteria B", cafeteria_type=CafeteriaType.FACULTY)


@pytest_asyncio.fixture
async def seed_user(db: AsyncSession) -> User:
    return await create_test_user(
        db,
        first_name="P49",
        last_name="Seeder",
        university_id="P49-SEED-001",
        university_email="p49.seeder@lgu.edu.pk",
        role=Role.STUDENT,
        category=UserCategory.STUDENT,
    )


# ===========================================================================
# A — Admin can access reports
# ===========================================================================


class TestA_AdminAccess:
    async def test_admin_sales_summary_with_new_volume_fields(
        self, admin_client: AsyncClient, caf_a: Cafeteria, seed_user: User, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, total=10000, method=PaymentMethod.CASH)
        await _seed_order(db, cafeteria=caf_a, total=20000, method=PaymentMethod.ONLINE)
        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.status_code == 200
        body = resp.json()
        summary = body["summary"]
        # Additive Phase 49 fields present alongside existing fields
        for key in (
            "total_revenue",
            "total_orders",
            "total_refunded",
            "net_revenue",
            "online_payment_volume",
            "cash_payment_volume",
            "currency",
        ):
            assert key in summary, f"missing {key}"
        assert summary["total_revenue"] == 30000
        assert summary["online_payment_volume"] == 20000
        assert summary["cash_payment_volume"] == 10000

    async def test_admin_order_summary_accessible(self, admin_client: AsyncClient) -> None:
        resp = await admin_client.get("/api/v1/reports/orders/summary")
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "total_orders",
            "status_breakdown",
            "type_breakdown",
            "payment_breakdown",
            "cancellation_rate",
            "completion_rate",
        ):
            assert key in body

    async def test_admin_by_cafeteria_accessible(
        self, admin_client: AsyncClient, caf_a: Cafeteria, caf_b: Cafeteria, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, total=10000)
        await _seed_order(db, cafeteria=caf_b, total=20000)
        resp = await admin_client.get("/api/v1/reports/sales/by-cafeteria")
        assert resp.status_code == 200
        names = {r["cafeteria_name"]: r for r in resp.json()["rows"]}
        assert "P49 Cafeteria A" in names and "P49 Cafeteria B" in names

    async def test_admin_cafeteria_performance_and_popular(
        self, admin_client: AsyncClient, caf_a: Cafeteria, seed_user: User, db: AsyncSession
    ) -> None:
        item = await create_test_menu_item(db, cafeteria_id=caf_a.id, name="P49 Dish")
        await _seed_order(db, cafeteria=caf_a, total=10000, item=item, quantity=2)
        perf = await admin_client.get(f"/api/v1/reports/cafeteria/{caf_a.id}/performance")
        assert perf.status_code == 200
        assert perf.json()["cafeteria_id"] == caf_a.id

        pop = await admin_client.get(f"/api/v1/reports/cafeteria/{caf_a.id}/popular-items")
        assert pop.status_code == 200
        assert pop.json()["cafeteria_id"] == caf_a.id


# ===========================================================================
# B — Manager restricted to permitted scope
# ===========================================================================


class TestB_ManagerScope:
    """Manager sees only assigned-cafeteria data.

    Note: cafeteria_assignments.user_id carries a UNIQUE constraint — a
    manager can belong to exactly one cafeteria by schema, so the router's
    multi-assignment "specify cafeteria_id" branch is defensive only and
    is not exercised here.
    """
    async def test_manager_assigned_cafeteria_200(
        self, client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        mgr = await create_test_user(
            db,
            first_name="P49",
            last_name="ManagerA",
            university_id="P49-MGR-A",
            university_email="p49.mgr.a@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await assign_user_to_cafeteria(db, mgr.id, caf_a.id, role=Role.CAFETERIA_MANAGER)
        await _seed_order(db, cafeteria=caf_a, total=10000)
        mclient = await _auth_client(client, mgr, db)

        resp = await mclient.get(f"/api/v1/reports/sales?cafeteria_id={caf_a.id}")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_revenue"] == 10000

        perf = await mclient.get(f"/api/v1/reports/cafeteria/{caf_a.id}/performance")
        assert perf.status_code == 200

        pop = await mclient.get(f"/api/v1/reports/cafeteria/{caf_a.id}/popular-items")
        assert pop.status_code == 200

    async def test_manager_single_assignment_auto_scope(
        self, client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        mgr = await create_test_user(
            db,
            first_name="P49",
            last_name="ManagerA2",
            university_id="P49-MGR-A2",
            university_email="p49.mgr.a2@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await assign_user_to_cafeteria(db, mgr.id, caf_a.id, role=Role.CAFETERIA_MANAGER)
        await _seed_order(db, cafeteria=caf_a, total=10000)
        mclient = await _auth_client(client, mgr, db)

        # No cafeteria_id: single assignment is auto-scoped by the backend
        resp = await mclient.get("/api/v1/reports/sales")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_revenue"] == 10000

    async def test_manager_unassigned_denied(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        mgr = await create_test_user(
            db,
            first_name="P49",
            last_name="ManagerNone",
            university_id="P49-MGR-N",
            university_email="p49.mgr.none@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        mclient = await _auth_client(client, mgr, db)
        resp = await mclient.get("/api/v1/reports/sales")
        assert resp.status_code == 403

    async def test_manager_by_cafeteria_forbidden(
        self, client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        mgr = await create_test_user(
            db,
            first_name="P49",
            last_name="ManagerX",
            university_id="P49-MGR-X",
            university_email="p49.mgr.x@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await assign_user_to_cafeteria(db, mgr.id, caf_a.id, role=Role.CAFETERIA_MANAGER)
        mclient = await _auth_client(client, mgr, db)

        # Cross-cafeteria comparison is university-admin only
        resp = await mclient.get("/api/v1/reports/sales/by-cafeteria")
        assert resp.status_code == 403


# ===========================================================================
# C — Student / faculty / staff denied
# ===========================================================================


class TestC_NonAdminDenied:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/reports/sales",
            "/api/v1/reports/orders/summary",
            "/api/v1/reports/sales/by-cafeteria",
        ],
    )
    async def test_student_faculty_staff_denied(
        self,
        student_client: AsyncClient,
        faculty_client: AsyncClient,
        staff_client: AsyncClient,
        endpoint: str,
    ) -> None:
        for c in (student_client, faculty_client, staff_client):
            resp = await c.get(endpoint)
            assert resp.status_code == 403, f"{endpoint} should deny role, got {resp.status_code}"


# ===========================================================================
# D/E/F — Date filtering
# ===========================================================================


class TestDateFilters:
    async def test_today_filter(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        today_order = await _seed_order(db, cafeteria=caf_a, days_ago=0, total=5000)
        await _seed_order(db, cafeteria=caf_a, days_ago=3, total=9000)
        today = date.today().isoformat()

        resp = await admin_client.get(f"/api/v1/reports/sales?start_date={today}&end_date={today}")
        assert resp.status_code == 200
        s = resp.json()["summary"]
        assert s["total_orders"] == 1
        assert s["total_revenue"] == 5000
        assert today_order.order_date == date.today()

    async def test_seven_day_filter(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, days_ago=1, total=1000)
        await _seed_order(db, cafeteria=caf_a, days_ago=3, total=2000)
        await _seed_order(db, cafeteria=caf_a, days_ago=10, total=9999)  # outside window

        start = (date.today() - timedelta(days=6)).isoformat()
        resp = await admin_client.get(
            f"/api/v1/reports/orders/summary?start_date={start}&end_date={date.today().isoformat()}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_orders"] == 2
        assert body["status_breakdown"]["completed"] == 2

    async def test_custom_range(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, days_ago=5, total=3000)  # before window
        await _seed_order(db, cafeteria=caf_a, days_ago=2, total=4000)  # inside
        await _seed_order(db, cafeteria=caf_a, days_ago=1, total=6000)  # inside

        start, end = _d(4), _d(1)
        resp = await admin_client.get(f"/api/v1/reports/sales?start_date={start}&end_date={end}")
        assert resp.status_code == 200
        s = resp.json()["summary"]
        assert s["total_orders"] == 2
        assert s["total_revenue"] == 10000

    async def test_empty_range_returns_zeroed_defaults(
        self, admin_client: AsyncClient
    ) -> None:
        # No data in future window -> 200 with zeros, never an error
        future = (date.today() + timedelta(days=90)).isoformat()
        resp = await admin_client.get(f"/api/v1/reports/sales?start_date={future}&end_date={future}")
        assert resp.status_code == 200
        s = resp.json()["summary"]
        assert s["total_revenue"] == 0
        assert s["total_orders"] == 0
        assert s["online_payment_volume"] == 0
        assert s["cash_payment_volume"] == 0

        summary = await admin_client.get(
            f"/api/v1/reports/orders/summary?start_date={future}&end_date={future}"
        )
        assert summary.status_code == 200
        assert summary.json()["total_orders"] == 0


# ===========================================================================
# G — All-cafeterias aggregate == sum of per-cafeteria data
# ===========================================================================


class TestG_AllCafeteriasAggregate:
    async def test_all_aggregates_equal_sum_of_cafeterias(
        self, admin_client: AsyncClient, caf_a: Cafeteria, caf_b: Cafeteria, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, total=10000, status=OrderStatus.COMPLETED)
        await _seed_order(db, cafeteria=caf_a, total=5000, status=OrderStatus.CANCELLED)
        await _seed_order(db, cafeteria=caf_b, total=20000, status=OrderStatus.COMPLETED)
        await _seed_order(db, cafeteria=caf_b, total=3000, status=OrderStatus.PENDING)

        all_sales = await admin_client.get("/api/v1/reports/sales")
        a_sales = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_a.id}")
        b_sales = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_b.id}")
        assert all_sales.status_code == a_sales.status_code == b_sales.status_code == 200

        total_rev = all_sales.json()["summary"]["total_revenue"]
        sum_rev = (
            a_sales.json()["summary"]["total_revenue"]
            + b_sales.json()["summary"]["total_revenue"]
        )
        assert total_rev == sum_rev == 38000

        by = await admin_client.get("/api/v1/reports/sales/by-cafeteria")
        rows = {r["cafeteria_id"]: r for r in by.json()["rows"]}
        assert rows[caf_a.id]["revenue"] == 15000
        assert rows[caf_a.id]["order_count"] == 2
        assert rows[caf_a.id]["completed_orders"] == 1
        assert rows[caf_a.id]["cancelled_orders"] == 1
        assert rows[caf_b.id]["revenue"] == 23000
        assert rows[caf_b.id]["completed_orders"] == 1
        assert rows[caf_b.id]["cancelled_orders"] == 0
        assert total_rev == rows[caf_a.id]["revenue"] + rows[caf_b.id]["revenue"]


# ===========================================================================
# H — Specific cafeteria returns only its data
# ===========================================================================


class TestH_SpecificCafeteriaOnly:
    async def test_cafeteria_scope_isolation(
        self, admin_client: AsyncClient, caf_a: Cafeteria, caf_b: Cafeteria, db: AsyncSession
    ) -> None:
        item_a = await create_test_menu_item(db, cafeteria_id=caf_a.id, name="P49 Dish A")
        item_b = await create_test_menu_item(db, cafeteria_id=caf_b.id, name="P49 Dish B")
        await _seed_order(db, cafeteria=caf_a, total=10000, item=item_a, quantity=3)
        await _seed_order(db, cafeteria=caf_b, total=20000, item=item_b, quantity=7)

        sales = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_a.id}")
        s = sales.json()["summary"]
        assert s["total_revenue"] == 10000
        assert s["total_orders"] == 1

        summary = await admin_client.get(
            f"/api/v1/reports/orders/summary?cafeteria_id={caf_a.id}"
        )
        assert summary.json()["total_orders"] == 1

        pop = await admin_client.get(f"/api/v1/reports/cafeteria/{caf_a.id}/popular-items")
        items = pop.json()["items"]
        assert len(items) == 1
        assert items[0]["menu_item_id"] == item_a.id
        assert items[0]["total_quantity"] == 3


# ===========================================================================
# I — Unauthorized cafeteria cannot bypass access control
# ===========================================================================


class TestI_AccessControlBypass:
    async def test_manager_cannot_request_other_cafeteria(
        self, client: AsyncClient, caf_a: Cafeteria, caf_b: Cafeteria, db: AsyncSession
    ) -> None:
        mgr = await create_test_user(
            db,
            first_name="P49",
            last_name="MgrScope",
            university_id="P49-MGR-SCOPE",
            university_email="p49.mgr.scope@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
            category=UserCategory.FACULTY,
        )
        await assign_user_to_cafeteria(db, mgr.id, caf_a.id, role=Role.CAFETERIA_MANAGER)
        await _seed_order(db, cafeteria=caf_b, total=10000)  # B data must never leak
        mclient = await _auth_client(client, mgr, db)

        resp = await mclient.get(f"/api/v1/reports/sales?cafeteria_id={caf_b.id}")
        assert resp.status_code == 403

        pop = await mclient.get(f"/api/v1/reports/cafeteria/{caf_b.id}/popular-items")
        assert pop.status_code == 403

        perf = await mclient.get(f"/api/v1/reports/cafeteria/{caf_b.id}/performance")
        assert perf.status_code == 403

    async def test_unknown_cafeteria_returns_zeros_not_other_data(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, total=10000)
        bogus = "00000000-0000-0000-0000-000000000000"
        resp = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={bogus}")
        assert resp.status_code == 200
        s = resp.json()["summary"]
        assert s["total_revenue"] == 0
        assert s["total_orders"] == 0


# ===========================================================================
# J — Order totals correct
# ===========================================================================


class TestJ_OrderTotals:
    async def test_status_type_and_paid_order_definitions(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        # 2 completed + 1 cancelled + 1 pending; 3 with succeeded payments,
        # 1 with pending payment -> sales total_orders (paid) = 3
        await _seed_order(db, cafeteria=caf_a, status=OrderStatus.COMPLETED, order_type=OrderType.IMMEDIATE)
        await _seed_order(db, cafeteria=caf_a, status=OrderStatus.COMPLETED, order_type=OrderType.IMMEDIATE)
        await _seed_order(
            db,
            cafeteria=caf_a,
            status=OrderStatus.CANCELLED,
            order_type=OrderType.SCHEDULED,
            pay_status=PaymentStatus.SUCCEEDED,
        )
        await _seed_order(
            db,
            cafeteria=caf_a,
            status=OrderStatus.PENDING,
            order_type=OrderType.SCHEDULED,
            pay_status=PaymentStatus.PENDING,
        )

        summary = await admin_client.get("/api/v1/reports/orders/summary")
        body = summary.json()
        assert body["total_orders"] == 4
        assert body["status_breakdown"]["completed"] == 2
        assert body["status_breakdown"]["cancelled"] == 1
        assert body["status_breakdown"]["pending"] == 1
        assert body["status_breakdown"]["preparing"] == 0
        assert body["status_breakdown"]["ready"] == 0
        assert body["type_breakdown"]["immediate"] == 2
        assert body["type_breakdown"]["scheduled"] == 2
        assert body["completion_rate"] == 0.5
        assert body["cancellation_rate"] == 0.25

        sales = await admin_client.get("/api/v1/reports/sales")
        # Paid-order definition: only orders with a succeeded payment
        assert sales.json()["summary"]["total_orders"] == 3


# ===========================================================================
# K — Revenue totals correct
# ===========================================================================


class TestK_RevenueTotals:
    async def test_revenue_counts_only_succeeded_and_net_of_refunds(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        paid = await _seed_order(db, cafeteria=caf_a, total=10000, pay_status=PaymentStatus.SUCCEEDED)
        await _seed_order(db, cafeteria=caf_a, total=20000, pay_status=PaymentStatus.PENDING)
        await _seed_order(db, cafeteria=caf_a, total=30000, pay_status=PaymentStatus.FAILED)
        await _seed_refund(db, order=paid, amount=2500, status=RefundStatus.SUCCEEDED)
        await _seed_refund(db, order=paid, amount=1000, status=RefundStatus.PENDING)  # excluded

        resp = await admin_client.get("/api/v1/reports/sales")
        s = resp.json()["summary"]
        assert s["total_revenue"] == 10000  # succeeded only
        assert s["total_refunded"] == 2500  # succeeded refunds only
        assert s["net_revenue"] == 7500

        # Scope filter applies to revenue too
        scoped = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_a.id}")
        assert scoped.json()["summary"]["total_revenue"] == 10000


# ===========================================================================
# L — Payment breakdown correct
# ===========================================================================


class TestL_PaymentBreakdown:
    async def test_counts_and_volume_split_by_method(
        self, admin_client: AsyncClient, caf_a: Cafeteria, caf_b: Cafeteria, db: AsyncSession
    ) -> None:
        await _seed_order(db, cafeteria=caf_a, method=PaymentMethod.CASH, total=1000)
        await _seed_order(db, cafeteria=caf_a, method=PaymentMethod.CASH, total=2000)
        await _seed_order(db, cafeteria=caf_a, method=PaymentMethod.ONLINE, total=5000)
        await _seed_order(
            db,
            cafeteria=caf_b,
            method=PaymentMethod.ONLINE,
            total=7000,
            pay_status=PaymentStatus.PENDING,  # excluded from volumes
        )

        summary = await admin_client.get("/api/v1/reports/orders/summary")
        pb = summary.json()["payment_breakdown"]
        assert pb["cash"] == 2
        assert pb["online"] == 2  # counts all orders regardless of payment status

        sales = await admin_client.get("/api/v1/reports/sales")
        s = sales.json()["summary"]
        assert s["online_payment_volume"] == 5000  # pending excluded
        assert s["cash_payment_volume"] == 3000

        # Cafeteria-scoped volumes
        scoped = await admin_client.get(f"/api/v1/reports/sales?cafeteria_id={caf_a.id}")
        ss = scoped.json()["summary"]
        assert ss["online_payment_volume"] == 5000
        assert ss["cash_payment_volume"] == 3000


# ===========================================================================
# M — Top-item data correct
# ===========================================================================


class TestM_TopItems:
    async def test_popular_items_quantities_revenue_and_limit(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        item = await create_test_menu_item(db, cafeteria_id=caf_a.id, name="P49 Top Item", price=25000)
        other = await create_test_menu_item(db, cafeteria_id=caf_a.id, name="P49 Other Item", price=10000)
        await _seed_order(db, cafeteria=caf_a, total=75000, item=item, quantity=3)
        await _seed_order(db, cafeteria=caf_a, total=75000, item=item, quantity=1)
        await _seed_order(db, cafeteria=caf_a, total=10000, item=other, quantity=1)

        resp = await admin_client.get(f"/api/v1/reports/cafeteria/{caf_a.id}/popular-items")
        items = resp.json()["items"]
        assert len(items) == 2
        top = items[0]
        assert top["menu_item_id"] == item.id
        assert top["total_quantity"] == 4
        assert top["total_revenue"] == 100000  # 25000 * 4
        assert top["order_count"] == 2

        limited = await admin_client.get(
            f"/api/v1/reports/cafeteria/{caf_a.id}/popular-items?limit=1"
        )
        lim = limited.json()["items"]
        assert len(lim) == 1
        assert lim[0]["menu_item_id"] == item.id

    async def test_date_range_applies_to_popular_items(
        self, admin_client: AsyncClient, caf_a: Cafeteria, db: AsyncSession
    ) -> None:
        item = await create_test_menu_item(db, cafeteria_id=caf_a.id, name="P49 Dated Item")
        await _seed_order(db, cafeteria=caf_a, days_ago=10, item=item, quantity=5)

        today = date.today().isoformat()
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{caf_a.id}/popular-items"
            f"?start_date={today}&end_date={today}"
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []  # old order excluded -> empty, not error
