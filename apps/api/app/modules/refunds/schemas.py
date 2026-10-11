"""Refund Pydantic schemas — request/response models for the refund API."""

from datetime import date, datetime

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


# ---------------------------------------------------------------------------
# Phase 51 — admin resolution (rejection + enriched context)
# ---------------------------------------------------------------------------


class RefundRejectRequest(BaseModel):
    """Request to reject a pending refund.

    The rejection reason is required and persisted on the refund record.
    """

    rejection_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Meaningful reason for rejecting the refund (10-500 characters)",
    )


class RefundStudentContext(BaseModel):
    """Student/employee identity context for an admin refund view."""

    id: str
    first_name: str
    last_name: str
    university_email: str
    university_id: str
    role: str


class RefundOrderContext(BaseModel):
    """Order context for an admin refund view."""

    id: str
    order_number: int
    status: str
    payment_method: str
    total_amount: int
    currency: str
    order_date: date | None = None
    cafeteria_id: str | None = None
    cafeteria_name: str | None = None
    created_at: datetime


class RefundPaymentContext(BaseModel):
    """Payment context for an admin refund view.

    Exposes only non-sensitive payment metadata (status, provider name and
    reference, amount) — never credentials, cards, or tokens.
    """

    id: str
    status: str
    provider_name: str | None = None
    provider_reference: str | None = None
    amount: int
    currency: str


class RefundAdminResponse(BaseModel):
    """Refund record with complete student/order/payment context."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    payment_id: str
    user_id: str
    amount: int
    currency: str
    status: str
    reason: str
    reason_note: str | None = None
    rejection_reason: str | None = None
    requested_by: str
    processed_by: str | None = None
    provider_reference: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    updated_at: datetime

    student: RefundStudentContext
    order: RefundOrderContext
    payment: RefundPaymentContext


class RefundAdminListResponse(BaseModel):
    """List of refunds with admin context."""

    refunds: list[RefundAdminResponse]
    total: int
