"""Refund service — business logic for refund processing.

Handles:
- Refund creation (full and partial)
- Refund deadline enforcement (configurable, default 72 hours)
- Refund amount validation (prevent over-refunding)
- Refund idempotency
- Refund authorization (admin/manager scope)
- Integration with payment state transitions
- Inventory release on refund
- Financial audit trail
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.config import settings
from app.core.exceptions import AuthorizationError, NotFoundException, ValidationError
from app.modules.notifications.service import emit_refund_notification
from app.modules.orders.models import Order
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundEvent, RefundReason, RefundStatus
from app.modules.refunds.processors.base import RefundProcessingResult
from app.modules.users.models import CafeteriaAssignment, Role, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.refunds.processors.base import RefundProcessor

logger = structlog.get_logger(__name__)

# Configurable refund deadline (hours)
REFUND_DEADLINE_HOURS = getattr(settings, "REFUND_DEADLINE_HOURS", 72)


class RefundService:
    """Service for refund operations."""

    def __init__(self, db: AsyncSession, processor: RefundProcessor) -> None:
        self.db = db
        self.processor = processor

    # ===================================================================
    # Create refund
    # ===================================================================

    async def create_refund(
        self,
        *,
        order_id: str,
        amount: int,
        reason: str,
        reason_note: str | None,
        requested_by_user_id: str,
        idempotency_key: str,
    ) -> Refund:
        """Create and process a refund.

        Validates:
        - Order exists and has a successful payment
        - Refund deadline not exceeded
        - Amount does not exceed refundable amount
        - Requester has appropriate permissions
        - Idempotency (same key = return existing refund)
        """
        # Check idempotency
        existing = await self._get_refund_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        # Load order
        order = await self._get_order(order_id)

        # Load payment
        payment = await self._get_successful_payment(order_id)
        if payment is None:
            raise ValidationError("No successful payment found for this order")

        # Validate refundable amount
        total_refunded = await self._get_total_refunded(payment.id)
        refundable = payment.amount - total_refunded
        if refundable <= 0:
            raise ValidationError("No refundable amount remaining")
        if amount > refundable:
            raise ValidationError(f"Refund amount {amount} exceeds refundable amount {refundable}")

        # Validate refund deadline
        if not self._is_within_refund_deadline(order):
            raise ValidationError(
                f"Refund deadline exceeded ({REFUND_DEADLINE_HOURS} hours after order)"
            )

        # Parse reason
        try:
            refund_reason = RefundReason(reason)
        except ValueError as err:
            raise ValidationError(
                f"Invalid refund reason: {reason}. "
                f"Valid reasons: {', '.join(r.value for r in RefundReason)}"
            ) from err

        # Create refund record
        refund = Refund(
            id=str(uuid.uuid4()),
            order_id=order.id,
            payment_id=payment.id,
            user_id=order.user_id,
            amount=amount,
            currency=payment.currency,
            status=RefundStatus.PENDING,
            reason=refund_reason,
            reason_note=reason_note,
            requested_by=requested_by_user_id,
            idempotency_key=idempotency_key,
        )
        self.db.add(refund)
        await self.db.flush()

        # Record refund requested event
        event = RefundEvent(
            refund_id=refund.id,
            event_type="refund_requested",
            actor_id=requested_by_user_id,
            notes=f"Reason: {reason}" + (f" — {reason_note}" if reason_note else ""),
        )
        self.db.add(event)

        # Emit notification (fire-and-forget)
        await emit_refund_notification(
            self.db,
            refund_id=refund.id,
            order_id=order.id,
            order_number=order.order_number,
            user_id=order.user_id,
            event_type="refund_requested",
            source_event_id=event.id,
            cafeteria_id=order.cafeteria_id,
        )

        await self.db.flush()

        logger.info(
            "refund_created",
            refund_id=refund.id,
            order_id=order.id,
            amount=amount,
            reason=reason,
        )
        return refund

    # ===================================================================
    # Process refund (admin/manager action)
    # ===================================================================

    async def process_refund(
        self,
        *,
        refund_id: str,
        processor_user_id: str,
        processor_role: Role,
    ) -> Refund:
        """Process/approve a refund.

        Authorization:
        - UNIVERSITY_ADMIN can process any refund
        - CAFETERIA_MANAGER can process refunds for their assigned cafeteria
        - Others are denied

        Calls the refund processor to execute the actual refund.
        """
        refund = await self._get_refund(refund_id)

        if refund.status not in (RefundStatus.PENDING,):
            raise ValidationError(f"Cannot process refund in {refund.status.value} status")

        # Load order for cafeteria scope check
        order = await self._get_order(refund.order_id)

        # Authorization check
        if processor_role == Role.UNIVERSITY_ADMIN:
            pass  # Admin can process any refund
        elif processor_role == Role.CAFETERIA_MANAGER:
            await self._verify_cafeteria_assignment(processor_user_id, order.cafeteria_id)
        else:
            raise AuthorizationError("You do not have permission to process refunds")

        # Transition to PROCESSING
        refund.status = RefundStatus.PROCESSING
        event = RefundEvent(
            refund_id=refund.id,
            event_type="refund_processing",
            actor_id=processor_user_id,
        )
        self.db.add(event)
        await self.db.flush()

        # Load payment for provider reference
        payment = await self._get_payment(refund.payment_id)

        # Cash ("pay at counter") payments were never captured by an online
        # provider, so there is no provider reference to refund against.
        # They are settled manually by staff handing cash back — record the
        # refund as succeeded with a manual reference instead of routing it
        # through the provider processor (Phase 8 D7).
        # Scope is strictly cash: an ONLINE payment missing its provider
        # reference is a data anomaly and must still fail closed in the
        # processor (never fabricate success).
        if payment.provider_name == "cash":
            result = RefundProcessingResult(
                success=True,
                provider_reference=f"manual_cash_{refund.id[:12]}",
                provider_metadata={"settlement": "manual", "method": payment.provider_name or "cash"},
            )
        else:
            # Call processor
            result = await self.processor.create_refund(
                refund_id=refund.id,
                payment_provider_reference=payment.provider_reference or "",
                amount=refund.amount,
                currency=refund.currency,
                idempotency_key=refund.idempotency_key,
                reason=refund.reason.value,
            )

        if result.success:
            refund.status = RefundStatus.SUCCEEDED
            refund.processed_by = processor_user_id
            refund.processed_at = datetime.now(UTC)
            refund.provider_reference = result.provider_reference

            # Update payment status
            total_refunded = await self._get_total_refunded(payment.id)
            if total_refunded >= payment.amount:
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED

            # Record success event
            event = RefundEvent(
                refund_id=refund.id,
                event_type="refund_succeeded",
                actor_id=processor_user_id,
                notes=f"Provider reference: {result.provider_reference}",
            )
            self.db.add(event)

            # Emit notification (fire-and-forget)
            await emit_refund_notification(
                self.db,
                refund_id=refund.id,
                order_id=order.id,
                order_number=order.order_number,
                user_id=order.user_id,
                event_type="refund_succeeded",
                source_event_id=event.id,
                cafeteria_id=order.cafeteria_id,
            )

            # Release inventory if order had reserved inventory
            if order.inventory_reserved:
                from app.modules.orders.service import OrderService

                order_service = OrderService(self.db)
                await order_service._release_inventory(order, processor_user_id)

            logger.info(
                "refund_succeeded",
                refund_id=refund.id,
                amount=refund.amount,
                provider_ref=result.provider_reference,
            )
        else:
            refund.status = RefundStatus.FAILED
            event = RefundEvent(
                refund_id=refund.id,
                event_type="refund_failed",
                actor_id=processor_user_id,
                notes=result.error_message,
            )
            self.db.add(event)

            # Emit notification (fire-and-forget)
            await emit_refund_notification(
                self.db,
                refund_id=refund.id,
                order_id=order.id,
                order_number=order.order_number,
                user_id=order.user_id,
                event_type="refund_failed",
                source_event_id=event.id,
                cafeteria_id=order.cafeteria_id,
            )

            logger.warning(
                "refund_failed",
                refund_id=refund.id,
                error=result.error_message,
            )

        await self.db.flush()
        return refund

    # ===================================================================
    # Reject refund (admin/manager action) — Phase 51
    # ===================================================================

    async def reject_refund(
        self,
        *,
        refund_id: str,
        rejected_by_user_id: str,
        rejected_by_role: Role,
        rejection_reason: str,
    ) -> Refund:
        """Reject a pending refund with a persisted reason.

        Authorization mirrors process_refund:
        - UNIVERSITY_ADMIN can reject any refund
        - CAFETERIA_MANAGER can reject refunds for their assigned cafeteria
        - Others are denied

        State rules: only PENDING refunds can be rejected. Rejected refunds
        are terminal for this workflow — they can no longer be processed
        or rejected again. No money movement occurs on rejection.
        """
        refund = await self._get_refund(refund_id)

        reason = (rejection_reason or "").strip()
        if len(reason) < 10:
            raise ValidationError(
                "Rejection reason must be at least 10 characters long"
            )

        if refund.status != RefundStatus.PENDING:
            raise ValidationError(
                f"Cannot reject refund in {refund.status.value} status"
            )

        # Load order for cafeteria scope check
        order = await self._get_order(refund.order_id)

        # Authorization check (same policy as process_refund)
        if rejected_by_role == Role.UNIVERSITY_ADMIN:
            pass  # Admin can reject any refund
        elif rejected_by_role == Role.CAFETERIA_MANAGER:
            await self._verify_cafeteria_assignment(
                rejected_by_user_id, order.cafeteria_id
            )
        else:
            raise AuthorizationError("You do not have permission to reject refunds")

        refund.status = RefundStatus.REJECTED
        refund.rejection_reason = reason
        refund.processed_by = rejected_by_user_id
        refund.processed_at = datetime.now(UTC)

        event = RefundEvent(
            refund_id=refund.id,
            event_type="refund_rejected",
            actor_id=rejected_by_user_id,
            notes=f"Reason: {reason}",
        )
        self.db.add(event)

        # Existing notification integration (refund event → in-app notification)
        await emit_refund_notification(
            self.db,
            refund_id=refund.id,
            order_id=order.id,
            order_number=order.order_number,
            user_id=order.user_id,
            event_type="refund_rejected",
            source_event_id=event.id,
            cafeteria_id=order.cafeteria_id,
        )

        await self.db.flush()
        logger.info(
            "refund_rejected",
            refund_id=refund.id,
            rejected_by=rejected_by_user_id,
        )
        return refund

    # ===================================================================
    # Retrieval
    # ===================================================================

    async def get_refund(self, refund_id: str) -> Refund:
        """Get a refund by ID."""
        return await self._get_refund(refund_id)

    async def build_admin_response(self, refund: Refund) -> Any:
        """Build the enriched admin refund view (student/order/payment context)."""
        from app.modules.cafeterias.models import Cafeteria
        from app.modules.refunds.schemas import (
            RefundAdminResponse,
            RefundOrderContext,
            RefundPaymentContext,
            RefundStudentContext,
        )

        user = await self._get_user(refund.user_id)
        order = await self._get_order(refund.order_id)
        payment = await self._get_payment(refund.payment_id)

        cafeteria_name: str | None = None
        if order.cafeteria_id:
            result = await self.db.execute(
                select(Cafeteria).where(Cafeteria.id == order.cafeteria_id)
            )
            cafeteria = result.scalar_one_or_none()
            cafeteria_name = cafeteria.name if cafeteria else None

        return RefundAdminResponse(
            id=refund.id,
            order_id=refund.order_id,
            payment_id=refund.payment_id,
            user_id=refund.user_id,
            amount=refund.amount,
            currency=refund.currency,
            status=refund.status.value,
            reason=refund.reason.value,
            reason_note=refund.reason_note,
            rejection_reason=refund.rejection_reason,
            requested_by=refund.requested_by,
            processed_by=refund.processed_by,
            provider_reference=refund.provider_reference,
            created_at=refund.created_at,
            processed_at=refund.processed_at,
            updated_at=refund.updated_at,
            student=RefundStudentContext(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                university_email=user.university_email,
                university_id=user.university_id,
                role=user.role.value,
            ),
            order=RefundOrderContext(
                id=order.id,
                order_number=order.order_number,
                status=order.status.value,
                payment_method=order.payment_method.value,
                total_amount=order.total_amount,
                currency=order.currency,
                order_date=order.order_date,
                cafeteria_id=order.cafeteria_id,
                cafeteria_name=cafeteria_name,
                created_at=order.created_at,
            ),
            payment=RefundPaymentContext(
                id=payment.id,
                status=payment.status.value,
                provider_name=payment.provider_name,
                provider_reference=payment.provider_reference,
                amount=payment.amount,
                currency=payment.currency,
            ),
        )

    async def list_admin_refunds(
        self,
        *,
        cafeteria_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Any], int]:
        """List refunds with admin context and a real total count."""
        base = select(Refund)
        if cafeteria_id:
            base = base.join(Order, Refund.order_id == Order.id).where(
                Order.cafeteria_id == cafeteria_id
            )
        if status:
            base = base.where(Refund.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(Refund.created_at.desc()).limit(limit).offset(offset)
        )
        refunds = list(result.scalars().all())
        enriched = [await self.build_admin_response(r) for r in refunds]
        return enriched, total

    async def get_admin_refund(self, refund_id: str) -> Any:
        """Get one refund with full admin context (404 if missing)."""
        refund = await self._get_refund(refund_id)
        return await self.build_admin_response(refund)

    async def get_order_refunds(self, order_id: str) -> list[Refund]:
        """Get all refunds for an order."""
        result = await self.db.execute(
            select(Refund).where(Refund.order_id == order_id).order_by(Refund.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_refundable_amount(self, order_id: str) -> dict[str, Any]:
        """Calculate the refundable amount for an order."""
        order = await self._get_order(order_id)
        payment = await self._get_successful_payment(order_id)

        if payment is None:
            return {
                "order_id": order.id,
                "paid_amount": 0,
                "total_refunded": 0,
                "refundable_amount": 0,
                "currency": order.currency,
            }

        total_refunded = await self._get_total_refunded(payment.id)
        return {
            "order_id": order.id,
            "paid_amount": payment.amount,
            "total_refunded": total_refunded,
            "refundable_amount": payment.amount - total_refunded,
            "currency": payment.currency,
        }

    async def list_order_refunds(
        self,
        *,
        cafeteria_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Refund]:
        """List refunds with optional filters."""
        query = select(Refund).order_by(Refund.created_at.desc())
        if cafeteria_id:
            query = query.join(Order, Refund.order_id == Order.id).where(
                Order.cafeteria_id == cafeteria_id
            )
        if status:
            query = query.where(Refund.status == status)
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ===================================================================
    # Private helpers
    # ===================================================================

    async def _get_user(self, user_id: str) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundException("User", user_id)
        return user

    async def _get_order(self, order_id: str) -> Order:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", order_id)
        return order

    async def _get_payment(self, payment_id: str) -> Payment:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment is None:
            raise NotFoundException("Payment", payment_id)
        return payment

    async def _get_successful_payment(self, order_id: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status.in_(
                    [
                        PaymentStatus.SUCCEEDED,
                        PaymentStatus.PARTIALLY_REFUNDED,
                        PaymentStatus.REFUNDED,
                    ]
                ),
            )
        )
        return result.scalar_one_or_none()

    async def _get_refund(self, refund_id: str) -> Refund:
        result = await self.db.execute(select(Refund).where(Refund.id == refund_id))
        refund = result.scalar_one_or_none()
        if refund is None:
            raise NotFoundException("Refund", refund_id)
        return refund

    async def _get_refund_by_idempotency_key(self, key: str) -> Refund | None:
        result = await self.db.execute(select(Refund).where(Refund.idempotency_key == key))
        return result.scalar_one_or_none()

    async def _get_total_refunded(self, payment_id: str) -> int:
        """Get total successfully refunded amount for a payment."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(
                Refund.payment_id == payment_id,
                Refund.status == RefundStatus.SUCCEEDED,
            )
        )
        return result.scalar() or 0

    def _is_within_refund_deadline(self, order: Order) -> bool:
        """Check if the order is within the refund deadline."""
        deadline = order.created_at + timedelta(hours=REFUND_DEADLINE_HOURS)
        now = datetime.now(UTC)
        # Handle timezone-naive datetimes (SQLite doesn't store timezone)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return now <= deadline

    async def _verify_cafeteria_assignment(self, user_id: str, cafeteria_id: str) -> None:
        """Verify a user is assigned to a cafeteria."""
        result = await self.db.execute(
            select(CafeteriaAssignment).where(
                CafeteriaAssignment.user_id == user_id,
                CafeteriaAssignment.cafeteria_id == cafeteria_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise AuthorizationError("You are not assigned to this cafeteria")
