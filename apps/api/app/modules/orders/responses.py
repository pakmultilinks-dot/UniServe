"""Fulfilment display data for already-authorized order responses."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderResponse
from app.modules.users.models import User


async def order_responses(db: AsyncSession, orders: Sequence[Order]) -> list[OrderResponse]:
    """Resolve names in one query, without exposing profiles or credentials."""
    if not orders:
        return []
    result = await db.execute(
        select(User.id, User.first_name, User.last_name).where(
            User.id.in_({order.user_id for order in orders})
        )
    )
    names = {row.id: f"{row.first_name} {row.last_name}".strip() for row in result}
    responses = []
    for order in orders:
        response = OrderResponse.model_validate(order)
        response.customer_name = names.get(order.user_id) or None
        responses.append(response)
    return responses


async def order_response(db: AsyncSession, order: Order) -> OrderResponse:
    return (await order_responses(db, [order]))[0]
