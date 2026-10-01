"""Payment API endpoints.

Handles:
- Payment retrieval
- Payment initiation (online)
- Webhook reception (provider-specific)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import AuthContext, get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.modules.payments.providers.test_provider import TestPaymentProvider
from app.modules.payments.schemas import (
    PaymentInitiateRequest,
    PaymentInitiationResponse,
    PaymentListResponse,
    PaymentResponse,
)
from app.modules.payments.service import PaymentService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.payments.providers.base import PaymentProvider

router = APIRouter()


def _get_payment_provider() -> PaymentProvider:
    """Get the payment provider.

    In production, this would load the configured provider.
    For now, uses the test provider.
    """
    return TestPaymentProvider()


def _get_payment_service(db: AsyncSession) -> PaymentService:
    """Create a PaymentService with the configured provider."""
    return PaymentService(db, _get_payment_provider())


@router.get("/", response_model=PaymentListResponse)
async def list_my_payments(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentListResponse:
    """List the current user's payments."""
    service = _get_payment_service(db)
    payments = await service.list_user_payments(user_id=auth.user.id)
    return PaymentListResponse(
        payments=[PaymentResponse.model_validate(p) for p in payments],
        total=len(payments),
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Get payment details (owner only)."""
    service = _get_payment_service(db)
    payment = await service.get_payment(payment_id)
    if payment.user_id != auth.user.id:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Payment not found")
    return PaymentResponse.model_validate(payment)


@router.post("/initiate/{order_id}", response_model=PaymentInitiationResponse, status_code=201)
async def initiate_payment_for_order(
    order_id: str,
    body: PaymentInitiateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentInitiationResponse:
    """Initiate an online payment for a specific order."""
    # Fail closed: the only wired provider is the test provider, which
    # simulates successful payments. It must never process real money in
    # production — refuse initiation until a real provider is configured.
    if settings.APP_ENV == "production" and isinstance(
        _get_payment_provider(), TestPaymentProvider
    ):
        raise ServiceUnavailableError(
            "Online payments are unavailable: no production payment provider is configured"
        )
    service = _get_payment_service(db)
    payment, redirect_url = await service.initiate_online_payment(
        order_id=order_id,
        user_id=auth.user.id,
        idempotency_key=body.idempotency_key,
    )
    return PaymentInitiationResponse(
        payment_id=payment.id,
        status=payment.status.value,
        provider_name=payment.provider_name,
        redirect_url=redirect_url,
        message="Payment initiated" if payment.status.value == "processing" else "Payment failed",
    )


@router.post("/webhook/{provider_name}")
async def payment_webhook(
    provider_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive a payment webhook from a provider.

    No authentication — security is handled via webhook signature verification.
    """
    payload = await request.body()
    headers = dict(request.headers)

    # Extract event ID from headers or body
    provider_event_id = headers.get("x-event-id", "unknown")

    service = _get_payment_service(db)
    processed = await service.process_webhook(
        provider_name=provider_name,
        payload=payload,
        provider_event_id=provider_event_id,
    )

    return {"status": "ok" if processed else "ignored"}


@router.get("/order/{order_id}", response_model=PaymentResponse)
async def get_order_payment(
    order_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Get the payment for an order (owner only)."""
    from sqlalchemy import select

    from app.core.exceptions import NotFoundException
    from app.modules.orders.models import Order

    service = _get_payment_service(db)

    # Verify order ownership
    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one_or_none()
    if order is None:
        raise NotFoundException("Order", order_id)
    if order.user_id != auth.user.id:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Order not found")

    payment = await service.get_order_payment(order_id)
    if payment is None:
        raise NotFoundException("Payment", f"for order {order_id}")
    return PaymentResponse.model_validate(payment)
