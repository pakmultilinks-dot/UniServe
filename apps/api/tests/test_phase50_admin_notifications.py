"""Phase 50 — Admin notifications & broadcast tests.

Covers:
- Authorization: unauthenticated → 401, non-admin → 403, admin → allowed
- Validation: empty title/message, invalid audience, unsupported targeting
  combos, malformed/unknown cafeteria_id, zero-recipient audiences
- Targeting: role audiences, all_users (active only), cafeteria audience
  via CafeteriaAssignment; unsupported users do NOT receive; counts accurate
- Creation: persisted broadcast + per-recipient Notification rows,
  multiple recipients, nothing persisted on rejection
- Duplicate safety: idempotency-key replay returns the original broadcast
  and creates no additional rows
- Existing behavior: broadcasts appear in the recipient's existing
  notification center; initially unread; mark-read and mark-all-read still
  work (unchanged behavior)
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import (
    AdminBroadcast,
    DeliveryStatus,
    Notification,
    NotificationType,
)
from app.modules.users.models import AccountStatus, CafeteriaAssignment, Role
from tests.conftest import (
    create_test_cafeteria,
    create_test_user,
    create_user_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload(**overrides) -> dict:
    base = {
        "title": "Campus announcement",
        "message": "The library will close early on Friday.",
        "audience": "students",
        "idempotency_key": str(uuid.uuid4()),
    }
    base.update(overrides)
    return base


async def _admin_bearer_client(client: AsyncClient, db: AsyncSession) -> AsyncClient:
    """Build an authenticated client for a fresh university admin."""
    admin = await create_test_user(
        db,
        first_name="Broadcast",
        last_name="Admin",
        university_id=f"ADM-{uuid.uuid4().hex[:8]}",
        university_email=f"bc.admin.{uuid.uuid4().hex[:8]}@lgu.edu.pk",
        role=Role.UNIVERSITY_ADMIN,
    )
    _, access_token, _ = await create_user_session(db, admin)
    return AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )


async def _recipient_client(
    client: AsyncClient,
    db: AsyncSession,
    *,
    role: Role,
    email: str | None = None,
):
    user = await create_test_user(
        db,
        first_name="Recip",
        last_name="Ent",
        university_id=f"RCP-{uuid.uuid4().hex[:8]}",
        university_email=email or f"rcp.{uuid.uuid4().hex[:8]}@lgu.edu.pk",
        role=role,
    )
    _, access_token, _ = await create_user_session(db, user)
    authed = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return authed, user


async def _notifications_for(db: AsyncSession, user_id: str) -> list[Notification]:
    result = await db.execute(
        select(Notification).where(Notification.user_id == user_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class TestAuthorization:
    async def test_unauthenticated_broadcast_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/notifications/broadcast", json=_payload())
        assert resp.status_code == 401

    async def test_non_admin_student_cannot_broadcast(
        self, client: AsyncClient, db: AsyncSession
    ):
        student, _ = await _recipient_client(client, db, role=Role.STUDENT)
        resp = await student.post("/api/v1/notifications/broadcast", json=_payload())
        assert resp.status_code == 403

        broadcasts = (await db.execute(select(AdminBroadcast))).scalars().all()
        assert len(broadcasts) == 0

    async def test_non_admin_manager_cannot_broadcast(
        self, client: AsyncClient, db: AsyncSession
    ):
        manager, _ = await _recipient_client(client, db, role=Role.CAFETERIA_MANAGER)
        resp = await manager.post("/api/v1/notifications/broadcast", json=_payload())
        assert resp.status_code == 403

    async def test_non_admin_staff_cannot_broadcast(
        self, client: AsyncClient, db: AsyncSession
    ):
        staff, _ = await _recipient_client(client, db, role=Role.CAFETERIA_STAFF)
        resp = await staff.post("/api/v1/notifications/broadcast", json=_payload())
        assert resp.status_code == 403

    async def test_non_admin_cannot_read_broadcast_history(
        self, client: AsyncClient, db: AsyncSession
    ):
        student, _ = await _recipient_client(client, db, role=Role.STUDENT)
        assert (await student.get("/api/v1/notifications/broadcasts")).status_code == 403
        assert (
            await student.get(
                "/api/v1/notifications/broadcasts/audience-count",
                params={"audience": "students"},
            )
        ).status_code == 403

    async def test_unauthenticated_history_rejected(self, client: AsyncClient):
        assert (await client.get("/api/v1/notifications/broadcasts")).status_code == 401

    async def test_admin_broadcast_allowed(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, student = await _recipient_client(client, db, role=Role.STUDENT)
        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post("/api/v1/notifications/broadcast", json=_payload(audience="students"))
        assert resp.status_code == 201
        data = resp.json()
        assert data["duplicate"] is False
        assert data["recipient_count"] == 1
        assert len(await _notifications_for(db, student.id)) == 1


# ---------------------------------------------------------------------------
# Validation (backend-authoritative)
# ---------------------------------------------------------------------------


class TestValidation:
    async def _reject(self, client: AsyncClient, db: AsyncSession, payload: dict, code: int):
        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post("/api/v1/notifications/broadcast", json=payload)
        assert resp.status_code == code, f"expected {code}, got {resp.status_code}: {resp.text}"
        broadcasts = (await db.execute(select(AdminBroadcast))).scalars().all()
        assert len(broadcasts) == 0, "rejected broadcast must not persist"
        notifications = (await db.execute(select(Notification))).scalars().all()
        assert len(notifications) == 0, "rejected broadcast must not create notifications"

    async def test_empty_title_rejected(self, client: AsyncClient, db: AsyncSession):
        await self._reject(client, db, _payload(title="   "), 400)
        await self._reject(client, db, _payload(title=""), 422)

    async def test_empty_message_rejected(self, client: AsyncClient, db: AsyncSession):
        await self._reject(client, db, _payload(message="   "), 400)
        await self._reject(client, db, _payload(message=""), 422)

    async def test_invalid_audience_rejected(self, client: AsyncClient, db: AsyncSession):
        await self._reject(client, db, _payload(audience="everyone_on_the_planet"), 422)

    async def test_unsupported_combination_cafeteria_id_without_cafeteria_audience(
        self, client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Combo Caf")
        await self._reject(
            client,
            db,
            _payload(audience="students", cafeteria_id=cafeteria.id),
            400,
        )

    async def test_cafeteria_audience_requires_cafeteria_id(
        self, client: AsyncClient, db: AsyncSession
    ):
        await self._reject(client, db, _payload(audience="cafeteria"), 400)

    async def test_unknown_cafeteria_id_rejected(
        self, client: AsyncClient, db: AsyncSession
    ):
        await self._reject(
            client,
            db,
            _payload(audience="cafeteria", cafeteria_id=str(uuid.uuid4())),
            404,
        )

    async def test_malformed_cafeteria_id_rejected(
        self, client: AsyncClient, db: AsyncSession
    ):
        await self._reject(
            client,
            db,
            _payload(audience="cafeteria", cafeteria_id="not-a-valid-id"),
            404,
        )

    async def test_zero_recipient_audience_rejected(
        self, client: AsyncClient, db: AsyncSession
    ):
        # No active cafeteria_manager users exist in this test DB.
        await self._reject(
            client, db, _payload(audience="cafeteria_managers"), 400
        )


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTargeting:
    async def test_role_audience_reaches_only_that_role(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, faculty = await _recipient_client(client, db, role=Role.FACULTY)
        _, student = await _recipient_client(client, db, role=Role.STUDENT)

        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast",
            json=_payload(audience="faculty", message="Faculty senate meets Tuesday."),
        )
        assert resp.status_code == 201
        assert resp.json()["recipient_count"] == 1

        faculty_notes = await _notifications_for(db, faculty.id)
        assert len(faculty_notes) == 1
        assert faculty_notes[0].notification_type == NotificationType.ADMIN_ANNOUNCEMENT
        assert faculty_notes[0].body == "Faculty senate meets Tuesday."

        student_notes = await _notifications_for(db, student.id)
        assert len(student_notes) == 0, "unsupported audience must not receive"

    async def test_all_users_targets_active_users_only(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, active_user = await _recipient_client(client, db, role=Role.STUDENT)
        suspended = await create_test_user(
            db,
            first_name="Suspended",
            last_name="Student",
            university_id=f"SUS-{uuid.uuid4().hex[:8]}",
            university_email=f"sus.{uuid.uuid4().hex[:8]}@lgu.edu.pk",
            role=Role.STUDENT,
            status=AccountStatus.SUSPENDED,
        )
        pending = await create_test_user(
            db,
            first_name="Pending",
            last_name="Student",
            university_id=f"PEND-{uuid.uuid4().hex[:8]}",
            university_email=f"pend.{uuid.uuid4().hex[:8]}@lgu.edu.pk",
            role=Role.STUDENT,
            status=AccountStatus.PENDING_VERIFICATION,
        )

        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="all_users")
        )
        assert resp.status_code == 201

        assert len(await _notifications_for(db, active_user.id)) == 1
        assert len(await _notifications_for(db, suspended.id)) == 0
        assert len(await _notifications_for(db, pending.id)) == 0

    async def test_cafeteria_audience_targets_assigned_active_staff(
        self, client: AsyncClient, db: AsyncSession
    ):
        cafeteria = await create_test_cafeteria(db, name="Targeting Caf")
        _, assigned_staff = await _recipient_client(client, db, role=Role.CAFETERIA_STAFF)
        _, unassigned_staff = await _recipient_client(client, db, role=Role.CAFETERIA_STAFF)

        db.add(
            CafeteriaAssignment(
                user_id=assigned_staff.id,
                cafeteria_id=cafeteria.id,
                role=Role.CAFETERIA_STAFF,
            )
        )
        await db.flush()

        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast",
            json=_payload(
                audience="cafeteria",
                cafeteria_id=cafeteria.id,
                message="Menu tasting at 2pm.",
            ),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["recipient_count"] == 1
        assert data["cafeteria_id"] == cafeteria.id

        assigned_notes = await _notifications_for(db, assigned_staff.id)
        assert len(assigned_notes) == 1
        assert assigned_notes[0].cafeteria_id == cafeteria.id

        unassigned_notes = await _notifications_for(db, unassigned_staff.id)
        assert len(unassigned_notes) == 0

    async def test_audience_count_preview_matches_send(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, student_a = await _recipient_client(client, db, role=Role.STUDENT)
        _, student_b = await _recipient_client(client, db, role=Role.STUDENT)

        admin_client = await _admin_bearer_client(client, db)
        preview = await admin_client.get(
            "/api/v1/notifications/broadcasts/audience-count",
            params={"audience": "students"},
        )
        assert preview.status_code == 200
        expected = preview.json()["recipient_count"]
        assert expected >= 2

        resp = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="students")
        )
        assert resp.status_code == 201
        assert resp.json()["recipient_count"] == expected

        for uid in (student_a.id, student_b.id):
            assert len(await _notifications_for(db, uid)) == 1


# ---------------------------------------------------------------------------
# Creation & persistence
# ---------------------------------------------------------------------------


class TestCreation:
    async def test_broadcast_persists_record_and_per_recipient_rows(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, recipient = await _recipient_client(client, db, role=Role.STUDENT)

        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast",
            json=_payload(audience="students", title="Exam schedule", message="Midterms start Monday."),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Exam schedule"
        assert data["message"] == "Midterms start Monday."
        assert data["audience"] == "students"
        assert data["recipient_count"] == 1
        assert data["duplicate"] is False
        assert "created_at" in data

        broadcast = (
            await db.execute(
                select(AdminBroadcast).where(AdminBroadcast.id == data["id"])
            )
        ).scalar_one()
        assert broadcast.created_by_name == "Broadcast Admin"
        assert broadcast.recipient_count == 1
        assert broadcast.idempotency_key

        notes = await _notifications_for(db, recipient.id)
        assert len(notes) == 1
        note = notes[0]
        assert note.notification_type == NotificationType.ADMIN_ANNOUNCEMENT
        assert note.title == "Exam schedule"
        assert note.body == "Midterms start Monday."
        assert note.is_read is False
        assert note.delivery_status == DeliveryStatus.PENDING
        assert note.reference_type == "broadcast"
        assert note.reference_id == broadcast.id
        assert note.source_event_type == "admin_broadcast"
        assert note.source_event_id is None  # per-row idempotency is at broadcast level

    async def test_multiple_recipients_each_get_exactly_one_row(
        self, client: AsyncClient, db: AsyncSession
    ):
        recipients = []
        for _ in range(3):
            _, u = await _recipient_client(client, db, role=Role.FACULTY)
            recipients.append(u)

        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="faculty")
        )
        assert resp.status_code == 201
        assert resp.json()["recipient_count"] == 3

        for u in recipients:
            notes = await _notifications_for(db, u.id)
            assert len(notes) == 1

        all_notes = (await db.execute(select(Notification))).scalars().all()
        assert len(all_notes) == 3, "no partial/duplicate rows"


# ---------------------------------------------------------------------------
# Duplicate safety
# ---------------------------------------------------------------------------


class TestDuplicateSafety:
    async def test_idempotency_key_replay_returns_original(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, recipient = await _recipient_client(client, db, role=Role.STUDENT)
        key = str(uuid.uuid4())

        admin_client = await _admin_bearer_client(client, db)
        first = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(idempotency_key=key)
        )
        assert first.status_code == 201

        second = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(idempotency_key=key)
        )
        assert second.status_code == 200
        data = second.json()
        assert data["duplicate"] is True
        assert data["id"] == first.json()["id"]
        assert data["recipient_count"] == first.json()["recipient_count"]

        broadcasts = (await db.execute(select(AdminBroadcast))).scalars().all()
        assert len(broadcasts) == 1, "replay must not create a second broadcast"

        notes = await _notifications_for(db, recipient.id)
        assert len(notes) == 1, "replay must not create duplicate recipient rows"

    async def test_distinct_keys_create_distinct_broadcasts(
        self, client: AsyncClient, db: AsyncSession
    ):
        admin_client = await _admin_bearer_client(client, db)
        r1 = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="university_admins")
        )
        r2 = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="university_admins")
        )
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

        broadcasts = (await db.execute(select(AdminBroadcast))).scalars().all()
        assert len(broadcasts) == 2


# ---------------------------------------------------------------------------
# Existing behavior preserved (notification center, read/unread)
# ---------------------------------------------------------------------------


class TestExistingBehavior:
    async def test_broadcast_appears_in_existing_center_unread_then_read(
        self, client: AsyncClient, db: AsyncSession
    ):
        recipient, user = await _recipient_client(client, db, role=Role.STUDENT)

        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="students")
        )
        assert resp.status_code == 201

        # Recipient sees the broadcast in the existing GET /notifications center.
        center = await recipient.get("/api/v1/notifications")
        assert center.status_code == 200
        body = center.json()
        assert body["unread_count"] == 1
        assert any(
            n["notification_type"] == "admin_announcement"
            and n["title"] == "Campus announcement"
            and n["is_read"] is False
            for n in body["items"]
        )

        # Mark-read behavior unchanged.
        note = (await _notifications_for(db, user.id))[0]
        read_resp = await recipient.patch(f"/api/v1/notifications/{note.id}/read")
        assert read_resp.status_code == 200
        assert read_resp.json()["is_read"] is True
        assert read_resp.json()["read_at"] is not None

        unread = await recipient.get("/api/v1/notifications/unread-count")
        assert unread.json()["unread_count"] == 0

    async def test_mark_all_read_still_works_with_broadcasts(
        self, client: AsyncClient, db: AsyncSession
    ):
        recipient, _user = await _recipient_client(client, db, role=Role.STUDENT)

        admin_client = await _admin_bearer_client(client, db)
        for _ in range(2):
            resp = await admin_client.post(
                "/api/v1/notifications/broadcast", json=_payload(audience="students")
            )
            assert resp.status_code == 201

        all_resp = await recipient.patch("/api/v1/notifications/read-all")
        assert all_resp.status_code == 200
        assert all_resp.json()["marked_count"] == 2

        unread = await recipient.get("/api/v1/notifications/unread-count")
        assert unread.json()["unread_count"] == 0

    async def test_broadcast_history_visible_to_admin(
        self, client: AsyncClient, db: AsyncSession
    ):
        _, student = await _recipient_client(client, db, role=Role.STUDENT)
        admin_client = await _admin_bearer_client(client, db)
        resp = await admin_client.post(
            "/api/v1/notifications/broadcast", json=_payload(audience="students")
        )
        assert resp.status_code == 201
        assert len(await _notifications_for(db, student.id)) == 1
        sent = resp.json()

        history = await admin_client.get("/api/v1/notifications/broadcasts")
        assert history.status_code == 200
        data = history.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        entry = data["items"][0]
        assert entry["id"] == sent["id"]
        assert entry["title"] == "Campus announcement"
        assert entry["audience"] == "students"
        assert entry["recipient_count"] == sent["recipient_count"]
        assert entry["duplicate"] is False
