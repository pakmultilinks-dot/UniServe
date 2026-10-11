"""Administration routes — university admin overview APIs.

All endpoints are UNIVERSITY_ADMIN only.
"""

from __future__ import annotations

from datetime import date  # noqa: TC003 — needed at runtime for Query validation
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthContext, RequireRole
from app.modules.users.models import Role

from .schemas import (
    AdministrationOverviewResponse,
    AuditEventListResponse,
    AuditEventResponse,
    CafeteriaSummary,
    ExceptionsSummary,
    FinancialSummary,
    OrderSummary,
    UserSummary,
)
from .service import AdminService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = structlog.get_logger(__name__)

router = APIRouter()

_ADMIN_ROLES = (Role.UNIVERSITY_ADMIN,)


@router.get(
    "/overview",
    response_model=AdministrationOverviewResponse,
)
async def administration_overview(
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    auth: AuthContext = Depends(RequireRole(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AdministrationOverviewResponse:
    """University-wide administration overview.

    Provides aggregated counts for users, cafeterias, orders,
    financials, and operational exceptions. University Admin only.
    """
    service = AdminService(db)

    users = await service.get_user_summary()
    cafeterias = await service.get_cafeteria_summary()
    orders = await service.get_order_summary(start_date=start_date, end_date=end_date)
    financial = await service.get_financial_summary(start_date=start_date, end_date=end_date)
    exceptions = await service.get_exceptions_summary(start_date=start_date, end_date=end_date)
    menu_items = await service.get_menu_item_count()

    return AdministrationOverviewResponse(
        users=UserSummary(**users),
        cafeterias=CafeteriaSummary(**cafeterias),
        orders=OrderSummary(**orders),
        financial=FinancialSummary(**financial),
        exceptions=ExceptionsSummary(**exceptions),
        menu_items=menu_items,
    )


@router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
)
async def list_audit_events(
    limit: int = Query(
        50, ge=1, le=200, description="Maximum number of events to return"
    ),
    offset: int = Query(0, ge=0, description="Number of events to skip (pagination)"),
    event_type: str | None = Query(
        None, description="Optional audit event type filter"
    ),
    auth: AuthContext = Depends(RequireRole(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AuditEventListResponse:
    """Security audit log — newest first, paginated. University Admin only.

    Phase 55 — read-only visibility into the security audit trail
    (logins, password changes, account lifecycle, administrative
    actions). ``user_id`` identifies the actor; ``user_name`` is a
    convenience enrichment resolved by the service. No write side
    effects — this endpoint never mutates audit data.
    """
    service = AdminService(db)
    data = await service.get_audit_events(
        limit=limit, offset=offset, event_type=event_type
    )
    return AuditEventListResponse(
        events=[AuditEventResponse(**e) for e in data["events"]],
        total=data["total"],
    )
