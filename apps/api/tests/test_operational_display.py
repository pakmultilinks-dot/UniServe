"""Names and active inventory on authorized cafeteria operational surfaces."""

from datetime import date

import pytest
from sqlalchemy import event

from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.orders.models import Order, OrderStatus, OrderType, PaymentMethod
from tests.conftest import assign_user_to_cafeteria, create_test_cafeteria, create_test_menu_item


@pytest.mark.asyncio
async def test_assigned_manager_gets_customer_name_without_profile_access(
    manager_client, manager_user, student_user, db
):
    cafe = await create_test_cafeteria(db)
    await assign_user_to_cafeteria(db, manager_user.id, cafe.id)
    order = Order(
        order_number=98501,
        user_id=student_user.id,
        cafeteria_id=cafe.id,
        order_type=OrderType.IMMEDIATE,
        payment_method=PaymentMethod.CASH,
        status=OrderStatus.READY,
        total_amount=22000,
        order_date=date.today(),
    )
    db.add(order)
    await db.flush()

    response = await manager_client.get(f"/api/v1/orders/{order.id}")
    assert response.status_code == 200
    assert response.json()["customer_name"] == f"{student_user.first_name} {student_user.last_name}"
    assert "university_email" not in response.json()
    queue = await manager_client.get(f"/api/v1/orders/cafeteria/{cafe.id}")
    assert queue.status_code == 200
    assert queue.json()["orders"][0]["customer_name"] == response.json()["customer_name"]

    other_cafe = await create_test_cafeteria(db, name="Unassigned")
    order.cafeteria_id = other_cafe.id
    await db.flush()
    denied = await manager_client.get(f"/api/v1/orders/{order.id}")
    assert denied.status_code == 403
    assert "customer_name" not in denied.json()


@pytest.mark.asyncio
async def test_inventory_names_are_in_response_and_retired_items_are_excluded(
    manager_client, manager_user, db
):
    cafe = await create_test_cafeteria(db)
    await assign_user_to_cafeteria(db, manager_user.id, cafe.id)
    active = await create_test_menu_item(db, cafeteria_id=cafe.id, name="Fresh lunch")
    retired = await create_test_menu_item(db, cafeteria_id=cafe.id, name="Retired test item")
    retired.is_active = False
    for item in (active, retired):
        db.add(
            InventoryItem(
                cafeteria_id=cafe.id,
                menu_item_id=item.id,
                quantity=0,
                unit=InventoryUnit.PORTIONS,
                low_threshold=10,
            )
        )
    await db.flush()
    for suffix in ("/", "/low-stock"):
        response = await manager_client.get(f"/api/v1/cafeterias/{cafe.id}/inventory{suffix}")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["menu_item_name"] == "Fresh lunch"
        assert body["items"][0]["menu_item_id"] == active.id


@pytest.mark.asyncio
async def test_authenticated_reads_do_not_load_password_hashes_or_all_sessions(
    student_client, engine
):
    queries = []

    def record_query(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", record_query)
    try:
        response = await student_client.get("/api/v1/auth/me")
        assert response.status_code == 200
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_query)
    assert not any("user_credentials" in query for query in queries)
    assert not any("user_sessions.user_id in" in query for query in queries)
    assert any("user_sessions.id =" in query for query in queries)
