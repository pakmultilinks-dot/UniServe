"""Phase 60 — operations hardening unit tests (Workstreams D/E/F).

- D: session reaping (revoked residue + dormant-active residue, grace
  windows, protection guard, dry-run parity).
- E: stale payment reconciliation (cancelled-order closure, completed-cash
  ledger confirmation, sandbox permissiveness, idempotency, dry-run).
- F: webhook idempotency + reconciliation proof (duplicate events, terminal
  state protection, explicit unprocessed logging).

All tests run on the existing aiosqlite in-memory suite via conftest
fixtures; no live database is touched.
"""

import itertools
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.auth.service import reap_sessions
from app.modules.orders.models import (
    Order,
    OrderEvent,
    OrderEventType,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import (
    Payment,
    PaymentStatus,
    WebhookEvent,
)
from app.modules.payments.providers.base import WebhookVerificationResult
from app.modules.payments.service import PaymentService, reconcile_stale_payments
from app.modules.users.models import User, UserSession
from tests.conftest import create_test_cafeteria, create_test_user

_order_numbers = itertools.count(900_000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_order(
    db: AsyncSession,
    *,
    user: User,
    cafeteria: Any,
    status: OrderStatus = OrderStatus.PENDING,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    order_type: OrderType = OrderType.IMMEDIATE,
    total_amount: int = 25_000,
) -> Order:
    order = Order(
        order_number=next(_order_numbers),
        user_id=user.id,
        cafeteria_id=cafeteria.id,
        order_type=order_type,
        payment_method=payment_method,
        status=status,
        total_amount=total_amount,
        currency="PKR",
        order_date=date.today(),
    )
    db.add(order)
    await db.flush()
    return order


async def _seed_payment(
    db: AsyncSession,
    *,
    order: Order,
    status: PaymentStatus = PaymentStatus.PENDING,
    provider_name: str = "cash",
    provider_reference: str | None = None,
    created_age_hours: int = 48,
    amount: int | None = None,
) -> Payment:
    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order.id,
        user_id=order.user_id,
        amount=amount if amount is not None else order.total_amount,
        currency=order.currency,
        status=status,
        provider_name=provider_name,
        provider_reference=provider_reference,
        idempotency_key=f"p60_{uuid.uuid4().hex}",
        created_at=datetime.now(UTC) - timedelta(hours=created_age_hours),
    )
    db.add(payment)
    await db.flush()
    return payment


async def _seed_session(
    db: AsyncSession,
    *,
    user: User,
    is_active: bool = True,
    revoked_at: datetime | None = None,
    last_activity_at: datetime | None = None,
) -> UserSession:
    session = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        refresh_token_jti=f"p60_{uuid.uuid4().hex}",
        is_active=is_active,
        revoked_at=revoked_at,
        last_activity_at=last_activity_at or datetime.now(UTC),
    )
    db.add(session)
    await db.flush()
    return session


async def _session_ids(db: AsyncSession) -> set[str]:
    result = await db.execute(select(UserSession.id))
    return set(result.scalars().all())


class _WebhookStubProvider:
    """Minimal PaymentProvider stand-in — only what process_webhook calls."""

    name = "stubpay"

    def __init__(self, verification: WebhookVerificationResult) -> None:
        self._verification = verification

    async def verify_webhook_signature(
        self, *, payload: bytes, headers: dict[str, str]
    ) -> WebhookVerificationResult:
        return self._verification


