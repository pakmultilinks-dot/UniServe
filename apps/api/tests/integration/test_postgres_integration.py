"""Phase 60 (Workstream C) — real-PostgreSQL integration tests.

Executed ONLY via an explicit, gated run:

    UNISERVE_INTEGRATION_PG=1 POSTGRES_DB=uniserve_test_p60 \
    POSTGRES_PASSWORD=<cluster password> python -m pytest tests/integration -q

Every test proves behaviour on genuine PostgreSQL (timestamptz columns,
native constraints, StrEnum storage, unique indexes) against a disposable
``uniserve_test*`` database created by the fixtures in conftest.py. The
default suite collects this module but skips it (gate off).
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(
    os.environ.get("UNISERVE_INTEGRATION_PG") != "1",
    reason="PostgreSQL integration tests gated behind UNISERVE_INTEGRATION_PG=1",
)


def _uid() -> str:
    return uuid.uuid4().hex[:10]


async def test_target_database_disposable_and_migrated(pg_db):
    from app.core.config import settings

    current = await pg_db.scalar(text("SELECT current_database()"))
    assert current == settings.POSTGRES_DB
    assert current.startswith("uniserve_test")
    assert current not in {"uniserve_prod", "uniserve_dev"}

    version = await pg_db.scalar(text("SELECT version_num FROM alembic_version"))
    assert version  # migrations applied via alembic upgrade head

    tables = {
        row[0]
        for row in (
            await pg_db.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        ).all()
    }
    for required in (
        "users",
        "user_credentials",
        "user_sessions",
        "orders",
        "order_events",
        "payments",
        "payment_attempts",
        "webhook_events",
        "cafeterias",
        "menu_items",
    ):
        assert required in tables, f"missing table after migration: {required}"


async def test_auth_login_refresh_and_reap_on_real_pg(pg_db):
    from app.modules.auth.service import AuthService, reap_sessions
    from tests.conftest import create_test_user
    from tests.test_phase60_maintenance import _seed_session

    suffix = _uid()
    user = await create_test_user(
        pg_db,
        university_email=f"pg.login.{suffix}@lgu.edu.pk",
        university_id=f"PG-L-{suffix}",
        password="StrongPass1!",
    )

    auth = AuthService(pg_db)
    logged_in, tokens = await auth.login(
        f"pg.login.{suffix}@lgu.edu.pk", "StrongPass1!"
    )
    assert logged_in.id == user.id
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    session_rows = (
        await pg_db.execute(
            text(
                "SELECT is_active FROM user_sessions "
                "WHERE user_id = :uid ORDER BY created_at DESC"
            ),
            {"uid": user.id},
        )
    ).all()
    assert session_rows and session_rows[0][0] is True

    rotated = await auth.refresh_tokens(tokens["refresh_token"])
    assert rotated["refresh_token"]
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # Reap semantics on PostgreSQL timestamptz columns: only the freshly
    # created active session exists → nothing eligible.
    preview = await reap_sessions(pg_db, dry_run=True)
    assert preview["total_deleted"] == 0

    # Dormant residue seeded with explicit old timestamps IS eligible.
    await _seed_session(
        pg_db,
        user=user,
        last_activity_at=datetime.now(UTC) - timedelta(days=60),
    )
    summary = await reap_sessions(pg_db)
    assert summary["stale_active_deleted"] == 1


async def test_unique_refresh_token_jti_enforced_on_pg(pg_db):
    from tests.conftest import create_test_user
    from tests.test_phase60_maintenance import _seed_session

    suffix = _uid()
    user = await create_test_user(
        pg_db,
        university_email=f"pg.jti.{suffix}@lgu.edu.pk",
        university_id=f"PG-J-{suffix}",
    )
    await _seed_session(pg_db, user=user)

    from app.modules.users.models import UserSession

    existing_jti = (
        await pg_db.execute(
            text("SELECT refresh_token_jti FROM user_sessions WHERE user_id = :uid"),
            {"uid": user.id},
        )
    ).scalar_one()
    duplicate = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        refresh_token_jti=existing_jti,  # same value on purpose
        is_active=True,
    )
    pg_db.add(duplicate)
    with pytest.raises(IntegrityError):
        await pg_db.flush()
    await pg_db.rollback()


async def test_payment_reconciliation_on_real_pg(pg_db):
    from sqlalchemy import select

    from app.modules.orders.models import OrderStatus
    from app.modules.payments.models import Payment, PaymentStatus
    from app.modules.payments.service import reconcile_stale_payments
    from tests.conftest import create_test_cafeteria, create_test_user
    from tests.test_phase60_maintenance import _seed_order, _seed_payment

    suffix = _uid()
    user = await create_test_user(
        pg_db,
        university_email=f"pg.pay.{suffix}@lgu.edu.pk",
        university_id=f"PG-P-{suffix}",
    )
    cafeteria = await create_test_cafeteria(pg_db, name=f"PG Caf {suffix}")
    order = await _seed_order(
        pg_db,
        user=user,
        cafeteria=cafeteria,
        status=OrderStatus.CANCELLED,
        total_amount=42_000,
    )
    payment = await _seed_payment(
        pg_db,
        order=order,
        provider_name="cash",
        created_age_hours=48,
    )

    summary = await reconcile_stale_payments(pg_db, stale_after_hours=24)
    assert summary["order_cancelled_payments_closed"] >= 1

    refreshed = (
        await pg_db.execute(
            select(Payment).where(Payment.id == payment.id)
        )
    ).scalar_one()
    assert refreshed.status == PaymentStatus.CANCELLED
    assert refreshed.amount == 42_000  # server-authoritative amount intact


async def test_webhook_idempotency_on_real_pg(pg_db):
    from sqlalchemy import func, select

    from app.modules.orders.models import OrderEvent, OrderEventType, PaymentMethod
    from app.modules.payments.models import PaymentStatus, WebhookEvent
    from app.modules.payments.service import PaymentService
    from tests.conftest import create_test_cafeteria, create_test_user
    from tests.test_phase60_maintenance import (
        _seed_order,
        _seed_payment,
        _verification,
        _WebhookStubProvider,
    )

    suffix = _uid()
    user = await create_test_user(
        pg_db,
        university_email=f"pg.wh.{suffix}@lgu.edu.pk",
        university_id=f"PG-W-{suffix}",
    )
    cafeteria = await create_test_cafeteria(pg_db, name=f"PG WH Caf {suffix}")
    order = await _seed_order(
        pg_db,
        user=user,
        cafeteria=cafeteria,
        payment_method=PaymentMethod.ONLINE,
    )
    ref = f"prov_pg_{suffix}"
    payment = await _seed_payment(
        pg_db,
        order=order,
        status=PaymentStatus.PROCESSING,
        provider_name="stubpay",
        provider_reference=ref,
    )

    service = PaymentService(
        pg_db,
        _WebhookStubProvider(
            _verification(
                event_id=f"evt_pg_{suffix}",
                payment_reference=ref,
                amount=order.total_amount,
            )
        ),
    )
    first = await service.process_webhook(
        provider_name="stubpay",
        payload=b"{}",
        provider_event_id=f"evt_pg_{suffix}",
    )
    second = await service.process_webhook(
        provider_name="stubpay",
        payload=b"{}",
        provider_event_id=f"evt_pg_{suffix}",
    )
    assert first is True
    assert second is False

    stored_events = (
        await pg_db.execute(
            select(WebhookEvent).where(
                WebhookEvent.provider_event_id == f"evt_pg_{suffix}"
            )
        )
    ).scalars().all()
    assert len(stored_events) == 1
    assert stored_events[0].processed is True

    confirmed = (
        await pg_db.execute(
            select(func.count())
            .select_from(OrderEvent)
            .where(
                OrderEvent.order_id == order.id,
                OrderEvent.event_type == OrderEventType.PAYMENT_CONFIRMED,
            )
        )
    ).scalar_one()
    assert confirmed == 1  # single business effect on PostgreSQL
