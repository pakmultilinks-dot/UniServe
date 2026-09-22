"""Tests for password management.

Covers:
- Password change (requires current password)
- Password change with wrong current password
- Password reset request (always returns success to prevent enumeration)
- Password reset confirm flow
"""

from datetime import UTC

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_otp, hash_otp
from app.modules.users.models import (
    AccountStatus,
    OTPChallenge,
    OTPPurpose,
    Role,
    UserCategory,
)
from tests.conftest import create_test_user, create_user_session

# ---------------------------------------------------------------------------
# Password Change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPasswordChange:
    """POST /api/v1/auth/password/change"""

    async def test_change_password_success(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/password/change",
            json={
                "current_password": "StrongPass1!",
                "new_password": "NewStrong2@",
            },
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

    async def test_change_password_wrong_current(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/password/change",
            json={
                "current_password": "WrongPass9!",
                "new_password": "NewStrong2@",
            },
        )
        assert resp.status_code == 401

    async def test_change_password_weak_new(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/password/change",
            json={
                "current_password": "StrongPass1!",
                "new_password": "weak",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPasswordReset:
    """POST /api/v1/auth/password/reset/request & /confirm"""

    EMAIL = "fa22-bse-reset@lgu.edu.pk"
    PASSWORD = "StrongPass1!"

    async def _seed_user(self, db: AsyncSession) -> str:
        user = await create_test_user(
            db,
            university_id="FA22-BSE-RESET",
            university_email=self.EMAIL,
            password=self.PASSWORD,
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
            status=AccountStatus.ACTIVE,
            email_verified=True,
        )
        return user.id

    async def test_reset_request_always_returns_success(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Requesting a reset for a non-existent email should still return success."""
        resp = await client.post(
            "/api/v1/auth/password/reset/request",
            json={"university_email": "nobody@lgu.edu.pk"},
        )
        assert resp.status_code == 200
        assert (
            "reset" in resp.json()["message"].lower() or "email" in resp.json()["message"].lower()
        )

    async def test_reset_request_existing_user(self, client: AsyncClient, db: AsyncSession):
        await self._seed_user(db)
        resp = await client.post(
            "/api/v1/auth/password/reset/request",
            json={"university_email": self.EMAIL},
        )
        assert resp.status_code == 200

    async def test_reset_confirm_invalid_otp(self, client: AsyncClient, db: AsyncSession):
        await self._seed_user(db)
        resp = await client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "university_email": self.EMAIL,
                "otp": "000000",
                "new_password": "ResetPass1!",
            },
        )
        assert resp.status_code == 400  # Invalid OTP

    async def test_reset_confirm_with_valid_otp(self, client: AsyncClient, db: AsyncSession):
        user_id = await self._seed_user(db)

        # Seed a valid OTP directly
        from datetime import datetime, timedelta

        otp_code = generate_otp()
        challenge = OTPChallenge(
            user_id=user_id,
            otp_hash=hash_otp(otp_code),
            purpose=OTPPurpose.PASSWORD_RESET,
            max_attempts=5,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(challenge)
        await db.flush()

        resp = await client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "university_email": self.EMAIL,
                "otp": otp_code,
                "new_password": "ResetPass1!",
            },
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()
