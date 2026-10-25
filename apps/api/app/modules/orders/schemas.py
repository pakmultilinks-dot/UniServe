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
    collection_token: str
    user_id: str
    customer_name: str | None = None
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

    # Phase 6 fields
    confirmed_at: datetime | None = None
    preparation_started_at: datetime | None = None
    ready_at: datetime | None = None
    pickup_deadline: datetime | None = None
    eta_minutes: int | None = None
    collection_method: str | None = None
    rejection_reason: str | None = None
    rejection_note: str | None = None

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


# ---- Phase 6 Schemas ----


class OrderConfirmRequest(BaseModel):
    """Request to confirm an order (manager/staff)."""

    notes: str | None = Field(None, max_length=500)


class OrderRejectRequest(BaseModel):
    """Request to reject an order (manager)."""

    reason: str = Field(..., max_length=30)
    notes: str | None = Field(None, max_length=500)


class OrderPrepareRequest(BaseModel):
    """Request to start preparation (staff)."""

    notes: str | None = Field(None, max_length=500)


class OrderReadyRequest(BaseModel):
    """Request to mark order as ready (staff)."""

    notes: str | None = Field(None, max_length=500)


class OrderDelayRequest(BaseModel):
    """Request to mark order as delayed (staff)."""

    additional_minutes: int = Field(..., ge=1, le=120)
    notes: str | None = Field(None, max_length=500)


class OrderPartialCancelRequest(BaseModel):
    """Request to cancel specific items from an order."""

    item_id: str = Field(..., min_length=1)
    reason: str | None = Field(None, max_length=500)


class EtaResponse(BaseModel):
    """ETA calculation response."""

    order_id: str
    eta_minutes: int
    pickup_deadline: datetime | None = None


class NoShowResponse(BaseModel):
    """No-show event response."""

    id: str
    user_id: str
    order_id: str
    cafeteria_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CafeteriaCloseRequest(BaseModel):
    """Request to close a cafeteria suddenly."""

    notes: str | None = Field(None, max_length=500)
