"""Tests for ORDER_AUTO_ACCEPT — automatic order acceptance.

When the flag is on, an immediate cash order must go PENDING → PREPARING
at checkout (confirmed_at set, ETA computed) so the customer sees progress
without staff intervention. When off (default), orders stay PENDING for
the manual staff workflow — covered by test_order_operations.py.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.orders.models import Order, OrderStatus
from app.modules.orders.service import OrderService
from app.modules.users.models import Role, User
from tests.conftest import assign_user_to_cafeteria
from tests.test_order_operations import (
    _add_cart_item,
    _checkout,
    _setup_order_test_data,
)


async def _create_pending_order(
    student_client: AsyncClient,
    db: AsyncSession,
    student_user: User,
    manager_user: User,
    staff_user: User,
) -> dict:
    """Build a fresh immediate cash order (flag off → stays PENDING)."""
    cafeteria, item, _ = await _setup_order_test_data(db)
    await assign_user_to_cafeteria(
        db, manager_user.id, cafeteria.id, Role.CAFETERIA_MANAGER
    )
    await assign_user_to_cafeteria(
        db, staff_user.id, cafeteria.id, Role.CAFETERIA_STAFF
    )
    await _add_cart_item(student_client, cafeteria.id, item.id, quantity=1)
    resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
class TestOrderAutoAccept:
    """Auto-acceptance behaviour under ORDER_AUTO_ACCEPT."""

    async def test_cash_order_auto_accepted_when_enabled(
        self,
        student_client: AsyncClient,
        student_user: User,
        db: AsyncSession,
        monkeypatch,
    ):
        """Flag on: immediate cash order lands in PREPARING with ETA."""
        monkeypatch.setattr(settings, "ORDER_AUTO_ACCEPT", True)

        cafeteria, item, _ = await _setup_order_test_data(db)
        await _add_cart_item(student_client, cafeteria.id, item.id, quantity=1)
        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        assert resp.status_code == 201, resp.text
        data = resp.json()

        assert data["status"] == OrderStatus.PREPARING.value
        assert data["confirmed_at"] is not None
        assert data["preparation_started_at"] is not None
        assert data["eta_minutes"] is not None

    async def test_cash_order_stays_pending_when_disabled(
        self,
        student_client: AsyncClient,
        student_user: User,
        manager_user: User,
        staff_user: User,
        db: AsyncSession,
        monkeypatch,
    ):
        """Flag off (default): manual staff workflow preserved."""
        monkeypatch.setattr(settings, "ORDER_AUTO_ACCEPT", False)

        data = await _create_pending_order(
            student_client, db, student_user, manager_user, staff_user
        )

        assert data["status"] == OrderStatus.PENDING.value
        assert data["confirmed_at"] is None
        assert data["preparation_started_at"] is None

    async def test_worker_sweep_backfills_stale_pending_orders(
        self,
        student_client: AsyncClient,
        student_user: User,
        manager_user: User,
        staff_user: User,
        db: AsyncSession,
        monkeypatch,
    ):
        """Flag on: the background sweep auto-accepts a PENDING order
        that was created while the flag was off (e.g. online order whose
        payment just succeeded)."""
        from app.modules.orders.service import OrderService

        monkeypatch.setattr(settings, "ORDER_AUTO_ACCEPT", False)
        data = await _create_pending_order(
            student_client, db, student_user, manager_user, staff_user
        )

        # Flip the flag on and run the worker sweep
        monkeypatch.setattr(settings, "ORDER_AUTO_ACCEPT", True)
        service = OrderService(db)
        stats = await service.process_expired_pickups()
        await db.commit()

        assert stats["auto_accepted"] >= 1

        result = await db.execute(select(Order).where(Order.id == data["id"]))
        order = result.scalar_one()
        assert order.status == OrderStatus.PREPARING
        assert order.confirmed_at is not None
        assert order.eta_minutes is not None