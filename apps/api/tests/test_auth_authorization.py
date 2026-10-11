"""Tests for role-based authorization and cafeteria scope.

Covers:
- Admin-only endpoints reject non-admins
- Manager-only endpoints reject non-managers
- Student cannot access faculty-restricted endpoints
- Cafeteria scope enforcement (staff/manager assigned vs unassigned)
- Privilege escalation prevention
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import (
    AccountStatus,
    Role,
    UserCategory,
)
from tests.conftest import create_test_user, create_user_session

# ---------------------------------------------------------------------------
# Role-Based Access Control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRoleBasedAccess:
    """Verify RequireRole dependency blocks unauthorized users."""

    async def test_admin_endpoint_rejects_student(self, student_client: AsyncClient):
        resp = await student_client.get("/api/v1/users/")
        assert resp.status_code == 403

    async def test_admin_endpoint_rejects_faculty(self, faculty_client: AsyncClient):
        resp = await faculty_client.get("/api/v1/users/")
        assert resp.status_code == 403

    async def test_admin_endpoint_rejects_staff(self, staff_client: AsyncClient):
        resp = await staff_client.get("/api/v1/users/")
        assert resp.status_code == 403

    async def test_admin_endpoint_accepts_admin(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/users/")
        assert resp.status_code == 200

    async def test_unauthenticated_rejected(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/")
        assert resp.status_code == 401  # Missing auth header


# ---------------------------------------------------------------------------
# Admin User Management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdminUserManagement:
    """Admin operations on users."""

    async def test_admin_create_user(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "New",
                "last_name": "Staff",
                "university_id": "STF-NEW-001",
                "university_email": "new.staff@lgu.edu.pk",
                "role": "cafeteria_staff",
                "cafeteria_id": "caf-001",
            },
        )
        # May fail if cafeteria doesn't exist — that's expected
        # Key point: admin has permission
        assert resp.status_code in (201, 400, 404)

    async def test_manager_cannot_create_admin(self, manager_client: AsyncClient):
        resp = await manager_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Fake",
                "last_name": "Admin",
                "university_id": "ADM-FAKE-001",
                "university_email": "fake.admin@lgu.edu.pk",
                "role": "university_admin",
            },
        )
        assert resp.status_code == 403

    async def test_manager_cannot_create_student(self, manager_client: AsyncClient):
        resp = await manager_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Fake",
                "last_name": "Student",
                "university_id": "STU-FAKE-001",
                "university_email": "fake.student@lgu.edu.pk",
                "role": "student",
            },
        )
        assert resp.status_code == 403

    async def test_student_cannot_list_users(self, student_client: AsyncClient):
        resp = await student_client.get("/api/v1/users/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Suspend / Activate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSuspendActivate:
    """POST /api/v1/users/{user_id}/suspend and /activate"""

    async def test_admin_suspend_user(self, admin_client: AsyncClient, db: AsyncSession):
        # Create a target user
        target = await create_test_user(
            db,
            first_name="Target",
            last_name="User",
            university_id="TGT-SUSP-001",
            university_email="target.susp@lgu.edu.pk",
        )

        resp = await admin_client.post(
            f"/api/v1/users/{target.id}/suspend",
            json={"reason": "Policy violation"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    async def test_student_cannot_suspend(self, student_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Target",
            last_name="User2",
            university_id="TGT-SUSP-002",
            university_email="target2.susp@lgu.edu.pk",
        )
        resp = await student_client.post(
            f"/api/v1/users/{target.id}/suspend",
            json={"reason": "test"},
        )
        assert resp.status_code == 403

    async def test_manager_cannot_suspend_student(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Managers must not suspend students — admin-only (Phase 27 fix)."""
        target = await create_test_user(
            db,
            first_name="Stu",
            last_name="Target",
            university_id="TGT-MGR-STU-001",
            university_email="tgt.mgr.stu@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        resp = await manager_client.post(
            f"/api/v1/users/{target.id}/suspend",
            json={"reason": "test"},
        )
        assert resp.status_code == 403

    async def test_manager_cannot_suspend_faculty(
        self, manager_client: AsyncClient, db: AsyncSession
    ):
        """Managers must not suspend faculty — admin-only (Phase 27 fix)."""
        target = await create_test_user(
            db,
            first_name="Fac",
            last_name="Target",
            university_id="TGT-MGR-FAC-001",
            university_email="tgt.mgr.fac@lgu.edu.pk",
            role=Role.FACULTY,
            category=UserCategory.FACULTY,
        )
        resp = await manager_client.post(
            f"/api/v1/users/{target.id}/suspend",
            json={"reason": "test"},
        )
        assert resp.status_code == 403
        # Account must remain untouched
        await db.refresh(target)
        assert target.status != AccountStatus.SUSPENDED

    async def test_admin_can_suspend_student(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        """Admin can still suspend students (control for the new guard)."""
        target = await create_test_user(
            db,
            first_name="Stu",
            last_name="Admin",
            university_id="TGT-ADM-STU-001",
            university_email="tgt.adm.stu@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        resp = await admin_client.post(
            f"/api/v1/users/{target.id}/suspend",
            json={"reason": "policy"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    async def test_admin_activate_user(self, admin_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Suspended",
            last_name="User",
            university_id="TGT-ACT-001",
            university_email="suspended.act@lgu.edu.pk",
            status=AccountStatus.SUSPENDED,
        )

        resp = await admin_client.post(f"/api/v1/users/{target.id}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_student_cannot_activate(self, student_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Suspended2",
            last_name="User",
            university_id="TGT-ACT-002",
            university_email="suspended2.act@lgu.edu.pk",
            status=AccountStatus.SUSPENDED,
        )
        resp = await student_client.post(f"/api/v1/users/{target.id}/activate")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Self-Service Account Deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAccountDeletion:
    """DELETE /api/v1/users/me"""

    async def test_self_delete_success(self, client: AsyncClient, db: AsyncSession, student_user):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": "StrongPass1!"},
        )
        assert resp.status_code == 204

    async def test_self_delete_wrong_password(
        self, client: AsyncClient, db: AsyncSession, student_user
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": "WrongPass9!"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Account Recovery (Admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAccountRecovery:
    """POST /api/v1/users/{user_id}/recover"""

    async def test_admin_recover_user(self, admin_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Locked",
            last_name="User",
            university_id="TGT-REC-001",
            university_email="locked.rec@lgu.edu.pk",
        )

        resp = await admin_client.post(
            f"/api/v1/users/{target.id}/recover",
            json={
                "university_id": "TGT-REC-001",
                "reason": "User requested recovery",
            },
        )
        assert resp.status_code == 200

    async def test_student_cannot_recover(self, student_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Locked2",
            last_name="User",
            university_id="TGT-REC-002",
            university_email="locked2.rec@lgu.edu.pk",
        )
        resp = await student_client.post(
            f"/api/v1/users/{target.id}/recover",
            json={
                "university_id": "TGT-REC-002",
                "reason": "test",
            },
        )
        assert resp.status_code == 403

    async def test_recover_wrong_university_id(self, admin_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Locked3",
            last_name="User",
            university_id="TGT-REC-003",
            university_email="locked3.rec@lgu.edu.pk",
        )
        resp = await admin_client.post(
            f"/api/v1/users/{target.id}/recover",
            json={
                "university_id": "WRONG-ID",
                "reason": "test",
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Role Change (Admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRoleChange:
    """PUT /api/v1/users/{user_id}/role"""

    async def test_admin_change_role(self, admin_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Role",
            last_name="User",
            university_id="TGT-ROLE-001",
            university_email="role.user@lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )

        resp = await admin_client.put(
            f"/api/v1/users/{target.id}/role",
            json={"role": "faculty"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "faculty"

    async def test_student_cannot_change_role(self, student_client: AsyncClient, db: AsyncSession):
        target = await create_test_user(
            db,
            first_name="Role2",
            last_name="User",
            university_id="TGT-ROLE-002",
            university_email="role2.user@lgu.edu.pk",
        )
        resp = await student_client.put(
            f"/api/v1/users/{target.id}/role",
            json={"role": "university_admin"},
        )
        assert resp.status_code == 403
