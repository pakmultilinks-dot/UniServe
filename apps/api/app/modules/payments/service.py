"""Payment service — business logic for payment processing.

Handles:
- Cash payment record creation
- Online payment initiation via provider
- Payment success verification
- Webhook processing (idempotent)
- Payment status transitions
- Provider abstraction
- Financial invariants (server-authoritative amounts)
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthorizationError, NotFoundException, ValidationError
from app.modules.notifications.service import emit_order_notification
from app.modules.orders.models import (
    Order,
    OrderEvent,
    OrderEventType,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentStatus,
    WebhookEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.payments.providers.base import PaymentProvider

logger = structlog.get_logger(__name__)


async def backfill_completed_cash_payments(db: AsyncSession) -> dict[str, int]:
    """Backfill the cash payment ledger for completed cash orders (P2-2).

    Before the Phase 43 fix, cash payments were created PENDING at checkout
    and never confirmed, so reporting (which sums SUCCEEDED payments) showed
    Rs 0 revenue. Completed cash orders now confirm their ledger at handover,
    but historical rows predate that wiring. This backfills exactly those:

    - COMPLETED cash order with a PENDING cash payment → confirm to SUCCEEDED
    - COMPLETED cash order with no payment row (scheduled cash orders never
      created one) → create + confirm one for the order total

    Never touches non-cash orders, non-completed orders, or payments in any
    other state. Idempotent — safe to re-run.
    """
    result = await db.execute(
        select(Order).where(
            Order.payment_method == PaymentMethod.CASH,
            Order.status == OrderStatus.COMPLETED,
        )
    )
    completed_cash_orders = list(result.scalars().all())

    confirmed = 0
    created = 0
    for order in completed_cash_orders:
        pay_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
        payment = pay_result.scalar_one_or_none()
        if payment is None:
            db.add(
                Payment(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    user_id=order.user_id,
                    amount=order.total_amount,
                    currency=order.currency,
                    status=PaymentStatus.SUCCEEDED,
                    provider_name="cash",
                    idempotency_key=f"cash_{order.id}",
                )
            )
            created += 1
        elif payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.SUCCEEDED
            confirmed += 1

    await db.flush()
    logger.info(
        "cash_payment_ledger_backfilled",
        completed_cash_orders=len(completed_cash_orders),
        payments_confirmed=confirmed,
        payments_created=created,
    )
    return {
        "completed_cash_orders": len(completed_cash_orders),
        "payments_confirmed": confirmed,
        "payments_created": created,
    }


def _attach_reconciliation_note(payment: Payment, reason: str) -> None:
    """Merge a reconciliation audit note into the payment metadata JSON."""
    note = {
        "reconciled_at": datetime.now(UTC).isoformat(),
        "reason": reason,
    }
    existing: Any = None
    if payment.provider_metadata_json:
        try:
            parsed = json.loads(payment.provider_metadata_json)
            if isinstance(parsed, dict):
                existing = parsed
        except (json.JSONDecodeError, TypeError):
            existing = None
    if isinstance(existing, dict):
        existing["reconciliation"] = note
        payment.provider_metadata_json = json.dumps(existing)
    else:
        payload: dict[str, Any] = {"reconciliation": note}
        if payment.provider_metadata_json:
            payload["previous_metadata_unparseable"] = True
        payment.provider_metadata_json = json.dumps(payload)


async def reconcile_stale_payments(
    db: AsyncSession,
    *,
    stale_after_hours: int = 24,
    dry_run: bool = False,
) -> dict[str, int]:
    """Reconcile stale non-terminal payment rows (Phase 60, Workstream E).

    Closed-loop hygiene for payments stuck in PENDING/PROCESSING older
    than ``stale_after_hours``. Classification follows **established**
    business rules only — nothing is invented:

    * **Order cancelled before payment completed** → payment status
      ``CANCELLED`` (payment closed by business rule, not provider
      failure — CANCELLED, not FAILED). Applies to cash AND online
      rows; nothing can legitimately complete after the order is gone.

    * **Completed cash order, PENDING ledger row** → ``SUCCEEDED``.
      This is the sanctioned Phase-43 rule
      (``backfill_completed_cash_payments``): cash money changes hands
      at handover, which already happened if the order COMPLETED — the
      stale PENDING row is bookkeeping residue, not unconfirmed money.

    Deliberately untouched (documented sandbox permissiveness):

    * PENDING/PROCESSING payments on non-terminal orders — the user
      may be mid-payment right now; only provider events or explicit
      business transitions should move them.
    * COMPLETED **online** PROCESSING rows — await provider callback
      or external provider-side reconciliation.
    * All SUCCEEDED/FAILED/REFUNDED/REFUND_PENDING/PARTIALLY_REFUNDED
      rows and all amounts/currency values — never altered.

    Idempotent — re-running finds nothing left to reconcile. With
    ``dry_run=True`` the same rows are classified but nothing is
    mutated (counts then mean "would change"). Caller must commit;
    this function only flushes when actually mutating.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=stale_after_hours)

    result = await db.execute(
        select(Payment).where(
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            Payment.created_at < cutoff,
        )
    )
    stale_payments = list(result.scalars().all())

    orders_by_id: dict[str, Order] = {}
    order_ids = {p.order_id for p in stale_payments}
    if order_ids:
        orders_result = await db.execute(select(Order).where(Order.id.in_(order_ids)))
        orders_by_id = {o.id: o for o in orders_result.scalars().all()}

    order_cancelled = 0
    cash_confirmed = 0
    untouched = 0

    for payment in stale_payments:
        order = orders_by_id.get(payment.order_id)
        if order is not None and order.status == OrderStatus.CANCELLED:
            if not dry_run:
                payment.status = PaymentStatus.CANCELLED
                _attach_reconciliation_note(
                    payment, "order_cancelled_before_payment_completed"
                )
            order_cancelled += 1
        elif (
            order is not None
            and order.status == OrderStatus.COMPLETED
            and payment.provider_name == "cash"
            and payment.status == PaymentStatus.PENDING
        ):
            if not dry_run:
                payment.status = PaymentStatus.SUCCEEDED
                _attach_reconciliation_note(
                    payment, "completed_cash_order_ledger_confirmation"
                )
            cash_confirmed += 1
        else:
            untouched += 1

    if not dry_run:
        await db.flush()
    logger.info(
        "stale_payments_reconciled",
        stale_after_hours=stale_after_hours,
        dry_run=dry_run,
        scanned=len(stale_payments),
        order_cancelled=order_cancelled,
        cash_confirmed=cash_confirmed,
        untouched=untouched,
    )
    return {
        "scanned": len(stale_payments),
        "order_cancelled_payments_closed": order_cancelled,
        "completed_cash_payments_confirmed": cash_confirmed,
        "untouched": untouched,
        "dry_run": dry_run,
    }


