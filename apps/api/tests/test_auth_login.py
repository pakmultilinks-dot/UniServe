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
    """Verify that the account locks after LOGIN_MAX_ATTEMPTS wrong passwords.

    Phase 63 note: this test previously exercised the shared no-rollback
    ``client`` session, where the old code's in-memory ORM mutation
    (``credential.password_failed_attempts += 1``) appeared to accumulate
    across requests — a false green that masked the counter never actually
    persisting (the production ``get_db`` rolls the request session back on
    the raised exception, making the lockout dead code). It now runs against
    the REAL ``get_db`` boundary: the user is seeded on the isolated
    persistence database and the per-test ``get_db`` override is popped so
    each request gets a fresh session with commit-on-success /
    rollback-on-exception. The counter/lockout now genuinely persist via
    ``_persist_credential_state``, and the 423 assertion below is a true
    green. Cross-request persistence + audit-trail assertions live in
    ``test_login_lockout_persistence.py``.
    """

    EMAIL = "fa22-bse-lock@lgu.edu.pk"
    PASSWORD = "StrongPass1!"

    async def test_lockout_after_max_attempts(self, otp_persistence_factory):
        import uuid as _uuid

        from httpx import ASGITransport

        from app.core.database import get_db
        from app.main import app

        suffix = _uuid.uuid4().hex[:8]
        email = f"fa22-bse-lock-{suffix}@lgu.edu.pk"
        uid = f"FA22-BSE-LOCK-{suffix.upper()}"

        # Seed on the isolated persistence DB (the factory the independent
        # counter-persistence path writes to) and commit.
        async with otp_persistence_factory() as session:
            await create_test_user(
                session,
                university_id=uid,
                university_email=email,
                password=self.PASSWORD,
                role=Role.STUDENT,
                category=UserCategory.STUDENT,
                status=AccountStatus.ACTIVE,
                email_verified=True,
            )
            await session.commit()

        # Use the REAL get_db boundary (fresh session per request,
        # rollback-on-exception) — the production request lifecycle.
        app.dependency_overrides.pop(get_db, None)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Exhaust wrong-password attempts (LOGIN_MAX_ATTEMPTS=10)
            for _ in range(10):
                resp = await ac.post(
                    "/api/v1/auth/login",
                    json={"university_email": email, "password": "WrongPass1!"},
                )
                assert resp.status_code == 401

            # Now even the correct password should be rejected (locked)
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"university_email": email, "password": self.PASSWORD},
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
        assert resp.status_code == 401  # Missing Authorization header

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
