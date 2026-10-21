"""Reporting service — aggregation queries for Phase 7 reports.

All queries use efficient SQL aggregation (group_by, func.count, func.sum, func.avg).
No loading of full datasets into Python. Empty result sets return zeroed defaults.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import Case, func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cafeterias.models import Cafeteria
from app.modules.inventory.models import InventoryAdjustment, InventoryItem
from app.modules.menus.models import MenuItem
from app.modules.orders.models import Order, OrderItem, OrderStatus, OrderType, PaymentMethod
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundStatus

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(d: str) -> date:
    """Parse YYYY-MM-DD string to date."""
    return date.fromisoformat(d)


def _default_date_range() -> tuple[date, date]:
    """Default: last 30 days inclusive."""
    # Orders use cafeteria-local order_date. LGU reporting defaults must use
    # the campus business day, not the UTC date of the hosting provider.
    # Otherwise payments placed after Pakistan midnight vanish from reports.
    today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    start = today - timedelta(days=29)
    return start, today


def _coalesce(value: float | None, default: float = 0.0) -> float:
    return value if value is not None else default


# ---------------------------------------------------------------------------
# Sales Reports
# ---------------------------------------------------------------------------


class ReportService:
    """Service for all reporting aggregation queries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- helpers -----------------------------------------------------------

    def _cafeteria_filter(self, cafeteria_id: str | None):
        """Return a where clause for cafeteria_id if provided."""
        if cafeteria_id:
            return Order.cafeteria_id == cafeteria_id
        return None

    def _date_filter(
        self,
        start_date: date | None,
        end_date: date | None,
    ):
        """Return list of where clauses for date range on order_date."""
        clauses = []
        if start_date:
            clauses.append(Order.order_date >= start_date)
        if end_date:
            clauses.append(Order.order_date <= end_date)
        return clauses

    def _payment_revenue_filter(self):
        """Where clause: only count revenue from succeeded payments."""
        return Payment.status == PaymentStatus.SUCCEEDED

    # -- Sales -------------------------------------------------------------

    async def get_sales_summary(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        cafeteria_id: str | None = None,
    ) -> dict[str, Any]:
        """Total revenue from succeeded payments, minus succeeded refunds."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        # Revenue: sum of succeeded payments linked to orders in range
        rev_q = (
            select(
                func.coalesce(func.sum(Payment.amount), 0).label("total_revenue"),
                func.count(func.distinct(Payment.order_id)).label("total_orders"),
            )
            .join(Order, Payment.order_id == Order.id)
            .where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        if cafeteria_id:
            rev_q = rev_q.where(Order.cafeteria_id == cafeteria_id)

        rev_result = await self.db.execute(rev_q)
        rev_row = rev_result.one()
        total_revenue = int(rev_row.total_revenue)
        total_orders = int(rev_row.total_orders)

        # Refunds: sum of succeeded refunds in range
        ref_q = (
            select(func.coalesce(func.sum(Refund.amount), 0).label("total_refunded"))
            .join(Order, Refund.order_id == Order.id)
            .where(
                Refund.status == RefundStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        if cafeteria_id:
            ref_q = ref_q.where(Order.cafeteria_id == cafeteria_id)

        ref_result = await self.db.execute(ref_q)
        total_refunded = int(ref_result.scalar() or 0)

        # Phase 49 — payment volume by method (succeeded payments only).
        # Mirrors administration.get_financial_summary so reports and
        # administration financials share one authoritative definition
        # (payment method lives on Order; Payment rows carry no method).
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
        if cafeteria_id:
            pay_q = pay_q.where(Order.cafeteria_id == cafeteria_id)
        pay_result = await self.db.execute(pay_q)
        pr = pay_result.one()

        return {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_refunded": total_refunded,
            "net_revenue": total_revenue - total_refunded,
            "online_payment_volume": int(pr.online_volume),
            "cash_payment_volume": int(pr.cash_volume),
            "currency": "PKR",
        }

    async def get_sales_daily(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        cafeteria_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Daily revenue breakdown."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        q = (
            select(
                Order.order_date.label("date"),
                func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
                func.count(func.distinct(Payment.order_id)).label("order_count"),
            )
            .join(Payment, Payment.order_id == Order.id)
            .where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
            .group_by(Order.order_date)
            .order_by(Order.order_date)
        )
        if cafeteria_id:
            q = q.where(Order.cafeteria_id == cafeteria_id)

        result = await self.db.execute(q)
        return [
            {
                "date": str(row.date),
                "revenue": int(row.revenue),
                "order_count": int(row.order_count),
            }
            for row in result.all()
        ]

    async def get_sales_by_cafeteria(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Revenue breakdown per cafeteria."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        q = (
            select(
                Order.cafeteria_id,
                Cafeteria.name.label("cafeteria_name"),
                func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
                func.count(func.distinct(Payment.order_id)).label("order_count"),
            )
            .join(Payment, Payment.order_id == Order.id)
            .join(Cafeteria, Cafeteria.id == Order.cafeteria_id)
            .where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
            .group_by(Order.cafeteria_id, Cafeteria.name)
            .order_by(Cafeteria.name)
        )
        result = await self.db.execute(q)
        rows = result.all()

        # Get refunded amounts per cafeteria
        ref_q = (
            select(
                Order.cafeteria_id,
                func.coalesce(func.sum(Refund.amount), 0).label("refunded"),
            )
            .join(Order, Refund.order_id == Order.id)
            .where(
                Refund.status == RefundStatus.SUCCEEDED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
            .group_by(Order.cafeteria_id)
        )
        ref_result = await self.db.execute(ref_q)
        ref_map = {r.cafeteria_id: int(r.refunded) for r in ref_result.all()}

        # Phase 49 — completed/cancelled counts per cafeteria so the admin
        # comparison table can show lifecycle columns without N+1 calls.
        stat_q = (
            select(
                Order.cafeteria_id,
                func.count().filter(Order.status == OrderStatus.COMPLETED).label("completed"),
                func.count().filter(Order.status == OrderStatus.CANCELLED).label("cancelled"),
            )
            .where(
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
            .group_by(Order.cafeteria_id)
        )
        stat_result = await self.db.execute(stat_q)
        stat_map = {
            r.cafeteria_id: (int(r.completed), int(r.cancelled)) for r in stat_result.all()
        }

        return [
            {
                "cafeteria_id": row.cafeteria_id,
                "cafeteria_name": row.cafeteria_name,
                "revenue": int(row.revenue),
                "order_count": int(row.order_count),
                "refunded_amount": ref_map.get(row.cafeteria_id, 0),
                "completed_orders": stat_map.get(row.cafeteria_id, (0, 0))[0],
                "cancelled_orders": stat_map.get(row.cafeteria_id, (0, 0))[1],
            }
            for row in rows
        ]

    # -- Order Analytics ---------------------------------------------------

    async def get_order_summary(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        cafeteria_id: str | None = None,
    ) -> dict[str, Any]:
        """Order counts by status, type, and payment method."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        base_filters = [Order.order_date >= sd, Order.order_date <= ed]
        if cafeteria_id:
            base_filters.append(Order.cafeteria_id == cafeteria_id)

        # Total + status counts
        status_q = select(
            func.count(Order.id).label("total"),
            func.count().filter(Order.status == OrderStatus.PENDING).label("pending"),
            func.count().filter(Order.status == OrderStatus.PREPARING).label("preparing"),
            func.count().filter(Order.status == OrderStatus.READY).label("ready"),
            func.count().filter(Order.status == OrderStatus.COMPLETED).label("completed"),
            func.count().filter(Order.status == OrderStatus.CANCELLED).label("cancelled"),
        ).where(*base_filters)
        status_result = await self.db.execute(status_q)
        sr = status_result.one()

        total = int(sr.total)
        completed = int(sr.completed)
        cancelled = int(sr.cancelled)

        # Type breakdown
        type_q = select(
            func.count().filter(Order.order_type == OrderType.IMMEDIATE).label("immediate"),
            func.count().filter(Order.order_type == OrderType.SCHEDULED).label("scheduled"),
        ).where(*base_filters)
        type_result = await self.db.execute(type_q)
        tr = type_result.one()

        # Payment breakdown
        pay_q = select(
            func.count().filter(Order.payment_method == PaymentMethod.CASH).label("cash"),
            func.count().filter(Order.payment_method == PaymentMethod.ONLINE).label("online"),
        ).where(*base_filters)
        pay_result = await self.db.execute(pay_q)
        pr = pay_result.one()

        return {
            "total_orders": total,
            "status_breakdown": {
                "pending": int(sr.pending),
                "preparing": int(sr.preparing),
                "ready": int(sr.ready),
                "completed": completed,
                "cancelled": cancelled,
            },
            "type_breakdown": {
                "immediate": int(tr.immediate),
                "scheduled": int(tr.scheduled),
            },
            "payment_breakdown": {
                "cash": int(pr.cash),
                "online": int(pr.online),
            },
            "cancellation_rate": round(cancelled / total, 4) if total > 0 else 0.0,
            "completion_rate": round(completed / total, 4) if total > 0 else 0.0,
        }

    async def get_order_volume(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        cafeteria_id: str | None = None,
    ) -> dict[str, Any]:
        """Daily and hourly order volume."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        base_filters = [Order.order_date >= sd, Order.order_date <= ed]
        if cafeteria_id:
            base_filters.append(Order.cafeteria_id == cafeteria_id)

        # Daily volume
        daily_q = (
            select(
                Order.order_date.label("date"),
                func.count(Order.id).label("order_count"),
                func.count().filter(Order.status == OrderStatus.COMPLETED).label("completed_count"),
                func.count().filter(Order.status == OrderStatus.CANCELLED).label("cancelled_count"),
            )
            .where(*base_filters)
            .group_by(Order.order_date)
            .order_by(Order.order_date)
        )
        daily_result = await self.db.execute(daily_q)
        daily = [
            {
                "date": str(r.date),
                "order_count": int(r.order_count),
                "completed_count": int(r.completed_count),
                "cancelled_count": int(r.cancelled_count),
            }
            for r in daily_result.all()
        ]

        # Hourly volume — extract hour from created_at (cross-DB)
        hourly_q = (
            select(
                func.extract("hour", Order.created_at).label("hour"),
                func.count(Order.id).label("order_count"),
            )
            .where(*base_filters)
            .group_by(func.extract("hour", Order.created_at))
            .order_by(func.extract("hour", Order.created_at))
        )
        hourly_result = await self.db.execute(hourly_q)
        hourly = [
            {"hour": int(r.hour), "order_count": int(r.order_count)} for r in hourly_result.all()
        ]

        return {"daily": daily, "hourly": hourly}

    async def get_cancellation_rate(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        cafeteria_id: str | None = None,
    ) -> dict[str, Any]:
        """Cancellation count, rate, and reason breakdown."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        base_filters = [Order.order_date >= sd, Order.order_date <= ed]
        if cafeteria_id:
            base_filters.append(Order.cafeteria_id == cafeteria_id)

        # Total and cancelled counts
        count_q = select(
            func.count(Order.id).label("total"),
            func.count().filter(Order.status == OrderStatus.CANCELLED).label("cancelled"),
        ).where(*base_filters)
        count_result = await self.db.execute(count_q)
        cr = count_result.one()
        total = int(cr.total)
        cancelled = int(cr.cancelled)

        # Cancellation reasons from order_events
        from app.modules.orders.models import OrderEvent, OrderEventType

        reason_q = (
            select(
                OrderEvent.notes.label("reason"),
                func.count(OrderEvent.id).label("reason_count"),
            )
            .join(Order, OrderEvent.order_id == Order.id)
            .where(
                OrderEvent.event_type == OrderEventType.CANCELLED,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
        )
        if cafeteria_id:
            reason_q = reason_q.where(Order.cafeteria_id == cafeteria_id)

        reason_q = reason_q.group_by(OrderEvent.notes)
        reason_result = await self.db.execute(reason_q)
        reasons = {r.reason or "unspecified": int(r.reason_count) for r in reason_result.all()}

        return {
            "total_orders": total,
            "cancelled_orders": cancelled,
            "cancellation_rate": round(cancelled / total, 4) if total > 0 else 0.0,
            "cancellation_reasons": reasons,
        }

    # -- Cafeteria Performance ---------------------------------------------

    async def get_cafeteria_performance(
        self,
        cafeteria_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Lifecycle metrics for a single cafeteria."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        # Load cafeteria name
        caf_q = select(Cafeteria.name).where(Cafeteria.id == cafeteria_id)
        caf_result = await self.db.execute(caf_q)
        caf_name = caf_result.scalar_one_or_none() or "Unknown"

        base_filters = [
            Order.cafeteria_id == cafeteria_id,
            Order.order_date >= sd,
            Order.order_date <= ed,
        ]

        # Counts
        count_q = select(
            func.count(Order.id).label("total"),
            func.count().filter(Order.status == OrderStatus.COMPLETED).label("completed"),
            func.count().filter(Order.status == OrderStatus.CANCELLED).label("cancelled"),
            func.count().filter(Order.uncollected_at.isnot(None)).label("uncollected"),
        ).where(*base_filters)
        count_result = await self.db.execute(count_q)
        cr = count_result.one()
        total = int(cr.total)
        completed = int(cr.completed)
        cancelled = int(cr.cancelled)
        uncollected = int(cr.uncollected)

        # Average preparation time: preparation_started_at -> ready_at (cross-DB via epoch)
        prep_q = select(
            func.avg(
                func.extract("epoch", Order.ready_at - Order.preparation_started_at) / 60.0
            ).label("avg_prep_minutes")
        ).where(
            *base_filters,
            Order.preparation_started_at.isnot(None),
            Order.ready_at.isnot(None),
        )
        prep_result = await self.db.execute(prep_q)
        _avg_prep = prep_result.scalar()
        avg_prep_minutes = round(_avg_prep, 1) if _avg_prep else None

        # Average time to ready: created_at -> ready_at
        ttr_q = select(
            func.avg(func.extract("epoch", Order.ready_at - Order.created_at) / 60.0).label(
                "avg_ttr_minutes"
            )
        ).where(
            *base_filters,
            Order.ready_at.isnot(None),
        )
        ttr_result = await self.db.execute(ttr_q)
        _avg_ttr = ttr_result.scalar()
        avg_ttr_minutes = round(_avg_ttr, 1) if _avg_ttr else None

        # Average ETA
        eta_q = select(func.avg(Order.eta_minutes).label("avg_eta")).where(
            *base_filters,
            Order.eta_minutes.isnot(None),
        )
        eta_result = await self.db.execute(eta_q)
        avg_eta = eta_result.scalar()
        avg_eta_minutes = round(float(avg_eta), 1) if avg_eta else None

        return {
            "cafeteria_id": cafeteria_id,
            "cafeteria_name": caf_name,
            "total_orders": total,
            "completed_orders": completed,
            "cancelled_orders": cancelled,
            "uncollected_orders": uncollected,
            "completion_rate": round(completed / total, 4) if total > 0 else 0.0,
            "cancellation_rate": round(cancelled / total, 4) if total > 0 else 0.0,
            "avg_preparation_time_minutes": avg_prep_minutes,
            "avg_time_to_ready_minutes": avg_ttr_minutes,
            "avg_eta_minutes": avg_eta_minutes,
        }

    async def get_cafeteria_popular_items(
        self,
        cafeteria_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Most popular items by order quantity."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        q = (
            select(
                OrderItem.menu_item_id,
                OrderItem.item_name,
                func.sum(OrderItem.quantity).label("total_quantity"),
                func.sum(OrderItem.subtotal).label("total_revenue"),
                func.count(func.distinct(OrderItem.order_id)).label("order_count"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.cafeteria_id == cafeteria_id,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
            .group_by(OrderItem.menu_item_id, OrderItem.item_name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        return [
            {
                "menu_item_id": r.menu_item_id,
                "item_name": r.item_name,
                "total_quantity": int(r.total_quantity),
                "total_revenue": int(r.total_revenue),
                "order_count": int(r.order_count),
            }
            for r in result.all()
        ]

    async def get_cafeteria_peak_hours(
        self,
        cafeteria_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Order volume by hour of day."""
        sd, ed = (start_date, end_date) if start_date and end_date else _default_date_range()

        q = (
            select(
                func.extract("hour", Order.created_at).label("hour"),
                func.count(Order.id).label("order_count"),
                func.count().filter(Order.status == OrderStatus.COMPLETED).label("completed_count"),
            )
            .where(
                Order.cafeteria_id == cafeteria_id,
                Order.order_date >= sd,
                Order.order_date <= ed,
            )
            .group_by(func.extract("hour", Order.created_at))
            .order_by(func.extract("hour", Order.created_at))
        )
        result = await self.db.execute(q)
        return [
            {
                "hour": int(r.hour),
                "order_count": int(r.order_count),
                "completed_count": int(r.completed_count),
            }
            for r in result.all()
        ]

    # -- Inventory Reports -------------------------------------------------

    async def get_inventory_stock_levels(
        self,
        cafeteria_id: str,
    ) -> dict[str, Any]:
        """Current stock levels for all inventory items in a cafeteria."""
        q = (
            select(
                InventoryItem.id.label("inventory_item_id"),
                InventoryItem.menu_item_id,
                MenuItem.name.label("menu_item_name"),
                InventoryItem.quantity,
                InventoryItem.unit,
                InventoryItem.low_threshold,
            )
            .join(MenuItem, InventoryItem.menu_item_id == MenuItem.id)
            .where(InventoryItem.cafeteria_id == cafeteria_id)
            .order_by(MenuItem.name)
        )
        result = await self.db.execute(q)
        rows = result.all()

        items = []
        out_of_stock = 0
        low_stock = 0
        for r in rows:
            is_oos = r.quantity == 0
            is_low = 0 < r.quantity <= r.low_threshold
            if is_oos:
                out_of_stock += 1
            if is_low:
                low_stock += 1
            items.append(
                {
                    "inventory_item_id": r.inventory_item_id,
                    "menu_item_id": r.menu_item_id,
                    "menu_item_name": r.menu_item_name,
                    "quantity": r.quantity,
                    "unit": r.unit.value if hasattr(r.unit, "value") else str(r.unit),
                    "low_threshold": r.low_threshold,
                    "is_out_of_stock": is_oos,
                    "is_low_stock": is_low,
                }
            )

        return {
            "cafeteria_id": cafeteria_id,
            "total_items": len(items),
            "out_of_stock_count": out_of_stock,
            "low_stock_count": low_stock,
            "items": items,
        }

    async def get_inventory_low_stock(
        self,
        cafeteria_id: str,
    ) -> dict[str, Any]:
        """Items that are low or out of stock."""
        q = (
            select(
                InventoryItem.id.label("inventory_item_id"),
                InventoryItem.menu_item_id,
                MenuItem.name.label("menu_item_name"),
                InventoryItem.quantity,
                InventoryItem.unit,
                InventoryItem.low_threshold,
            )
            .join(MenuItem, InventoryItem.menu_item_id == MenuItem.id)
            .where(
                InventoryItem.cafeteria_id == cafeteria_id,
                InventoryItem.quantity <= InventoryItem.low_threshold,
            )
            .order_by(InventoryItem.quantity)
        )
        result = await self.db.execute(q)
        rows = result.all()

        items = []
        for r in rows:
            status = "out_of_stock" if r.quantity == 0 else "low_stock"
            items.append(
                {
                    "inventory_item_id": r.inventory_item_id,
                    "menu_item_id": r.menu_item_id,
                    "menu_item_name": r.menu_item_name,
                    "quantity": r.quantity,
                    "unit": r.unit.value if hasattr(r.unit, "value") else str(r.unit),
                    "low_threshold": r.low_threshold,
                    "stock_status": status,
                }
            )

        return {
            "cafeteria_id": cafeteria_id,
            "total_low_stock": len(items),
            "items": items,
        }

    async def get_inventory_turnover(
        self,
        cafeteria_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Inventory adjustment activity (not a mathematical turnover ratio)."""
        base_filters = [InventoryItem.cafeteria_id == cafeteria_id]
        date_filters = []
        if start_date:
            # Convert date to datetime for comparison with created_at
            date_filters.append(
                InventoryAdjustment.created_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
            )
        if end_date:
            date_filters.append(
                InventoryAdjustment.created_at
                <= datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
            )

        # Summary counts
        summary_q: Any = (
            select(
                func.count(InventoryAdjustment.id).label("total_adjustments"),
                func.coalesce(
                    func.sum(
                        Case(
                            (
                                InventoryAdjustment.adjustment_quantity > 0,
                                InventoryAdjustment.adjustment_quantity,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_restock"),
                func.coalesce(
                    func.sum(
                        Case(
                            (
                                InventoryAdjustment.adjustment_quantity < 0,
                                func.abs(InventoryAdjustment.adjustment_quantity),
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_usage"),
            )
            .join(InventoryItem, InventoryAdjustment.inventory_item_id == InventoryItem.id)
            .where(*base_filters, *date_filters)
        )
        summary_result = await self.db.execute(summary_q)
        sr = summary_result.one()

        # Recent adjustments
        adj_q = (
            select(
                InventoryAdjustment.id,
                InventoryAdjustment.inventory_item_id,
                MenuItem.name.label("menu_item_name"),
                InventoryAdjustment.adjustment_quantity,
                InventoryAdjustment.reason,
                InventoryAdjustment.created_at,
            )
            .join(InventoryItem, InventoryAdjustment.inventory_item_id == InventoryItem.id)
            .join(MenuItem, InventoryItem.menu_item_id == MenuItem.id)
            .where(*base_filters, *date_filters)
            .order_by(InventoryAdjustment.created_at.desc())
            .limit(limit)
        )
        adj_result = await self.db.execute(adj_q)
        adjustments = [
            {
                "id": str(r.id),
                "inventory_item_id": r.inventory_item_id,
                "menu_item_name": r.menu_item_name,
                "adjustment_quantity": r.adjustment_quantity,
                "reason": r.reason,
                "adjusted_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in adj_result.all()
        ]

        return {
            "cafeteria_id": cafeteria_id,
            "total_adjustments": int(sr.total_adjustments),
            "total_restock": int(sr.total_restock),
            "total_usage": int(sr.total_usage),
            "adjustments": adjustments,
        }
