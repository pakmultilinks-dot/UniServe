"""Phase 47 — Member & Staff Management backend tests.

Covers the new admin-management behavior:
- Cafeteria assignment exposure in admin user summaries (GET /users/, GET /users/{id})
- Admin member creation (POST /users/) incl. temporary password + auto-assignment
- Role change with required cafeteria (PUT /users/{id}/role) — the Phase 45
  "changeUserRole omits cafeteria_id" defect's backend counterpart
- Cafeteria reassignment through the same coherent role endpoint
- Role change back to non-operational roles removes the assignment
- Duplicate email / university ID rejection (409)
- Validation: staff/manager creation without cafeteria_id is rejected
- Lifecycle: create -> reassign -> suspend -> activate (no persistence —
  the test transaction rolls back)
"""

import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import CafeteriaAssignment, Role
from tests.conftest import create_test_cafeteria, create_test_user


@pytest.mark.asyncio
class TestAssignmentExposure:
    """GET /users/ and GET /users/{id} surface cafeteria assignment info."""

    async def test_staff_assignment_visible_in_list(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Student Cafeteria")
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Ali",
                "last_name": "Raza",
                "university_id": "P47-STF-001",
                "university_email": "ali.raza.p47@lgu.edu.pk",
                "role": "cafeteria_staff",
                "cafeteria_id": cafeteria.id,
            },
        )
        assert resp.status_code == 201
        created_id = resp.json()["user"]["id"]

        resp = await admin_client.get("/api/v1/users/")
        assert resp.status_code == 200
        created = next(u for u in resp.json() if u["id"] == created_id)
        assert created["cafeteria_id"] == cafeteria.id
        assert created["cafeteria_name"] == "Student Cafeteria"

    async def test_detail_exposes_assignment(self, admin_client: AsyncClient, db: AsyncSession):
        cafeteria = await create_test_cafeteria(db, name="Faculty Cafeteria")
        target = await create_test_user(
            db,
            first_name="Sana",
            last_name="Manager",
            university_id="P47-MGR-001",
            university_email="sana.mgr.p47@lgu.edu.pk",
            role=Role.CAFETERIA_MANAGER,
        )
        from tests.conftest import assign_user_to_cafeteria

        await assign_user_to_cafeteria(db, target.id, cafeteria.id, Role.CAFETERIA_MANAGER)

        resp = await admin_client.get(f"/api/v1/users/{target.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cafeteria_id"] == cafeteria.id
        assert body["cafeteria_name"] == "Faculty Cafeteria"

    async def test_student_detail_has_null_assignment(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        target = await create_test_user(
            db,
            first_name="No",
            last_name="Assign",
            university_id="P47-STU-002",
            university_email="no.assign.p47@lgu.edu.pk",
            role=Role.STUDENT,
        )
        resp = await admin_client.get(f"/api/v1/users/{target.id}")
        assert resp.status_code == 200
        assert resp.json()["cafeteria_id"] is None
        assert resp.json()["cafeteria_name"] is None


@pytest.mark.asyncio
class TestMemberCreation:
    """POST /users/ — the real Admin member-creation contract."""

    async def test_create_student(self, admin_client: AsyncClient, db: AsyncSession):
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Test",
                "last_name": "Student",
                "university_id": "P47-STU-003",
                "university_email": "test.stu.p47@lgu.edu.pk",
                "role": "student",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["user"]["role"] == "student"
        assert body["user"]["status"] == "active"
        assert body["user"]["email_verified"] is True
        assert body["user"]["cafeteria_id"] is None
        # Temp-password contract: 6-digit OTP + "Aa1!" suffix (returned once).
        pwd = body["temporary_password"]
        assert pwd.endswith("Aa1!")
        assert re.match(r"^\d{6}Aa1!$", pwd)

    async def test_create_staff_with_cafeteria_assigns(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Student Cafeteria")
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Bilal",
                "last_name": "Ahmed",
                "university_id": "P47-STF-002",
                "university_email": "bilal.ahmed.p47@lgu.edu.pk",
                "role": "cafeteria_staff",
                "cafeteria_id": cafeteria.id,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["user"]["role"] == "cafeteria_staff"
        assert body["user"]["cafeteria_id"] == cafeteria.id
        assert body["user"]["cafeteria_name"] == "Student Cafeteria"
        # Assignment row exists in the authoritative table.
        assignment = await db.execute(
            select(CafeteriaAssignment).where(
                CafeteriaAssignment.user_id == body["user"]["id"]
            )
        )
        assert assignment.scalar_one_or_none() is not None

    async def test_create_manager_with_cafeteria(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Faculty Cafeteria")
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Raza",
                "last_name": "Khan",
                "university_id": "P47-MGR-002",
                "university_email": "raza.khan.p47@lgu.edu.pk",
                "role": "cafeteria_manager",
                "cafeteria_id": cafeteria.id,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["user"]["cafeteria_id"] == cafeteria.id
        assert resp.json()["user"]["cafeteria_name"] == "Faculty Cafeteria"

    async def test_create_staff_without_cafeteria_rejected(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "No",
                "last_name": "Cafe",
                "university_id": "P47-STF-003",
                "university_email": "no.cafe.p47@lgu.edu.pk",
                "role": "cafeteria_staff",
            },
        )
        # Pydantic field validator (422) or backend ValidationError (400).
        assert resp.status_code in (400, 422)

    async def test_duplicate_email_rejected(self, admin_client: AsyncClient, db: AsyncSession):
        payload = {
            "first_name": "Dup",
            "last_name": "Mail",
            "university_id": "P47-DUP-001",
            "university_email": "dup.mail.p47@lgu.edu.pk",
            "role": "student",
        }
        resp = await admin_client.post("/api/v1/users/", json=payload)
        assert resp.status_code == 201
        resp2 = await admin_client.post("/api/v1/users/", json=payload)
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]

    async def test_duplicate_university_id_rejected(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Dup",
                "last_name": "Id",
                "university_id": "P47-DUP-002",
                "university_email": "dup.id1.p47@lgu.edu.pk",
                "role": "student",
            },
        )
        assert resp.status_code == 201
        resp2 = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Dup",
                "last_name": "Id",
                "university_id": "P47-DUP-002",
                "university_email": "dup.id2.p47@lgu.edu.pk",
                "role": "faculty",
            },
        )
        assert resp2.status_code == 409