def _verification(
    *,
    valid: bool = True,
    event_id: str = "evt_1",
    event_type: str = "payment_success",
    payment_reference: str | None = None,
    amount: int | None = None,
    currency: str = "PKR",
    error_message: str | None = None,
) -> WebhookVerificationResult:
    return WebhookVerificationResult(
        valid=valid,
        event_id=event_id,
        event_type=event_type,
        payment_reference=payment_reference,
        amount=amount,
        currency=currency,
        metadata={"stub": True},
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# Workstream D — session reaping
# ---------------------------------------------------------------------------


class TestSessionReaping:
    async def test_reap_deletes_old_revoked_sessions_only(self, db: AsyncSession):
        user = await create_test_user(db, university_email="reap1@lgu.edu.pk")
        old_revoked = await _seed_session(
            db,
            user=user,
            is_active=False,
            revoked_at=datetime.now(UTC) - timedelta(days=10),
        )
        _recent_revoked = await _seed_session(
            db,
            user=user,
            is_active=False,
            revoked_at=datetime.now(UTC) - timedelta(days=1),
        )
        _recent_active = await _seed_session(db, user=user)

        summary = await reap_sessions(db, revoked_grace_days=7)

        assert summary["revoked_deleted"] == 1
        assert summary["stale_active_deleted"] == 0
        assert summary["total_deleted"] == 1
        remaining = await _session_ids(db)
        assert old_revoked.id not in remaining
        assert len(remaining) == 2  # recent revoked + recent active kept

    async def test_reap_deletes_dormant_active_beyond_jwt_ttl(self, db: AsyncSession):
        user = await create_test_user(db, university_email="reap2@lgu.edu.pk")
        dormant = await _seed_session(
            db,
            user=user,
            last_activity_at=datetime.now(UTC)
            - timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS + 6),
        )
        active_within_ttl = await _seed_session(
            db,
            user=user,
            # Comfortably inside the (configured TTL + grace) window —
            # .env sets JWT_REFRESH_TOKEN_EXPIRE_DAYS=7, so the inactive
            # cutoff is 8 days; 4 days old must survive.
            last_activity_at=datetime.now(UTC)
            - timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS - 3),
        )

        summary = await reap_sessions(
            db, revoked_grace_days=7, inactive_grace_days=1
        )

        assert summary["stale_active_deleted"] == 1
        assert summary["revoked_deleted"] == 0
        remaining = await _session_ids(db)
        assert dormant.id not in remaining
        assert active_within_ttl.id in remaining

    async def test_reap_protects_session_id(self, db: AsyncSession):
        user = await create_test_user(db, university_email="reap3@lgu.edu.pk")
        old_revoked = await _seed_session(
            db,
            user=user,
            is_active=False,
            revoked_at=datetime.now(UTC) - timedelta(days=30),
        )

        summary = await reap_sessions(
            db, protect_session_id=old_revoked.id
        )

        assert summary["total_deleted"] == 0
        assert old_revoked.id in await _session_ids(db)

    async def test_reap_returns_zero_when_nothing_eligible(self, db: AsyncSession):
        user = await create_test_user(db, university_email="reap4@lgu.edu.pk")
        await _seed_session(db, user=user)
        await _seed_session(
            db,
            user=user,
            is_active=False,
            revoked_at=datetime.now(UTC) - timedelta(hours=2),
        )

        summary = await reap_sessions(db)

        assert summary["total_deleted"] == 0

    async def test_reap_dry_run_matches_execute_predicates(self, db: AsyncSession):
        user = await create_test_user(db, university_email="reap5@lgu.edu.pk")
        await _seed_session(
            db,
            user=user,
            is_active=False,
            revoked_at=datetime.now(UTC) - timedelta(days=10),
        )
        await _seed_session(
            db,
            user=user,
            last_activity_at=datetime.now(UTC)
            - timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS + 6),
        )

        preview = await reap_sessions(db, dry_run=True)
        assert preview["dry_run"] is True
        assert preview["revoked_deleted"] == 1
        assert preview["stale_active_deleted"] == 1

        applied = await reap_sessions(db)
        assert applied["dry_run"] is False
        assert applied["total_deleted"] == 2
        # Execute removed both eligible rows; dry-run had deleted nothing
        # before this call (preview assertions above passed on live rows).
        assert len(await _session_ids(db)) == 0


