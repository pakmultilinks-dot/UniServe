"""Phase 44 — Product Completeness & UX Hardening regression tests.

Covers:
- P3-8: generic update_status('preparing') delegates to start_preparation
  (sets preparation_started_at, same business gates as POST /prepare)
- P3-14: scheduled PENDING order auto-expiry (Phase 2 of the pickup
  expiry worker — grace window, inventory release, cancellation + event)
- WS4: daily-menu unpublish (archive, published-lookup exclusion,
  replacement draft for the same date, only-published gate, staff RBAC,
  foreign-cafeteria denial)
- P3-3: GET /auth/me/cafeterias assignment discovery (web console
  assignment-aware cafeteria selectors)
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.modules.cafeterias.models import CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import DailyMenuStatus
from app.modules.orders.models import (
    Order,
    OrderEvent,
    OrderEventType,
    OrderItem,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.orders.service import (
    SCHEDULED_EXPIRY_GRACE_MINUTES,
    OrderService,
)
from app.modules.users.models import Role, User
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_daily_menu,
    create_test_menu_item,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_scheduled_pending_order(
    db: AsyncSession,
    *,
    user: User,
    cafeteria_id: str,
    slot_local: datetime,
    order_number: int = 7001,
    status: OrderStatus = OrderStatus.PENDING,
    inventory_reserved: bool = False,
) -> Order:
    """Insert a scheduled order with its collection slot at a local time.

    ``slot_local`` must be tz-aware (Asia/Karachi); the order date and the
    ``HH:MM`` slot string are derived from it, which keeps the test correct
    even when the slot falls on the previous/next calendar day (near
    midnight).
    """
    order = Order(
        order_number=order_number,
        user_id=user.id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.SCHEDULED,
        payment_method=PaymentMethod.CASH,
        status=status,
        total_amount=25000,
        currency="PKR",
        order_date=slot_local.date(),
        scheduled_collection_time=slot_local.strftime("%H:%M"),
        inventory_reserved=inventory_reserved,
    )
    db.add(order)
    await db.flush()
    return order


async def _get_manager(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_MANAGER))
    return result.scalar_one()


# ===========================================================================
# P3-8 — generic update_status → preparing delegates to start_preparation
# ===========================================================================


class TestP38GenericPreparingDelegation:
    """The generic status endpoint must not be a weaker path into PREPARING."""

    @pytest.mark.asyncio
    async def test_generic_update_status_sets_preparation_lifecycle(
        self,
        db: AsyncSession,
        student_user: User,
        staff_user: User,
    ):
        """PENDING → PREPARING via update_status sets preparation_started_at
        and records a PREPARATION_STARTED event (same as POST /prepare)."""
        cafeteria = await create_test_cafeteria(
            db, name="P38 Cafeteria", cafeteria_type=CafeteriaType.STUDENT
        )
        order = Order(
            order_number=7100,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.PENDING,
            confirmed_at=datetime.now(UTC),
            total_amount=25000,
            currency="PKR",
            order_date=date.today(),
            inventory_reserved=False,
        )
        db.add(order)
        await db.flush()

        service = OrderService(db)
        updated = await service.update_status(
            order_id=order.id,
            new_status="preparing",
            actor_id=staff_user.id,
        )

        assert updated.status == OrderStatus.PREPARING
        assert updated.preparation_started_at is not None
        assert updated.preparation_started is True

        event_result = await db.execute(
            select(OrderEvent).where(
                OrderEvent.order_id == order.id,
                OrderEvent.event_type == OrderEventType.PREPARATION_STARTED,
            )
        )
        assert event_result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_generic_update_status_preparing_requires_confirmation(
        self,
        db: AsyncSession,
        student_user: User,
        staff_user: User,
    ):
        """The delegation keeps start_preparation's confirmation gate."""
        cafeteria = await create_test_cafeteria(db, name="P38 Gate Cafeteria")
        order = Order(
            order_number=7101,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.PENDING,
            confirmed_at=None,
            total_amount=25000,
            currency="PKR",
            order_date=date.today(),
            inventory_reserved=False,
        )
        db.add(order)
        await db.flush()

        service = OrderService(db)
        with pytest.raises(ValidationError):
            await service.update_status(
                order_id=order.id,
                new_status="preparing",
                actor_id=staff_user.id,
            )

        await db.refresh(order)
        assert order.status == OrderStatus.PENDING
        assert order.preparation_started_at is None

    @pytest.mark.asyncio
    async def test_generic_update_status_ready_sets_ready_invariants(
        self,
        db: AsyncSession,
        student_user: User,
        staff_user: User,
    ):
        """PREPARING → READY via update_status delegates to mark_ready and
        sets ready_at + pickup_deadline."""
        cafeteria = await create_test_cafeteria(db, name="P38 Ready Cafeteria")
        now = datetime.now(UTC)
        order = Order(
            order_number=7102,
            user_id=student_user.id,
            cafeteria_id=cafeteria.id,
            order_type=OrderType.IMMEDIATE,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.PREPARING,
            confirmed_at=now - timedelta(minutes=10),
            preparation_started_at=now - timedelta(minutes=5),
            preparation_started=True,
            total_amount=25000,
            currency="PKR",
            order_date=date.today(),
            inventory_reserved=True,
        )
        db.add(order)
        await db.flush()

        service = OrderService(db)
        updated = await service.update_status(
            order_id=order.id,
            new_status="ready",
            actor_id=staff_user.id,
        )

        assert updated.status == OrderStatus.READY
        assert updated.ready_at is not None
        assert updated.pickup_deadline is not None


