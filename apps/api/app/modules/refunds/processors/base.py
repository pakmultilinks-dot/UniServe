"""Refund processor abstraction — interface for refund processing."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class RefundProcessingResult:
    """Result of processing a refund through a processor/provider."""

    success: bool
    provider_reference: str | None = None
    provider_metadata: dict[str, Any] | None = None
    error_message: str | None = None


class RefundProcessor(abc.ABC):
    """Abstract base class for refund processors.

    A refund processor handles the actual refund transaction with
    an external provider. It follows the same abstraction boundary
    as the PaymentProvider.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique processor name."""

    @abc.abstractmethod
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
        """Create a refund with the external processor."""

    @abc.abstractmethod
    async def verify_refund(
        self,
        *,
        provider_reference: str,
    ) -> RefundProcessingResult:
        """Verify a refund's status with the processor."""
