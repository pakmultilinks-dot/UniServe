"""Administration response schemas.

All monetary values are in paisa (smallest PKR unit).
Percentages are expressed as decimals (e.g. 0.15 = 15%).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic resolves fields at runtime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# User Summary
# ---------------------------------------------------------------------------


class UserSummary(BaseModel):
    """University-wide user counts."""

    total: int
    students: int
    faculty: int
    university_admins: int
    cafeteria_managers: int
    cafeteria_staff: int
    active: int
    suspended: int
    ordering_suspended: int


# ---------------------------------------------------------------------------
# Cafeteria Summary
# ---------------------------------------------------------------------------


class CafeteriaOverviewItem(BaseModel):
    """Operational overview for a single cafeteria."""

    cafeteria_id: str
    name: str
    type: str
    operational_status: str
    is_active: bool
    assigned_managers: int
    assigned_staff: int
    preparation_capacity: int


class CafeteriaSummary(BaseModel):
    """University-wide cafeteria summary."""

    total: int
    active: int
    cafeterias: list[CafeteriaOverviewItem]


# ---------------------------------------------------------------------------
# Order Summary
# ---------------------------------------------------------------------------


class OrderSummary(BaseModel):
    """University-wide order summary for a date range."""

    total_orders: int
    pending: int
    preparing: int
    ready: int
    completed: int
    cancelled: int
    uncollected: int
    cancellation_rate: float = Field(description="cancelled / total (0.0 if no orders)")


# ---------------------------------------------------------------------------
# Financial Summary
# ---------------------------------------------------------------------------


class FinancialSummary(BaseModel):
    """University-wide financial summary for a date range."""

    total_revenue: int = Field(description="Successful payment revenue in paisa")
    total_refunded: int = Field(description="Successful refund amount in paisa")
    net_revenue: int = Field(description="total_revenue - total_refunded")
    online_payment_volume: int = Field(description="Revenue from successful online payments")
    cash_payment_volume: int = Field(description="Revenue from successful cash payments")
    currency: str = Field(default="PKR")


# ---------------------------------------------------------------------------
# Exceptions Summary
# ---------------------------------------------------------------------------


class ExceptionsSummary(BaseModel):
    """Operational issues requiring University Admin attention."""

    overdue_refunds: int = Field(
        description="Refunds in pending/processing state for more than 7 days"
    )
    ordering_suspended_users: int = Field(description="Users with ordering currently suspended")
    uncollected_orders: int = Field(description="Total no-show records")
    cafeteria_closure_cancellations: int = Field(
        description="Refunds with reason 'cafeteria_closed' in date range"
    )


# ---------------------------------------------------------------------------
# Overview Response
# ---------------------------------------------------------------------------


class AdministrationOverviewResponse(BaseModel):
    """Full university administration overview."""

    users: UserSummary
    cafeterias: CafeteriaSummary
    orders: OrderSummary
    financial: FinancialSummary
    exceptions: ExceptionsSummary
    menu_items: int = 0


# ---------------------------------------------------------------------------
# Audit Events (Phase 55 — admin security visibility)
# ---------------------------------------------------------------------------


class AuditEventResponse(BaseModel):
    """Single security audit event."""

    id: int
    event_type: str
    user_id: str | None = None
    user_name: str | None = Field(
        default=None,
        description="Actor display name resolved server-side (None when unknown)",
    )
    description: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    """Paginated audit event list (newest first)."""

    events: list[AuditEventResponse]
    total: int