# ---------------------------------------------------------------------------
# Workstream E — stale payment reconciliation
# ---------------------------------------------------------------------------


class TestPaymentReconciliation:
    async def test_cancelled_order_pending_payment_becomes_cancelled(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="rec1@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db, user=user, cafeteria=cafeteria, status=OrderStatus.CANCELLED
        )
        payment = await _seed_payment(
            db,
            order=order,
            provider_name="cash",
            created_age_hours=48,
        )

        summary = await reconcile_stale_payments(db, stale_after_hours=24)

        assert summary["scanned"] == 1
        assert summary["order_cancelled_payments_closed"] == 1
        await db.refresh(payment)
        assert payment.status == PaymentStatus.CANCELLED
        assert payment.amount == order.total_amount  # amount never altered
        note = json.loads(payment.provider_metadata_json or "{}")["reconciliation"]
        assert note["reason"] == "order_cancelled_before_payment_completed"

    async def test_cancelled_order_recent_pending_payment_untouched(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="rec2@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db, user=user, cafeteria=cafeteria, status=OrderStatus.CANCELLED
        )
        payment = await _seed_payment(
            db, order=order, provider_name="online", created_age_hours=1
        )

        summary = await reconcile_stale_payments(db, stale_after_hours=24)

        assert summary["scanned"] == 0
        await db.refresh(payment)
        assert payment.status == PaymentStatus.PENDING

    async def test_completed_cash_pending_payment_confirmed(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="rec3@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db,
            user=user,
            cafeteria=cafeteria,
            status=OrderStatus.COMPLETED,
            payment_method=PaymentMethod.CASH,
        )
        payment = await _seed_payment(
            db, order=order, provider_name="cash", created_age_hours=48
        )

        summary = await reconcile_stale_payments(db)

        assert summary["completed_cash_payments_confirmed"] == 1
        await db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.amount == order.total_amount

    async def test_online_processing_on_cancelled_order_closed(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="rec4@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db,
            user=user,
            cafeteria=cafeteria,
            status=OrderStatus.CANCELLED,
            payment_method=PaymentMethod.ONLINE,
        )
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.PROCESSING,
            provider_name="jazzcash",
            provider_reference="prov_ref_1",
            created_age_hours=72,
        )

        summary = await reconcile_stale_payments(db)

        assert summary["order_cancelled_payments_closed"] == 1
        await db.refresh(payment)
        assert payment.status == PaymentStatus.CANCELLED

    async def test_succeeded_payment_untouched(self, db: AsyncSession):
        user = await create_test_user(db, university_email="rec5@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(db, user=user, cafeteria=cafeteria)
        payment = await _seed_payment(
            db, order=order, status=PaymentStatus.SUCCEEDED, created_age_hours=96
        )

        summary = await reconcile_stale_payments(db)

        assert summary["scanned"] == 0
        await db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED

    async def test_pending_on_non_terminal_order_untouched_sandbox(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="rec6@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db, user=user, cafeteria=cafeteria, status=OrderStatus.PENDING
        )
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.PENDING,
            provider_name="jazzcash",
            created_age_hours=96,
        )

        summary = await reconcile_stale_payments(db)

        assert summary["scanned"] == 1
        assert summary["untouched"] == 1
        await db.refresh(payment)
        assert payment.status == PaymentStatus.PENDING

    async def test_reconcile_is_idempotent(self, db: AsyncSession):
        user = await create_test_user(db, university_email="rec7@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db, user=user, cafeteria=cafeteria, status=OrderStatus.CANCELLED
        )
        await _seed_payment(db, order=order, created_age_hours=48)

        first = await reconcile_stale_payments(db)
        second = await reconcile_stale_payments(db)

        assert first["order_cancelled_payments_closed"] == 1
        assert second["scanned"] == 0
        assert second["order_cancelled_payments_closed"] == 0

    async def test_dry_run_classifies_without_mutating(self, db: AsyncSession):
        user = await create_test_user(db, university_email="rec8@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        cancelled_order = await _seed_order(
            db, user=user, cafeteria=cafeteria, status=OrderStatus.CANCELLED
        )
        completed_order = await _seed_order(
            db,
            user=user,
            cafeteria=cafeteria,
            status=OrderStatus.COMPLETED,
            payment_method=PaymentMethod.CASH,
        )
        cancelled_payment = await _seed_payment(
            db, order=cancelled_order, created_age_hours=48
        )
        cash_payment = await _seed_payment(
            db,
            order=completed_order,
            provider_name="cash",
            created_age_hours=48,
        )

        preview = await reconcile_stale_payments(db, dry_run=True)
        assert preview["dry_run"] is True
        assert preview["order_cancelled_payments_closed"] == 1
        assert preview["completed_cash_payments_confirmed"] == 1
        await db.refresh(cancelled_payment)
        await db.refresh(cash_payment)
        assert cancelled_payment.status == PaymentStatus.PENDING
        assert cash_payment.status == PaymentStatus.PENDING