# ===========================================================================
# P3-14 — scheduled PENDING order auto-expiry (Phase 2)
# ===========================================================================


class TestP314ScheduledOrderAutoExpiry:
    """process_expired_pickups must cancel scheduled PENDING orders whose
    collection slot + grace window have passed."""

    @pytest.mark.asyncio
    async def test_scheduled_pending_order_past_slot_and_grace_is_cancelled(
        self,
        db: AsyncSession,
        student_user: User,
    ):
        """Past slot + grace → cancelled, inventory released, event recorded."""
        cafeteria = await create_test_cafeteria(
            db, name="Expiry Cafeteria", cafeteria_type=CafeteriaType.STUDENT
        )
        now_local = datetime.now(ZoneInfo("Asia/Karachi"))
        slot = now_local - timedelta(minutes=SCHEDULED_EXPIRY_GRACE_MINUTES + 60)
        order = await _insert_scheduled_pending_order(
            db,
            user=student_user,
            cafeteria_id=cafeteria.id,
            slot_local=slot,
        )

        item = await create_test_menu_item(db, cafeteria_id=cafeteria.id)
        inv = InventoryItem(
            cafeteria_id=cafeteria.id,
            menu_item_id=item.id,
            quantity=50,
            unit=InventoryUnit.PIECES,
        )
        db.add(inv)
        await db.flush()
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=item.id,
                item_name=item.name,
                unit_price=item.price,
                quantity=2,
                subtotal=item.price * 2,
            )
        )
        order.inventory_reserved = True
        await db.flush()

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["scheduled_examined"] == 1
        assert stats["scheduled_expired"] == 1

        await db.refresh(order)
        assert order.status == OrderStatus.CANCELLED
        assert order.cancelled_at is not None
        assert order.cancellation_reason is not None
        assert "Automatic expiry" in order.cancellation_reason
        assert order.inventory_reserved is False

        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.id == inv.id)
        )
        inv_row = inv_result.scalar_one()
        assert inv_row.quantity == 52

        event_result = await db.execute(
            select(OrderEvent).where(
                OrderEvent.order_id == order.id,
                OrderEvent.event_type == OrderEventType.CANCELLED,
            )
        )
        assert event_result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_scheduled_pending_order_inside_grace_is_untouched(
        self,
        db: AsyncSession,
        student_user: User,
    ):
        """Inside slot + grace window → left for staff to confirm."""
        cafeteria = await create_test_cafeteria(db, name="Grace Cafeteria")
        now_local = datetime.now(ZoneInfo("Asia/Karachi"))
        slot = now_local + timedelta(minutes=5)  # well within the grace window
        order = await _insert_scheduled_pending_order(
            db,
            user=student_user,
            cafeteria_id=cafeteria.id,
            slot_local=slot,
        )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["scheduled_examined"] == 1
        assert stats["scheduled_expired"] == 0

        await db.refresh(order)
        assert order.status == OrderStatus.PENDING
        assert order.cancelled_at is None

    @pytest.mark.asyncio
    async def test_completed_and_cancelled_scheduled_orders_untouched(
        self,
        db: AsyncSession,
        student_user: User,
    ):
        """Only PENDING scheduled orders are candidates — completed and
        already-cancelled orders past their slot are never reprocessed."""
        cafeteria = await create_test_cafeteria(db, name="NonPending Cafeteria")
        now_local = datetime.now(ZoneInfo("Asia/Karachi"))
        slot = now_local - timedelta(minutes=120)

        completed = await _insert_scheduled_pending_order(
            db,
            user=student_user,
            cafeteria_id=cafeteria.id,
            slot_local=slot,
            order_number=7201,
            status=OrderStatus.COMPLETED,
        )
        cancelled = await _insert_scheduled_pending_order(
            db,
            user=student_user,
            cafeteria_id=cafeteria.id,
            slot_local=slot,
            order_number=7202,
            status=OrderStatus.CANCELLED,
        )

        service = OrderService(db)
        stats = await service.process_expired_pickups()

        assert stats["scheduled_examined"] == 0
        assert stats["scheduled_expired"] == 0

        await db.refresh(completed)
        await db.refresh(cancelled)
        assert completed.status == OrderStatus.COMPLETED
        assert cancelled.status == OrderStatus.CANCELLED
        assert cancelled.cancelled_at is None


