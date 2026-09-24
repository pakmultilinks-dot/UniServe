"""Base payment provider interface.

All payment provider implementations must inherit from this ABC.
Business logic MUST depend on this interface, never on concrete providers.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class PaymentInitiationResult:
    """Result of initiating a payment with a provider."""

    success: bool
    provider_reference: str | None = None
    redirect_url: str | None = None
    provider_metadata: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class PaymentVerificationResult:
    """Result of verifying a payment with a provider."""

    success: bool
    provider_reference: str | None = None
    provider_metadata: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class WebhookVerificationResult:
    """Result of verifying and parsing a webhook event."""

    valid: bool
    event_id: str | None = None
    event_type: str | None = None
    payment_reference: str | None = None
    amount: int | None = None
    currency: str | None = None
    metadata: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class RefundResult:
    """Result of processing a refund with a provider."""

    success: bool
    provider_reference: str | None = None
    provider_metadata: dict[str, Any] | None = None
    error_message: str | None = None


class PaymentProvider(abc.ABC):
    """Abstract base class for payment providers.

    A payment provider handles:
    - Initiating payments
    - Verifying payment status
    - Processing webhooks
    - Processing refunds

    Concrete implementations should be isolated in their own modules.
    Never put provider-specific logic in business services.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique provider name (e.g., 'test', 'stripe', 'jazzcash')."""

    @abc.abstractmethod
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
        """Initiate a payment with the provider.

        The amount and currency are server-derived — the provider
        should confirm these match what it expects.
        """

    @abc.abstractmethod
    async def verify_payment(
        self,
        *,
        provider_reference: str,
        payment_id: str | None = None,
    ) -> PaymentVerificationResult:
        """Verify a payment's status with the provider."""

    @abc.abstractmethod
    async def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> WebhookVerificationResult:
        """Verify and parse a webhook event.

        Must verify the signature/authenticity of the webhook before
        returning any data.
        """

    @abc.abstractmethod
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
        """Process a refund through the provider."""
