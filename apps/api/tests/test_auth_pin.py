"""Tests for PIN authentication.

Covers:
- Enable PIN (requires current password)
- PIN login
- Wrong PIN / PIN lockout
- Change PIN
- Disable PIN
- PIN login when not enabled
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_pin
from app.modules.users.models import UserCredential
from tests.conftest import create_user_session

# ---------------------------------------------------------------------------
# PIN Enable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPINEnable:
    """POST /api/v1/auth/pin/enable"""

    async def test_enable_pin_success(self, client: AsyncClient, db: AsyncSession, student_user):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "1234",
                "confirm_pin": "1234",
            },
        )
        assert resp.status_code == 200
        assert "enabled" in resp.json()["message"].lower()

    async def test_enable_pin_wrong_password(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "WrongPass9!",
                "pin": "1234",
                "confirm_pin": "1234",
            },
        )
        assert resp.status_code == 401

    async def test_enable_pin_non_numeric(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "abcd",
                "confirm_pin": "abcd",
            },
        )
        assert resp.status_code == 422

    async def test_enable_pin_mismatch(self, client: AsyncClient, db: AsyncSession, student_user):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "1234",
                "confirm_pin": "5678",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PIN Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPINLogin:
    """POST /api/v1/auth/pin/login"""

    async def _enable_pin(self, db: AsyncSession, user_id: str) -> None:
        """Set PIN hash directly in the database."""
        cred_result = await db.execute(
            __import__("sqlalchemy").select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credential = cred_result.scalar_one()
        credential.pin_hash = hash_pin("1234")
        credential.pin_enabled = True
        await db.flush()

    async def test_pin_login_success(self, client: AsyncClient, db: AsyncSession, student_user):
        await self._enable_pin(db, student_user.id)

        resp = await client.post(
            "/api/v1/auth/pin/login",
            json={"user_id": student_user.id, "pin": "1234"},
        )
        assert resp.status_code == 200
        assert "tokens" in resp.json()

    async def test_pin_login_wrong_pin(self, client: AsyncClient, db: AsyncSession, student_user):
        await self._enable_pin(db, student_user.id)

        resp = await client.post(
            "/api/v1/auth/pin/login",
            json={"user_id": student_user.id, "pin": "9999"},
        )
        assert resp.status_code == 400

    async def test_pin_login_not_enabled(self, client: AsyncClient, db: AsyncSession, student_user):
        """PIN login should fail when PIN is not enabled."""
        resp = await client.post(
            "/api/v1/auth/pin/login",
            json={"user_id": student_user.id, "pin": "1234"},
        )
        assert resp.status_code == 400

    async def test_pin_lockout_after_max_attempts(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        await self._enable_pin(db, student_user.id)

        # Exhaust wrong PIN attempts (PIN_MAX_FAILED_ATTEMPTS=5)
        for _ in range(5):
            resp = await client.post(
                "/api/v1/auth/pin/login",
                json={"user_id": student_user.id, "pin": "9999"},
            )
            assert resp.status_code == 400

        # Even correct PIN should now be locked
        resp = await client.post(
            "/api/v1/auth/pin/login",
            json={"user_id": student_user.id, "pin": "1234"},
        )
        assert resp.status_code == 423


# ---------------------------------------------------------------------------
# PIN Change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPINChange:
    """POST /api/v1/auth/pin/change"""

    async def test_change_pin_success(self, client: AsyncClient, db: AsyncSession, student_user):
        # Enable PIN first
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        enable_resp = await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "1234",
                "confirm_pin": "1234",
            },
        )
        assert enable_resp.status_code == 200

        # Change PIN
        resp = await client.post(
            "/api/v1/auth/pin/change",
            json={
                "current_pin": "1234",
                "new_pin": "5678",
                "confirm_pin": "5678",
            },
        )
        assert resp.status_code == 200

    async def test_change_pin_wrong_current(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        # Enable PIN
        await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "1234",
                "confirm_pin": "1234",
            },
        )

        # Change with wrong current PIN
        resp = await client.post(
            "/api/v1/auth/pin/change",
            json={
                "current_pin": "9999",
                "new_pin": "5678",
                "confirm_pin": "5678",
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PIN Disable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPINDisable:
    """POST /api/v1/auth/pin/disable"""

    async def test_disable_pin_success(self, client: AsyncClient, db: AsyncSession, student_user):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        # Enable PIN
        await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "1234",
                "confirm_pin": "1234",
            },
        )

        # Disable PIN
        resp = await client.post(
            "/api/v1/auth/pin/disable",
            json={"current_password": "StrongPass1!"},
        )
        assert resp.status_code == 200
        assert "disabled" in resp.json()["message"].lower()

    async def test_disable_pin_wrong_password(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        # Enable PIN
        await client.post(
            "/api/v1/auth/pin/enable",
            json={
                "current_password": "StrongPass1!",
                "pin": "1234",
                "confirm_pin": "1234",
            },
        )

        # Disable with wrong password
        resp = await client.post(
            "/api/v1/auth/pin/disable",
            json={"current_password": "WrongPass9!"},
        )
        assert resp.status_code == 401
