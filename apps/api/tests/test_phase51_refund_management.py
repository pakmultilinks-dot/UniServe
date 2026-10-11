"""Tests for Phase 51 — Admin refund management and resolution.

Covers:
- Authorization for reject / admin list / admin detail (admin, manager,
  staff, student, faculty, unauthenticated) — backend-authoritative
- Cafeteria scoping for manager reject (assigned vs other cafeteria)
- Rejection state machine (pending → rejected; only pending; single
  resolution; rejected refunds are terminal for the workflow)
- Rejection reason validation (missing/empty/too-short/too-long/whitespace)
- Approval with context (enriched admin list/detail, processed_by/at,
  payment status transitions, RefundEvent audit)
- Failed-processor path (non-test_pay_ provider ref → FAILED, not SUCCEEDED)
- refund_rejected notification emitted through existing infrastructure
- Data integrity (order totals, payment amounts, payment status on reject)
- Existing behavior preserved (user request flow, /admin/all filters/total)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification, NotificationType
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import (
    Refund,
    RefundEvent,
    RefundStatus,
)
from app.modules.refunds.processors.test_processor import TestRefundProcessor
from app.modules.refunds.service import RefundService
from app.modules.users.models import Role
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_user,
    create_user_session,
)

REFUNDS = "/api/v1/refunds"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_order_with_payment(
    db: AsyncSession,
    *,
    user_id: str,
    cafeteria_id: str,
    amount: int = 50000,
    payment_status: PaymentStatus = PaymentStatus.SUCCEEDED,
    provider_reference: str | None = None,
):
    """Create an order + payment for Phase 51 tests. Returns (order, payment)."""
    from datetime import date as date_type

    order = Order(
        order_number=9500 + int(uuid.uuid4().int % 500),
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        order_type=OrderType.IMMEDIATE,
        payment_method=PaymentMethod.CASH,
        status=OrderStatus.PENDING,
        total_amount=amount,
        currency="PKR",
        order_date=date_type.today(),
        inventory_reserved=False,
    )
    db.add(order)
    await db.flush()

    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order.id,
        user_id=user_id,
        amount=amount,
        currency="PKR",
        status=payment_status,
        provider_name="test_provider",
        provider_reference=(
            provider_reference
            if provider_reference is not None
            else f"test_pay_{uuid.uuid4().hex[:12]}"
        ),
        idempotency_key=f"pay_{order.id}",
    )
    db.add(payment)
    await db.flush()
    return order, payment


async def _create_pending_refund(
    db: AsyncSession,
    *,
    order: Order,
    student_id: str,
    amount: int | None = None,
    key_prefix: str = "p51",
) -> Refund:
    """Create a PENDING refund through the real service flow."""
    svc = RefundService(db, TestRefundProcessor())
    return await svc.create_refund(
        order_id=order.id,
        amount=amount if amount is not None else order.total_amount,
        reason="order_cancelled",
        reason_note="Phase 51 test refund",
        requested_by_user_id=student_id,
        idempotency_key=f"{key_prefix}_{uuid.uuid4().hex[:12]}",
    )


async def _auth_client(
    client: AsyncClient,
    db: AsyncSession,
    user,
) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, user)
    return AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )


async def _fresh_user(
    db: AsyncSession,
    *,
    role: Role,
    prefix: str,
):
    return await create_test_user(
        db,
        first_name=prefix.title(),
        last_name="Phase51",
        university_id=f"P51-{uuid.uuid4().hex[:8]}",
        university_email=f"{prefix}.{uuid.uuid4().hex[:8]}@lgu.edu.pk",
        role=role,
    )


async def _notifications_for(db: AsyncSession, user_id: str) -> list[Notification]:
    result = await db.execute(
        select(Notification).where(Notification.user_id == user_id)
    )
    return list(result.scalars().all())


REJECT_REASON = "Duplicate charge confirmed after manual review."


# ---------------------------------------------------------------------------
# Authorization — reject / admin endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRejectAuthorization:
    """Backend authorization for rejection and admin visibility."""

    async def _pending_refund(self, db: AsyncSession, student_id: str, caf_id: str):
        order, payment = await _create_order_with_payment(
            db, user_id=student_id, cafeteria_id=caf_id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student_id
        )
        return order, payment, refund

    async def test_unauthenticated_reject_returns_401(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AuthCafe")
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)
        res = await client.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 401

    async def test_student_cannot_reject(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AuthCafe")
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)
        authed = await _auth_client(client, db, student)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 403
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_faculty_cannot_reject(self, client: AsyncClient, db):
        faculty = await _fresh_user(db, role=Role.FACULTY, prefix="p51fac")
        cafeteria = await create_test_cafeteria(db, name="P51 AuthCafe")
        _, _, refund = await self._pending_refund(db, faculty.id, cafeteria.id)
        authed = await _auth_client(client, db, faculty)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 403

    async def test_staff_cannot_reject(self, client: AsyncClient, db):
        staff = await _fresh_user(db, role=Role.CAFETERIA_STAFF, prefix="p51stf")
        cafeteria = await create_test_cafeteria(db, name="P51 AuthCafe")
        _, _, refund = await self._pending_refund(db, staff.id, cafeteria.id)
        authed = await _auth_client(client, db, staff)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 403

    async def test_manager_can_reject_assigned_cafeteria(
        self, client: AsyncClient, db
    ):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 MgrCafe")
        manager = await _fresh_user(db, role=Role.CAFETERIA_MANAGER, prefix="p51mgr")
        await assign_user_to_cafeteria(
            db, manager.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)
        authed = await _auth_client(client, db, manager)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 200
        await db.refresh(refund)
        assert refund.status == RefundStatus.REJECTED
        assert refund.rejection_reason == REJECT_REASON

    async def test_manager_cannot_reject_other_cafeteria(
        self, client: AsyncClient, db
    ):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 MgrCafe")
        other = await create_test_cafeteria(db, name="P51 OtherCafe")
        manager = await _fresh_user(db, role=Role.CAFETERIA_MANAGER, prefix="p51mgr")
        await assign_user_to_cafeteria(
            db, manager.id, other.id, Role.CAFETERIA_MANAGER
        )
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)
        authed = await _auth_client(client, db, manager)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 403
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_admin_can_reject_any_refund(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AdminCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)
        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 200

    async def test_admin_list_requires_university_admin(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 ListCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)

        res = await client.get(f"{REFUNDS}/admin/all")
        assert res.status_code == 401

        authed_student = await _auth_client(client, db, student)
        res = await authed_student.get(f"{REFUNDS}/admin/all")
        assert res.status_code == 403

        authed_admin = await _auth_client(client, db, admin)
        res = await authed_admin.get(f"{REFUNDS}/admin/all")
        assert res.status_code == 200
        payload = res.json()
        assert payload["total"] >= 1
        assert any(r["id"] == refund.id for r in payload["refunds"])

    async def test_manager_cannot_use_admin_list(self, client: AsyncClient, db):
        cafeteria = await create_test_cafeteria(db, name="P51 ListCafe")
        manager = await _fresh_user(db, role=Role.CAFETERIA_MANAGER, prefix="p51mgr")
        await assign_user_to_cafeteria(
            db, manager.id, cafeteria.id, Role.CAFETERIA_MANAGER
        )
        authed = await _auth_client(client, db, manager)
        res = await authed.get(f"{REFUNDS}/admin/all")
        assert res.status_code == 403

    async def test_admin_detail_returns_context(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 DetailCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        _, payment, refund = await self._pending_refund(
            db, student.id, cafeteria.id
        )
        authed = await _auth_client(client, db, admin)
        res = await authed.get(f"{REFUNDS}/admin/{refund.id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["id"] == refund.id
        assert payload["student"]["id"] == student.id
        assert payload["student"]["university_email"] == student.university_email
        assert payload["order"]["order_number"] is not None
        assert payload["order"]["cafeteria_name"] == cafeteria.name
        assert payload["payment"]["id"] == payment.id
        assert payload["payment"]["provider_reference"] is not None

    async def test_admin_detail_404_for_unknown_refund(self, client: AsyncClient, db):
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        authed = await _auth_client(client, db, admin)
        res = await authed.get(f"{REFUNDS}/admin/{uuid.uuid4()}")
        assert res.status_code == 404

    async def test_admin_detail_requires_admin(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 DetailCafe")
        _, _, refund = await self._pending_refund(db, student.id, cafeteria.id)
        authed = await _auth_client(client, db, student)
        res = await authed.get(f"{REFUNDS}/admin/{refund.id}")
        assert res.status_code == 403


# ---------------------------------------------------------------------------
# Rejection workflow — state machine + validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRejectionWorkflow:
    """Rejection transitions, validation, audit trail, notifications."""

    async def test_reject_pending_refund_success(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, payment = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )

        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "rejected"
        assert body["rejection_reason"] == REJECT_REASON
        assert body["processed_by"] == admin.id
        assert body["processed_at"] is not None
        assert body["student"]["id"] == student.id

        await db.refresh(refund)
        assert refund.status == RefundStatus.REJECTED
        assert refund.rejection_reason == REJECT_REASON
        assert refund.processed_by == admin.id
        assert refund.processed_at is not None

        # Audit event recorded
        events = (
            await db.execute(
                select(RefundEvent).where(RefundEvent.refund_id == refund.id)
            )
        ).scalars().all()
        types = {e.event_type for e in events}
        assert "refund_rejected" in types

        # No money movement on rejection
        await db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED

        # Requester notified through existing notification infrastructure
        notifications = await _notifications_for(db, student.id)
        types = {n.notification_type for n in notifications}
        assert NotificationType.REFUND_REJECTED.value in types

    async def test_reject_twice_fails(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)

        res1 = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res1.status_code == 200
        res2 = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res2.status_code == 400
        await db.refresh(refund)
        assert refund.status == RefundStatus.REJECTED

    async def test_approve_after_reject_fails(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)

        res1 = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res1.status_code == 200
        res2 = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res2.status_code == 400
        await db.refresh(refund)
        assert refund.status == RefundStatus.REJECTED

    async def test_reject_missing_reason_422(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)
        res = await authed.post(f"{REFUNDS}/{refund.id}/reject", json={})
        assert res.status_code == 422
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_reject_empty_reason_422(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject", json={"rejection_reason": ""}
        )
        assert res.status_code == 422
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_reject_whitespace_reason_rejected_by_service(
        self, client: AsyncClient, db
    ):
        """Whitespace-only reasons pass schema min_length but are stripped
        server-side to empty → service-level ValidationError (400)."""
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": "            "},
        )
        assert res.status_code == 400
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_reject_too_short_reason_422(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": "too short"},
        )
        assert res.status_code == 422
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_reject_too_long_reason_422(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 RejCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": "x" * 501},
        )
        assert res.status_code == 422
        await db.refresh(refund)
        assert refund.status == RefundStatus.PENDING

    async def test_reject_nonexistent_refund_404(self, client: AsyncClient, db):
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{uuid.uuid4()}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 404

    async def test_process_nonexistent_refund_404(self, client: AsyncClient, db):
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        authed = await _auth_client(client, db, admin)
        res = await authed.post(f"{REFUNDS}/{uuid.uuid4()}/process")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Approval workflow — context, invariants, processor failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestApprovalWorkflow:
    """Approval (process) behavior with Phase 51 admin context invariants."""

    async def test_approve_pending_refund_succeeds(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AppCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, payment = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )

        authed = await _auth_client(client, db, admin)
        res = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "succeeded"
        assert body["processed_by"] == admin.id
        assert body["processed_at"] is not None

        await db.refresh(refund)
        assert refund.status == RefundStatus.SUCCEEDED
        await db.refresh(payment)
        assert payment.status == PaymentStatus.REFUNDED

    async def test_approve_again_fails(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AppCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)

        res1 = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res1.status_code == 200
        res2 = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res2.status_code == 400

    async def test_reject_after_approve_fails(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AppCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )
        authed = await _auth_client(client, db, admin)

        res1 = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res1.status_code == 200
        res2 = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res2.status_code == 400
        await db.refresh(refund)
        assert refund.status == RefundStatus.SUCCEEDED

    async def test_failed_processor_creates_failed_refund(
        self, client: AsyncClient, db
    ):
        """Payment without test_pay_ ref → processor refuses → FAILED refund,
        payment status unchanged. Never fabricates success."""
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 FailCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, payment = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        # Simulate a live payment without a usable provider reference
        payment.provider_reference = None
        await db.flush()
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id
        )

        authed = await _auth_client(client, db, admin)
        res = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "failed"

        await db.refresh(refund)
        assert refund.status == RefundStatus.FAILED
        await db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED  # unchanged

    async def test_partial_refund_payment_partially_refunded(
        self, client: AsyncClient, db
    ):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 AppCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, payment = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id, amount=50000
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id, amount=20000
        )

        authed = await _auth_client(client, db, admin)
        res = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res.status_code == 200
        assert res.json()["status"] == "succeeded"

        await db.refresh(payment)
        assert payment.status == PaymentStatus.PARTIALLY_REFUNDED

    async def test_admin_list_enriched_and_filtered(
        self, client: AsyncClient, db
    ):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 ListCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")

        order_a, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        pending_refund = await _create_pending_refund(
            db, order=order_a, student_id=student.id
        )
        order_b, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        rejected_refund = await _create_pending_refund(
            db, order=order_b, student_id=student.id
        )
        svc = RefundService(db, TestRefundProcessor())
        await svc.reject_refund(
            refund_id=rejected_refund.id,
            rejected_by_user_id=admin.id,
            rejected_by_role=Role.UNIVERSITY_ADMIN,
            rejection_reason=REJECT_REASON,
        )

        authed = await _auth_client(client, db, admin)
        res_all = await authed.get(f"{REFUNDS}/admin/all")
        assert res_all.status_code == 200
        all_payload = res_all.json()
        assert all_payload["total"] >= 2
        mine = {
            r["id"]: r
            for r in all_payload["refunds"]
            if r["id"] in (pending_refund.id, rejected_refund.id)
        }
        assert pending_refund.id in mine
        assert rejected_refund.id in mine
        assert mine[pending_refund.id]["status"] == "pending"
        assert mine[rejected_refund.id]["status"] == "rejected"
        # Enriched context present
        assert mine[pending_refund.id]["student"]["university_email"] == (
            student.university_email
        )
        assert mine[pending_refund.id]["order"]["cafeteria_name"] == cafeteria.name
        assert mine[pending_refund.id]["payment"]["status"] == "succeeded"
        assert mine[rejected_refund.id]["rejection_reason"] == REJECT_REASON

        res_rej = await authed.get(f"{REFUNDS}/admin/all?status=rejected")
        assert res_rej.status_code == 200
        rej_ids = {r["id"] for r in res_rej.json()["refunds"]}
        assert rejected_refund.id in rej_ids
        assert pending_refund.id not in rej_ids


# ---------------------------------------------------------------------------
# Data integrity — orders/payments never altered by resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDataIntegrity:
    """Resolution must not alter order/payment core amounts."""

    async def test_rejection_preserves_order_and_payment_amounts(
        self, client: AsyncClient, db
    ):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 IntCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, payment = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id, amount=75000
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id, amount=75000
        )

        authed = await _auth_client(client, db, admin)
        res = await authed.post(
            f"{REFUNDS}/{refund.id}/reject",
            json={"rejection_reason": REJECT_REASON},
        )
        assert res.status_code == 200

        await db.refresh(order)
        await db.refresh(payment)
        await db.refresh(refund)
        assert order.total_amount == 75000
        assert payment.amount == 75000
        assert payment.status == PaymentStatus.SUCCEEDED
        assert refund.amount == 75000

    async def test_approval_preserves_order_total(self, client: AsyncClient, db):
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 IntCafe")
        admin = await _fresh_user(db, role=Role.UNIVERSITY_ADMIN, prefix="p51adm")
        order, payment = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id, amount=75000
        )
        refund = await _create_pending_refund(
            db, order=order, student_id=student.id, amount=75000
        )

        authed = await _auth_client(client, db, admin)
        res = await authed.post(f"{REFUNDS}/{refund.id}/process")
        assert res.status_code == 200

        await db.refresh(order)
        await db.refresh(payment)
        assert order.total_amount == 75000  # never altered
        assert payment.amount == 75000
        # Existing semantics: payment transitions to refunded
        assert payment.status == PaymentStatus.REFUNDED

    async def test_user_request_flow_still_works(self, client: AsyncClient, db):
        """Existing creation flow unchanged: PENDING + REFUND_REQUESTED notif."""
        student = await _fresh_user(db, role=Role.STUDENT, prefix="p51stu")
        cafeteria = await create_test_cafeteria(db, name="P51 IntCafe")
        order, _ = await _create_order_with_payment(
            db, user_id=student.id, cafeteria_id=cafeteria.id
        )
        svc = RefundService(db, TestRefundProcessor())
        refund = await svc.create_refund(
            order_id=order.id,
            amount=order.total_amount,
            reason="order_cancelled",
            reason_note="still works",
            requested_by_user_id=student.id,
            idempotency_key=f"p51_keep_{uuid.uuid4().hex[:8]}",
        )
        assert refund.status == RefundStatus.PENDING
        notifications = await _notifications_for(db, student.id)
        types = {n.notification_type for n in notifications}
        assert NotificationType.REFUND_REQUESTED.value in types
