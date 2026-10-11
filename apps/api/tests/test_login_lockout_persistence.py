"""Regression tests for password/PIN failed-attempt persistence (Phase 63).

Phase 63 security testing demonstrated the same transaction-boundary defect
that Phase 38 fixed for OTP, still present on the PASSWORD and PIN login
paths: ``login`` / ``login_with_pin`` incremented the failed-attempt counter
(and set the lockout timestamp) on the request session, then raised — while
``get_db`` rolls the request session back on exceptions. The counter and
lockout therefore never persisted, and the ``LOGIN_MAX_ATTEMPTS`` /
``PIN_MAX_FAILED_ATTEMPTS`` brute-force lockout controls were unreachable in
the production runtime.

Live evidence (Phase 63): 12 consecutive wrong-password logins against a
dedicated account left ``password_failed_attempts`` at 0 and produced zero
``login_failed`` rows in ``security_audit_events`` — the lockout never
engaged and the audit trail was blind to failed authentication.

These tests exercise the REAL ``get_db`` request boundary — a fresh DB
session per HTTP request with commit-on-success / rollback-on-exception —
against the isolated persistence database wired up by the session-scoped
``otp_persistence_factory`` fixture, and assert that:
1. Failed password attempts persist across separate requests.
2. The account locks at ``LOGIN_MAX_ATTEMPTS`` and stays locked (the
   correct password is rejected while locked).
3. Failed-login audit events survive (security audit trail integrity).
4. The same persistence holds for the PIN login path.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.users.models import UserCredential
from tests.conftest import create_test_user


async def _seed_user_with_password(factory, *, email: str, uid: str, password: str) -> str:
    """Seed a user + credential directly on the persistence DB; return user id."""
    async with factory() as session:
        user = await create_test_user(
            session,
            university_id=uid,
            university_email=email,
            password=password,
        )
        # create_test_user only flushes — commit so the fixture survives
        # the session close (matches the OTP persistence test pattern).
        await session.commit()
        return user.id


async def _read_credential(factory, user_id: str) -> UserCredential:
    """Read the credential row through a FRESH session (not in-memory state)."""
    async with factory() as session:
        result = await session.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        return result.scalar_one()


@pytest.mark.asyncio
async def test_password_failed_attempts_persist_and_lockout_engages(
    otp_persistence_factory,
):
    """Failed password attempts persist; the lockout control is reachable.

    Proves, across real request/session boundaries:
    1. Wrong passwords increment a PERSISTED attempt counter (survives the
       per-request rollback that discards flush-only updates).
    2. At LOGIN_MAX_ATTEMPTS the account locks (persisted lockout timestamp).
    3. While locked, even the CORRECT password is rejected with 423.
    4. Failed-login audit events survive for the security audit trail.
    """
    password = "CorrectHorse1!"
    user_id = await _seed_user_with_password(
        otp_persistence_factory,
        email="fa22-bse-lock1@lgu.edu.pk",
        uid="FA22-BSE-LOCK1",
        password=password,
    )

    # Requests run through the REAL get_db: one session per request,
    # commit on success, rollback on exception — the production boundary.
    app.dependency_overrides.pop(get_db, None)
    transport = ASGITransport(app=app)
    login_url = "/api/v1/auth/login"
    payload = {"university_email": "fa22-bse-lock1@lgu.edu.pk"}

    max_attempts = settings.LOGIN_MAX_ATTEMPTS
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Wrong passwords each get their own request context (401 each).
        for i in range(max_attempts):
            resp = await client.post(login_url, json={**payload, "password": f"Wrong{i}!"})
            assert resp.status_code == 401
            assert resp.json()["code"] == "AUTHENTICATION_ERROR"

        # 2. The counter persisted across request boundaries — read back
        #    through a FRESH session, not in-memory ORM state.
        cred = await _read_credential(otp_persistence_factory, user_id)
        assert cred.password_failed_attempts == max_attempts
        assert cred.password_locked_until is not None

        # 3. The lockout is now ENFORCED: even the correct password is
        #    rejected while the lock is active.
        resp = await client.post(login_url, json={**payload, "password": password})
        assert resp.status_code == 423
        assert resp.json()["code"] == "ACCOUNT_LOCKED"

    # 4. Failed-login audit events survived the rollback (audit trail integrity).
    from app.core.audit import AuditEventType, SecurityAuditEvent

    async with otp_persistence_factory() as session:
        result = await session.execute(
            select(SecurityAuditEvent).where(
                SecurityAuditEvent.user_id == user_id,
                SecurityAuditEvent.event_type == AuditEventType.LOGIN_FAILED,
            )
        )
        events = list(result.scalars().all())
        # At least one failed-login event per wrong attempt persisted.
        assert len(events) >= max_attempts


@pytest.mark.asyncio
async def test_password_lockout_expires_and_resets(otp_persistence_factory):
    """An expired lockout clears the counter and permits login again.

    Guards the reset path: after the lockout window passes, a correct
    password must authenticate (the persisted lockout is cleared).
    """
    password = "AnotherPass1!"
    user_id = await _seed_user_with_password(
        otp_persistence_factory,
        email="fa22-bse-lock2@lgu.edu.pk",
        uid="FA22-BSE-LOCK2",
        password=password,
    )

    # Drive the account into a locked state via real requests.
    app.dependency_overrides.pop(get_db, None)
    transport = ASGITransport(app=app)
    login_url = "/api/v1/auth/login"
    payload = {"university_email": "fa22-bse-lock2@lgu.edu.pk"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(settings.LOGIN_MAX_ATTEMPTS):
            resp = await client.post(login_url, json={**payload, "password": f"Nope{i}!"})
            assert resp.status_code == 401

        cred = await _read_credential(otp_persistence_factory, user_id)
        assert cred.password_locked_until is not None

        # Backdate the lockout so it is now "expired", then verify a correct
        # password authenticates and the counter resets.
        expired = datetime.now(UTC) - timedelta(minutes=1)
        async with otp_persistence_factory() as session:
            from sqlalchemy import update

            await session.execute(
                update(UserCredential)
                .where(UserCredential.user_id == user_id)
                .values(password_locked_until=expired)
            )
            await session.commit()

        resp = await client.post(login_url, json={**payload, "password": password})
        assert resp.status_code == 200
        body = resp.json()
        # LoginResponse nests tokens under "tokens".
        assert "access_token" in body.get("tokens", body)

        cred = await _read_credential(otp_persistence_factory, user_id)
        assert cred.password_failed_attempts == 0
        assert cred.password_locked_until is None


@pytest.mark.asyncio
async def test_pin_failed_attempts_persist_and_lockout_engages(otp_persistence_factory):
    """PIN failed attempts persist; the PIN lockout control is reachable.

    Same defect class as the password path (Phase 63): the PIN login path
    incremented ``pin_failed_attempts`` on the request session then raised,
    so the lockout never engaged. Verifies persistence across requests.
    """
    from app.core.security import hash_pin

    password = "PinOwnerPass1!"
    pin = "1234"
    user_id = await _seed_user_with_password(
        otp_persistence_factory,
        email="fa22-bse-pin1@lgu.edu.pk",
        uid="FA22-BSE-PIN1",
        password=password,
    )
    # Enable PIN directly on the persistence DB (bypasses self-service flow).
    async with otp_persistence_factory() as session:
        from sqlalchemy import update

        await session.execute(
            update(UserCredential)
            .where(UserCredential.user_id == user_id)
            .values(pin_enabled=True, pin_hash=hash_pin(pin))
        )
        await session.commit()

    app.dependency_overrides.pop(get_db, None)
    transport = ASGITransport(app=app)
    pin_url = "/api/v1/auth/pin/login"
    payload = {"user_id": user_id}
    wrong_pin = "9999" if pin != "9999" else "8888"

    max_pin = settings.PIN_MAX_FAILED_ATTEMPTS
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(max_pin):
            resp = await client.post(pin_url, json={**payload, "pin": wrong_pin})
            assert resp.status_code == 400
            assert resp.json()["code"] == "PIN_ERROR"

        # Counter persisted across request boundaries (fresh-session read).
        cred = await _read_credential(otp_persistence_factory, user_id)
        assert cred.pin_failed_attempts == max_pin
        assert cred.pin_locked_until is not None

        # Lockout enforced: even the correct PIN is rejected while locked.
        resp = await client.post(pin_url, json={**payload, "pin": pin})
        assert resp.status_code in (400, 423)
        assert resp.json()["code"] in ("PIN_LOCKED", "PIN_ERROR")
