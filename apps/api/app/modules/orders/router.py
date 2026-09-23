"""Order module — API endpoints for order management and lifecycle."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireCafeteriaWriteScope,
    RequireRole,
    get_current_user,
)
from app.modules.orders.schemas import (
    OrderCancelRequest,
    OrderCollectRequest,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdateRequest,
)
from app.modules.orders.service import OrderService
from app.modules.users.models import Role

router = APIRouter()


# ---- Manager/staff: cafeteria-scoped routes (must come before /{order_id}) ----


@router.get("/cafeteria/{cafeteria_id}", response_model=OrderListResponse)
async def list_cafeteria_orders(
    cafeteria_id: str,
    status: str | None = Query(None),
    order_date: date | None = Query(None),
    auth: AuthContext = Depends(RequireCafeteriaWriteScope(Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF)),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    """List orders for a specific cafeteria (manager/staff view)."""
    service = OrderService(db)
    orders = await service.list_cafeteria_orders(
        cafeteria_id=cafeteria_id,
        status=status,
        order_date=order_date,
    )
    return OrderListResponse(
        orders=[OrderResponse.model_validate(o) for o in orders],
        total=len(orders),
    )


# ---- User-facing routes ----


@router.get("/", response_model=OrderListResponse)
async def list_my_orders(
    cafeteria_id: str | None = Query(None),
    status: str | None = Query(None),
    days: int = Query(7, ge=1, le=90),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    """List the current user's orders."""
    service = OrderService(db)
    orders = await service.list_user_orders(
        user_id=auth.user.id,
        cafeteria_id=cafeteria_id,
        status=status,
        days=days,
    )
    return OrderListResponse(
        orders=[OrderResponse.model_validate(o) for o in orders],
        total=len(orders),
    )


@router.get("/by-number/{order_number}", response_model=OrderResponse)
async def get_order_by_number(
    order_number: int,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Get order details by order number (owner only)."""
    service = OrderService(db)
    order = await service.get_order_by_number(order_number)
    if order.user_id != auth.user.id:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Order not found")
    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Get order details by ID."""
    service = OrderService(db)
    order = await service.get_order(order_id)
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    body: OrderCancelRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Cancel an order (user cancel — only pending orders)."""
    service = OrderService(db)
    order = await service.cancel_order(
        order_id=order_id,
        user_id=auth.user.id,
        actor_id=auth.user.id,
        reason=body.reason,
        is_manager=False,
    )
    return OrderResponse.model_validate(order)


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    body: OrderStatusUpdateRequest,
    auth: AuthContext = Depends(RequireRole(Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF)),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Update order status (manager/staff only).

    Verifies the user is assigned to the order's cafeteria.
    """
    service = OrderService(db)

    # Resolve order to get cafeteria_id for assignment check
    order = await service.get_order(order_id)

    # Verify manager/staff is assigned to this order's cafeteria
    from sqlalchemy import select as sa_select

    from app.modules.users.models import CafeteriaAssignment

    result = await db.execute(
        sa_select(CafeteriaAssignment).where(
            CafeteriaAssignment.user_id == auth.user.id,
            CafeteriaAssignment.cafeteria_id == order.cafeteria_id,
        )
    )
    if result.scalar_one_or_none() is None:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("You are not assigned to this cafeteria")

    order = await service.update_status(
        order_id=order_id,
        new_status=body.status,
        actor_id=auth.user.id,
        notes=body.notes,
    )
    return OrderResponse.model_validate(order)


@router.post("/collect", response_model=OrderResponse)
async def collect_order(
    body: OrderCollectRequest,
    auth: AuthContext = Depends(RequireRole(Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF)),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Collect an order by order number or QR token (staff/manager only).

    Resolves the order and verifies cafeteria assignment.
    """
    service = OrderService(db)

    # Resolve order first to get cafeteria_id
    if body.order_number:
        order = await service.get_order_by_number(body.order_number)
    elif body.collection_token:
        order = await service.get_order_by_token(body.collection_token)
    else:
        from app.core.exceptions import ValidationError

        raise ValidationError("Provide either order_number or collection_token")

    # Verify manager/staff is assigned to this order's cafeteria
    cafeteria_id = order.cafeteria_id
    from sqlalchemy import select as sa_select

    from app.modules.users.models import CafeteriaAssignment

    result = await db.execute(
        sa_select(CafeteriaAssignment).where(
            CafeteriaAssignment.user_id == auth.user.id,
            CafeteriaAssignment.cafeteria_id == cafeteria_id,
        )
    )
    if result.scalar_one_or_none() is None:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("You are not assigned to this cafeteria")

    order = await service.collect_order(
        order_id=order.id,
        collector_id=auth.user.id,
        cafeteria_id=cafeteria_id,
    )
    return OrderResponse.model_validate(order)


# Manager-only: cancel any order in the cafeteria
@router.post("/{order_id}/manager-cancel", response_model=OrderResponse)
async def manager_cancel_order(
    order_id: str,
    body: OrderCancelRequest,
    auth: AuthContext = Depends(RequireRole(Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Manager cancels an order in their cafeteria.

    Verifies the manager is assigned to the order's cafeteria.
    """
    service = OrderService(db)

    # Resolve order to get cafeteria_id for assignment check
    order = await service.get_order(order_id)

    # Verify manager is assigned to this order's cafeteria
    from sqlalchemy import select as sa_select

    from app.modules.users.models import CafeteriaAssignment

    result = await db.execute(
        sa_select(CafeteriaAssignment).where(
            CafeteriaAssignment.user_id == auth.user.id,
            CafeteriaAssignment.cafeteria_id == order.cafeteria_id,
        )
    )
    if result.scalar_one_or_none() is None:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("You are not assigned to this cafeteria")

    order = await service.cancel_order(
        order_id=order_id,
        actor_id=auth.user.id,
        reason=body.reason,
        is_manager=True,
    )
    return OrderResponse.model_validate(order)
