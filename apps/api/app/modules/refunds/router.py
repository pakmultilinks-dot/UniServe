"""Refund API endpoints.

Handles:
- Refund creation (user request)
- Refund processing (admin/manager)
- Refund retrieval
- Refundable amount check
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import AuthContext, RequireRole, get_current_user
from app.core.exceptions import AuthorizationError
from app.modules.refunds.processors.test_processor import TestRefundProcessor
from app.modules.refunds.schemas import (
    RefundableAmountResponse,
    RefundCreateRequest,
    RefundListResponse,
    RefundResponse,
)
from app.modules.refunds.service import RefundService
from app.modules.users.models import Role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.refunds.processors.base import RefundProcessor

router = APIRouter()


def _get_refund_processor() -> RefundProcessor:
    """Get the refund processor. Uses test processor for Phase 5."""
    return TestRefundProcessor()


def _get_refund_service(db: AsyncSession) -> RefundService:
    """Create a RefundService with the configured processor."""
    return RefundService(db, _get_refund_processor())


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=RefundResponse, status_code=201)
async def request_refund(
    order_id: str = Query(..., description="Order ID to refund"),
    body: RefundCreateRequest = ...,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """Request a refund for an order.

    Any authenticated user can request a refund for their own order.
    Processing requires admin/manager authorization.
    """
    service = _get_refund_service(db)

    # Verify order ownership
    from sqlalchemy import select

    from app.modules.orders.models import Order

    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if order is None:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Order", order_id)
    if order.user_id != auth.user.id:
        raise AuthorizationError("You can only request refunds for your own orders")

    refund = await service.create_refund(
        order_id=order_id,
        amount=body.amount,
        reason=body.reason,
        reason_note=body.reason_note,
        requested_by_user_id=auth.user.id,
        idempotency_key=body.idempotency_key,
    )
    return RefundResponse.model_validate(refund)


@router.get("/order/{order_id}", response_model=RefundListResponse)
async def list_order_refunds(
    order_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefundListResponse:
    """List refunds for an order (owner only)."""
    from sqlalchemy import select

    from app.core.exceptions import NotFoundException
    from app.modules.orders.models import Order

    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if order is None:
        raise NotFoundException("Order", order_id)
    if order.user_id != auth.user.id:
        raise AuthorizationError("You can only view refunds for your own orders")

    service = _get_refund_service(db)
    refunds = await service.get_order_refunds(order_id)
    return RefundListResponse(
        refunds=[RefundResponse.model_validate(r) for r in refunds],
        total=len(refunds),
    )


@router.get("/refundable/{order_id}", response_model=RefundableAmountResponse)
async def get_refundable_amount(
    order_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefundableAmountResponse:
    """Check the refundable amount for an order (owner only)."""
    from sqlalchemy import select

    from app.core.exceptions import NotFoundException
    from app.modules.orders.models import Order

    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if order is None:
        raise NotFoundException("Order", order_id)
    if order.user_id != auth.user.id:
        raise AuthorizationError("You can only view refund details for your own orders")

    service = _get_refund_service(db)
    data = await service.get_refundable_amount(order_id)
    return RefundableAmountResponse(**data)


# ---------------------------------------------------------------------------
# Admin/Manager endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/all", response_model=RefundListResponse)
async def list_all_refunds(
    cafeteria_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RefundListResponse:
    """List all refunds (university admin only)."""
    service = _get_refund_service(db)
    refunds = await service.list_order_refunds(
        cafeteria_id=cafeteria_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return RefundListResponse(
        refunds=[RefundResponse.model_validate(r) for r in refunds],
        total=len(refunds),
    )


@router.post("/{refund_id}/process", response_model=RefundResponse)
async def process_refund(
    refund_id: str,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """Process/approve a refund.

    - UNIVERSITY_ADMIN: can process any refund
    - CAFETERIA_MANAGER: can process refunds for their assigned cafeteria
    - Others: denied
    """
    service = _get_refund_service(db)
    refund = await service.process_refund(
        refund_id=refund_id,
        processor_user_id=auth.user.id,
        processor_role=auth.user.role,
    )
    return RefundResponse.model_validate(refund)
