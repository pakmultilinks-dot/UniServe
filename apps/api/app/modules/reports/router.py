"""Report module — API endpoints for reporting and analytics.

Authorization rules:
- University Admin: all cafeterias
- Manager: assigned cafeteria only
- Staff: assigned cafeteria only (read-only reporting)
- Student/Faculty: denied from all reporting endpoints
- Unauthenticated: denied

All monetary values are in paisa (smallest currency unit).
"""

from __future__ import annotations

from datetime import date  # noqa: TC003 — used at runtime by FastAPI Query
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireRole,
)
from app.core.exceptions import AuthorizationError
from app.modules.users.models import CafeteriaAssignment, Role

from .schemas import (
    CafeteriaPeakHoursResponse,
    CafeteriaPerformanceResponse,
    CafeteriaPopularItemsResponse,
    CafeteriaSalesRow,
    CancellationRateResponse,
    DailySalesRow,
    InventoryLowStockResponse,
    InventoryStockLevelsResponse,
    InventoryTurnoverResponse,
    OrderSummaryResponse,
    OrderVolumeResponse,
    PeakHourRow,
    PopularItemRow,
    SalesByCafeteriaResponse,
    SalesDailyResponse,
    SalesReportResponse,
    SalesSummary,
)
from .service import ReportService

router = APIRouter()


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------

_REPORT_ROLES = (Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF)


