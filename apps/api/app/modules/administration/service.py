"""Administration service — aggregation queries for university overview.

All queries use efficient SQL aggregation.
No full dataset loading into Python. Empty result sets return zeroed defaults.
Reuses existing reporting logic where practical.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import Cafeteria
from app.modules.menus.models import MenuItem
from app.modules.orders.models import NoShow, Order, OrderStatus, PaymentMethod
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundReason, RefundStatus
from app.modules.users.models import (
    AccountStatus,
    CafeteriaAssignment,
    Role,
    User,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_date_range() -> tuple[date, date]:
    """Default: last 30 days inclusive (matches reports module)."""
    today = date.today()
    start = today - timedelta(days=29)
    return start, today


# ---------------------------------------------------------------------------
# Administration Service
# ---------------------------------------------------------------------------


class AdminService:
    """Service for university administration overview queries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- Menu Items --------------------------------------------------------

    async def get_menu_item_count(self) -> int:
        """Count all active menu items across all cafeterias."""
        q = select(func.count(MenuItem.id)).where(MenuItem.is_active == True)
        result = await self.db.execute(q)
        return result.scalar() or 0

    # -- Users -------------------------------------------------------------

    async def get_user_summary(self) -> dict[str, Any]:
        """University-wide user counts by role and status."""
        q = select(
            func.count(User.id).label("total"),
            func.count().filter(User.role == Role.STUDENT).label("students"),
            func.count().filter(User.role == Role.FACULTY).label("faculty"),
            func.count().filter(User.role == Role.UNIVERSITY_ADMIN).label("university_admins"),
            func.count().filter(User.role == Role.CAFETERIA_MANAGER).label("cafeteria_managers"),
            func.count().filter(User.role == Role.CAFETERIA_STAFF).label("cafeteria_staff"),
            func.count().filter(User.status == AccountStatus.ACTIVE).label("active"),
            func.count().filter(User.status == AccountStatus.SUSPENDED).label("suspended"),
            func.count().filter(User.ordering_suspended == True).label("ordering_suspended"),
        )
        result = await self.db.execute(q)
        r = result.one()
        return {
            "total": r.total,
            "students": r.students,
            "faculty": r.faculty,
            "university_admins": r.university_admins,
            "cafeteria_managers": r.cafeteria_managers,
            "cafeteria_staff": r.cafeteria_staff,
            "active": r.active,
            "suspended": r.suspended,
            "ordering_suspended": r.ordering_suspended,
        }

    # -- Cafeterias --------------------------------------------------------

    async def get_cafeteria_summary(self) -> dict[str, Any]:
        """University-wide cafeteria overview with manager/staff counts."""
        # Get all cafeterias
        caf_q = select(Cafeteria).order_by(Cafeteria.name)
        caf_result = await self.db.execute(caf_q)
        cafeterias = caf_result.scalars().all()

        # Get assignment counts per cafeteria
        assign_q = select(
            CafeteriaAssignment.cafeteria_id,
            func.count()
            .filter(CafeteriaAssignment.role == Role.CAFETERIA_MANAGER)
            .label("manager_count"),
            func.count()
            .filter(CafeteriaAssignment.role == Role.CAFETERIA_STAFF)
            .label("staff_count"),
        ).group_by(CafeteriaAssignment.cafeteria_id)
        assign_result = await self.db.execute(assign_q)
        assign_map: dict[str, dict[str, int]] = {}
        for row in assign_result.all():
            assign_map[row.cafeteria_id] = {
                "managers": row.manager_count,
                "staff": row.staff_count,
            }

        active_count = 0
        items = []
        for caf in cafeterias:
            counts = assign_map.get(caf.id, {"managers": 0, "staff": 0})
            if caf.is_active:
                active_count += 1
            items.append(
                {
                    "cafeteria_id": caf.id,
                    "name": caf.name,
                    "type": caf.type.value if hasattr(caf.type, "value") else str(caf.type),
                    "operational_status": (
                        caf.operational_status.value
                        if hasattr(caf.operational_status, "value")
                        else str(caf.operational_status)
                    ),
                    "is_active": caf.is_active,
                    "assigned_managers": counts["managers"],
                    "assigned_staff": counts["staff"],
                    "preparation_capacity": caf.preparation_capacity,
                }
            )

        return {
            "total": len(cafeterias),
            "active": active_count,
            "cafeterias": items,
        }

    # -- Orders ------------------------------------------------------------

    async def get_order_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """University-wide order counts for a date range."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        q = select(
            func.count(Order.id).label("total_orders"),
            func.count().filter(Order.status == OrderStatus.PENDING).label("pending"),
            func.count().filter(Order.status == OrderStatus.PREPARING).label("preparing"),
            func.count().filter(Order.status == OrderStatus.READY).label("ready"),
            func.count().filter(Order.status == OrderStatus.COMPLETED).label("completed"),
            func.count().filter(Order.status == OrderStatus.CANCELLED).label("cancelled"),
            func.count().filter(Order.uncollected_at.isnot(None)).label("uncollected"),
        ).where(
            Order.order_date >= sd,
            Order.order_date <= ed,
        )
        result = await self.db.execute(q)
        r = result.one()

        total = r.total_orders
        cancellation_rate = r.cancelled / total if total > 0 else 0.0

        return {
            "total_orders": total,
            "pending": r.pending,
            "preparing": r.preparing,
            "ready": r.ready,
            "completed": r.completed,
            "cancelled": r.cancelled,
            "uncollected": r.uncollected,
            "cancellation_rate": round(cancellation_rate, 4),
        }

    # -- Financial ---------------------------------------------------------

    async def get_financial_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """University-wide financial summary for a date range."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        # Revenue: SUM(Payment.amount) WHERE status = SUCCEEDED, joined to orders in date range
        rev_q = (
            select(func.coalesce(func.sum(Payment.amount), 0).label("total_revenue"))
            .select_from(Payment)
            .join(Order, Payment.order_id == Order.id)
            .where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        rev_result = await self.db.execute(rev_q)
        total_revenue = rev_result.scalar() or 0

        # Refunds: SUM(Refund.amount) WHERE status = SUCCEEDED, in date range
        ref_q = (
            select(func.coalesce(func.sum(Refund.amount), 0).label("total_refunded"))
            .select_from(Refund)
            .join(Order, Refund.order_id == Order.id)
            .where(
                Refund.status == RefundStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        ref_result = await self.db.execute(ref_q)
        total_refunded = ref_result.scalar() or 0

        # Online vs cash payment volume (successful payments only)
        pay_q = (
            select(
                func.coalesce(
                    func.sum(Payment.amount).filter(Order.payment_method == PaymentMethod.ONLINE),
                    0,
                ).label("online_volume"),
                func.coalesce(
                    func.sum(Payment.amount).filter(Order.payment_method == PaymentMethod.CASH),
                    0,
                ).label("cash_volume"),
            )
            .select_from(Payment)
            .join(Order, Payment.order_id == Order.id)
            .where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        pay_result = await self.db.execute(pay_q)
        pr = pay_result.one()

        return {
            "total_revenue": int(total_revenue),
            "total_refunded": int(total_refunded),
            "net_revenue": int(total_revenue) - int(total_refunded),
            "online_payment_volume": int(pr.online_volume),
            "cash_payment_volume": int(pr.cash_volume),
            "currency": "PKR",
        }

    # -- Exceptions --------------------------------------------------------

    async def get_exceptions_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Operational issues requiring University Admin attention."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()
        cutoff = datetime.now(UTC) - timedelta(days=7)

        # Overdue refunds: pending/processing for more than 7 days
        overdue_q = select(func.count(Refund.id)).where(
            Refund.status.in_([RefundStatus.PENDING, RefundStatus.PROCESSING]),
            Refund.created_at < cutoff,
        )
        overdue_result = await self.db.execute(overdue_q)
        overdue_refunds = overdue_result.scalar() or 0

        # Ordering-suspended users
        susp_q = select(func.count(User.id)).where(User.ordering_suspended == True)
        susp_result = await self.db.execute(susp_q)
        ordering_suspended_users = susp_result.scalar() or 0

        # Uncollected orders (no-show records)
        noshows_q = select(func.count(NoShow.id)).where(
            NoShow.created_at >= datetime.combine(sd, time.min, tzinfo=UTC),
            NoShow.created_at <= datetime.combine(ed + timedelta(days=1), time.min, tzinfo=UTC),
        )
        noshows_result = await self.db.execute(noshows_q)
        uncollected_orders = noshows_result.scalar() or 0

        # Cafeteria closure cancellations: refunds with reason CAFETERIA_CLOSED in date range
        closure_q = (
            select(func.count(Refund.id))
            .join(Order, Refund.order_id == Order.id)
            .where(
                Refund.reason == RefundReason.CAFETERIA_CLOSED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        closure_result = await self.db.execute(closure_q)
        cafeteria_closure_cancellations = closure_result.scalar() or 0

        return {
            "overdue_refunds": int(overdue_refunds),
            "ordering_suspended_users": int(ordering_suspended_users),
            "uncollected_orders": int(uncollected_orders),
            "cafeteria_closure_cancellations": int(cafeteria_closure_cancellations),
        }