# ---------------------------------------------------------------------------
# Workstream F — webhook idempotency + reconciliation
# ---------------------------------------------------------------------------


class TestWebhookIdempotency:
    async def test_duplicate_success_webhook_single_business_effect(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="wh1@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db,
            user=user,
            cafeteria=cafeteria,
            payment_method=PaymentMethod.ONLINE,
        )
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.PROCESSING,
            provider_name="stubpay",
            provider_reference="prov_ref_dup",
        )
        service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    event_id="evt_dup_1",
                    payment_reference="prov_ref_dup",
                    amount=order.total_amount,
                )
            ),
        )

        first = await service.process_webhook(
            provider_name="stubpay",
            payload=b'{"event":"payment_success"}',
            provider_event_id="evt_dup_1",
        )
        second = await service.process_webhook(
            provider_name="stubpay",
            payload=b'{"event":"payment_success"}',
            provider_event_id="evt_dup_1",
        )

        assert first is True
        assert second is False  # duplicate detected via verified event ID
        await db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED

        confirmed_events = (
            await db.execute(
                select(OrderEvent).where(
                    OrderEvent.order_id == order.id,
                    OrderEvent.event_type == OrderEventType.PAYMENT_CONFIRMED,
                )
            )
        ).scalars().all()
        assert len(confirmed_events) == 1  # single business effect

        stored = (
            await db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.provider_event_id == "evt_dup_1"
                )
            )
        ).scalars().all()
        assert len(stored) == 1
        assert stored[0].processed is True

    async def test_failure_webhook_after_success_is_ignored(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="wh2@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db,
            user=user,
            cafeteria=cafeteria,
            payment_method=PaymentMethod.ONLINE,
        )
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.PROCESSING,
            provider_name="stubpay",
            provider_reference="prov_ref_fail",
        )
        success_service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    event_id="evt_ok",
                    payment_reference="prov_ref_fail",
                    amount=order.total_amount,
                )
            ),
        )
        await success_service.process_webhook(
            provider_name="stubpay",
            payload=b"{}",
            provider_event_id="evt_ok",
        )

        failure_service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    event_id="evt_late_fail",
                    event_type="payment_failed",
                    payment_reference="prov_ref_fail",
                    amount=order.total_amount,
                )
            ),
        )
        result = await failure_service.process_webhook(
            provider_name="stubpay",
            payload=b"{}",
            provider_event_id="evt_late_fail",
        )

        await db.refresh(payment)
        assert result is True  # event processed, but no state flip
        assert payment.status == PaymentStatus.SUCCEEDED
        all_events = (
            await db.execute(
                select(OrderEvent).where(OrderEvent.order_id == order.id)
            )
        ).scalars().all()
        # Only the success-time pair exists — INVENTORY_RESERVED + the single
        # PAYMENT_CONFIRMED emitted by the first webhook. The failure event
        # added nothing and never flipped the payment.
        assert len(all_events) == 2
        event_types = {e.event_type for e in all_events}
        assert event_types == {
            OrderEventType.INVENTORY_RESERVED,
            OrderEventType.PAYMENT_CONFIRMED,
        }

    async def test_amount_mismatch_webhook_logged_unprocessed(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="wh3@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db, user=user, cafeteria=cafeteria, total_amount=25_000
        )
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.PENDING,
            provider_name="stubpay",
            provider_reference="prov_ref_amt",
        )
        service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    event_id="evt_amt_bad",
                    payment_reference="prov_ref_amt",
                    amount=1,  # spoofed/wrong amount
                )
            ),
        )

        result = await service.process_webhook(
            provider_name="stubpay",
            payload=b"{}",
            provider_event_id="evt_amt_bad",
        )

        assert result is False
        await db.refresh(payment)
        assert payment.status == PaymentStatus.PENDING  # never auto-succeeded
        stored = (
            await db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.provider_event_id == "evt_amt_bad"
                )
            )
        ).scalar_one()
        assert stored.processed is False
        assert "Amount mismatch" in (stored.error_message or "")

    async def test_invalid_signature_webhook_logged_unprocessed(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="wh4@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(db, user=user, cafeteria=cafeteria)
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.PENDING,
            provider_name="stubpay",
            provider_reference="prov_ref_sig",
        )
        service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    valid=False,
                    event_id="evt_bad_sig",
                    payment_reference="prov_ref_sig",
                    amount=order.total_amount,
                    error_message="signature check failed",
                )
            ),
        )

        result = await service.process_webhook(
            provider_name="stubpay",
            payload=b"{}",
            provider_event_id="evt_bad_sig",
        )

        assert result is False
        await db.refresh(payment)
        assert payment.status == PaymentStatus.PENDING
        stored = (
            await db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.provider_event_id == "evt_bad_sig"
                )
            )
        ).scalar_one()
        assert stored.processed is False
        assert stored.error_message == "signature check failed"

    async def test_unknown_payment_reference_logged_unprocessed(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="wh5@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        await _seed_order(db, user=user, cafeteria=cafeteria)
        service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    event_id="evt_unknown_ref",
                    payment_reference="does_not_exist",
                    amount=25_000,
                )
            ),
        )

        result = await service.process_webhook(
            provider_name="stubpay",
            payload=b"{}",
            provider_event_id="evt_unknown_ref",
        )

        assert result is False
        stored = (
            await db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.provider_event_id == "evt_unknown_ref"
                )
            )
        ).scalar_one()
        assert stored.processed is False
        assert "Unknown payment reference" in (stored.error_message or "")

    async def test_late_success_on_terminal_payment_treated_processed(
        self, db: AsyncSession
    ):
        user = await create_test_user(db, university_email="wh6@lgu.edu.pk")
        cafeteria = await create_test_cafeteria(db)
        order = await _seed_order(
            db, user=user, cafeteria=cafeteria, status=OrderStatus.CANCELLED
        )
        payment = await _seed_payment(
            db,
            order=order,
            status=PaymentStatus.CANCELLED,
            provider_name="stubpay",
            provider_reference="prov_ref_terminal",
        )
        service = PaymentService(
            db,
            _WebhookStubProvider(
                _verification(
                    event_id="evt_late",
                    payment_reference="prov_ref_terminal",
                    amount=order.total_amount,
                )
            ),
        )

        result = await service.process_webhook(
            provider_name="stubpay",
            payload=b"{}",
            provider_event_id="evt_late",
        )

        assert result is True  # valid event, terminally ignored
        await db.refresh(payment)
        assert payment.status == PaymentStatus.CANCELLED  # never resurrected
        stored = (
            await db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.provider_event_id == "evt_late"
                )
            )
        ).scalar_one()
        assert stored.processed is True
