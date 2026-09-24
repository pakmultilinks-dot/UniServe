"""Test payment provider — for development and testing only.

NOT a production provider. Never treat as real financial processing.
Kept isolated from production configuration.
"""

from __future__ import annotations

import json
from typing import Any

from app.modules.payments.providers.base import (
    PaymentInitiationResult,
    PaymentProvider,
    PaymentVerificationResult,
    RefundResult,
    WebhookVerificationResult,
)


class TestPaymentProvider(PaymentProvider):
    """Mock payment provider for testing.

    Simulates payment flows without real financial transactions.
    - All payments succeed immediately
    - Refunds succeed immediately
    - Webhook signatures always valid
    """

    @property
    def name(self) -> str:
        return "test_provider"

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
        """Simulate payment initiation — returns a test reference."""
        return PaymentInitiationResult(
            success=True,
            provider_reference=f"test_pay_{payment_id[:12]}",
            provider_metadata={"test": True, "simulated_at": "initiation"},
        )

    async def verify_payment(
        self,
        *,
        provider_reference: str,
        payment_id: str | None = None,
    ) -> PaymentVerificationResult:
        """Simulate payment verification — always succeeds for test refs."""
        if provider_reference and provider_reference.startswith("test_pay_"):
            return PaymentVerificationResult(
                success=True,
                provider_reference=provider_reference,
                provider_metadata={"test": True, "verified": True},
            )
        return PaymentVerificationResult(
            success=False,
            error_message="Unknown test payment reference",
        )

    async def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> WebhookVerificationResult:
        """Simulate webhook verification — always succeeds in test mode."""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return WebhookVerificationResult(
                valid=False,
                error_message="Invalid JSON payload",
            )

        return WebhookVerificationResult(
            valid=True,
            event_id=data.get("event_id", "test_event"),
            event_type=data.get("event_type", "payment_success"),
            payment_reference=data.get("payment_reference"),
            amount=data.get("amount"),
            currency=data.get("currency", "PKR"),
            metadata=data.get("metadata"),
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
        """Simulate refund processing — always succeeds for test refs."""
        if provider_reference and provider_reference.startswith("test_pay_"):
            return RefundResult(
                success=True,
                provider_reference=f"test_ref_{refund_id[:12]}",
                provider_metadata={"test": True, "simulated_at": "refund"},
            )
        return RefundResult(
            success=False,
            error_message="Cannot refund unknown test payment reference",
        )
