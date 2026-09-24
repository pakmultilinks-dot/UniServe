"""Test refund processor — for development and testing only.

NOT a production processor. Never treat as real financial processing.
Kept isolated from production configuration.
"""

from __future__ import annotations

from app.modules.refunds.processors.base import RefundProcessingResult, RefundProcessor


class TestRefundProcessor(RefundProcessor):
    """Mock refund processor for testing.

    Simulates refund flows without real financial transactions.
    """

    @property
    def name(self) -> str:
        return "test_processor"

    async def create_refund(
        self,
        *,
        refund_id: str,
        payment_provider_reference: str,
        amount: int,
        currency: str,
        idempotency_key: str,
        reason: str | None = None,
    ) -> RefundProcessingResult:
        """Simulate refund creation — always succeeds in test mode."""
        if payment_provider_reference and payment_provider_reference.startswith("test_pay_"):
            return RefundProcessingResult(
                success=True,
                provider_reference=f"test_ref_{refund_id[:12]}",
                provider_metadata={"test": True, "simulated": True},
            )
        return RefundProcessingResult(
            success=False,
            error_message="Cannot refund unknown test payment reference",
        )

    async def verify_refund(
        self,
        *,
        provider_reference: str,
    ) -> RefundProcessingResult:
        """Simulate refund verification."""
        if provider_reference and provider_reference.startswith("test_ref_"):
            return RefundProcessingResult(
                success=True,
                provider_reference=provider_reference,
                provider_metadata={"test": True, "verified": True},
            )
        return RefundProcessingResult(
            success=False,
            error_message="Unknown test refund reference",
        )
