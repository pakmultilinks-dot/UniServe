"""Deterministic ETA calculation for order preparation.

Formula: queue_depth * (avg_prep_time / capacity) + item_prep_time
"""

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import Order, OrderStatus

logger = structlog.get_logger(__name__)


async def calculate_eta(
    *,
    db: AsyncSession,
    cafeteria_id: str,
    order_id: str | None = None,
) -> int:
    """Calculate ETA in minutes for an order.

    Considers:
    - Number of orders currently being prepared
    - Cafeteria's preparation capacity
    - Average item preparation time

    Returns a minimum of 5 minutes.
    """
    from app.modules.cafeterias.models import Cafeteria

    # Get cafeteria capacity
    caf_result = await db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria_id))
    cafeteria = caf_result.scalar_one_or_none()
    capacity = cafeteria.preparation_capacity if cafeteria else 10

    # Count orders currently being prepared (excluding this order)
    query = select(func.count(Order.id)).where(
        Order.cafeteria_id == cafeteria_id,
        Order.status == OrderStatus.PREPARING,
    )
    if order_id:
        query = query.where(Order.id != order_id)

    result = await db.execute(query)
    preparing_count = result.scalar() or 0

    # Get average preparation time for items in this order
    avg_prep_time = 15  # default
    if order_id:
        from app.modules.menus.models import MenuItem
        from app.modules.orders.models import OrderItem

        # Get menu item ids for this order
        items_result = await db.execute(
            select(OrderItem.menu_item_id).where(
                OrderItem.order_id == order_id,
                OrderItem.menu_item_id.isnot(None),
            )
        )
        menu_item_ids = [r[0] for r in items_result.all()]

        if menu_item_ids:
            mi_result = await db.execute(
                select(func.avg(MenuItem.preparation_time_minutes)).where(
                    MenuItem.id.in_(menu_item_ids)
                )
            )
            avg = mi_result.scalar()
            if avg is not None:
                avg_prep_time = int(avg)

    # ETA formula: queue depth contribution + per-order prep time
    if capacity > 0:
        queue_minutes = int((preparing_count * avg_prep_time) / capacity)
    else:
        queue_minutes = preparing_count * avg_prep_time

    eta = queue_minutes + avg_prep_time
    eta = max(eta, 5)  # minimum 5 minutes

    logger.info(
        "eta_calculated",
        order_id=order_id,
        preparing_count=preparing_count,
        capacity=capacity,
        avg_prep_time=avg_prep_time,
        eta_minutes=eta,
    )
    return eta
