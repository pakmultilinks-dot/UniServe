"""Orders module — Pydantic schemas for request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field

# ---- Response Schemas ----


class OrderItemResponse(BaseModel):
    """A single order line item (historical snapshot)."""

    id: str
    item_name: str
    unit_price: int
    quantity: int
    subtotal: int
    currency: str

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Order detail response."""

    id: str
    order_number: int
    user_id: str
    cafeteria_id: str
    order_type: str
    payment_method: str
    status: str
    total_amount: int
    currency: str
    order_date: date
    scheduled_collection_time: str | None = None
    items: list[OrderItemResponse] = []
    note: str | None = None
    inventory_reserved: bool = False
    collected_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """List of orders."""

    orders: list[OrderResponse]
    total: int


class OrderEventResponse(BaseModel):
    """Order event (audit trail)."""

    id: str
    event_type: str
    actor_id: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdateRequest(BaseModel):
    """Request to update order status (manager/staff)."""

    status: str = Field(..., pattern="^(preparing|ready|completed)$")
    notes: str | None = Field(None, max_length=500)


class OrderCancelRequest(BaseModel):
    """Request to cancel an order."""

    reason: str | None = Field(None, max_length=500)


class OrderCollectRequest(BaseModel):
    """Request to collect an order."""

    order_number: int | None = None
    collection_token: str | None = None
