"""Tests for login, account lockout, and token management.

Covers:
- Successful login with email + password
- Failed login (wrong password)
- Account lockout after max attempts
- Login with pending verification / suspended / deleted accounts
- Token refresh
- Token reuse detection
- Current user (/me)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import AccountStatus, Role, UserCategory
from tests.conftest import create_test_user, create_user_session

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogin:
    """POST /api/v1/auth/login"""

    EMAIL = "fa22-bse-login@lgu.edu.pk"
    PASSWORD = "StrongPass1!"

    async def _seed_user(self, db: AsyncSession) -> None:
        await create_test_user(
            db,
            university_id="FA22-BSE-LOGIN",
            university_email=self.EMAIL,
            password=self.PASSWORD,
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
            status=AccountStatus.ACTIVE,
            email_verified=True,
        )

    async def test_login_success(self, client: AsyncClient, db: AsyncSession):
        await self._seed_user(db)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"university_email": self.EMAIL, "password": self.PASSWORD},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "tokens" in body
        assert "access_token" in body["tokens"]
        assert "refresh_token" in body["tokens"]
        assert "user" in body
        assert body["user"]["email_verified"] is True

    async def test_login_wrong_password(self, client: AsyncClient, db: AsyncSession):
        await self._seed_user(db)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"university_email": self.EMAIL, "password": "WrongPass1!"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient, db: AsyncSession):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "university_email": "nobody@lgu.edu.pk",
                "password": "StrongPass1!",
            },
        )
        # Same status as wrong password — prevents user enumeration
        assert resp.status_code == 401

    async def test_login_pending_verification(self, client: AsyncClient, db: AsyncSession):
        await create_test_user(
            db,
            university_id="FA22-BSE-PEND",
            university_email="fa22-bse-pend@lgu.edu.pk",
            password=self.PASSWORD,
            status=AccountStatus.PENDING_VERIFICATION,
            email_verified=False,
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "university_email": "fa22-bse-pend@lgu.edu.pk",
                "password": self.PASSWORD,
            },
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "EMAIL_NOT_VERIFIED"

    async def test_login_suspended_account(self, client: AsyncClient, db: AsyncSession):
        await create_test_user(
            db,
            university_id="FA22-BSE-SUSP",
            university_email="fa22-bse-susp@lgu.edu.pk",
            password=self.PASSWORD,
            status=AccountStatus.SUSPENDED,
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "university_email": "fa22-bse-susp@lgu.edu.pk",
                "password": self.PASSWORD,
            },
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "ACCOUNT_SUSPENDED"

    async def test_login_deleted_account(self, client: AsyncClient, db: AsyncSession):
        await create_test_user(
            db,
            university_id="FA22-BSE-DEL",
            university_email="fa22-bse-del@lgu.edu.pk",
            password=self.PASSWORD,
            status=AccountStatus.DELETED,
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "university_email": "fa22-bse-del@lgu.edu.pk",
                "password": self.PASSWORD,
            },
        )
        # Same as wrong password to prevent enumeration
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Account Lockout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAccountLockout:
    """Verify that the account locks after LOGIN_MAX_ATTEMPTS wrong passwords."""

    EMAIL = "fa22-bse-lock@lgu.edu.pk"
    PASSWORD = "StrongPass1!"

    async def _seed_user(self, db: AsyncSession) -> None:
        await create_test_user(
            db,
            university_id="FA22-BSE-LOCK",
            university_email=self.EMAIL,
            password=self.PASSWORD,
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
            status=AccountStatus.ACTIVE,
            email_verified=True,
        )

    async def test_lockout_after_max_attempts(self, client: AsyncClient, db: AsyncSession):
        await self._seed_user(db)

        # Exhaust wrong-password attempts (LOGIN_MAX_ATTEMPTS=10)
        for _ in range(10):
            resp = await client.post(
                "/api/v1/auth/login",
                json={"university_email": self.EMAIL, "password": "WrongPass1!"},
            )
            assert resp.status_code == 401

        # Now even the correct password should be rejected (locked)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"university_email": self.EMAIL, "password": self.PASSWORD},
        )
        assert resp.status_code == 423  # Locked


# ---------------------------------------------------------------------------
# Current User /me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetCurrentUser:
    """GET /api/v1/auth/me"""

    async def test_me_authenticated(self, student_client: AsyncClient):
        resp = await student_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["role"] == "student"

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 422  # Missing Authorization header

    async def test_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTokenRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, client: AsyncClient, db: AsyncSession, student_user):
        _, access_token, refresh_token = await create_user_session(db, student_user)
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        # Token rotation — new refresh token should differ from original
        assert body["refresh_token"] != refresh_token

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "garbage"},
        )
        assert resp.status_code == 401

    async def test_refresh_reuse_detection(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        """Using an old refresh token after rotation should revoke the session."""
        _, _, refresh_token = await create_user_session(db, student_user)

        # First refresh — succeeds
        resp1 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp1.status_code == 200

        # Reuse the old refresh token — should fail and revoke session
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp2.status_code == 401
