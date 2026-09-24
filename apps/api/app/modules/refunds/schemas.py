"""Refund Pydantic schemas — request/response models for the refund API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RefundCreateRequest(BaseModel):
    """Request to create a refund."""

    amount: int = Field(
        ...,
        gt=0,
        description="Refund amount (must not exceed refundable amount)",
    )
    reason: str = Field(
        ...,
        description="Refund reason: order_cancelled, item_unavailable, payment_error, "
        "duplicate_payment, cafeteria_closed, other",
    )
    reason_note: str | None = Field(
        None,
        max_length=500,
        description="Optional additional note",
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique key to prevent duplicate refund requests",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RefundResponse(BaseModel):
    """Refund information for client-facing responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    payment_id: str
    amount: int
    currency: str
    status: str
    reason: str
    reason_note: str | None = None
    requested_by: str
    processed_by: str | None = None
    provider_reference: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    updated_at: datetime


class RefundListResponse(BaseModel):
    """List of refunds."""

    refunds: list[RefundResponse]
    total: int


class RefundableAmountResponse(BaseModel):
    """Response showing the refundable amount for an order."""

    order_id: str
    paid_amount: int
    total_refunded: int
    refundable_amount: int
    currency: str
