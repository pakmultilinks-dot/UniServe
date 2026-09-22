"""Tests for session management and logout.

Covers:
- Listing active sessions
- Logout from current device
- Logout from all devices
- Session is invalidated after logout
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import create_user_session

# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSessions:
    """GET /api/v1/auth/sessions"""

    async def test_list_sessions(self, student_client: AsyncClient):
        resp = await student_client.get("/api/v1/auth/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert "sessions" in body
        assert len(body["sessions"]) >= 1

    async def test_list_sessions_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/sessions")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogout:
    """POST /api/v1/auth/logout"""

    async def test_logout_current_device(self, client: AsyncClient, db: AsyncSession, student_user):
        session, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert "Logged out" in resp.json()["message"]

        # After logout, /me should fail (session revoked)
        resp2 = await client.get("/api/v1/auth/me")
        assert resp2.status_code == 401


@pytest.mark.asyncio
class TestLogoutAll:
    """POST /api/v1/auth/logout-all"""

    async def test_logout_all_devices(self, client: AsyncClient, db: AsyncSession, student_user):
        # Create two sessions
        _, token1, _ = await create_user_session(db, student_user)
        _, token2, _ = await create_user_session(db, student_user)

        # Logout from one device
        client.headers["Authorization"] = f"Bearer {token1}"
        resp = await client.post("/api/v1/auth/logout-all")
        assert resp.status_code == 200

        # The other session should also be revoked
        client.headers["Authorization"] = f"Bearer {token2}"
        resp2 = await client.get("/api/v1/auth/me")
        assert resp2.status_code == 401
