"""Payment provider abstraction layer.

Provider selection is configuration-driven via settings.PAYMENT_PROVIDER.
Unknown names fail closed — the system never silently falls back to the
test provider.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.modules.payments.providers.base import PaymentProvider
from app.modules.payments.providers.test_provider import TestPaymentProvider

# Registry of provider name -> implementation.
# A real provider registers here; selection is via settings.PAYMENT_PROVIDER.
PROVIDER_REGISTRY: dict[str, type[PaymentProvider]] = {
    "test": TestPaymentProvider,
}

DEFAULT_PROVIDER_NAME = "test"


def create_payment_provider(name: str | None = None) -> PaymentProvider:
    """Instantiate the configured payment provider by name.

    Fails closed on unknown/unconfigured names — never silently falls
    back to the mock provider. Production must set PAYMENT_PROVIDER to
    a registered real provider name to enable online payments.
    """
    provider_name = name or settings.PAYMENT_PROVIDER or DEFAULT_PROVIDER_NAME
    provider_name = provider_name.strip().lower()
    provider_cls = PROVIDER_REGISTRY.get(provider_name)
    if provider_cls is None:
        raise ServiceUnavailableError("Payment provider is not configured")
    return provider_cls()
