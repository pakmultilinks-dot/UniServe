"""Tests — payment provider configuration & isolation boundaries.

Phase 24 provider-readiness guarantees:
- Test provider usable in development and testing environments
- Unknown/unconfigured provider fails closed (no silent mock fallback)
- Production initiation stays blocked with the mock provider (Phase 23 guard)
- Cash payments unaffected in production
- Webhook idempotency keyed on the verified payload event ID
  (x-event-id header no longer required)
"""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.modules.payments.models import Payment, WebhookEvent
from app.modules.payments.providers import (
    DEFAULT_PROVIDER_NAME,
    PROVIDER_REGISTRY,
    create_payment_provider,
)
from app.modules.payments.providers.test_provider import TestPaymentProvider
from tests.test_payments import _add_cart_item, _checkout, _setup_test_data

# ---------------------------------------------------------------------------
# Provider factory — selection & fail-closed behavior
# ---------------------------------------------------------------------------


class TestProviderFactory:
    """Provider selection is configuration-driven and fails closed."""

    def test_default_selection_returns_test_provider(self):
        """Default/dev/test configuration resolves the mock provider."""
        provider = create_payment_provider()
        assert isinstance(provider, TestPaymentProvider)
        assert provider.name == "test_provider"

    def test_explicit_test_name_is_case_insensitive(self):
        """PAYMENT_PROVIDER=test / TEST both resolve the mock provider."""
        assert isinstance(create_payment_provider("test"), TestPaymentProvider)
        assert isinstance(create_payment_provider("TEST"), TestPaymentProvider)

    def test_unknown_provider_name_fails_closed(self):
        """Unregistered provider names raise — never fall back to mock."""
        with pytest.raises(ServiceUnavailableError) as exc_info:
            create_payment_provider("nonexistent_provider")
        assert exc_info.value.code == "SERVICE_UNAVAILABLE"

    def test_unconfigured_production_style_name_fails_closed(
        self, monkeypatch
    ):
        """An unregistered PAYMENT_PROVIDER setting fails closed."""
        monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "some-bank-gateway")
        with pytest.raises(ServiceUnavailableError):
            create_payment_provider()

    def test_registry_contains_only_test_provider(self):
        """Until a real provider is implemented, only 'test' is registered."""
        assert set(PROVIDER_REGISTRY.keys()) == {"test"}
        assert DEFAULT_PROVIDER_NAME == "test"