class PaymentService:
    """Service for payment operations."""

    def __init__(self, db: AsyncSession, provider: PaymentProvider) -> None:
        self.db = db
        self.provider = provider

    # ===================================================================
    # Cash payment
    # ===================================================================

    async def create_cash_payment(self, order: Order, user_id: str) -> Payment:
        """Create a payment record for a cash order.

        Cash orders don't go through a provider. The payment record
        tracks the financial state cleanly.
        """
        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            user_id=user_id,
            amount=order.total_amount,
            currency=order.currency,
            status=PaymentStatus.PENDING,
            provider_name="cash",
            idempotency_key=f"cash_{order.id}",
        )
        self.db.add(payment)
        await self.db.flush()
        logger.info("cash_payment_created", payment_id=payment.id, order_id=order.id)
        return payment

    async def confirm_cash_payment(self, payment: Payment) -> Payment:
        """Confirm a cash payment (at collection/counter).

        Cash payments are confirmed when the order is collected.
        """
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(f"Cannot confirm cash payment in {payment.status.value} status")

        payment.status = PaymentStatus.SUCCEEDED
        await self.db.flush()
        logger.info("cash_payment_confirmed", payment_id=payment.id)
        return payment

    # ===================================================================
    # Online payment initiation
    # ===================================================================

    async def initiate_online_payment(
        self,
        *,
        order_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> tuple[Payment, str | None]:
        """Initiate an online payment for an order.

        Validates:
        - User owns the order
        - Order is online-payment type
        - Order is in a payment-eligible state
        - No successful payment already exists
        - Amount is server-derived

        Returns (payment, redirect_url).
        """
        # Load order
        order = await self._get_order(order_id)

        # Verify ownership
        if order.user_id != user_id:
            raise AuthorizationError("You do not have access to this order")

        # Validate order type
        if order.payment_method != PaymentMethod.ONLINE:
            raise ValidationError("This order does not require online payment")

        # Validate order state
        if order.status == OrderStatus.CANCELLED:
            raise ValidationError("Cannot pay for a cancelled order")
        if order.status not in (OrderStatus.PENDING,):
            raise ValidationError(f"Order is not in a payment-eligible state: {order.status.value}")

        # Check for existing successful payment
        existing = await self._get_successful_payment(order_id)
        if existing:
            raise ValidationError("Payment has already been completed for this order")

        # Check idempotency — return existing payment if key matches
        existing_by_key = await self._get_payment_by_idempotency_key(idempotency_key)
        if existing_by_key:
            return existing_by_key, None

        # Create payment record (server-authoritative amount)
        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            user_id=user_id,
            amount=order.total_amount,  # Always from order, never from client
            currency=order.currency,
            status=PaymentStatus.PENDING,
            provider_name=self.provider.name,
            idempotency_key=idempotency_key,
        )
        self.db.add(payment)
        try:
            # Savepoint: a concurrent initiation with the same idempotency key
            # may win the race — return the existing payment, not a 500.
            async with self.db.begin_nested():
                await self.db.flush()
        except IntegrityError:
            existing_retry = await self._get_payment_by_idempotency_key(idempotency_key)
            if existing_retry is not None:
                return existing_retry, None
            raise

        # Create first attempt
        attempt = PaymentAttempt(
            id=str(uuid.uuid4()),
            payment_id=payment.id,
            attempt_number=1,
            status=PaymentAttemptStatus.PENDING,
            amount=payment.amount,
        )
        self.db.add(attempt)
        await self.db.flush()

        # Initiate with provider
        result = await self.provider.initiate_payment(
            payment_id=payment.id,
            order_id=order.id,
            amount=payment.amount,
            currency=payment.currency,
            idempotency_key=idempotency_key,
        )

        if result.success:
            payment.status = PaymentStatus.PROCESSING
            payment.provider_reference = result.provider_reference
            attempt.status = PaymentAttemptStatus.PROCESSING
            attempt.provider_reference = result.provider_reference
            if result.provider_metadata:
                payment.provider_metadata_json = json.dumps(result.provider_metadata)
        else:
            payment.status = PaymentStatus.FAILED
            attempt.status = PaymentAttemptStatus.FAILED
            attempt.error_message = result.error_message

        await self.db.flush()
        logger.info(
            "online_payment_initiated",
            payment_id=payment.id,
            order_id=order.id,
            success=result.success,
        )
        return payment, result.redirect_url

    # ===================================================================
    # Payment success (provider webhook / verification)
    # ===================================================================

    async def handle_payment_success(
        self,
        *,
        payment_id: str,
        provider_reference: str,
        provider_metadata: dict[str, Any] | None = None,
    ) -> Payment:
        """Handle a verified payment success event.

        Called after webhook signature verification or provider API verification.
        NEVER called directly from client requests.

        - Transitions payment to SUCCEEDED
        - Confirms cash payment or marks online payment as succeeded
        - Reserves inventory for online orders
        - Transitions order if needed
        """
        payment = await self._get_payment(payment_id)

        # Idempotent — already succeeded is fine
        if payment.status == PaymentStatus.SUCCEEDED:
            return payment

        # Validate payment is in a processable state
        if payment.status in (PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
            raise ValidationError(f"Payment is in terminal state: {payment.status.value}")

        # Verify amount matches order (provider spoofing protection)
        order = await self._get_order(payment.order_id)
        if payment.amount != order.total_amount:
            logger.warning(
                "payment_amount_mismatch",
                payment_id=payment.id,
                payment_amount=payment.amount,
                order_amount=order.total_amount,
            )
            raise ValidationError("Payment amount does not match order total")

        if payment.currency != order.currency:
            raise ValidationError("Payment currency does not match order currency")

        # Update payment
        payment.status = PaymentStatus.SUCCEEDED
        payment.provider_reference = provider_reference
        if provider_metadata:
            payment.provider_metadata_json = json.dumps(provider_metadata)

        # Update latest attempt
        attempt = await self._get_latest_attempt(payment.id)
        if attempt:
            attempt.status = PaymentAttemptStatus.SUCCEEDED
            attempt.provider_reference = provider_reference
            if provider_metadata:
                attempt.provider_response_json = json.dumps(provider_metadata)

        # Reserve inventory for online immediate orders
        if order.order_type == OrderType.IMMEDIATE and not order.inventory_reserved:
            from app.modules.orders.service import OrderService

            order_service = OrderService(self.db)
            await order_service._reserve_inventory_for_online_payment(order)

        # Record payment event on the order
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.PAYMENT_CONFIRMED,
            notes=f"Payment {payment.id} confirmed via {payment.provider_name}",
        )
        self.db.add(event)

        # Emit notification (fire-and-forget)
        await emit_order_notification(
            self.db,
            order_id=order.id,
            order_number=order.order_number,
            user_id=order.user_id,
            event_type=OrderEventType.PAYMENT_CONFIRMED.value,
            source_event_id=event.id,
            notes=event.notes,
            cafeteria_id=order.cafeteria_id,
        )

        await self.db.flush()
        logger.info(
            "payment_succeeded",
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
        )
        return payment

    async def handle_payment_failure(
        self,
        *,
        payment_id: str,
        error_message: str | None = None,
    ) -> Payment:
        """Handle a payment failure event."""
        payment = await self._get_payment(payment_id)

        if payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.CANCELLED):
            return payment

        payment.status = PaymentStatus.FAILED

        attempt = await self._get_latest_attempt(payment.id)
        if attempt:
            attempt.status = PaymentAttemptStatus.FAILED
            attempt.error_message = error_message

        await self.db.flush()
        logger.info("payment_failed", payment_id=payment.id, error=error_message)
        return payment

    # ===================================================================
    # Webhook processing (idempotent)
    # ===================================================================

    async def process_webhook(
        self,
        *,
        provider_name: str,
        payload: bytes,
        provider_event_id: str,
    ) -> bool:
        """Process a payment webhook event.

        Idempotent — the same event_id will only be processed once.
        Returns True if the event was processed, False if already processed.
        """
        # Verify and parse webhook FIRST. Idempotency decisions must be based
        # on the provider-verified event ID from the signed payload — never
        # on unverified client/header input (e.g. x-event-id), which may be
        # absent, forged, or collapse distinct events into a single key.
        result = await self.provider.verify_webhook_signature(
            payload=payload,
            headers={"provider": provider_name},
        )

        # Prefer the verified event ID; fall back to the caller-supplied ID.
        event_id = (result.event_id or "").strip() or provider_event_id

        # Check if already processed (keyed by the verified event ID)
        existing = await self._get_webhook_event(event_id)
        if existing and existing.processed:
            logger.info("webhook_already_processed", event_id=event_id)
            return False

        if not result.valid:
            # Log the failed webhook
            if not existing:
                event = WebhookEvent(
                    provider_name=provider_name,
                    provider_event_id=event_id,
                    payload_json=payload.decode("utf-8", errors="replace"),
                    processed=False,
                    error_message=result.error_message,
                )
                self.db.add(event)
            else:
                existing.error_message = result.error_message
            await self.db.flush()
            logger.warning(
                "webhook_signature_invalid",
                event_id=event_id,
                error=result.error_message,
            )
            return False

        # Find the payment
        if not result.payment_reference:
            await self._log_unprocessed_webhook(
                provider_name, event_id, payload, "No payment reference in event"
            )
            return False

        payment = await self._get_payment_by_provider_reference(result.payment_reference)
        if not payment:
            await self._log_unprocessed_webhook(
                provider_name,
                event_id,
                payload,
                f"Unknown payment reference: {result.payment_reference}",
            )
            return False

        # Validate amount from webhook matches order
        order = await self._get_order(payment.order_id)
        if result.amount is not None and result.amount != order.total_amount:
            await self._log_unprocessed_webhook(
                provider_name,
                event_id,
                payload,
                f"Amount mismatch: webhook={result.amount}, order={order.total_amount}",
            )
            return False

        if result.currency and result.currency != order.currency:
            await self._log_unprocessed_webhook(
                provider_name,
                event_id,
                payload,
                f"Currency mismatch: webhook={result.currency}, order={order.currency}",
            )
            return False

        # Process based on event type
        if result.event_type == "payment_success":
            try:
                await self.handle_payment_success(
                    payment_id=payment.id,
                    provider_reference=result.payment_reference,
                    provider_metadata=result.metadata,
                )
            except ValidationError as exc:
                # Terminal state (e.g. late webhook for already-refunded payment).
                # Accept the webhook gracefully — the event is valid but the
                # payment is no longer processable.  Log and treat as processed.
                logger.warning(
                    "webhook_ignored_terminal_state",
                    event_id=provider_event_id,
                    payment_id=payment.id,
                    status=payment.status.value,
                    detail=str(exc),
                )
        elif result.event_type == "payment_failed":
            await self.handle_payment_failure(
                payment_id=payment.id,
                error_message="Payment failed per webhook",
            )
        else:
            logger.info("unknown_webhook_event_type", event_type=result.event_type)

        # Log webhook as processed
        if existing:
            existing.processed = True
            existing.processed_at = datetime.now(UTC)
        else:
            event = WebhookEvent(
                provider_name=provider_name,
                provider_event_id=event_id,
                payload_json=payload.decode("utf-8", errors="replace"),
                processed=True,
                processed_at=datetime.now(UTC),
            )
            self.db.add(event)

        await self.db.flush()
        return True

    # ===================================================================
    # Retrieval
    # ===================================================================

    async def get_payment(self, payment_id: str) -> Payment:
        """Get a payment by ID."""
        return await self._get_payment(payment_id)

    async def get_order_payment(self, order_id: str) -> Payment | None:
        """Get the payment for an order."""
        result = await self.db.execute(select(Payment).where(Payment.order_id == order_id))
        return result.scalar_one_or_none()

    async def list_user_payments(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Payment]:
        """List payments for a user."""
        result = await self.db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_payment_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        """Get payment by idempotency key (public for duplicate detection)."""
        return await self._get_payment_by_idempotency_key(idempotency_key)

    # ===================================================================
    # Private helpers
    # ===================================================================

    async def _get_order(self, order_id: str) -> Order:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", order_id)
        return order

    async def _get_payment(self, payment_id: str) -> Payment:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.attempts))
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            raise NotFoundException("Payment", payment_id)
        return payment

    async def _get_payment_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.idempotency_key == key))
        return result.scalar_one_or_none()

    async def _get_payment_by_provider_reference(self, ref: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.provider_reference == ref))
        return result.scalar_one_or_none()

    async def _get_successful_payment(self, order_id: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.SUCCEEDED,
            )
        )
        return result.scalar_one_or_none()

    async def _get_latest_attempt(self, payment_id: str) -> PaymentAttempt | None:
        result = await self.db.execute(
            select(PaymentAttempt)
            .where(PaymentAttempt.payment_id == payment_id)
            .order_by(PaymentAttempt.attempt_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_webhook_event(self, provider_event_id: str) -> WebhookEvent | None:
        result = await self.db.execute(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == provider_event_id)
        )
        return result.scalar_one_or_none()

    async def _log_unprocessed_webhook(
        self,
        provider_name: str,
        event_id: str,
        payload: bytes,
        error_message: str,
    ) -> None:
        """Log an unprocessed webhook event for auditing."""
        existing = await self._get_webhook_event(event_id)
        if existing:
            existing.error_message = error_message
        else:
            event = WebhookEvent(
                provider_name=provider_name,
                provider_event_id=event_id,
                payload_json=payload.decode("utf-8", errors="replace"),
                processed=False,
                error_message=error_message,
            )
            self.db.add(event)
        await self.db.flush()
