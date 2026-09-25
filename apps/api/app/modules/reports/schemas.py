"""Report response schemas.

All monetary values are in paisa (smallest currency unit).
Percentages are expressed as decimals (e.g. 0.15 = 15%).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Sales Reports
# ---------------------------------------------------------------------------


class SalesSummary(BaseModel):
    """Overall sales summary for a date range."""

    total_revenue: int = Field(
        description="Successful payment revenue in paisa (net of failed/abandoned)"
    )
    total_orders: int = Field(description="Orders with at least one successful payment")
    total_refunded: int = Field(description="Refunded amount in paisa (succeeded refunds only)")
    net_revenue: int = Field(description="total_revenue - total_refunded")
    currency: str = Field(default="PKR")


class DailySalesRow(BaseModel):
    """Revenue breakdown for a single day."""

    date: str = Field(description="Date as YYYY-MM-DD")
    revenue: int = Field(description="Revenue in paisa for this day")
    order_count: int


class CafeteriaSalesRow(BaseModel):
    """Revenue breakdown for a single cafeteria."""

    cafeteria_id: str
    cafeteria_name: str
    revenue: int
    order_count: int
    refunded_amount: int


class SalesReportResponse(BaseModel):
    """Response for GET /reports/sales."""

    summary: SalesSummary
    currency: str = Field(default="PKR")


class SalesDailyResponse(BaseModel):
    """Response for GET /reports/sales/daily."""

    rows: list[DailySalesRow]
    currency: str = Field(default="PKR")


class SalesByCafeteriaResponse(BaseModel):
    """Response for GET /reports/sales/by-cafeteria."""

    rows: list[CafeteriaSalesRow]
    currency: str = Field(default="PKR")


# ---------------------------------------------------------------------------
# Order Analytics
# ---------------------------------------------------------------------------


class OrderStatusBreakdown(BaseModel):
    """Count of orders in each status."""

    pending: int = 0
    preparing: int = 0
    ready: int = 0
    completed: int = 0
    cancelled: int = 0


class OrderTypeBreakdown(BaseModel):
    """Count of orders by type."""

    immediate: int = 0
    scheduled: int = 0


class OrderPaymentBreakdown(BaseModel):
    """Count of orders by payment method."""

    cash: int = 0
    online: int = 0


class OrderSummaryResponse(BaseModel):
    """Response for GET /reports/orders/summary."""

    total_orders: int
    status_breakdown: OrderStatusBreakdown
    type_breakdown: OrderTypeBreakdown
    payment_breakdown: OrderPaymentBreakdown
    cancellation_rate: float = Field(description="cancelled / total (0.0 if no orders)")
    completion_rate: float = Field(description="completed / total (0.0 if no orders)")


class DailyVolumeRow(BaseModel):
    """Order volume for a single day."""

    date: str
    order_count: int
    completed_count: int
    cancelled_count: int


class HourlyVolumeRow(BaseModel):
    """Order volume for a single hour (0-23)."""

    hour: int = Field(description="Hour of day (0-23, in cafeteria timezone)")
    order_count: int


class OrderVolumeResponse(BaseModel):
    """Response for GET /reports/orders/volume."""

    daily: list[DailyVolumeRow]
    hourly: list[HourlyVolumeRow]


class CancellationRateResponse(BaseModel):
    """Response for GET /reports/orders/cancellation-rate."""

    total_orders: int
    cancelled_orders: int
    cancellation_rate: float = Field(description="cancelled / total (0.0 if no orders)")
    cancellation_reasons: dict[str, int] = Field(
        default_factory=dict,
        description="Map of reason -> count for cancelled orders with known reasons",
    )


# ---------------------------------------------------------------------------
# Cafeteria Performance
# ---------------------------------------------------------------------------


class CafeteriaPerformanceResponse(BaseModel):
    """Response for GET /reports/cafeteria/{cafeteria_id}/performance."""

    cafeteria_id: str
    cafeteria_name: str
    total_orders: int
    completed_orders: int
    cancelled_orders: int
    uncollected_orders: int
    completion_rate: float
    cancellation_rate: float
    avg_preparation_time_minutes: float | None = Field(
        description="Average minutes from preparation_started_at to ready_at (None if no data)"
    )
    avg_time_to_ready_minutes: float | None = Field(
        description="Average minutes from order creation to ready_at (None if no data)"
    )
    avg_eta_minutes: float | None = Field(
        description="Average ETA reported at order time (None if no data)"
    )


class PopularItemRow(BaseModel):
    """A popular menu item in a cafeteria."""

    menu_item_id: str | None
    item_name: str
    total_quantity: int = Field(description="Total units ordered")
    total_revenue: int = Field(description="Total revenue from this item in paisa")
    order_count: int = Field(description="Number of orders containing this item")


class CafeteriaPopularItemsResponse(BaseModel):
    """Response for GET /reports/cafeteria/{cafeteria_id}/popular-items."""

    cafeteria_id: str
    items: list[PopularItemRow]


class PeakHourRow(BaseModel):
    """Order volume for a single hour."""

    hour: int = Field(description="Hour of day (0-23)")
    order_count: int
    completed_count: int


class CafeteriaPeakHoursResponse(BaseModel):
    """Response for GET /reports/cafeteria/{cafeteria_id}/peak-hours."""

    cafeteria_id: str
    timezone: str
    hours: list[PeakHourRow]


# ---------------------------------------------------------------------------
# Inventory Reports
# ---------------------------------------------------------------------------


class InventoryStockLevelRow(BaseModel):
    """Current stock for one inventory item."""

    inventory_item_id: str
    menu_item_id: str
    menu_item_name: str
    quantity: int
    unit: str
    low_threshold: int
    is_out_of_stock: bool
    is_low_stock: bool


class InventoryStockLevelsResponse(BaseModel):
    """Response for GET /reports/inventory/stock-levels."""

    cafeteria_id: str
    total_items: int
    out_of_stock_count: int
    low_stock_count: int
    items: list[InventoryStockLevelRow]


class InventoryLowStockRow(BaseModel):
    """An item that is low or out of stock."""

    inventory_item_id: str
    menu_item_id: str
    menu_item_name: str
    quantity: int
    unit: str
    low_threshold: int
    stock_status: str = Field(description="'out_of_stock' or 'low_stock'")


class InventoryLowStockResponse(BaseModel):
    """Response for GET /reports/inventory/low-stock."""

    cafeteria_id: str
    total_low_stock: int
    items: list[InventoryLowStockRow]


class InventoryAdjustmentRow(BaseModel):
    """A single inventory adjustment record."""

    id: str
    inventory_item_id: str
    menu_item_name: str
    adjustment_quantity: int
    reason: str | None
    adjusted_at: str


class InventoryTurnoverResponse(BaseModel):
    """Response for GET /reports/inventory/turnover."""

    cafeteria_id: str
    total_adjustments: int
    total_restock: int = Field(description="Sum of positive adjustments")
    total_usage: int = Field(description="Sum of negative adjustments (absolute value)")
    adjustments: list[InventoryAdjustmentRow]
