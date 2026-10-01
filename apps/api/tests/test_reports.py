"""Tests for reporting APIs — Phase 7.

Covers:
- Sales reports (summary, daily, by-cafeteria)
- Order analytics (summary, volume, cancellation-rate)
- Cafeteria performance (performance, popular-items, peak-hours)
- Inventory reports (stock-levels, low-stock, turnover)
- Authorization (admin, manager, staff, student, faculty, unauthenticated, cross-cafeteria IDOR)
- Empty datasets
- Date filtering
- Division-by-zero safety
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import AsyncClient

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.menus.models import MenuItem

from app.modules.cafeterias.models import Cafeteria, CafeteriaType
from app.modules.inventory.models import InventoryAdjustment, InventoryItem, InventoryUnit
from app.modules.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundReason, RefundStatus
from app.modules.users.models import (
    Role,
    User,
    UserCategory,
)
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_menu_item,
    create_test_user,
    create_user_session,
)

# ---------------------------------------------------------------------------
# Fixtures — two cafeterias + orders for testing
# ---------------------------------------------------------------------------

# Module-level counter for unique order numbers across all tests
_order_seq_counter = 100000


@pytest_asyncio.fixture
async def student_cafeteria_obj(db: AsyncSession) -> Cafeteria:
    return await create_test_cafeteria(
        db,
        name="Student Cafeteria Reports",
        cafeteria_type=CafeteriaType.STUDENT,
    )


@pytest_asyncio.fixture
async def faculty_cafeteria_obj(db: AsyncSession) -> Cafeteria:
    return await create_test_cafeteria(
        db,
        name="Faculty Cafeteria Reports",
        cafeteria_type=CafeteriaType.FACULTY,
    )


@pytest_asyncio.fixture
async def manager_b_user(db: AsyncSession) -> User:
    """Manager assigned to the faculty cafeteria (for IDOR testing)."""
    return await create_test_user(
        db,
        first_name="Manager",
        last_name="B",
        university_id="MGR-B-001",
        university_email="manager.b@lgu.edu.pk",
        role=Role.CAFETERIA_MANAGER,
        category=UserCategory.FACULTY,
    )


@pytest_asyncio.fixture
async def manager_b_client(
    client: AsyncClient, manager_b_user: User, db: AsyncSession
) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, manager_b_user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    yield new_client
    await new_client.aclose()


async def _seed_orders(
    db: AsyncSession,
    *,
    cafeteria: Cafeteria,
    item: MenuItem,
    count: int = 5,
    status: OrderStatus = OrderStatus.COMPLETED,
    payment_status: PaymentStatus = PaymentStatus.SUCCEEDED,
    order_type: OrderType = OrderType.IMMEDIATE,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    days_ago: int = 0,
    with_prep_times: bool = False,
) -> list[Order]:
    """Create orders with payments for testing."""
    orders = []
    global _order_seq_counter
    for i in range(count):
        order_date = date.today() - timedelta(days=days_ago)
        order = Order(
            cafeteria_id=cafeteria.id,
            order_number=_order_seq_counter,
            user_id="00000000-0000-0000-0000-000000000001",
            order_type=order_type,
            payment_method=payment_method,
            status=status,
            total_amount=25000 * (i + 1),
            currency="PKR",
            order_date=order_date,
            collection_token=f"test_{_uuid.uuid4()}",
        )
        _order_seq_counter += 1
        db.add(order)
        await db.flush()

        # Add order item
        oi = OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            item_name=item.name,
            unit_price=item.price,
            quantity=i + 1,
            subtotal=item.price * (i + 1),
            currency="PKR",
        )
        db.add(oi)

        # Add payment
        payment = Payment(
            id=f"pay-{order.id}",
            order_id=order.id,
            user_id="00000000-0000-0000-0000-000000000001",  # dummy user
            amount=order.total_amount,
            currency="PKR",
            status=payment_status,
            idempotency_key=f"pay_{order.id}",
        )
        db.add(payment)

        # Set lifecycle timestamps if requested
        if with_prep_times and status == OrderStatus.COMPLETED:
            order.created_at = datetime.now(UTC) - timedelta(hours=2)
            order.preparation_started_at = datetime.now(UTC) - timedelta(hours=1, minutes=30)
            order.ready_at = datetime.now(UTC) - timedelta(hours=1)
            order.confirmed_at = datetime.now(UTC) - timedelta(hours=1, minutes=45)
            order.collected_at = datetime.now(UTC) - timedelta(minutes=45)
            order.eta_minutes = 30

        if status == OrderStatus.CANCELLED:
            order.cancelled_at = datetime.now(UTC)

        if status == OrderStatus.PENDING:
            pass  # no lifecycle timestamps

        orders.append(order)
    await db.flush()
    return orders


# ===========================================================================
# SALES REPORTS
# ===========================================================================


class TestSalesSummary:
    """GET /reports/sales"""

    @pytest.mark.asyncio
    async def test_empty_dataset(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_revenue"] == 0
        assert data["summary"]["total_orders"] == 0
        assert data["summary"]["total_refunded"] == 0
        assert data["summary"]["net_revenue"] == 0

    @pytest.mark.asyncio
    async def test_successful_revenue(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, price=50000)
        await _seed_orders(
            db,
            cafeteria=cafeteria,
            item=item,
            count=3,
            payment_status=PaymentStatus.SUCCEEDED,
        )

        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_orders"] == 3
        # Revenue = 25000*(1+2+3) = 150000
        assert data["summary"]["total_revenue"] == 150000

    @pytest.mark.asyncio
    async def test_failed_payment_excluded(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, price=50000)
        await _seed_orders(
            db,
            cafeteria=cafeteria,
            item=item,
            count=2,
            payment_status=PaymentStatus.SUCCEEDED,
        )
        await _seed_orders(
            db,
            cafeteria=cafeteria,
            item=item,
            count=1,
            payment_status=PaymentStatus.FAILED,
        )

        resp = await admin_client.get("/api/v1/reports/sales")
        data = resp.json()
        assert data["summary"]["total_orders"] == 2  # Only succeeded
        assert data["summary"]["total_revenue"] == 75000  # 25000*(1+2)

    @pytest.mark.asyncio
    async def test_refund_handling(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, price=50000)
        orders = await _seed_orders(
            db,
            cafeteria=cafeteria,
            item=item,
            count=1,
            payment_status=PaymentStatus.SUCCEEDED,
        )

        # Add a succeeded refund for the order
        refund = Refund(
            id=f"ref-{orders[0].id}",
            order_id=orders[0].id,
            payment_id=f"pay-{orders[0].id}",
            user_id="00000000-0000-0000-0000-000000000001",
            amount=25000,
            currency="PKR",
            status=RefundStatus.SUCCEEDED,
            reason=RefundReason.ORDER_CANCELLED,
            requested_by="00000000-0000-0000-0000-000000000001",
            idempotency_key=f"ref_{orders[0].id}",
        )
        db.add(refund)
        await db.flush()

        resp = await admin_client.get("/api/v1/reports/sales")
        data = resp.json()
        assert data["summary"]["total_revenue"] == 25000
        assert data["summary"]["total_refunded"] == 25000
        assert data["summary"]["net_revenue"] == 0

    @pytest.mark.asyncio
    async def test_date_filtering(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, price=50000)
        # Orders 5 days ago
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=2, days_ago=5)
        # Orders today
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=1, days_ago=0)

        today = date.today().isoformat()
        resp = await admin_client.get(f"/api/v1/reports/sales?start_date={today}&end_date={today}")
        data = resp.json()
        assert data["summary"]["total_orders"] == 1

    @pytest.mark.asyncio
    async def test_cafeteria_filtering(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria_obj: Cafeteria,
        faculty_cafeteria_obj: Cafeteria,
    ):
        item_s = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id, price=50000)
        item_f = await create_test_menu_item(db, cafeteria_id=faculty_cafeteria_obj.id, price=60000)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item_s, count=2)
        await _seed_orders(db, cafeteria=faculty_cafeteria_obj, item=item_f, count=3)

        resp = await admin_client.get(
            f"/api/v1/reports/sales?cafeteria_id={student_cafeteria_obj.id}"
        )
        data = resp.json()
        assert data["summary"]["total_orders"] == 2


class TestSalesDaily:
    """GET /reports/sales/daily"""

    @pytest.mark.asyncio
    async def test_empty_dataset(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/sales/daily")
        assert resp.status_code == 200
        assert resp.json()["rows"] == []

    @pytest.mark.asyncio
    async def test_daily_breakdown(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, price=50000)
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=2, days_ago=0)
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=1, days_ago=1)

        resp = await admin_client.get("/api/v1/reports/sales/daily")
        data = resp.json()
        assert len(data["rows"]) == 2
        # Today should have 2 orders, yesterday 1
        today_row = [r for r in data["rows"] if r["date"] == date.today().isoformat()]
        assert len(today_row) == 1
        assert today_row[0]["order_count"] == 2


class TestSalesByCafeteria:
    """GET /reports/sales/by-cafeteria"""

    @pytest.mark.asyncio
    async def test_empty_dataset(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/sales/by-cafeteria")
        assert resp.status_code == 200
        assert resp.json()["rows"] == []

    @pytest.mark.asyncio
    async def test_by_cafeteria(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria_obj: Cafeteria,
        faculty_cafeteria_obj: Cafeteria,
    ):
        item_s = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id, price=50000)
        item_f = await create_test_menu_item(db, cafeteria_id=faculty_cafeteria_obj.id, price=60000)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item_s, count=2)
        await _seed_orders(db, cafeteria=faculty_cafeteria_obj, item=item_f, count=1)

        resp = await admin_client.get("/api/v1/reports/sales/by-cafeteria")
        data = resp.json()
        assert len(data["rows"]) == 2
        # Find student cafeteria row
        s_row = [r for r in data["rows"] if r["cafeteria_id"] == student_cafeteria_obj.id]
        assert len(s_row) == 1
        assert s_row[0]["order_count"] == 2


# ===========================================================================
# ORDER ANALYTICS
# ===========================================================================


class TestOrderSummary:
    """GET /reports/orders/summary"""

    @pytest.mark.asyncio
    async def test_empty_dataset(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/orders/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 0
        assert data["cancellation_rate"] == 0.0
        assert data["completion_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_summary_counts(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        # 3 completed, 1 cancelled, 1 pending
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=3, status=OrderStatus.COMPLETED
        )
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=1, status=OrderStatus.CANCELLED
        )
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=1, status=OrderStatus.PENDING)

        resp = await admin_client.get("/api/v1/reports/orders/summary")
        data = resp.json()
        assert data["total_orders"] == 5
        assert data["status_breakdown"]["completed"] == 3
        assert data["status_breakdown"]["cancelled"] == 1
        assert data["status_breakdown"]["pending"] == 1
        assert data["cancellation_rate"] == 0.2
        assert data["completion_rate"] == 0.6

    @pytest.mark.asyncio
    async def test_immediate_vs_scheduled(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=3, order_type=OrderType.IMMEDIATE
        )
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=2, order_type=OrderType.SCHEDULED
        )

        resp = await admin_client.get("/api/v1/reports/orders/summary")
        data = resp.json()
        assert data["type_breakdown"]["immediate"] == 3
        assert data["type_breakdown"]["scheduled"] == 2

    @pytest.mark.asyncio
    async def test_cash_vs_online(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=2, payment_method=PaymentMethod.CASH
        )
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=3, payment_method=PaymentMethod.ONLINE
        )

        resp = await admin_client.get("/api/v1/reports/orders/summary")
        data = resp.json()
        assert data["payment_breakdown"]["cash"] == 2
        assert data["payment_breakdown"]["online"] == 3

    @pytest.mark.asyncio
    async def test_zero_denominator(self, admin_client: AsyncClient):
        """No orders → rates should be 0.0, no ZeroDivisionError."""
        resp = await admin_client.get("/api/v1/reports/orders/summary")
        data = resp.json()
        assert data["cancellation_rate"] == 0.0
        assert data["completion_rate"] == 0.0


class TestOrderVolume:
    """GET /reports/orders/volume"""

    @pytest.mark.asyncio
    async def test_empty_dataset(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/orders/volume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily"] == []
        assert data["hourly"] == []

    @pytest.mark.asyncio
    async def test_daily_volume(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=3, days_ago=0)
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=2, days_ago=1)

        resp = await admin_client.get("/api/v1/reports/orders/volume")
        data = resp.json()
        assert len(data["daily"]) == 2


class TestCancellationRate:
    """GET /reports/orders/cancellation-rate"""

    @pytest.mark.asyncio
    async def test_empty_dataset(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/reports/orders/cancellation-rate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 0
        assert data["cancellation_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_cancellation_calculation(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=4, status=OrderStatus.COMPLETED
        )
        await _seed_orders(
            db, cafeteria=cafeteria, item=item, count=1, status=OrderStatus.CANCELLED
        )

        resp = await admin_client.get("/api/v1/reports/orders/cancellation-rate")
        data = resp.json()
        assert data["total_orders"] == 5
        assert data["cancelled_orders"] == 1
        assert data["cancellation_rate"] == 0.2


# ===========================================================================
# CAFETERIA PERFORMANCE
# ===========================================================================


class TestCafeteriaPerformance:
    """GET /reports/cafeteria/{cafeteria_id}/performance"""

    @pytest.mark.asyncio
    async def test_empty_cafeteria(
        self, admin_client: AsyncClient, student_cafeteria_obj: Cafeteria
    ):
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/performance"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 0
        assert data["completion_rate"] == 0.0
        assert data["cancellation_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_lifecycle_metrics(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        await _seed_orders(
            db,
            cafeteria=cafeteria,
            item=item,
            count=3,
            status=OrderStatus.COMPLETED,
            with_prep_times=True,
        )
        await _seed_orders(
            db,
            cafeteria=cafeteria,
            item=item,
            count=1,
            status=OrderStatus.CANCELLED,
        )

        resp = await admin_client.get(f"/api/v1/reports/cafeteria/{cafeteria.id}/performance")
        data = resp.json()
        assert data["total_orders"] == 4
        assert data["completed_orders"] == 3
        assert data["cancelled_orders"] == 1
        assert data["completion_rate"] == 0.75
        assert data["cancellation_rate"] == 0.25
        assert data["avg_preparation_time_minutes"] is not None
        assert data["avg_time_to_ready_minutes"] is not None

    @pytest.mark.asyncio
    async def test_nonexistent_cafeteria(self, admin_client: AsyncClient):
        resp = await admin_client.get("/reports/cafeteria/nonexistent-id/performance")
        assert resp.status_code in (404, 422)


class TestCafeteriaPopularItems:
    """GET /reports/cafeteria/{cafeteria_id}/popular-items"""

    @pytest.mark.asyncio
    async def test_empty_cafeteria(
        self, admin_client: AsyncClient, student_cafeteria_obj: Cafeteria
    ):
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/popular-items"
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    @pytest.mark.asyncio
    async def test_popularity_ranking(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item1 = await create_test_menu_item(
            db, cafeteria_id=cafeteria.id, name="Biryani", price=50000
        )
        item2 = await create_test_menu_item(
            db, cafeteria_id=cafeteria.id, name="Burger", price=30000
        )

        # Create orders with different quantities
        for _ in range(3):
            await _seed_orders(
                db, cafeteria=cafeteria, item=item1, count=1, payment_status=PaymentStatus.SUCCEEDED
            )
        await _seed_orders(
            db, cafeteria=cafeteria, item=item2, count=1, payment_status=PaymentStatus.SUCCEEDED
        )

        resp = await admin_client.get(f"/api/v1/reports/cafeteria/{cafeteria.id}/popular-items")
        data = resp.json()
        assert len(data["items"]) == 2
        # Biryani should be first (more quantity)
        assert data["items"][0]["item_name"] == "Biryani"


class TestCafeteriaPeakHours:
    """GET /reports/cafeteria/{cafeteria_id}/peak-hours"""

    @pytest.mark.asyncio
    async def test_empty_cafeteria(
        self, admin_client: AsyncClient, student_cafeteria_obj: Cafeteria
    ):
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/peak-hours"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hours"] == []
        assert data["cafeteria_id"] == student_cafeteria_obj.id

    @pytest.mark.asyncio
    async def test_peak_hours_data(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        await _seed_orders(db, cafeteria=cafeteria, item=item, count=5)

        resp = await admin_client.get(f"/api/v1/reports/cafeteria/{cafeteria.id}/peak-hours")
        data = resp.json()
        assert "timezone" in data
        assert len(data["hours"]) >= 1


# ===========================================================================
# INVENTORY REPORTS
# ===========================================================================


class TestInventoryStockLevels:
    """GET /reports/cafeteria/{cafeteria_id}/inventory/stock-levels"""

    @pytest.mark.asyncio
    async def test_empty_inventory(
        self, admin_client: AsyncClient, student_cafeteria_obj: Cafeteria
    ):
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/inventory/stock-levels"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 0
        assert data["out_of_stock_count"] == 0
        assert data["low_stock_count"] == 0

    @pytest.mark.asyncio
    async def test_stock_levels(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item1 = await create_test_menu_item(db, cafeteria_id=cafeteria.id, name="Rice")
        item2 = await create_test_menu_item(db, cafeteria_id=cafeteria.id, name="Chicken")
        item3 = await create_test_menu_item(db, cafeteria_id=cafeteria.id, name="Oil")

        # Normal stock
        inv1 = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item1.id,
            quantity=50,
            unit=InventoryUnit.PIECES,
            low_threshold=10,
        )
        # Low stock
        inv2 = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item2.id,
            quantity=5,
            unit=InventoryUnit.KG,
            low_threshold=10,
        )
        # Out of stock
        inv3 = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item3.id,
            quantity=0,
            unit=InventoryUnit.LITERS,
            low_threshold=5,
        )
        db.add_all([inv1, inv2, inv3])
        await db.flush()

        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{cafeteria.id}/inventory/stock-levels"
        )
        data = resp.json()
        assert data["total_items"] == 3
        assert data["out_of_stock_count"] == 1
        assert data["low_stock_count"] == 1


class TestInventoryLowStock:
    """GET /reports/cafeteria/{cafeteria_id}/inventory/low-stock"""

    @pytest.mark.asyncio
    async def test_no_low_stock(self, admin_client: AsyncClient, student_cafeteria_obj: Cafeteria):
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/inventory/low-stock"
        )
        assert resp.status_code == 200
        assert resp.json()["total_low_stock"] == 0

    @pytest.mark.asyncio
    async def test_low_stock_items(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item1 = await create_test_menu_item(db, cafeteria_id=cafeteria.id, name="Rice")
        item2 = await create_test_menu_item(db, cafeteria_id=cafeteria.id, name="Chicken")

        inv1 = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item1.id,
            quantity=3,
            unit=InventoryUnit.KG,
            low_threshold=10,
        )
        inv2 = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item2.id,
            quantity=0,
            unit=InventoryUnit.PIECES,
            low_threshold=5,
        )
        db.add_all([inv1, inv2])
        await db.flush()

        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{cafeteria.id}/inventory/low-stock"
        )
        data = resp.json()
        assert data["total_low_stock"] == 2
        statuses = {i["stock_status"] for i in data["items"]}
        assert "low_stock" in statuses
        assert "out_of_stock" in statuses


class TestInventoryTurnover:
    """GET /reports/cafeteria/{cafeteria_id}/inventory/turnover"""

    @pytest.mark.asyncio
    async def test_empty_adjustments(
        self, admin_client: AsyncClient, student_cafeteria_obj: Cafeteria
    ):
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/inventory/turnover"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_adjustments"] == 0
        assert data["total_restock"] == 0
        assert data["total_usage"] == 0

    @pytest.mark.asyncio
    async def test_adjustment_activity(
        self, admin_client: AsyncClient, db: AsyncSession, student_cafeteria_obj: Cafeteria
    ):
        cafeteria = student_cafeteria_obj
        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id, name="Rice")

        inv = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item.id,
            quantity=50,
            unit=InventoryUnit.KG,
            low_threshold=10,
        )
        db.add(inv)
        await db.flush()

        # Restock +20
        adj1 = InventoryAdjustment(
            inventory_item_id=inv.id,
            adjustment_quantity=20,
            reason="Restock",
        )
        # Usage -5
        adj2 = InventoryAdjustment(
            inventory_item_id=inv.id,
            adjustment_quantity=-5,
            reason="Daily usage",
        )
        db.add_all([adj1, adj2])
        await db.flush()

        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{cafeteria.id}/inventory/turnover"
        )
        data = resp.json()
        assert data["total_adjustments"] == 2
        assert data["total_restock"] == 20
        assert data["total_usage"] == 5
        assert len(data["adjustments"]) == 2


# ===========================================================================
# AUTHORIZATION
# ===========================================================================


class TestAuthorization:
    """Cross-role authorization tests for all report endpoints."""

    @pytest.mark.asyncio
    async def test_unauthenticated_denied(self, client: AsyncClient):
        """Unauthenticated requests should be rejected."""
        resp = await client.get("/api/v1/reports/sales")
        assert resp.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_student_denied(self, student_client: AsyncClient):
        """Students must not access reporting endpoints."""
        resp = await student_client.get("/api/v1/reports/sales")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_faculty_denied(self, faculty_client: AsyncClient):
        """Faculty must not access reporting endpoints."""
        resp = await faculty_client.get("/api/v1/reports/sales")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_own_cafeteria(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
        student_cafeteria_obj: Cafeteria,
    ):
        """Manager accessing own cafeteria report should succeed."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria_obj.id, Role.CAFETERIA_MANAGER
        )
        item = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item, count=1)

        resp = await manager_client.get(
            f"/api/v1/reports/sales?cafeteria_id={student_cafeteria_obj.id}"
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_manager_other_cafeteria_denied(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
        student_cafeteria_obj: Cafeteria,
        faculty_cafeteria_obj: Cafeteria,
    ):
        """Manager accessing another cafeteria's report must be rejected."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria_obj.id, Role.CAFETERIA_MANAGER
        )
        resp = await manager_client.get(
            f"/api/v1/reports/sales?cafeteria_id={faculty_cafeteria_obj.id}"
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_own_cafeteria(
        self,
        staff_client: AsyncClient,
        db: AsyncSession,
        staff_user: User,
        student_cafeteria_obj: Cafeteria,
    ):
        """Staff accessing own cafeteria report should succeed."""
        await assign_user_to_cafeteria(
            db, staff_user.id, student_cafeteria_obj.id, Role.CAFETERIA_STAFF
        )
        item = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item, count=1)

        resp = await staff_client.get(
            f"/api/v1/reports/sales?cafeteria_id={student_cafeteria_obj.id}"
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_staff_cross_cafeteria_denied(
        self,
        staff_client: AsyncClient,
        db: AsyncSession,
        staff_user: User,
        student_cafeteria_obj: Cafeteria,
        faculty_cafeteria_obj: Cafeteria,
    ):
        """Staff accessing another cafeteria must be rejected."""
        await assign_user_to_cafeteria(
            db, staff_user.id, student_cafeteria_obj.id, Role.CAFETERIA_STAFF
        )
        resp = await staff_client.get(
            f"/api/v1/reports/sales?cafeteria_id={faculty_cafeteria_obj.id}"
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_cafeteria_performance_idor(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
        student_cafeteria_obj: Cafeteria,
        faculty_cafeteria_obj: Cafeteria,
    ):
        """Manager trying to access another cafeteria's performance must be rejected."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria_obj.id, Role.CAFETERIA_MANAGER
        )
        resp = await manager_client.get(
            f"/api/v1/reports/cafeteria/{faculty_cafeteria_obj.id}/performance"
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_student_denied_cafeteria_performance(
        self,
        student_client: AsyncClient,
        student_cafeteria_obj: Cafeteria,
    ):
        """Student must not access cafeteria performance reports."""
        resp = await student_client.get(
            f"/api/v1/reports/cafeteria/{student_cafeteria_obj.id}/performance"
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_cross_cafeteria_ok(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria_obj: Cafeteria,
        faculty_cafeteria_obj: Cafeteria,
    ):
        """Admin should access any cafeteria's reports."""
        resp = await admin_client.get(
            f"/api/v1/reports/cafeteria/{faculty_cafeteria_obj.id}/performance"
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sales_by_cafeteria_admin_only(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
        student_cafeteria_obj: Cafeteria,
    ):
        """Sales by cafeteria is admin-only. Manager should be denied."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria_obj.id, Role.CAFETERIA_MANAGER
        )
        resp = await manager_client.get("/api/v1/reports/sales/by-cafeteria")
        assert resp.status_code == 403


# ===========================================================================
# EXISTING TESTS UNAFFECTED
# ===========================================================================


class TestExistingTestsUnaffected:
    """Verify report endpoints don't break existing functionality."""

    @pytest.mark.asyncio
    async def test_health_still_works(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_still_works(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "university_email": "nonexistent@lgu.edu.pk",
                "password": "whatever",
            },
        )
        # Should get 401, not 500
        assert resp.status_code in (401, 422)


# ===========================================================================
# Phase 27: Non-Payment Release Readiness — Query-Scoped Report Tests
# ===========================================================================


@pytest.mark.asyncio
class TestQueryScopedReportResolution:
    """Phase 27 fix: omitted cafeteria_id no longer yields university-wide data."""

    async def test_manager_single_assignment_defaults_to_own_cafeteria(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
        student_cafeteria_obj: Cafeteria,
    ):
        """Manager with one assignment gets their cafeteria scope automatically."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria_obj.id, Role.CAFETERIA_MANAGER
        )
        item = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item, count=1)

        resp = await manager_client.get("/api/v1/reports/sales")
        assert resp.status_code == 200

    async def test_manager_unassigned_denied_when_omitted(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
    ):
        """Manager with no assignment cannot pull any report scope."""
        resp = await manager_client.get("/api/v1/reports/sales")
        assert resp.status_code == 403

    async def test_staff_single_assignment_defaults_to_own_cafeteria(
        self,
        staff_client: AsyncClient,
        db: AsyncSession,
        staff_user: User,
        student_cafeteria_obj: Cafeteria,
    ):
        """Staff with one assignment gets their cafeteria scope automatically."""
        await assign_user_to_cafeteria(
            db, staff_user.id, student_cafeteria_obj.id, Role.CAFETERIA_STAFF
        )
        item = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item, count=1)

        resp = await staff_client.get("/api/v1/reports/orders/summary")
        assert resp.status_code == 200

    async def test_admin_omitted_cafeteria_id_still_university_wide(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
        student_cafeteria_obj: Cafeteria,
    ):
        """Control: admin retains the university-wide view when omitted."""
        resp = await admin_client.get("/api/v1/reports/sales")
        assert resp.status_code == 200

    async def test_all_five_query_scoped_endpoints_resolved(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
        manager_user: User,
        student_cafeteria_obj: Cafeteria,
    ):
        """Every query-scoped endpoint resolves scope for a single-assignment manager."""
        await assign_user_to_cafeteria(
            db, manager_user.id, student_cafeteria_obj.id, Role.CAFETERIA_MANAGER
        )
        item = await create_test_menu_item(db, cafeteria_id=student_cafeteria_obj.id)
        await _seed_orders(db, cafeteria=student_cafeteria_obj, item=item, count=1)

        for path in (
            "/api/v1/reports/sales",
            "/api/v1/reports/sales/daily",
            "/api/v1/reports/orders/summary",
            "/api/v1/reports/orders/volume",
            "/api/v1/reports/orders/cancellation-rate",
        ):
            resp = await manager_client.get(path)
            assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text[:200]}"