@pytest.mark.asyncio
class TestRoleChangeWithCafeteria:
    """PUT /users/{id}/role — Phase 45 bug: cafeteria_id must be honored."""

    async def test_student_to_staff_requires_and_sets_cafeteria(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Student Cafeteria")
        target = await create_test_user(
            db,
            first_name="Promo",
            last_name="ToStaff",
            university_id="P47-PROM-001",
            university_email="promo.tostaff.p47@lgu.edu.pk",
            role=Role.STUDENT,
        )
        # Without cafeteria_id the backend must reject (the Phase 45 defect
        # sent exactly this broken payload).
        resp = await admin_client.put(
            f"/api/v1/users/{target.id}/role",
            json={"role": "cafeteria_staff"},
        )
        assert resp.status_code in (400, 422)

        # With cafeteria_id the change succeeds and the assignment is visible.
        resp = await admin_client.put(
            f"/api/v1/users/{target.id}/role",
            json={"role": "cafeteria_staff", "cafeteria_id": cafeteria.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "cafeteria_staff"
        assert body["cafeteria_id"] == cafeteria.id
        assert body["cafeteria_name"] == "Student Cafeteria"

        # Persists: detail endpoint agrees.
        detail = await admin_client.get(f"/api/v1/users/{target.id}")
        assert detail.json()["cafeteria_id"] == cafeteria.id

    async def test_reassign_cafeteria_via_role_endpoint(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        student_caf = await create_test_cafeteria(db, name="Student Cafeteria")
        faculty_caf = await create_test_cafeteria(db, name="Faculty Cafeteria")
        target = await create_test_user(
            db,
            first_name="Move",
            last_name="Me",
            university_id="P47-MOVE-001",
            university_email="move.me.p47@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
        )
        from tests.conftest import assign_user_to_cafeteria

        await assign_user_to_cafeteria(db, target.id, student_caf.id, Role.CAFETERIA_STAFF)

        # One coherent workflow: same role + new cafeteria reassigns.
        resp = await admin_client.put(
            f"/api/v1/users/{target.id}/role",
            json={"role": "cafeteria_staff", "cafeteria_id": faculty_caf.id},
        )
        assert resp.status_code == 200
        assert resp.json()["cafeteria_id"] == faculty_caf.id

        detail = await admin_client.get(f"/api/v1/users/{target.id}")
        assert detail.json()["cafeteria_id"] == faculty_caf.id

    async def test_change_to_student_removes_assignment(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Student Cafeteria")
        target = await create_test_user(
            db,
            first_name="Back",
            last_name="ToStudent",
            university_id="P47-BACK-001",
            university_email="back.tostu.p47@lgu.edu.pk",
            role=Role.CAFETERIA_STAFF,
        )
        from tests.conftest import assign_user_to_cafeteria

        await assign_user_to_cafeteria(db, target.id, cafeteria.id, Role.CAFETERIA_STAFF)

        resp = await admin_client.put(
            f"/api/v1/users/{target.id}/role",
            json={"role": "student"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "student"
        assert body["cafeteria_id"] is None
        # Stale operational assignment data removed per backend model.
        assignment = await db.execute(
            select(CafeteriaAssignment).where(CafeteriaAssignment.user_id == target.id)
        )
        assert assignment.scalar_one_or_none() is None


@pytest.mark.asyncio
class TestLifecycle:
    """Full member lifecycle through the real API (no SQL, rolled back)."""

    async def test_create_reassign_suspend_activate(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        student_caf = await create_test_cafeteria(db, name="Student Cafeteria")
        faculty_caf = await create_test_cafeteria(db, name="Faculty Cafeteria")

        # 1. Create
        resp = await admin_client.post(
            "/api/v1/users/",
            json={
                "first_name": "Life",
                "last_name": "Cycle",
                "university_id": "P47-LIFE-001",
                "university_email": "life.cycle.p47@lgu.edu.pk",
                "role": "cafeteria_staff",
                "cafeteria_id": student_caf.id,
            },
        )
        assert resp.status_code == 201
        user_id = resp.json()["user"]["id"]
        assert resp.json()["user"]["cafeteria_name"] == "Student Cafeteria"

        # 2. Reassign
        resp = await admin_client.put(
            f"/api/v1/users/{user_id}/role",
            json={"role": "cafeteria_staff", "cafeteria_id": faculty_caf.id},
        )
        assert resp.status_code == 200
        assert resp.json()["cafeteria_name"] == "Faculty Cafeteria"

        # 3. Suspend
        resp = await admin_client.post(
            f"/api/v1/users/{user_id}/suspend",
            json={"reason": "Phase 47 lifecycle test"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

        # 4. Activate
        resp = await admin_client.post(f"/api/v1/users/{user_id}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # 5. Persisted through every step
        detail = await admin_client.get(f"/api/v1/users/{user_id}")
        body = detail.json()
        assert body["status"] == "active"
        assert body["cafeteria_id"] == faculty_caf.id
        assert body["cafeteria_name"] == "Faculty Cafeteria"
