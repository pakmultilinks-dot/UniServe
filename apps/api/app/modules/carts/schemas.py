"""Cart module — Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field

# ---- Request Schemas ----


class CartAddItemRequest(BaseModel):
    """Request to add an item to the cart."""

    menu_item_id: str
    quantity: int = Field(..., gt=0, le=99)


class CartUpdateQuantityRequest(BaseModel):
    """Request to update cart item quantity."""

    quantity: int = Field(..., ge=0, le=99)


# ---- Response Schemas ----


class CartItemResponse(BaseModel):
    """A single cart line item."""

    id: str
    menu_item_id: str
    quantity: int
    price_snapshot: int
    currency: str
    subtotal: int  # price_snapshot * quantity
    item_name: str | None = None
    item_available: bool | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    """Cart detail response."""

    id: str
    user_id: str
    cafeteria_id: str
    status: str
    items: list[CartItemResponse] = []
    total_amount: int = 0  # Sum of line subtotals
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CartCheckoutRequest(BaseModel):
    """Request to checkout a cart and create an order."""

    payment_method: str = Field("cash", pattern="^(cash|online)$")
    order_type: str = Field("immediate", pattern="^(immediate|scheduled)$")
    scheduled_collection_time: str | None = Field(None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    note: str | None = Field(None, max_length=500)
