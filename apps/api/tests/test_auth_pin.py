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
        self, client: AsyncClient, db: AsyncSession, student_user, otp_persistence_factory
    ):
        """PIN lockout engages after PIN_MAX_FAILED_ATTEMPTS wrong PINs.

        Phase 63 note: like the password path, the PIN failed-attempt counter
        previously mutated the shared no-rollback in-memory session (false
        green) while production ``get_db`` rolled the increment back —
        dead-code lockout. The counter is now persisted independently via
        ``_persist_credential_state``. This test seeds the PIN-enabled user on
        the isolated persistence DB and exercises the REAL ``get_db`` boundary
        so the lockout is a true green. Full cross-request persistence
        assertions live in ``test_login_lockout_persistence.py``.
        """
        import uuid as _uuid

        from httpx import ASGITransport

        from app.core.database import get_db
        from app.core.security import hash_password
        from app.main import app
        from app.modules.users.models import AccountStatus, Role, User, UserCategory

        suffix = _uuid.uuid4().hex[:8]
        uid = f"FA22-BSE-PINLK-{suffix.upper()}"

        # Seed a PIN-enabled user on the isolated persistence DB and commit.
        async with otp_persistence_factory() as session:
            user = User(
                first_name="Pin",
                last_name="Lockout",
                university_id=uid,
                university_email=f"{uid.lower()}@lgu.edu.pk",
                category=UserCategory.STUDENT,
                role=Role.STUDENT,
                status=AccountStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            cred = UserCredential(
                user_id=user.id,
                password_hash=hash_password("StrongPass1!"),
                pin_hash=hash_pin("1234"),
                pin_enabled=True,
            )
            session.add(cred)
            await session.commit()
            user_id = user.id

        # Use the REAL get_db boundary (fresh session per request,
        # rollback-on-exception) — the production request lifecycle.
        app.dependency_overrides.pop(get_db, None)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Exhaust wrong PIN attempts (PIN_MAX_FAILED_ATTEMPTS=5)
            for _ in range(5):
                resp = await ac.post(
                    "/api/v1/auth/pin/login",
                    json={"user_id": user_id, "pin": "9999"},
                )
                assert resp.status_code == 400

            # Even correct PIN should now be locked
            resp = await ac.post(
                "/api/v1/auth/pin/login",
                json={"user_id": user_id, "pin": "1234"},
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