# ---------------------------------------------------------------------------
# Environment isolation — dev/test allowed, production rejected, cash safe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEnvironmentIsolation:
    """Mock provider usable in dev/test; rejected in production; cash safe."""

    async def test_cash_payment_works_in_production(
        self, student_client: AsyncClient, student_user, db: AsyncSession, monkeypatch
    ):
        """Cash checkout succeeds even with APP_ENV=production.

        The production guard targets the mock online provider only —
        cash payments never touch a provider and must keep working.
        """
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        monkeypatch.setattr(settings, "APP_ENV", "production")
        resp = await _checkout(student_client, cafeteria.id, payment_method="cash")
        assert resp.status_code == 201, resp.text

        result = await db.execute(
            select(Payment).where(Payment.order_id == resp.json()["id"])
        )
        payment = result.scalar_one()
        assert payment.provider_name == "cash"
        assert payment.status.value == "pending"

    async def test_unknown_provider_blocks_initiation(
        self, student_client: AsyncClient, student_user, db: AsyncSession, monkeypatch
    ):
        """Initiation with an unregistered provider fails closed (503).

        Proves there is no silent fallback to the mock provider when
        PAYMENT_PROVIDER points at a provider that is not implemented.
        """
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "jazzcash-not-registered")

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "unknown_provider_key"},
        )
        assert resp.status_code == 503, resp.text
        assert resp.json()["code"] == "SERVICE_UNAVAILABLE"

    async def test_testing_environment_can_use_mock_provider(
        self, student_client: AsyncClient, student_user, db: AsyncSession, monkeypatch
    ):
        """APP_ENV=testing is NOT blocked — mock provider stays usable."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        resp = await _checkout(student_client, cafeteria.id, payment_method="online")
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        monkeypatch.setattr(settings, "APP_ENV", "testing")

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "testing_env_key"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["provider_name"] == "test_provider"


# ---------------------------------------------------------------------------
# Webhook idempotency — verified payload event ID, header optional
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookVerifiedEventId:
    """Idempotency uses the verified payload event ID, not the header."""

    async def test_webhook_idempotent_without_header(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """Duplicate webhooks are ignored even without x-event-id header.

        The canonical event ID comes from the signed payload. A provider
        that does not send an x-event-id header must still get correct
        duplicate suppression.
        """
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(
            student_client, cafeteria.id, payment_method="online"
        )
        order_id = checkout_resp.json()["id"]
        total_amount = checkout_resp.json()["total_amount"]

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "no_header_key"},
        )
        assert resp.status_code == 201, resp.text

        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()

        payload = json.dumps(
            {
                "event_id": "nohdr_evt_001",
                "event_type": "payment_success",
                "payment_reference": payment.provider_reference,
                "amount": total_amount,
                "currency": "PKR",
            }
        ).encode()
        headers = {"Content-Type": "application/json"}  # deliberately NO x-event-id

        r1 = await student_client.post(
            "/api/v1/payments/webhook/test_provider",
            content=payload,
            headers=headers,
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["status"] == "ok"

        # Event stored under the verified payload event ID
        stored = await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == "nohdr_evt_001")
        )
        assert stored.scalar_one_or_none() is not None

        # Duplicate — same signed payload, no header — must be ignored
        r2 = await student_client.post(
            "/api/v1/payments/webhook/test_provider",
            content=payload,
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "ignored"

    async def test_spoofed_header_cannot_suppress_new_event(
        self, student_client: AsyncClient, student_user, db: AsyncSession
    ):
        """A forged x-event-id cannot cause a NEW signed event to be dropped.

        Idempotency is decided after signature verification, using the
        verified payload event ID — unverified header input is never used
        as the deduplication key.
        """
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(
            student_client, cafeteria.id, payment_method="online"
        )
        order_id = checkout_resp.json()["id"]
        total_amount = checkout_resp.json()["total_amount"]

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "spoof_header_key"},
        )
        assert resp.status_code == 201, resp.text

        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()

        # First event — processed and recorded under its verified ID
        payload1 = json.dumps(
            {
                "event_id": "spoof_evt_001",
                "event_type": "payment_success",
                "payment_reference": payment.provider_reference,
                "amount": total_amount,
                "currency": "PKR",
            }
        ).encode()
        r1 = await student_client.post(
            "/api/v1/payments/webhook/test_provider",
            content=payload1,
            headers={"Content-Type": "application/json", "x-event-id": "spoof_evt_001"},
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "ok"

        # Payment is already SUCCEEDED — a second distinct signed event with
        # a SPOOFED header (claiming the processed ID) is verified first:
        # the payload event ID differs, so it is NOT treated as a replay
        # and must be acknowledged as processed ("ok"), not dropped.
        payload2 = json.dumps(
            {
                "event_id": "spoof_evt_002",
                "event_type": "payment_success",
                "payment_reference": payment.provider_reference,
                "amount": total_amount,
                "currency": "PKR",
            }
        ).encode()
        r2 = await student_client.post(
            "/api/v1/payments/webhook/test_provider",
            content=payload2,
            headers={
                "Content-Type": "application/json",
                "x-event-id": "spoof_evt_001",  # forged — claims processed ID
            },
        )
        assert r2.status_code == 200
        # Verified payload ID (spoof_evt_002) wins over the forged header —
        # the event is processed idempotently, not suppressed as a replay.
        assert r2.json()["status"] == "ok"

        # State remains correct: exactly one succeeded payment, no duplicates
        await db.refresh(payment)
        assert payment.status.value == "succeeded"


# ---------------------------------------------------------------------------
# Production webhook guard — test provider rejected in production
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookProductionGuard:
    """Webhook traffic is blocked in production while the mock provider
    is configured — mirroring the initiation guard (Phase 36).

    Signature/idempotency behavior stays covered by
    TestWebhookVerifiedEventId; this class proves the fail-closed
    boundary itself.
    """

    async def test_webhook_blocked_in_production_with_test_provider(
        self, student_client: AsyncClient, student_user, db: AsyncSession, monkeypatch
    ):
        """503 in production + mock provider; no event stored; payment untouched."""
        cafeteria, item, _ = await _setup_test_data(db)

        await _add_cart_item(student_client, cafeteria.id, item.id)
        checkout_resp = await _checkout(
            student_client, cafeteria.id, payment_method="online"
        )
        order_id = checkout_resp.json()["id"]
        total_amount = checkout_resp.json()["total_amount"]

        resp = await student_client.post(
            f"/api/v1/payments/initiate/{order_id}",
            json={"idempotency_key": "webhook_guard_key"},
        )
        assert resp.status_code == 201, resp.text

        result = await db.execute(select(Payment).where(Payment.order_id == order_id))
        payment = result.scalar_one()
        status_before_webhook = payment.status.value  # "processing" after initiation

        monkeypatch.setattr(settings, "APP_ENV", "production")

        payload = json.dumps(
            {
                "event_id": "guarded_evt_001",
                "event_type": "payment_success",
                "payment_reference": payment.provider_reference,
                "amount": total_amount,
                "currency": "PKR",
            }
        ).encode()

        r = await student_client.post(
            "/api/v1/payments/webhook/test_provider",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 503, r.text
        assert r.json()["code"] == "SERVICE_UNAVAILABLE"

        # No webhook event recorded; payment state untouched — the guard
        # rejects before any processing side effect.
        stored = await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == "guarded_evt_001")
        )
        assert stored.scalar_one_or_none() is None
        await db.refresh(payment)
        assert payment.status.value == status_before_webhook
