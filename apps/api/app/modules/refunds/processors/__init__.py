"""Refund processor abstraction layer.

Processor selection is configuration-driven via settings.REFUND_PROCESSOR.
Unknown names fail closed — the system never silently falls back to the
test processor (mirrors app.modules.payments.providers).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.modules.refunds.processors.test_processor import TestRefundProcessor

if TYPE_CHECKING:
    from app.modules.refunds.processors.base import RefundProcessor

# Registry of processor name -> implementation.
# A real processor registers here; selection is via settings.REFUND_PROCESSOR.
PROCESSOR_REGISTRY: dict[str, type[RefundProcessor]] = {
    "test": TestRefundProcessor,
}

DEFAULT_PROCESSOR_NAME = "test"


def create_refund_processor(name: str | None = None) -> RefundProcessor:
    """Instantiate the configured refund processor by name.

    Fails closed on unknown/unconfigured names — never silently falls
    back to the mock processor.
    """
    processor_name = (name or settings.REFUND_PROCESSOR or DEFAULT_PROCESSOR_NAME).strip().lower()
    processor_cls = PROCESSOR_REGISTRY.get(processor_name)
    if processor_cls is None:
        raise ServiceUnavailableError("Refund processor is not configured")
    return processor_cls()

