"""Phase 55 — Admin self-service & settings foundation.

Covers the new Phase 55 backend surface:
- PATCH /api/v1/auth/me — profile self-update (validation, auth, immutability)
- GET /api/v1/administration/audit-events — admin-only audit read,
  pagination, event-type filter, actor enrichment
- GET /api/v1/users/ — limit/offset pagination + server-side filters,
  bare-list compatibility when pagination params are omitted
- POST /api/v1/users/{id}/recover — one-time temporary password issuance
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditEventType, log_audit_event
from app.core.security import verify_password
from app.modules.users.models import (
    AccountStatus,
    Role,
    User,
    UserCategory,
    UserCredential,
)
from tests.conftest import create_test_user, create_user_session

# ---------------------------------------------------------------------------
# PATCH /api/v1/auth/me — profile self-update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProfileSelfUpdate:
    """PATCH /api/v1/auth/me"""

    async def test_update_profile_success(
        self, client: AsyncClient, db: AsyncSession, student_user: User
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.patch(
            "/api/v1/auth/me",
            json={"first_name": "  Phase55  ", "last_name": " Updated  "},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Whitespace is trimmed by the schema validators.
        assert body["first_name"] == "Phase55"
        assert body["last_name"] == "Updated"

        # The change is persisted for the authenticated user only.
        # populate_existing: the db session identity map still holds the
        # pre-request instance; the API session wrote through the shared
        # transaction, so re-populate from the database row.
        result = await db.execute(
            select(User)
            .where(User.id == student_user.id)
            .execution_options(populate_existing=True)
        )
        db_user = result.scalar_one()
        assert db_user.first_name == "Phase55"
        assert db_user.last_name == "Updated"

    async def test_update_profile_preserves_immutable_fields(
        self, client: AsyncClient, db: AsyncSession, student_user: User
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.patch(
            "/api/v1/auth/me",
            json={"first_name": "Safe", "last_name": "Name"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Email, role, and status are immutable through this endpoint.
        assert body["university_email"] == student_user.university_email
        assert body["role"] == student_user.role.value
        assert body["status"] == student_user.status.value

    async def test_update_profile_rejects_blank_names(
        self, client: AsyncClient, db: AsyncSession, student_user: User
    ):
        _, access_token, _ = await create_user_session(db, student_user)
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.patch(
            "/api/v1/auth/me",
            json={"first_name": "   ", "last_name": "Valid"},
        )
        assert resp.status_code == 422

        resp2 = await client.patch(
            "/api/v1/auth/me",
            json={"first_name": "Valid", "last_name": "   "},
        )
        assert resp2.status_code == 422

    async def test_update_profile_requires_authentication(
        self, client: AsyncClient
    ):
        resp = await client.patch(
            "/api/v1/auth/me",
            json={"first_name": "Anon", "last_name": "Attack"},
        )
        assert resp.status_code == 401

    async def test_staff_can_update_own_profile(
        self, staff_client: AsyncClient, db: AsyncSession, staff_user: User
    ):
        resp = await staff_client.patch(
            "/api/v1/auth/me",
            json={"first_name": "Staff", "last_name": "Member"},
        )
        assert resp.status_code == 200
        result = await db.execute(select(User).where(User.id == staff_user.id))
        db_user = result.scalar_one()
        assert db_user.first_name == "Staff"
        assert db_user.last_name == "Member"


# ---------------------------------------------------------------------------
# GET /api/v1/users/ — pagination + filters + compatibility
# ---------------------------------------------------------------------------


async def _seed_extra_students(db: AsyncSession, count: int) -> list[User]:
    users = []
    for i in range(count):
        user = await create_test_user(
            db,
            first_name=f"Pagination{i}",
            last_name="Student",
            university_id=f"P55-PAG-{i:03d}",
            university_email=f"p55.pag.{i:03d}@student.lgu.edu.pk",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
        )
        users.append(user)
    return users


@pytest.mark.asyncio
class TestUsersListPagination:
    """GET /api/v1/users/ — Phase 55 limit/offset + filters."""

    async def test_paginated_shape_and_limit(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        await _seed_extra_students(db, 5)

        resp = await admin_client.get("/api/v1/users/?limit=3&offset=0")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert "users" in body and "total" in body
        assert len(body["users"]) == 3
        # 5 seeded + the admin fixture user.
        assert body["total"] == 6

    async def test_offset_beyond_end_returns_empty_page(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        await _seed_extra_students(db, 2)

        resp = await admin_client.get("/api/v1/users/?limit=10&offset=999")
        assert resp.status_code == 200
        body = resp.json()
        assert body["users"] == []
        # 2 seeded + the admin fixture user — total stays honest.
        assert body["total"] == 3

    async def test_role_filter_with_pagination(
        self, admin_client: AsyncClient, db: AsyncSession, student_user: User
    ):
        await _seed_extra_students(db, 2)

        resp = await admin_client.get(
            "/api/v1/users/?role=student&limit=10&offset=0"
        )
        assert resp.status_code == 200
        body = resp.json()
        # 1 fixture student + 2 seeded.
        assert body["total"] == 3
        assert len(body["users"]) == 3
        assert all(u["role"] == "student" for u in body["users"])

    async def test_search_filter(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        await _seed_extra_students(db, 4)

        resp = await admin_client.get(
            "/api/v1/users/?q=Pagination2&limit=10&offset=0"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["users"][0]["first_name"] == "Pagination2"

    async def test_bare_list_compat_without_params(
        self, admin_client: AsyncClient
    ):
        """Omitting limit/offset preserves the original bare-list shape."""
        resp = await admin_client.get("/api/v1/users/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert all("id" in u and "role" in u for u in body)

    async def test_invalid_role_filter_rejected(
        self, admin_client: AsyncClient
    ):
        resp = await admin_client.get("/api/v1/users/?role=bogus_role")
        assert resp.status_code == 400

    async def test_pagination_requires_admin(
        self, student_client: AsyncClient, client: AsyncClient
    ):
        resp = await student_client.get("/api/v1/users/?limit=5")
        assert resp.status_code == 403

        resp2 = await client.get("/api/v1/users/?limit=5")
        assert resp2.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/administration/audit-events — admin-only audit read
# ---------------------------------------------------------------------------


async def _seed_audit_events(db: AsyncSession, actor: User) -> list[str]:
    """Seed distinct audit events; return their event_type values."""
    seeds = [
        (AuditEventType.LOGIN_SUCCESS, actor.id, "login ok"),
        (AuditEventType.PASSWORD_CHANGED, actor.id, None),
        (AuditEventType.LOGIN_FAILED, None, "bad password"),
        (AuditEventType.LOGOUT_ALL, actor.id, None),
    ]
    created = []
    for event_type, user_id, description in seeds:
        await log_audit_event(
            session=db,
            event_type=event_type,
            user_id=user_id,
            description=description,
            ip_address="10.55.0.1",
            user_agent="pytest-phase55",
        )
        created.append(event_type.value)
    return created


@pytest.mark.asyncio
class TestAuditEventsRead:
    """GET /api/v1/administration/audit-events"""

    async def test_admin_reads_audit_events_newest_first(
        self, admin_client: AsyncClient, db: AsyncSession, student_user: User
    ):
        await _seed_audit_events(db, student_user)

        resp = await admin_client.get("/api/v1/administration/audit-events")
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body and "total" in body
        assert body["total"] >= 4
        assert len(body["events"]) >= 4

        # Newest first — timestamps must be non-increasing.
        timestamps = [e["created_at"] for e in body["events"]]
        assert timestamps == sorted(timestamps, reverse=True)

        # Required response fields per Phase 55 spec §10.
        for event in body["events"]:
            assert "id" in event
            assert "event_type" in event
            assert "user_id" in event
            assert "description" in event
            assert "ip_address" in event
            assert "user_agent" in event
            assert "created_at" in event

    async def test_audit_pagination(
        self, admin_client: AsyncClient, db: AsyncSession, student_user: User
    ):
        await _seed_audit_events(db, student_user)

        resp = await admin_client.get(
            "/api/v1/administration/audit-events?limit=2&offset=0"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["events"]) == 2
        assert body["total"] == 4

        resp2 = await admin_client.get(
            "/api/v1/administration/audit-events?limit=2&offset=2"
        )
        body2 = resp2.json()
        assert len(body2["events"]) == 2
        assert body2["total"] == 4
        # No overlap between pages.
        page_ids = {e["id"] for e in body["events"]}
        page2_ids = {e["id"] for e in body2["events"]}
        assert not (page_ids & page2_ids)

        resp3 = await admin_client.get(
            "/api/v1/administration/audit-events?limit=2&offset=999"
        )
        body3 = resp3.json()
        assert body3["events"] == []
        assert body3["total"] == 4

    async def test_audit_event_type_filter(
        self, admin_client: AsyncClient, db: AsyncSession, student_user: User
    ):
        await _seed_audit_events(db, student_user)

        resp = await admin_client.get(
            "/api/v1/administration/audit-events?event_type=login_success"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["events"]) == 1
        assert body["events"][0]["event_type"] == "login_success"

    async def test_audit_actor_enrichment(
        self, admin_client: AsyncClient, db: AsyncSession, student_user: User
    ):
        await _seed_audit_events(db, student_user)

        resp = await admin_client.get(
            "/api/v1/administration/audit-events?event_type=login_success"
        )
        body = resp.json()
        event = body["events"][0]
        assert event["user_id"] == student_user.id
        assert isinstance(event["user_name"], str)
        assert len(event["user_name"]) > 0
        # Anonymous event (no user_id) resolves to a null actor.
        resp2 = await admin_client.get(
            "/api/v1/administration/audit-events?event_type=login_failed"
        )
        body2 = resp2.json()
        assert body2["events"][0]["user_id"] is None
        assert body2["events"][0]["user_name"] is None

    async def test_audit_invalid_event_type_rejected(
        self, admin_client: AsyncClient
    ):
        resp = await admin_client.get(
            "/api/v1/administration/audit-events?event_type=bogus_type"
        )
        assert resp.status_code == 400

    async def test_audit_rbac_denies_non_admin_roles(
        self,
        student_client: AsyncClient,
        faculty_client: AsyncClient,
        staff_client: AsyncClient,
        manager_client: AsyncClient,
        client: AsyncClient,
    ):
        for role_client in (student_client, faculty_client, staff_client, manager_client):
            resp = await role_client.get("/api/v1/administration/audit-events")
            assert resp.status_code == 403, f"expected 403, got {resp.status_code}"

        resp = await client.get("/api/v1/administration/audit-events")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/users/{id}/recover — one-time temporary password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUserRecoveryTempPassword:
    """POST /api/v1/users/{user_id}/recover (Phase 55 extension)."""

    async def test_recover_suspended_user_issues_temp_password(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        target = await create_test_user(
            db,
            first_name="P55",
            last_name="Suspended",
            university_id="P55-REC-001",
            university_email="p55.rec001@lgu.edu.pk",
            password="StrongPass1!",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
            status=AccountStatus.SUSPENDED,
        )

        resp = await admin_client.post(
            f"/api/v1/users/{target.id}/recover",
            json={
                "university_id": "P55-REC-001",
                "reason": "Phase 55 E2E — forgot password",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        temp_password = body["temporary_password"]
        assert isinstance(temp_password, str)
        assert len(temp_password) >= 8

        # Account is reactivated and the credential hash changed.
        result = await db.execute(
            select(User)
            .where(User.id == target.id)
            .execution_options(populate_existing=True)
        )
        db_user = result.scalar_one()
        assert db_user.status == AccountStatus.ACTIVE

        cred_result = await db.execute(
            select(UserCredential)
            .where(UserCredential.user_id == target.id)
            .execution_options(populate_existing=True)
        )
        credential = cred_result.scalar_one()
        assert verify_password(temp_password, credential.password_hash)
        # The old password must no longer work.
        assert not verify_password("StrongPass1!", credential.password_hash)

    async def test_recover_wrong_university_id_changes_nothing(
        self, admin_client: AsyncClient, db: AsyncSession
    ):
        target = await create_test_user(
            db,
            first_name="P55",
            last_name="Locked",
            university_id="P55-REC-002",
            university_email="p55.rec002@lgu.edu.pk",
            password="StrongPass1!",
            role=Role.STUDENT,
            category=UserCategory.STUDENT,
            status=AccountStatus.SUSPENDED,
        )

        resp = await admin_client.post(
            f"/api/v1/users/{target.id}/recover",
            json={"university_id": "WRONG-ID", "reason": "test"},
        )
        assert resp.status_code == 400

        cred_result = await db.execute(
            select(UserCredential)
            .where(UserCredential.user_id == target.id)
            .execution_options(populate_existing=True)
        )
        credential = cred_result.scalar_one()
        # Credential untouched after failed verification.
        assert verify_password("StrongPass1!", credential.password_hash)

    async def test_recover_requires_admin_role(
        self, student_client: AsyncClient, db: AsyncSession
    ):
        target = await create_test_user(
            db,
            first_name="P55",
            last_name="Target",
            university_id="P55-REC-003",
            university_email="p55.rec003@lgu.edu.pk",
        )
        resp = await student_client.post(
            f"/api/v1/users/{target.id}/recover",
            json={"university_id": "P55-REC-003", "reason": "test"},
        )
        assert resp.status_code == 403