# ===========================================================================
# WS4 — daily-menu unpublish
# ===========================================================================


class TestDailyMenuUnpublish:
    """Unpublish archives the menu, removes it from published lookups, and
    frees the same-date slot for a replacement draft."""

    @pytest.mark.asyncio
    async def test_unpublish_archives_menu_and_clears_today_lookup(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
    ):
        """Published → unpublish → archived and absent from /today."""
        caf = await create_test_cafeteria(db)
        mgr = await _get_manager(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        today = date.today().isoformat()
        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/",
            json={"menu_date": today},
        )
        assert resp.status_code == 201, resp.text
        menu_id = resp.json()["id"]

        item = await create_test_menu_item(db, cafeteria_id=caf.id)
        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/items",
            json={"menu_item_id": item.id},
        )
        assert resp.status_code == 200, resp.text
        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/publish"
        )
        assert resp.status_code == 200, resp.text

        # Published menu is visible in today's lookup
        resp = await manager_client.get(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/today"
        )
        assert resp.status_code == 200
        assert resp.json() is not None

        # Unpublish → archived
        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/unpublish"
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "archived"

        # Archived menu no longer shadows today's published lookup
        resp = await manager_client.get(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/today"
        )
        assert resp.status_code == 200
        assert resp.json() is None

    @pytest.mark.asyncio
    async def test_replacement_draft_can_be_created_after_unpublish(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
    ):
        """Archived menus do not block a new draft for the same date."""
        caf = await create_test_cafeteria(db)
        mgr = await _get_manager(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        today = date.today().isoformat()
        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/",
            json={"menu_date": today},
        )
        assert resp.status_code == 201, resp.text
        menu_id = resp.json()["id"]

        item = await create_test_menu_item(db, cafeteria_id=caf.id)
        await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/items",
            json={"menu_item_id": item.id},
        )
        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/publish"
        )
        assert resp.status_code == 200, resp.text
        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/unpublish"
        )
        assert resp.status_code == 200, resp.text

        # Replacement draft for the same date succeeds (uniqueness excludes
        # archived menus)
        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/",
            json={"menu_date": today},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "draft"

    @pytest.mark.asyncio
    async def test_unpublish_draft_menu_rejected(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
    ):
        """Only published menus can be unpublished."""
        caf = await create_test_cafeteria(db)
        mgr = await _get_manager(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/",
            json={"menu_date": date.today().isoformat()},
        )
        assert resp.status_code == 201, resp.text
        menu_id = resp.json()["id"]

        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/unpublish"
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_staff_cannot_unpublish_daily_menu(
        self,
        staff_client: AsyncClient,
        manager_client: AsyncClient,
        db: AsyncSession,
    ):
        """Assigned staff are read-only on daily menus (server-side RBAC)."""
        caf = await create_test_cafeteria(db)
        staff = (
            await db.execute(select(User).where(User.role == Role.CAFETERIA_STAFF))
        ).scalar_one()
        await assign_user_to_cafeteria(db, staff.id, caf.id, role=Role.CAFETERIA_STAFF)

        # Manager creates + publishes a menu for today
        mgr = await _get_manager(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)
        today = date.today().isoformat()
        resp = await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/",
            json={"menu_date": today},
        )
        assert resp.status_code == 201, resp.text
        menu_id = resp.json()["id"]
        item = await create_test_menu_item(db, cafeteria_id=caf.id)
        await manager_client.post(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/items",
            json={"menu_item_id": item.id},
        )
        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/publish"
        )
        assert resp.status_code == 200, resp.text

        # Assigned staff still cannot unpublish — RBAC is server-side
        resp = await staff_client.patch(
            f"/api/v1/cafeterias/{caf.id}/daily-menus/{menu_id}/unpublish"
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_cannot_unpublish_foreign_menu(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
    ):
        """Cafeteria write scope holds for unpublish too."""
        own = await create_test_cafeteria(db, name="Own Cafeteria")
        foreign = await create_test_cafeteria(db, name="Foreign Cafeteria")
        mgr = await _get_manager(db)
        await assign_user_to_cafeteria(db, mgr.id, own.id)

        menu = await create_test_daily_menu(db, cafeteria_id=foreign.id)

        resp = await manager_client.patch(
            f"/api/v1/cafeterias/{foreign.id}/daily-menus/{menu.id}/unpublish"
        )
        assert resp.status_code == 403


# ===========================================================================
# P3-3 — GET /auth/me/cafeterias
# ===========================================================================


class TestMyCafeteriasEndpoint:
    """Assignment discovery for the web console's cafeteria selectors."""

    @pytest.mark.asyncio
    async def test_manager_returns_assigned_cafeteria_ids(
        self,
        manager_client: AsyncClient,
        db: AsyncSession,
    ):
        caf = await create_test_cafeteria(db)
        mgr = await _get_manager(db)
        await assign_user_to_cafeteria(db, mgr.id, caf.id)

        resp = await manager_client.get("/api/v1/auth/me/cafeterias")
        assert resp.status_code == 200
        assert resp.json() == {"cafeteria_ids": [caf.id]}

    @pytest.mark.asyncio
    async def test_staff_returns_assigned_id(
        self,
        staff_client: AsyncClient,
        db: AsyncSession,
    ):
        """Staff returns their own cafeteria assignment (one per user)."""
        caf = await create_test_cafeteria(db, name="Staff Caf")
        staff = (
            await db.execute(select(User).where(User.role == Role.CAFETERIA_STAFF))
        ).scalar_one()
        await assign_user_to_cafeteria(db, staff.id, caf.id, role=Role.CAFETERIA_STAFF)

        resp = await staff_client.get("/api/v1/auth/me/cafeterias")
        assert resp.status_code == 200
        assert resp.json() == {"cafeteria_ids": [caf.id]}

    @pytest.mark.asyncio
    async def test_admin_returns_empty_list(
        self,
        admin_client: AsyncClient,
        db: AsyncSession,
    ):
        """Admins select any cafeteria — no assignments of their own."""
        resp = await admin_client.get("/api/v1/auth/me/cafeterias")
        assert resp.status_code == 200
        assert resp.json() == {"cafeteria_ids": []}

    @pytest.mark.asyncio
    async def test_student_returns_empty_list(
        self,
        student_client: AsyncClient,
        db: AsyncSession,
    ):
        resp = await student_client.get("/api/v1/auth/me/cafeterias")
        assert resp.status_code == 200
        assert resp.json() == {"cafeteria_ids": []}
