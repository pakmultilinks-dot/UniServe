"""Payment Pydantic schemas — request/response models for the payment API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PaymentInitiateRequest(BaseModel):
    """Request to initiate an online payment."""

    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique key to prevent duplicate payment initiation",
    )


class WebhookPayload(BaseModel):
    """Generic webhook payload — actual structure depends on provider."""

    model_config = ConfigDict(extra="allow")

    event_id: str = Field(..., description="Provider's unique event ID")
    event_type: str = Field(..., description="Type of event (e.g., payment_success)")
    payment_reference: str | None = Field(None, description="Provider payment reference")
    amount: int | None = Field(None, ge=0, description="Payment amount")
    currency: str | None = Field(None, description="Payment currency")
    metadata: dict | None = Field(None, description="Additional event metadata")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PaymentResponse(BaseModel):
    """Payment information for client-facing responses.

    Does NOT expose: provider secrets, webhook signatures, internal metadata.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    amount: int
    currency: str
    status: str
    provider_name: str | None = None
    created_at: datetime
    updated_at: datetime


class PaymentInitiationResponse(BaseModel):
    """Response after initiating a payment."""

    payment_id: str
    status: str
    provider_name: str | None = None
    redirect_url: str | None = None
    message: str = "Payment initiated"


class PaymentListResponse(BaseModel):
    """List of payments."""

    payments: list[PaymentResponse]
    total: int
