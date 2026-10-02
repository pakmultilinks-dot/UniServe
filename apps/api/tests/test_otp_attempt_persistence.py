"""Regression tests for OTP attempt-limit persistence (Phase 38).

Phase 37 demonstrated a transaction-boundary defect: ``verify_otp``
incremented the failed-attempt counter and then raised, while ``get_db``
rolls the request session back on exceptions. The counter therefore never
persisted, and the ``OTP_MAX_ATTEMPTS`` control was unreachable in the
production runtime — masked in the test suite because the shared-session
fixtures never rolled back.

These tests exercise the REAL ``get_db`` request boundary — a fresh DB
session per HTTP request with commit-on-success / rollback-on-exception —
against the isolated persistence database wired up by the session-scoped
``otp_persistence_factory`` fixture, and assert that the attempt count
survives across separate requests (verified through fresh DB sessions, not
in-memory ORM state).
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import generate_otp, hash_otp
from app.main import app
from app.modules.users.models import OTPChallenge, OTPPurpose
from tests.conftest import create_test_user


@pytest.mark.asyncio
async def test_otp_attempt_limit_persists_across_requests(otp_persistence_factory):
    """Failed OTP attempts persist across requests; the limit cannot be bypassed.

    Proves, across real request/session boundaries:
    1. Wrong OTPs increment a persisted attempt counter.
    2. The counter survives rollback of each failed request.
    3. At the configured limit the OTP is blocked per existing policy.
    4. A valid OTP cannot succeed after the limit has been reached.
    """
    # --- Seed a user + a valid OTP challenge on the persistence database ---
    async with otp_persistence_factory() as session:
        user = await create_test_user(
            session,
            university_id="FA22-BSE-OTP1",
            university_email="fa22-bse-otp1@lgu.edu.pk",
            email_verified=False,
        )
        otp_code = generate_otp()
        challenge = OTPChallenge(
            user_id=user.id,
            otp_hash=hash_otp(otp_code),
            purpose=OTPPurpose.EMAIL_VERIFICATION,
            max_attempts=settings.OTP_MAX_ATTEMPTS,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        session.add(challenge)
        await session.commit()
        user_id, challenge_id = user.id, challenge.id

    wrong_otp = "111111" if otp_code != "111111" else "222222"

    # Requests run through the REAL get_db: one session per request,
    # commit on success, rollback on exception — the production boundary.
    app.dependency_overrides.pop(get_db, None)
    transport = ASGITransport(app=app)
    verify_url = "/api/v1/auth/otp/verify"
    payload = {"user_id": user_id, "purpose": "email_verification"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1-2. Wrong OTPs each get their own request context
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            resp = await client.post(verify_url, json={**payload, "otp": wrong_otp})
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Invalid OTP. Please try again."

        # 3. The attempt count persisted across request boundaries —
        #    read back through a FRESH session, not in-memory ORM state
        async with otp_persistence_factory() as session:
            result = await session.execute(
                select(OTPChallenge).where(OTPChallenge.id == challenge_id)
            )
            persisted = result.scalar_one()
            assert persisted.attempts == settings.OTP_MAX_ATTEMPTS
            assert persisted.is_used is False

        # 4. The limit is now enforced (existing policy message)
        resp = await client.post(verify_url, json={**payload, "otp": wrong_otp})
        assert resp.status_code == 400
        assert resp.json()["detail"] == (
            "Maximum OTP attempts reached. Please request a new one."
        )

        # 5. A valid OTP cannot succeed after the limit — further attempts
        #    are rejected regardless of OTP correctness
        for _ in range(2):
            resp = await client.post(verify_url, json={**payload, "otp": otp_code})
            assert resp.status_code == 400
            assert resp.json()["detail"] in (
                "Maximum OTP attempts reached. Please request a new one.",
                "No active OTP found. Please request a new one.",
            )

    # 6. Final persisted state: challenge consumed, counter intact
    async with otp_persistence_factory() as session:
        result = await session.execute(
            select(OTPChallenge).where(OTPChallenge.id == challenge_id)
        )
        persisted = result.scalar_one()
        assert persisted.is_used is True
        assert persisted.attempts == settings.OTP_MAX_ATTEMPTS
