"""Cash payment provider (null provider).

Cash orders never go through an external payment provider: the payment
record is pure bookkeeping (PENDING at checkout, SUCCEEDED at handover).
This null provider exists so production code paths never reference the
test mock — every provider operation on it fails closed.

It is intentionally NOT registered in PROVIDER_REGISTRY: cash is selected
by payment method, never via the settings.PAYMENT_PROVIDER name.
"""

from __future__ import annotations

from typing import Any

from app.modules.payments.providers.base import (
    PaymentInitiationResult,
    PaymentProvider,
    PaymentVerificationResult,
    RefundResult,
    WebhookVerificationResult,
)


class CashPaymentProvider(PaymentProvider):
    """Null provider for cash bookkeeping. All operations fail closed."""

    @property
    def name(self) -> str:
        return "cash"

    async def initiate_payment(
        self,
        *,
        payment_id: str,
        order_id: str,
        amount: int,
        currency: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> PaymentInitiationResult:
        return PaymentInitiationResult(
            success=False,
            error_message="Cash payments do not use a payment provider",
        )

    async def verify_payment(
        self,
        *,
        provider_reference: str,
        payment_id: str | None = None,
    ) -> PaymentVerificationResult:
        return PaymentVerificationResult(
            success=False,
            error_message="Cash payments do not use a payment provider",
        )

    async def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> WebhookVerificationResult:
        return WebhookVerificationResult(
            valid=False,
            error_message="Cash payments do not use a payment provider",
        )

    async def process_refund(
        self,
        *,
        refund_id: str,
        payment_id: str,
        provider_reference: str,
        amount: int,
        currency: str,
        idempotency_key: str,
        reason: str | None = None,
    ) -> RefundResult:
        return RefundResult(
            success=False,
            error_message="Cash payments do not use a payment provider",
        )