async def _verify_cafeteria_assignment(
    *,
    auth: AuthContext,
    cafeteria_id: str,
    db: AsyncSession,
) -> None:
    """Verify manager/staff is assigned to the cafeteria. Admin passes automatically."""
    if auth.user.role == Role.UNIVERSITY_ADMIN:
        return
    if auth.user.role in (Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF):
        result = await db.execute(
            select(CafeteriaAssignment).where(
                CafeteriaAssignment.user_id == auth.user.id,
                CafeteriaAssignment.cafeteria_id == cafeteria_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise AuthorizationError("You are not assigned to this cafeteria")
    else:
        raise AuthorizationError("Insufficient permissions for reporting")


# ---------------------------------------------------------------------------
# Sales Reports
# ---------------------------------------------------------------------------


@router.get("/sales", response_model=SalesReportResponse)
async def sales_report(
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    cafeteria_id: str | None = Query(None, description="Filter by cafeteria"),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> SalesReportResponse:
    """Sales summary — total revenue from succeeded payments, net of refunds.

    Revenue definition: sum of Payment.amount where status=SUCCEEDED,
    for orders in the date range. Failed, abandoned, and cancelled
    payments are excluded. Succeeded refund amounts are subtracted separately.
    """
    if cafeteria_id:
        await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_sales_summary(
        start_date=start_date, end_date=end_date, cafeteria_id=cafeteria_id
    )
    return SalesReportResponse(summary=SalesSummary(**data))


@router.get("/sales/daily", response_model=SalesDailyResponse)
async def sales_daily(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    cafeteria_id: str | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> SalesDailyResponse:
    """Daily revenue breakdown."""
    if cafeteria_id:
        await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    rows = await service.get_sales_daily(
        start_date=start_date, end_date=end_date, cafeteria_id=cafeteria_id
    )
    return SalesDailyResponse(rows=[DailySalesRow.model_validate(r) for r in rows])


@router.get("/sales/by-cafeteria", response_model=SalesByCafeteriaResponse)
async def sales_by_cafeteria(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SalesByCafeteriaResponse:
    """Revenue breakdown per cafeteria. Admin only (cross-cafeteria view)."""
    service = ReportService(db)
    rows = await service.get_sales_by_cafeteria(start_date=start_date, end_date=end_date)
    return SalesByCafeteriaResponse(rows=[CafeteriaSalesRow.model_validate(r) for r in rows])


# ---------------------------------------------------------------------------
# Order Analytics
# ---------------------------------------------------------------------------


@router.get("/orders/summary", response_model=OrderSummaryResponse)
async def order_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    cafeteria_id: str | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> OrderSummaryResponse:
    """Order counts by status, type, and payment method."""
    if cafeteria_id:
        await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_order_summary(
        start_date=start_date, end_date=end_date, cafeteria_id=cafeteria_id
    )
    return OrderSummaryResponse(**data)


@router.get("/orders/volume", response_model=OrderVolumeResponse)
async def order_volume(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    cafeteria_id: str | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> OrderVolumeResponse:
    """Daily and hourly order volume."""
    if cafeteria_id:
        await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_order_volume(
        start_date=start_date, end_date=end_date, cafeteria_id=cafeteria_id
    )
    return OrderVolumeResponse(**data)


@router.get("/orders/cancellation-rate", response_model=CancellationRateResponse)
async def cancellation_rate(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    cafeteria_id: str | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CancellationRateResponse:
    """Cancellation count, rate, and reason breakdown."""
    if cafeteria_id:
        await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_cancellation_rate(
        start_date=start_date, end_date=end_date, cafeteria_id=cafeteria_id
    )
    return CancellationRateResponse(**data)


# ---------------------------------------------------------------------------
# Cafeteria Performance (cafeteria-scoped)
# ---------------------------------------------------------------------------


@router.get(
    "/cafeteria/{cafeteria_id}/performance",
    response_model=CafeteriaPerformanceResponse,
)
async def cafeteria_performance(
    cafeteria_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaPerformanceResponse:
    """Cafeteria lifecycle metrics — completion rate, prep time, etc."""
    await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_cafeteria_performance(
        cafeteria_id, start_date=start_date, end_date=end_date
    )
    return CafeteriaPerformanceResponse(**data)


@router.get(
    "/cafeteria/{cafeteria_id}/popular-items",
    response_model=CafeteriaPopularItemsResponse,
)
async def cafeteria_popular_items(
    cafeteria_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaPopularItemsResponse:
    """Most popular menu items by order quantity."""
    await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    items = await service.get_cafeteria_popular_items(
        cafeteria_id, start_date=start_date, end_date=end_date, limit=limit
    )
    return CafeteriaPopularItemsResponse(
        cafeteria_id=cafeteria_id, items=[PopularItemRow.model_validate(i) for i in items]
    )


@router.get(
    "/cafeteria/{cafeteria_id}/peak-hours",
    response_model=CafeteriaPeakHoursResponse,
)
async def cafeteria_peak_hours(
    cafeteria_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaPeakHoursResponse:
    """Order volume by hour of day."""
    await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    hours = await service.get_cafeteria_peak_hours(
        cafeteria_id, start_date=start_date, end_date=end_date
    )
    # Get cafeteria timezone
    from app.modules.cafeterias.models import Cafeteria

    caf_result = await db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria_id))
    caf = caf_result.scalar_one_or_none()
    tz = caf.timezone if caf else "Asia/Karachi"

    return CafeteriaPeakHoursResponse(
        cafeteria_id=cafeteria_id, timezone=tz, hours=[PeakHourRow.model_validate(h) for h in hours]
    )


# ---------------------------------------------------------------------------
# Inventory Reports (cafeteria-scoped)
# ---------------------------------------------------------------------------


@router.get(
    "/cafeteria/{cafeteria_id}/inventory/stock-levels",
    response_model=InventoryStockLevelsResponse,
)
async def inventory_stock_levels(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> InventoryStockLevelsResponse:
    """Current stock levels for all inventory items."""
    await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_inventory_stock_levels(cafeteria_id)
    return InventoryStockLevelsResponse(**data)


@router.get(
    "/cafeteria/{cafeteria_id}/inventory/low-stock",
    response_model=InventoryLowStockResponse,
)
async def inventory_low_stock(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> InventoryLowStockResponse:
    """Items that are low or out of stock."""
    await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_inventory_low_stock(cafeteria_id)
    return InventoryLowStockResponse(**data)


@router.get(
    "/cafeteria/{cafeteria_id}/inventory/turnover",
    response_model=InventoryTurnoverResponse,
)
async def inventory_turnover(
    cafeteria_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    auth: AuthContext = Depends(RequireRole(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> InventoryTurnoverResponse:
    """Inventory adjustment activity — restock and usage summary."""
    await _verify_cafeteria_assignment(auth=auth, cafeteria_id=cafeteria_id, db=db)
    service = ReportService(db)
    data = await service.get_inventory_turnover(
        cafeteria_id, start_date=start_date, end_date=end_date
    )
    return InventoryTurnoverResponse(**data)
