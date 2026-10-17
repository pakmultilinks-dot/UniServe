"""Order service — business logic for order creation, lifecycle, and collection.

Handles:
- Checkout (cart → order conversion)
- Order numbering (sequential, globally unique)
- Inventory reservation (immediate: at checkout; scheduled: at preparation)
- Cancellation rules (user before deadline, manager anytime)
- Collection via order number or QR token
- Order events (audit trail)
- Order confirmation / rejection by staff/manager (Phase 6)
- Preparation lifecycle (start, ready, delay, uncollected) (Phase 6)
- Partial item cancellation (Phase 6)
- Cafeteria sudden closure (Phase 6)
- No-show tracking (Phase 6)
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    AccountSuspendedError,
    NotFoundException,
    ValidationError,
)
from app.modules.carts.models import Cart, CartStatus
from app.modules.menus.models import DailyMenuStatus
from app.modules.notifications.service import emit_order_notification
from app.modules.orders.models import (
    Order,
    OrderEvent,
    OrderEventType,
    OrderItem,
    OrderNumberSequence,
    OrderRejectionReason,
    OrderStatus,
    OrderType,
    PaymentMethod,
)

logger = structlog.get_logger(__name__)

# Scheduled order cancellation deadline (30 minutes before collection)
CANCELLATION_DEADLINE_MINUTES = 30

# P3-14: scheduled orders still PENDING this long after their collection
# slot can no longer be fulfilled at the promised time — the background
# worker cancels them automatically. Mirrors the 30-minute user-cancellation
# window on the other side of the slot.
SCHEDULED_EXPIRY_GRACE_MINUTES = 30


class OrderService:
    """Service for order operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _emit_notification(self, order: Order, event: OrderEvent) -> None:
        """Fire-and-forget: emit a notification for an order event."""
        try:
            # Flush first so event.id is populated: the notification dedup key
            # is (source_event_type, source_event_id), and without the flush
            # the id is still None, so the dedup guard never triggers and
            # retries/double-emits create duplicates.
            await self.db.flush()
        except Exception:
            logger.warning("order_notification_flush_failed", order_id=order.id)
            return
        await emit_order_notification(
            self.db,
            order_id=order.id,
            order_number=order.order_number,
            user_id=order.user_id,
            event_type=event.event_type.value,
            source_event_id=event.id,
            notes=event.notes,
            cafeteria_id=order.cafeteria_id,
        )

    # ===================================================================
    # Checkout
    # ===================================================================

    async def checkout(
        self,
        *,
        user_id: str,
        cafeteria_id: str,
        payment_method: str = "cash",
        order_type: str = "immediate",
        scheduled_collection_time: str | None = None,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> Order:
        """Convert a cart into an order.

        Server is authoritative: validates everything, calculates total
        server-side, creates order items from cart snapshots.
        """
        # 0. Enforce no-show suspension: a suspended user cannot place new
        # orders until the suspension expires (check_suspension also clears
        # expired suspensions).
        from app.modules.orders.noshow import check_suspension

        if await check_suspension(db=self.db, user_id=user_id):
            raise AccountSuspendedError(
                "Your ordering is temporarily suspended due to repeated uncollected orders. "
                "Please contact the cafeteria."
            )

        # Return the original order when a retried checkout uses the same key.
        if idempotency_key:
            existing_result = await self.db.execute(
                select(Order).where(
                    Order.user_id == user_id,
                    Order.cafeteria_id == cafeteria_id,
                    Order.checkout_idempotency_key == idempotency_key,
                )
            )
            existing_order = existing_result.scalar_one_or_none()
            if existing_order is not None:
                return await self.get_order(existing_order.id)

        # 1. Get active cart with items
        cart = await self._get_active_cart_with_items(user_id, cafeteria_id)

        if not cart.items:
            raise ValidationError("Cannot checkout an empty cart")

        # 2. Validate scheduled order constraints
        parsed_order_type = OrderType(order_type)
        if parsed_order_type == OrderType.SCHEDULED:
            self._validate_scheduled_order(scheduled_collection_time)

        # 3. Validate cafeteria is operational
        from app.modules.cafeterias.models import Cafeteria, OperationalStatus

        caf_result = await self.db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria_id))
        cafeteria = caf_result.scalar_one_or_none()
        if cafeteria is None:
            raise NotFoundException("Cafeteria", cafeteria_id)
        if cafeteria.operational_status == OperationalStatus.CLOSED:
            raise ValidationError("Cafeteria is closed")
        if cafeteria.operational_status == OperationalStatus.MAINTENANCE:
            raise ValidationError("Cafeteria is under maintenance")

        # 3b. Validate scheduled order time constraints (requires cafeteria)
        if parsed_order_type == OrderType.SCHEDULED:
            self._validate_scheduled_order_time(scheduled_collection_time, cafeteria)

        # The cafeteria-local date is the product-correct "today": order_date
        # anchors scheduled-time parsing and the cancellation deadline, both of
        # which are cafeteria-local (P2 ΓÇö server UTC date made same-day PKT
        # slots look already past the 30-minute deadline).
        try:
            from zoneinfo import ZoneInfo

            caf_tz = ZoneInfo(cafeteria.timezone)
        except (ValueError, KeyError):
            caf_tz = UTC
        local_order_date = datetime.now(caf_tz).date()

        # 4. Validate published menu for today
        await self._validate_published_menu(cafeteria_id)

        # 5. Validate each cart item against current inventory and menu
        from app.modules.carts.service import CartService
        from app.modules.menus.service import get_effective_unit_price

        cart_service = CartService(self.db)
        total_amount = 0
        order_items_data = []

        for ci in cart.items:
            # Re-validate menu item
            mi = await cart_service._get_valid_menu_item(ci.menu_item_id, cafeteria_id)
            # Re-validate inventory
            await cart_service._validate_inventory(ci.menu_item_id, cafeteria_id, ci.quantity)

            # Server-authoritative effective price at charge time (Phase 42
            # P2-1): today's published-menu special price when set, else the
            # menu item's base price. Refreshes the cart snapshot so the order
            # item/total always match what the customer is charged.
            unit_price = await get_effective_unit_price(
                self.db, menu_item=mi, cafeteria_id=cafeteria_id
            )
            ci.price_snapshot = unit_price

            subtotal = unit_price * ci.quantity
            total_amount += subtotal
            order_items_data.append(
                {
                    "menu_item_id": ci.menu_item_id,
                    "item_name": mi.name,
                    "unit_price": unit_price,
                    "quantity": ci.quantity,
                    "subtotal": subtotal,
                    "currency": ci.currency,
                }
            )

        # 6. Allocate order number (atomic)
        order_number = await self._allocate_order_number()

        # 6b. Order currency comes from the cart snapshot (menu items carry
        # their own currency), not a hardcoded default. Mixed currencies in
        # one cart are rejected — they cannot be totaled coherently.
        currencies = {item_data["currency"] for item_data in order_items_data}
        if len(currencies) > 1:
            raise ValidationError("Cart contains items with mixed currencies")
        order_currency = next(iter(currencies))

        # 7. Create order
        order = Order(
            order_number=order_number,
            checkout_idempotency_key=idempotency_key,
            user_id=user_id,
            cafeteria_id=cafeteria_id,
            order_type=parsed_order_type,
            payment_method=PaymentMethod(payment_method),
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            currency=order_currency,
            order_date=local_order_date,
            scheduled_collection_time=scheduled_collection_time
            if parsed_order_type == OrderType.SCHEDULED
            else None,
            inventory_reserved=False,
            note=note,
        )
        self.db.add(order)
        await self.db.flush()

        # 8. Create order items (snapshots)
        for item_data in order_items_data:
            order_item = OrderItem(order_id=order.id, **item_data)
            self.db.add(order_item)

        # 9. Record creation event
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.CREATED,
            actor_id=user_id,
        )
        self.db.add(event)
        await self._emit_notification(order, event)

        # 10. Handle inventory reservation
        if parsed_order_type == OrderType.IMMEDIATE:
            if PaymentMethod(payment_method) == PaymentMethod.CASH:
                # Cash: reserve inventory immediately, create cash payment record
                await self._reserve_inventory(order, cart.items, user_id)
                from app.modules.payments.providers.cash_provider import (
                    CashPaymentProvider,
                )
                from app.modules.payments.service import PaymentService

                payment_svc = PaymentService(self.db, CashPaymentProvider())
                await payment_svc.create_cash_payment(order, user_id)
            elif PaymentMethod(payment_method) == PaymentMethod.ONLINE:
                # Online: inventory reserved after successful payment (Phase 5)
                event_pending = OrderEvent(
                    order_id=order.id,
                    event_type=OrderEventType.PAYMENT_PENDING,
                    notes="Awaiting online payment",
                )
                self.db.add(event_pending)
        # Scheduled: inventory reserved when preparation starts (not at checkout)

        # 10b. Auto-acceptance (ORDER_AUTO_ACCEPT): immediate cash orders are
        # confirmed and start preparation right away so the customer sees the
        # order progress immediately instead of waiting for staff. Online
        # orders are picked up by the background sweep once payment succeeds.
        if (
            settings.ORDER_AUTO_ACCEPT
            and parsed_order_type == OrderType.IMMEDIATE
            and PaymentMethod(payment_method) == PaymentMethod.CASH
        ):
            await self.auto_accept_order(
                order_id=order.id,
                notes="Auto-accepted at checkout",
            )

        # 11. Expire the cart
        cart.status = CartStatus.EXPIRED

        await self.db.flush()
        logger.info(
            "order_created",
            order_id=order.id,
            order_number=order_number,
            user_id=user_id,
            cafeteria_id=cafeteria_id,
            total=total_amount,
        )

        # Re-fetch with items loaded
        return await self.get_order(order.id)

    # ===================================================================
    # Order retrieval
    # ===================================================================

    async def get_order(self, order_id: str) -> Order:
        """Get an order by ID with items and events loaded."""
        result = await self.db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.events),
            )
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", order_id)
        return order

    async def _get_order_for_update(self, order_id: str) -> Order:
        """Get an order by ID with a row-level lock for mutation.

        Uses SELECT FOR UPDATE on PostgreSQL so two staff members cannot
        concurrently pass the same status check (e.g. double preparation or
        double inventory reservation). Skipped on SQLite (tests/dev), which
        does not support it — mirroring collect_order's convention.
        """
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.events),
            )
        )
        dialect_name = self.db.bind.dialect.name if self.db.bind else ""
        if dialect_name == "postgresql":
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", order_id)
        return order

    async def get_order_by_number(self, order_number: int) -> Order:
        """Get an order by its sequential order number."""
        result = await self.db.execute(
            select(Order)
            .where(Order.order_number == order_number)
            .options(
                selectinload(Order.items),
                selectinload(Order.events),
            )
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", str(order_number))
        return order

    async def get_order_by_token(self, token: str) -> Order:
        """Get an order by its collection QR token."""
        result = await self.db.execute(
            select(Order)
            .where(Order.collection_token == token)
            .options(
                selectinload(Order.items),
                selectinload(Order.events),
            )
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", "invalid collection token")
        return order

    async def list_user_orders(
        self,
        *,
        user_id: str,
        cafeteria_id: str | None = None,
        status: str | None = None,
        days: int = 7,
    ) -> list[Order]:
        """List orders for a user, defaulting to last 7 days."""
        cutoff = date.today() - timedelta(days=days)
        query = (
            select(Order)
            .where(
                Order.user_id == user_id,
                Order.order_date >= cutoff,
            )
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        )
        if cafeteria_id is not None:
            query = query.where(Order.cafeteria_id == cafeteria_id)
        if status is not None:
            query = query.where(Order.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_cafeteria_orders(
        self,
        *,
        cafeteria_id: str,
        status: str | None = None,
        order_date: date | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Order], int]:
        """List orders for a cafeteria (manager/staff view).

        Phase 54 — optional limit/offset paginate the queue; the returned
        total is the full count of orders matching the filters (before
        pagination) so callers can render page navigation. Omitting both
        preserves the original unpaginated behaviour exactly.
        """
        filters = [Order.cafeteria_id == cafeteria_id]
        if status is not None:
            filters.append(Order.status == status)
        if order_date is not None:
            filters.append(Order.order_date == order_date)

        count_query = select(func.count()).select_from(Order).where(*filters)
        total = (await self.db.execute(count_query)).scalar_one()

        query = (
            select(Order)
            .where(*filters)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        )
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    # ===================================================================
    # Cancellation
    # ===================================================================

    async def cancel_order(
        self,
        *,
        order_id: str,
        user_id: str | None = None,
        actor_id: str,
        reason: str | None = None,
        is_manager: bool = False,
    ) -> Order:
        """Cancel an order.

        User cancellation rules:
        - Order must be PENDING
        - For scheduled orders, must be >= 30 min before collection time

        Manager cancellation:
        - Can cancel PENDING or PREPARING orders
        """
        order = await self.get_order(order_id)

        if (
            not is_manager
            # Verify ownership BEFORE any status validation so that the
            # response cannot be used as an order-status oracle (Phase 8 D8).
            # Non-owners get the same "Order not found" answer as GET /orders/{id}.
            and user_id
            and order.user_id != user_id
        ):
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError("Order not found")

        # Already cancelled or completed
        if order.status == OrderStatus.CANCELLED:
            raise ValidationError("Order is already cancelled")
        if order.status == OrderStatus.COMPLETED:
            raise ValidationError("Cannot cancel a completed order")
        if order.status == OrderStatus.READY:
            raise ValidationError("Cannot cancel an order that is ready for collection")

        if is_manager:
            # Manager can cancel PENDING or PREPARING
            if order.status not in (OrderStatus.PENDING, OrderStatus.PREPARING):
                raise ValidationError(f"Cannot cancel order in {order.status.value} status")
        else:
            # User can only cancel PENDING orders
            if order.status != OrderStatus.PENDING:
                raise ValidationError(f"Cannot cancel order in {order.status.value} status")

            # Scheduled cancellation deadline check
            if order.order_type == OrderType.SCHEDULED and order.scheduled_collection_time:
                await self._check_scheduled_cancellation_deadline(order)

        # Release inventory if it was reserved
        if order.inventory_reserved:
            await self._release_inventory(order, actor_id)

        # Update order status
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(UTC)
        order.cancelled_by = actor_id
        order.cancellation_reason = reason

        # Record event
        event_type = OrderEventType.CANCELLED_BY_MANAGER if is_manager else OrderEventType.CANCELLED
        event = OrderEvent(
            order_id=order.id,
            event_type=event_type,
            actor_id=actor_id,
            notes=reason,
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info(
            "order_cancelled",
            order_id=order.id,
            order_number=order.order_number,
            actor_id=actor_id,
            is_manager=is_manager,
        )
        return order

    # ===================================================================
    # Status transitions (manager/staff)
    # ===================================================================

    async def _confirm_cash_payment_if_pending(self, order: Order) -> None:
        """Confirm the cash payment ledger when an order completes (P2-2).

        Cash is settled at handover, so the ledger must reflect completion:
        - COMPLETED cash order with a PENDING payment → confirm to SUCCEEDED
          (reporting sums SUCCEEDED payments; revenue showed Rs 0 otherwise).
        - COMPLETED cash order with no payment row (scheduled cash orders
          never create one at checkout) → create + confirm one for the
          order total. Idempotent — already-confirmed/cancelled/refunded
          payments are left untouched. Online orders are not affected.
        """
        if order.payment_method != PaymentMethod.CASH:
            return

        from app.modules.payments.models import Payment, PaymentStatus
        from app.modules.payments.providers.cash_provider import CashPaymentProvider
        from app.modules.payments.service import PaymentService

        result = await self.db.execute(select(Payment).where(Payment.order_id == order.id))
        payment = result.scalar_one_or_none()
        payment_svc = PaymentService(self.db, CashPaymentProvider())
        if payment is None:
            payment = await payment_svc.create_cash_payment(order, order.user_id)
        if payment.status == PaymentStatus.PENDING:
            await payment_svc.confirm_cash_payment(payment)

    async def update_status(
        self,
        *,
        order_id: str,
        new_status: str,
        actor_id: str,
        notes: str | None = None,
    ) -> Order:
        """Transition order status.

        Valid transitions:
        PENDING → PREPARING
        PREPARING → READY
        READY → COMPLETED
        """
        order = await self._get_order_for_update(order_id)
        previous_status = order.status

        valid_transitions = {
            OrderStatus.PENDING: OrderStatus.PREPARING,
            OrderStatus.PREPARING: OrderStatus.READY,
            OrderStatus.READY: OrderStatus.COMPLETED,
        }

        expected_next = valid_transitions.get(order.status)
        if expected_next is None or expected_next.value != new_status:
            raise ValidationError(f"Invalid status transition: {order.status.value} → {new_status}")

        # READY invariants (ready_at + pickup_deadline) must hold regardless of
        # which first-party transition path is used. Delegate to mark_ready —
        # the single source of truth for the PREPARING → READY transition — so
        # the generic path can never produce a READY order without them.
        if new_status == "ready":
            return await self.mark_ready(order_id=order_id, actor_id=actor_id, notes=notes)

        # P3-8: PENDING → PREPARING through this generic endpoint must satisfy
        # the same business gates as start_preparation (POST /prepare) AND set
        # the same lifecycle fields. Delegating keeps the two paths
        # indistinguishable — previously this path left preparation_started_at
        # NULL and skipped ETA when staff skipped the explicit Prepare step.
        if new_status == "preparing":
            return await self.start_preparation(
                order_id=order_id, actor_id=actor_id, notes=notes
            )

        order.status = OrderStatus(new_status)

        # Record event
        event_type_map = {
            "preparing": OrderEventType.PREPARATION_STARTED,
            "ready": OrderEventType.READY_FOR_COLLECTION,
            "completed": OrderEventType.COLLECTED,
        }
        event = OrderEvent(
            order_id=order.id,
            event_type=event_type_map[new_status],
            actor_id=actor_id,
            notes=notes,
        )
        self.db.add(event)
        await self._emit_notification(order, event)

        # For scheduled orders: reserve inventory when preparation starts
        if (
            new_status == "preparing"
            and not order.inventory_reserved
            and order.order_type == OrderType.SCHEDULED
        ):
            await self._reserve_inventory_for_order(order, actor_id)

        # Cash orders settle at handover — the READY → COMPLETED transition
        # completes the sale, so the cash ledger must follow (P2-2).
        if new_status == "completed":
            await self._confirm_cash_payment_if_pending(order)

        await self.db.flush()
        logger.info(
            "order_status_updated",
            order_id=order.id,
            old_status=previous_status.value,
            new_status=new_status,
        )
        return order

    # ===================================================================
    # Collection
    # ===================================================================

    async def collect_order(
        self,
        *,
        order_id: str,
        collector_id: str,
        cafeteria_id: str,
    ) -> Order:
        """Collect an order (mark as COMPLETED).

        Uses SELECT FOR UPDATE to prevent race with automatic expiry.
        Validates:
        - Order exists and belongs to the cafeteria
        - Order is READY
        - Not already collected
        - Not already marked uncollected
        - QR token is valid (if applicable)
        """
        # Lock the row to prevent concurrent collection vs expiry.
        # Skip row-level locking on SQLite (tests/dev) — only supported on PostgreSQL.
        stmt = select(Order).where(Order.id == order_id)
        dialect_name = self.db.bind.dialect.name if self.db.bind else ""
        if dialect_name == "postgresql":
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException("Order", order_id)

        # Eagerly load relationships after lock
        await self.db.refresh(order, ["items", "events"])

        if order.cafeteria_id != cafeteria_id:
            raise ValidationError("Order does not belong to this cafeteria")

        if order.status == OrderStatus.COMPLETED:
            if order.uncollected_at is not None:
                raise ValidationError("Order was marked as uncollected and cannot be collected")
            raise ValidationError("Order has already been collected")

        if order.status == OrderStatus.CANCELLED:
            raise ValidationError("Cannot collect a cancelled order")

        if order.status != OrderStatus.READY:
            raise ValidationError(
                f"Order is not ready for collection (current status: {order.status.value})"
            )

        if order.uncollected_at is not None:
            raise ValidationError("Order has already been marked as uncollected")

        order.status = OrderStatus.COMPLETED
        order.collected_at = datetime.now(UTC)
        order.collected_by = collector_id

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.COLLECTED,
            actor_id=collector_id,
        )
        self.db.add(event)

        # Cash is received at handover — collection completes the sale, so
        # the cash payment ledger must move to SUCCEEDED for reporting
        # (Phase 42 P2-2: revenue showed Rs 0 for completed cash orders).
        await self._confirm_cash_payment_if_pending(order)

        await self.db.flush()
        logger.info(
            "order_collected",
            order_id=order.id,
            order_number=order.order_number,
            collector_id=collector_id,
        )
        return order

    async def collect_by_order_number(
        self,
        *,
        order_number: int,
        collector_id: str,
        cafeteria_id: str,
    ) -> Order:
        """Collect an order by order number."""
        order = await self.get_order_by_number(order_number)
        return await self.collect_order(
            order_id=order.id,
            collector_id=collector_id,
            cafeteria_id=cafeteria_id,
        )

    async def collect_by_token(
        self,
        *,
        collection_token: str,
        collector_id: str,
        cafeteria_id: str,
    ) -> Order:
        """Collect an order by QR collection token."""
        order = await self.get_order_by_token(collection_token)
        return await self.collect_order(
            order_id=order.id,
            collector_id=collector_id,
            cafeteria_id=cafeteria_id,
        )

    # ===================================================================
    # Phase 6: Manager order confirmation / rejection
    # ===================================================================

    async def auto_accept_order(
        self,
        *,
        order_id: str,
        notes: str | None = None,
    ) -> Order:
        """Auto-confirm and start preparation (ORDER_AUTO_ACCEPT).

        PENDING → PREPARING in one step: sets confirmed_at (with a
        CONFIRMED_BY_STAFF event), then delegates to start_preparation so
        the PREPARING invariants (ETA, events, scheduled reservation) are
        identical to the manual staff path. actor_id=None marks a system
        action. Online orders whose payment has not succeeded yet are left
        PENDING — the background sweep retries after payment confirms.
        """
        order = await self._get_order_for_update(order_id)

        if order.status != OrderStatus.PENDING:
            return order

        if order.payment_method == PaymentMethod.ONLINE:
            from app.modules.payments.models import Payment, PaymentStatus

            result = await self.db.execute(
                select(Payment).where(Payment.order_id == order.id)
            )
            payment = result.scalar_one_or_none()
            if payment is None or payment.status != PaymentStatus.SUCCEEDED:
                return order  # awaiting payment — sweep will retry

        if order.confirmed_at is None:
            order.confirmed_at = datetime.now(UTC)
            event = OrderEvent(
                order_id=order.id,
                event_type=OrderEventType.CONFIRMED_BY_STAFF,
                actor_id=None,
                notes=notes or "Auto-accepted",
            )
            self.db.add(event)
            await self._emit_notification(order, event)

        return await self.start_preparation(
            order_id=order.id,
            actor_id=None,
            notes=notes or "Auto-accepted",
        )

    async def confirm_order(
        self,
        *,
        order_id: str,
        actor_id: str,
        notes: str | None = None,
    ) -> Order:
        """Manager/staff confirms an order for preparation.

        Transitions: PENDING → PENDING (confirmed flag set).
        """
        order = await self._get_order_for_update(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValidationError(f"Cannot confirm order in {order.status.value} status")

        if order.confirmed_at is not None:
            raise ValidationError("Order is already confirmed")

        order.confirmed_at = datetime.now(UTC)

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.CONFIRMED_BY_STAFF,
            actor_id=actor_id,
            notes=notes,
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info("order_confirmed", order_id=order.id, actor_id=actor_id)
        return order

    async def reject_order(
        self,
        *,
        order_id: str,
        actor_id: str,
        reason: str,
        notes: str | None = None,
    ) -> Order:
        """Manager rejects an order.

        Transitions: PENDING → CANCELLED.
        Releases inventory if reserved.
        """
        order = await self._get_order_for_update(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValidationError(f"Cannot reject order in {order.status.value} status")

        # Validate rejection reason
        try:
            OrderRejectionReason(reason)
        except ValueError as exc:
            raise ValidationError(
                f"Invalid rejection reason. Must be one of: "
                f"{', '.join(r.value for r in OrderRejectionReason)}"
            ) from exc

        # Release inventory if reserved
        if order.inventory_reserved:
            await self._release_inventory(order, actor_id)

        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(UTC)
        order.cancelled_by = actor_id
        order.rejection_reason = reason
        order.rejection_note = notes

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.MANAGER_REJECTED,
            actor_id=actor_id,
            notes=f"Reason: {reason}. {notes or ''}",
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info(
            "order_rejected",
            order_id=order.id,
            reason=reason,
            actor_id=actor_id,
        )
        return order

    # ===================================================================
    # Phase 6: Preparation lifecycle
    # ===================================================================

    async def start_preparation(
        self,
        *,
        order_id: str,
        actor_id: str,
        notes: str | None = None,
    ) -> Order:
        """Staff starts preparing an order.

        Transitions: PENDING → PREPARING (must be confirmed first).
        Sets preparation_started_at, calculates and records ETA.
        Reserves inventory for scheduled orders.
        """
        order = await self._get_order_for_update(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValidationError(
                f"Cannot start preparation for order in {order.status.value} status"
            )

        if order.confirmed_at is None:
            raise ValidationError("Order must be confirmed before starting preparation")

        # Online orders must have a successful payment before preparation
        if order.payment_method == PaymentMethod.ONLINE:
            from app.modules.payments.models import Payment, PaymentStatus

            result = await self.db.execute(
                select(Payment).where(Payment.order_id == order.id)
            )
            payment = result.scalar_one_or_none()

            if payment is None:
                raise ValidationError(
                    "Payment not found for online order"
                )
            if payment.status != PaymentStatus.SUCCEEDED:
                raise ValidationError(
                    f"Cannot start preparation: payment is {payment.status.value}, "
                    f"must be succeeded"
                )

        now = datetime.now(UTC)

        order.status = OrderStatus.PREPARING
        order.preparation_started_at = now
        order.preparation_started = True

        # Calculate ETA
        from app.modules.orders.eta import calculate_eta

        eta_minutes = await calculate_eta(
            db=self.db,
            cafeteria_id=order.cafeteria_id,
            order_id=order.id,
        )
        order.eta_minutes = eta_minutes

        # Reserve inventory for scheduled orders
        if not order.inventory_reserved and order.order_type == OrderType.SCHEDULED:
            await self._reserve_inventory_for_order(order, actor_id)

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.PREPARATION_STARTED,
            actor_id=actor_id,
            notes=notes,
        )
        self.db.add(event)
        await self._emit_notification(order, event)

        eta_event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.ETA_UPDATED,
            actor_id=actor_id,
            notes=f"ETA: {eta_minutes} minutes",
        )
        self.db.add(eta_event)

        await self.db.flush()
        logger.info(
            "preparation_started",
            order_id=order.id,
            eta_minutes=eta_minutes,
        )
        return order

    async def mark_ready(
        self,
        *,
        order_id: str,
        actor_id: str,
        notes: str | None = None,
    ) -> Order:
        """Staff marks an order as ready for collection.

        Transitions: PREPARING → READY.
        Sets ready_at and pickup_deadline.
        pickup_deadline = min(ready_at + PICKUP_WINDOW_MINUTES, cafeteria closing time)
        """
        from datetime import time as dt_time

        from app.modules.cafeterias.models import Cafeteria

        order = await self._get_order_for_update(order_id)

        if order.status != OrderStatus.PREPARING:
            raise ValidationError(f"Cannot mark ready: order is in {order.status.value} status")

        now = datetime.now(UTC)

        order.status = OrderStatus.READY
        order.ready_at = now

        # Calculate pickup_deadline: earlier of 30-min window or cafeteria closing
        deadline_30min = now + timedelta(minutes=settings.PICKUP_WINDOW_MINUTES)

        # Check cafeteria closing time
        caf_result = await self.db.execute(
            select(Cafeteria).where(Cafeteria.id == order.cafeteria_id)
        )
        cafeteria = caf_result.scalar_one_or_none()

        pickup_deadline = deadline_30min
        if cafeteria and cafeteria.closing_time:
            # Parse closing_time string "HH:MM" and combine with today's date
            try:
                hour, minute = map(int, cafeteria.closing_time.split(":"))
                # Closing time is in the cafeteria's local timezone, convert to UTC
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(cafeteria.timezone)

                # The cafeteria-local date is the product-correct "today": the
                # closing time is cafeteria-local, so combining it with the
                # server-local date is wrong near midnight (e.g. UTC server,
                # PKT cafeteria). checkout() already uses this convention.
                local_today = datetime.now(tz).date()
                local_closing = datetime.combine(local_today, dt_time(hour, minute), tzinfo=tz)
                utc_closing = local_closing.astimezone(UTC)
                if utc_closing < deadline_30min:
                    pickup_deadline = utc_closing
            except (ValueError, IndexError):
                pass  # Invalid closing_time format — fall back to 30-min window

        order.pickup_deadline = pickup_deadline

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.READY_FOR_COLLECTION,
            actor_id=actor_id,
            notes=notes,
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info(
            "order_ready",
            order_id=order.id,
            pickup_deadline=order.pickup_deadline.isoformat(),
        )
        return order

    async def mark_delayed(
        self,
        *,
        order_id: str,
        actor_id: str,
        additional_minutes: int = 15,
        notes: str | None = None,
    ) -> Order:
        """Staff marks an order as delayed with updated ETA.

        Updates eta_minutes and extends pickup_deadline if order is READY.
        """
        order = await self.get_order(order_id)

        if order.status not in (OrderStatus.PREPARING, OrderStatus.READY):
            raise ValidationError(f"Cannot delay order in {order.status.value} status")

        if additional_minutes < 1 or additional_minutes > 120:
            raise ValidationError("Additional minutes must be between 1 and 120")

        # Update ETA
        if order.eta_minutes is not None:
            order.eta_minutes += additional_minutes
        else:
            order.eta_minutes = additional_minutes

        # Extend pickup deadline if ready
        if order.status == OrderStatus.READY and order.pickup_deadline:
            order.pickup_deadline = order.pickup_deadline + timedelta(minutes=additional_minutes)

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.DELAYED,
            actor_id=actor_id,
            notes=f"Delayed by {additional_minutes} minutes. {notes or ''}",
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info(
            "order_delayed",
            order_id=order.id,
            new_eta=order.eta_minutes,
        )
        return order

    async def mark_uncollected(
        self,
        *,
        order_id: str,
        actor_id: str | None = None,
        notes: str | None = None,
    ) -> Order:
        """System marks an order as uncollected after pickup deadline.

        Transitions: READY → COMPLETED (marked uncollected).
        Records no-show event and may suspend user.
        Sets uncollected_at for idempotency.

        Money handling (the terminal state is explicit):
        - Cash orders: the PENDING cash ledger is voided (CANCELLED) — no cash
          changed hands, and the stale-payment reconciler must NOT later mark
          it SUCCEEDED under the completed-cash rule.
        - Online orders with a SUCCEEDED payment: a refund request is created
          for normal review (it is not auto-processed).
        """
        order = await self._get_order_for_update(order_id)

        # Idempotency: skip if already processed (checked before the status
        # gate so a repeated call on a COMPLETED-uncollected order is a
        # no-op rather than a ValidationError).
        if order.uncollected_at is not None:
            return order

        if order.status != OrderStatus.READY:
            raise ValidationError(
                f"Cannot mark uncollected: order is in {order.status.value} status"
            )

        now = datetime.now(UTC)
        order.uncollected_at = now
        # Terminal state: the order leaves staff READY queues and is counted
        # as completed-with-uncollected in reports.
        order.status = OrderStatus.COMPLETED

        # Record no-show
        from app.modules.orders.noshow import record_no_show

        await record_no_show(
            db=self.db,
            user_id=order.user_id,
            order_id=order.id,
            cafeteria_id=order.cafeteria_id,
        )

        # Settle money for the terminal state.
        await self._settle_uncollected_payment(order)

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.UNCOLLECTED,
            actor_id=actor_id,
            notes=notes,
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info(
            "order_uncollected",
            order_id=order.id,
            user_id=order.user_id,
        )
        return order

    async def _settle_uncollected_payment(self, order: Order) -> None:
        """Void or refund the payment of an uncollected order.

        Called once from mark_uncollected (which is idempotent via
        uncollected_at), so this never double-settles.
        """
        from app.modules.payments.models import Payment, PaymentStatus

        result = await self.db.execute(
            select(Payment).where(Payment.order_id == order.id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            return

        if (
            order.payment_method == PaymentMethod.CASH
            and payment.status == PaymentStatus.PENDING
        ):
            # No handover happened: void the bookkeeping ledger. This must
            # happen here — not via the stale-payment reconciler, whose
            # completed-cash rule would otherwise mark it SUCCEEDED.
            payment.status = PaymentStatus.CANCELLED
            logger.info(
                "uncollected_cash_payment_voided",
                order_id=order.id,
                payment_id=payment.id,
            )
        elif (
            order.payment_method == PaymentMethod.ONLINE
            and payment.status == PaymentStatus.SUCCEEDED
        ):
            # Customer paid but never collected: raise a refund request for
            # normal review. Idempotency key is deterministic; mark_uncollected
            # itself is idempotent, so this runs at most once per order.
            from app.modules.refunds.processors import create_refund_processor
            from app.modules.refunds.service import RefundService

            refund_svc = RefundService(self.db, create_refund_processor())
            await refund_svc.create_refund(
                order_id=order.id,
                amount=payment.amount,
                reason="other",
                reason_note="Order uncollected after pickup deadline — auto-requested refund",
                requested_by_user_id=order.user_id,
                idempotency_key=f"uncollected_{order.id}",
            )
            logger.info(
                "uncollected_online_refund_requested",
                order_id=order.id,
                payment_id=payment.id,
            )

    # ===================================================================
    # Phase 6: Partial item cancellation
    # ===================================================================

    async def partial_item_cancel(
        self,
        *,
        order_id: str,
        item_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> Order:
        """Cancel individual items from an order.

        Only allowed for PENDING orders. If all items cancelled, order is cancelled.
        If inventory was reserved, releases inventory for the cancelled items.
        """
        order = await self.get_order(order_id)

        if order.status not in (OrderStatus.PENDING,):
            raise ValidationError(f"Cannot cancel items from order in {order.status.value} status")

        # Find the item
        target_item = None
        for item in order.items:
            if item.id == item_id:
                target_item = item
                break

        if target_item is None:
            raise NotFoundException("Order item", item_id)

        # Release inventory for this item
        if order.inventory_reserved:
            await self._release_inventory_item(order, target_item, actor_id)

        # Remove item. Capture the display name first: after delete()+flush()
        # the ORM object may expire and attribute access can raise
        # ObjectDeletedError depending on session configuration.
        cancelled_item_name = target_item.item_name
        await self.db.delete(target_item)
        await self.db.flush()

        # Refresh the order items relationship so callers see current state
        await self.db.refresh(order, ["items"])

        # Recalculate total
        result = await self.db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        remaining_items = list(result.scalars().all())

        if not remaining_items:
            # All items cancelled — cancel the entire order
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now(UTC)
            order.cancelled_by = actor_id
            order.cancellation_reason = reason or "All items cancelled"
            event_type = OrderEventType.CANCELLED
        else:
            # Update total amount
            order.total_amount = sum(i.subtotal for i in remaining_items)
            event_type = OrderEventType.PARTIAL_CANCELLED

        event = OrderEvent(
            order_id=order.id,
            event_type=event_type,
            actor_id=actor_id,
            notes=f"Cancelled item: {cancelled_item_name}. {reason or ''}",
        )
        self.db.add(event)
        await self._emit_notification(order, event)
        await self.db.flush()
        logger.info(
            "partial_item_cancel",
            order_id=order.id,
            item_id=item_id,
        )
        return order

    async def _release_inventory_item(
        self,
        order: Order,
        item: OrderItem,
        actor_id: str,
    ) -> None:
        """Release inventory for a single cancelled item."""
        from app.modules.inventory.models import InventoryItem

        if item.menu_item_id is None:
            return

        inv_result = await self.db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.menu_item_id == item.menu_item_id,
                InventoryItem.cafeteria_id == order.cafeteria_id,
            )
            # Row-level lock, matching the reservation paths: concurrent
            # cancel + checkout must not drift inventory counts.
            .with_for_update()
        )
        inv = inv_result.scalar_one_or_none()
        if inv is not None:
            inv.quantity += item.quantity

    # ===================================================================
    # Phase 6: Cafeteria sudden closure
    # ===================================================================

    async def cafeteria_sudden_close(
        self,
        *,
        cafeteria_id: str,
        actor_id: str,
        notes: str | None = None,
    ) -> list[Order]:
        """Cancel all PENDING and PREPARING orders when cafeteria closes suddenly.

        Releases inventory for each order. Returns list of cancelled orders.
        """
        from app.modules.cafeterias.models import Cafeteria, OperationalStatus

        # Update cafeteria status
        caf_result = await self.db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria_id))
        cafeteria = caf_result.scalar_one_or_none()
        if cafeteria is None:
            raise NotFoundException("Cafeteria", cafeteria_id)

        cafeteria.operational_status = OperationalStatus.CLOSED

        # Find affected orders
        result = await self.db.execute(
            select(Order).where(
                Order.cafeteria_id == cafeteria_id,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PREPARING]),
            )
        )
        affected_orders = list(result.scalars().all())

        cancelled_orders = []
        for order in affected_orders:
            # Release inventory
            if order.inventory_reserved:
                await self._release_inventory(order, actor_id)

            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now(UTC)
            order.cancelled_by = actor_id
            order.cancellation_reason = notes or "Cafeteria closed suddenly"

            event = OrderEvent(
                order_id=order.id,
                event_type=OrderEventType.CAFETERIA_CLOSED,
                actor_id=actor_id,
                notes=notes,
            )
            self.db.add(event)
            await self._emit_notification(order, event)
            cancelled_orders.append(order)

        await self.db.flush()
        logger.info(
            "cafeteria_sudden_close",
            cafeteria_id=cafeteria_id,
            orders_cancelled=len(cancelled_orders),
        )
        return cancelled_orders

    # ===================================================================
    # Order number allocation
    # ===================================================================

    async def _allocate_order_number(self) -> int:
        """Allocate the next sequential order number atomically.

        Uses SELECT FOR UPDATE on the sequence row to prevent races.
        """
        from sqlalchemy import text

        # Ensure sequence row exists
        seq_result = await self.db.execute(select(OrderNumberSequence).limit(1))
        seq = seq_result.scalar_one_or_none()
        if seq is None:
            seq = OrderNumberSequence(last_number=0)
            self.db.add(seq)
            await self.db.flush()

        # Atomic increment using raw SQL for row-level locking
        await self.db.execute(
            text("UPDATE order_number_sequence SET last_number = last_number + 1 WHERE id = :id"),
            {"id": seq.id},
        )
        await self.db.refresh(seq)
        return seq.last_number

    # ===================================================================
    # Inventory reservation
    # ===================================================================

    async def _reserve_inventory(self, order: Order, cart_items: list[Any], actor_id: str) -> None:
        """Reserve inventory for immediate cash orders using row-level locking."""
        from app.modules.inventory.models import InventoryItem

        for ci in cart_items:
            # SELECT FOR UPDATE — row-level lock
            result = await self.db.execute(
                select(InventoryItem)
                .where(
                    InventoryItem.menu_item_id == ci.menu_item_id,
                    InventoryItem.cafeteria_id == order.cafeteria_id,
                )
                .with_for_update()
            )
            inv = result.scalar_one_or_none()
            if inv is None:
                # Clean user-facing error — never leak raw UUIDs (Phase 42 P1).
                raise ValidationError("This item is currently unavailable")

            if inv.quantity < ci.quantity:
                raise ValidationError(
                    f"Insufficient inventory: available={inv.quantity}, requested={ci.quantity}"
                )

            inv.quantity -= ci.quantity

        order.inventory_reserved = True
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.INVENTORY_RESERVED,
            actor_id=actor_id,
        )
        self.db.add(event)
        logger.info("inventory_reserved", order_id=order.id)

    async def _reserve_inventory_for_order(self, order: Order, actor_id: str) -> None:
        """Reserve inventory for a scheduled order when preparation starts."""
        result = await self.db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        order_items = result.scalars().all()

        from app.modules.inventory.models import InventoryItem

        for oi in order_items:
            inv_result = await self.db.execute(
                select(InventoryItem)
                .where(
                    InventoryItem.menu_item_id == oi.menu_item_id,
                    InventoryItem.cafeteria_id == order.cafeteria_id,
                )
                .with_for_update()
            )
            inv = inv_result.scalar_one_or_none()
            if inv is None:
                # Clean user-facing error — never leak raw UUIDs (Phase 42 P1).
                raise ValidationError("This item is currently unavailable")
            if inv.quantity < oi.quantity:
                raise ValidationError(
                    f"Insufficient inventory: available={inv.quantity}, requested={oi.quantity}"
                )
            inv.quantity -= oi.quantity

        order.inventory_reserved = True
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.INVENTORY_RESERVED,
            actor_id=actor_id,
            notes="Reserved at preparation start (scheduled order)",
        )
        self.db.add(event)
        logger.info("scheduled_inventory_reserved", order_id=order.id)

    async def _reserve_inventory_for_online_payment(self, order: Order) -> None:
        """Reserve inventory after successful online payment.

        B20: now delegates to InventoryService.reserve_for_order (the
        inventory concern lives in the inventory module). Kept as a thin
        wrapper so existing callers/tests keep working.
        """
        from app.modules.inventory.service import InventoryService

        await InventoryService(self.db).reserve_for_order(order)

    async def _release_inventory(self, order: Order, actor_id: str) -> None:
        """Release reserved inventory when an order is cancelled."""
        from app.modules.inventory.models import InventoryItem

        result = await self.db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        order_items = result.scalars().all()

        for oi in order_items:
            inv_result = await self.db.execute(
                select(InventoryItem)
                .where(
                    InventoryItem.menu_item_id == oi.menu_item_id,
                    InventoryItem.cafeteria_id == order.cafeteria_id,
                )
                # Row-level lock, matching the reservation paths.
                .with_for_update()
            )
            inv = inv_result.scalar_one_or_none()
            if inv is not None:
                inv.quantity += oi.quantity

        order.inventory_reserved = False
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.INVENTORY_RELEASED,
            actor_id=actor_id,
        )
        self.db.add(event)
        logger.info("inventory_released", order_id=order.id)

    # ===================================================================
    # Validation helpers
    # ===================================================================

    async def _get_active_cart_with_items(self, user_id: str, cafeteria_id: str) -> Cart:
        """Get the user's active cart with items loaded."""
        result = await self.db.execute(
            select(Cart)
            .where(
                Cart.user_id == user_id,
                Cart.cafeteria_id == cafeteria_id,
                Cart.status == CartStatus.ACTIVE,
            )
            .options(selectinload(Cart.items))
        )
        cart = result.scalar_one_or_none()
        if cart is None:
            raise ValidationError("No active cart found for this cafeteria")
        return cart

    async def _validate_published_menu(self, cafeteria_id: str) -> None:
        """Validate that today's menu is published for the cafeteria."""
        from app.modules.menus.models import DailyMenu

        result = await self.db.execute(
            select(DailyMenu).where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == date.today(),
                DailyMenu.status == DailyMenuStatus.PUBLISHED,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValidationError("No published menu available for today")

    def _validate_scheduled_order(self, scheduled_collection_time: str | None) -> None:
        """Validate scheduled order constraints."""
        if not scheduled_collection_time:
            raise ValidationError("Scheduled order requires a collection time")

        # Must be today (same-day only)
        # Time must be in HH:MM format and within operating hours
        # (Full operating hours validation requires the cafeteria's config)
        # For now, basic format validation
        parts = scheduled_collection_time.split(":")
        if len(parts) != 2:
            raise ValidationError("Invalid time format. Use HH:MM")

        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise ValidationError("Invalid time format. Use HH:MM") from exc

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValidationError("Invalid time values")

    def _validate_scheduled_order_time(
        self,
        scheduled_collection_time: str | None,
        cafeteria,
    ) -> None:
        """Validate scheduled order time against current time and operating hours.

        Called after cafeteria is loaded so we can access closing_time.
        """
        if not scheduled_collection_time:
            return  # Already validated by _validate_scheduled_order

        from datetime import time as dt_time

        parts = scheduled_collection_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1])

        # 1. Future-time enforcement: collection time must be after current local time
        now = datetime.now(UTC)
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(cafeteria.timezone)
        except (ValueError, KeyError):
            tz = UTC
        collection_time = dt_time(hour, minute)
        local_today = datetime.now(tz).date()
        collection_dt = datetime.combine(local_today, collection_time, tzinfo=tz)
        utc_collection = collection_dt.astimezone(UTC)

        if utc_collection <= now:
            raise ValidationError(
                f"Scheduled collection time {scheduled_collection_time} is in the past. "
                f"Orders must be scheduled for a future time today."
            )

        # 2. Operating-hours enforcement: collection time must be before closing
        if cafeteria.closing_time:
            try:
                close_hour, close_minute = map(int, cafeteria.closing_time.split(":"))
                close_time = dt_time(close_hour, close_minute)
                close_dt = datetime.combine(local_today, close_time, tzinfo=tz)
                utc_close = close_dt.astimezone(UTC)

                if utc_collection >= utc_close:
                    raise ValidationError(
                        f"Scheduled collection time {scheduled_collection_time} "
                        f"is after cafeteria closing time ({cafeteria.closing_time}). "
                        f"Orders must be scheduled before closing."
                    )
            except (ValueError, IndexError):
                pass  # Invalid closing_time format — skip operating-hours check

    async def _scheduled_collection_utc(self, order: Order) -> datetime | None:
        """Resolve a scheduled order's collection slot as a UTC datetime.

        scheduled_collection_time is cafeteria-local (same convention as
        checkout validation in _validate_scheduled_order_time), combined
        with the order date using the cafeteria's timezone. Returns None
        when the order has no scheduled time or it is malformed.
        """
        if not order.scheduled_collection_time:
            return None

        parts = order.scheduled_collection_time.split(":")
        if len(parts) != 2:
            return None
        try:
            collection_hour = int(parts[0])
            collection_minute = int(parts[1])
        except ValueError:
            return None

        from datetime import time as dt_time
        from zoneinfo import ZoneInfo

        from app.modules.cafeterias.models import Cafeteria

        try:
            caf_result = await self.db.execute(
                select(Cafeteria).where(Cafeteria.id == order.cafeteria_id)
            )
            cafeteria = caf_result.scalar_one_or_none()
            tz = ZoneInfo(cafeteria.timezone) if cafeteria else UTC
        except (ValueError, KeyError):
            tz = UTC

        collection_dt = datetime.combine(
            order.order_date,
            dt_time(collection_hour, collection_minute),
            tzinfo=tz,
        )
        return collection_dt.astimezone(UTC)

    async def _check_scheduled_cancellation_deadline(self, order: Order) -> None:
        """Check if a scheduled order can still be cancelled by the user.

        User can cancel until 30 minutes before scheduled collection time.
        """
        collection_utc = await self._scheduled_collection_utc(order)
        if collection_utc is None:
            return

        deadline = (
            collection_utc - timedelta(minutes=CANCELLATION_DEADLINE_MINUTES)
        )
        now = datetime.now(UTC)

        if now > deadline:
            raise ValidationError(
                f"Cancellation deadline has passed. "
                f"Orders can be cancelled up to {CANCELLATION_DEADLINE_MINUTES} "
                f"minutes before the scheduled collection time."
            )

    # ===================================================================
    # Automatic pickup expiry processing (Phase 6 background worker)
    # ===================================================================

    async def process_expired_pickups(self) -> dict[str, int]:
        """Process orders whose pickup deadline has expired.

        Phase 1 — READY orders where pickup_deadline <= now and
        uncollected_at is NULL are marked uncollected (no-show).

        Phase 2 (P3-14) — SCHEDULED orders still PENDING more than
        SCHEDULED_EXPIRY_GRACE_MINUTES after their collection slot are
        cancelled automatically. Before this phase existed, a scheduled
        order that staff never confirmed stayed PENDING indefinitely
        (hours past its slot). Completed/collected/cancelled orders and
        orders still inside the grace window are never touched.

        Uses SELECT FOR UPDATE SKIP LOCKED to handle concurrent workers
        safely on PostgreSQL. On other dialects (SQLite), locking is skipped.

        Returns processing statistics: {examined, processed, skipped,
        failed, scheduled_examined, scheduled_expired}.
        """
        stats = {
            "examined": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "scheduled_examined": 0,
            "scheduled_expired": 0,
            "auto_accepted": 0,
        }
        now = datetime.now(UTC)

        # Find eligible orders: READY, deadline passed, not yet uncollected
        eligible_stmt = select(Order).where(
            Order.status == OrderStatus.READY,
            Order.pickup_deadline <= now,
            Order.uncollected_at.is_(None),
            Order.collected_at.is_(None),
        )

        # Apply row-level locking only on dialects that support it (PostgreSQL).
        # SQLite does not support FOR UPDATE — skip locking for tests/dev.
        dialect_name = self.db.bind.dialect.name if self.db.bind else ""
        if dialect_name == "postgresql":
            eligible_stmt = eligible_stmt.with_for_update(skip_locked=True)

        result = await self.db.execute(eligible_stmt)
        orders = list(result.scalars().all())
        stats["examined"] = len(orders)

        for order in orders:
            try:
                # Re-check status after acquiring lock
                if (
                    order.status != OrderStatus.READY
                    or order.uncollected_at is not None
                    or order.collected_at is not None
                ):
                    stats["skipped"] += 1
                    continue

                await self.mark_uncollected(
                    order_id=order.id,
                    actor_id=None,
                    notes="Automatic expiry: pickup deadline reached",
                )
                stats["processed"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception(
                    "failed_to_process_expired_order",
                    order_id=order.id,
                )
                # Continue processing other orders
                continue

        # ------------------------------------------------------------------
        # Phase 2 (P3-14): scheduled PENDING orders past their collection slot
        # ------------------------------------------------------------------
        # Scheduled orders are same-day-only, so a bounded date window is
        # enough to find every candidate; the exact slot deadline is then
        # resolved in Python (cafeteria-local time → UTC).
        scheduled_cutoff_date = (now + timedelta(days=1)).date()
        scheduled_stmt = select(Order).where(
            Order.status == OrderStatus.PENDING,
            Order.order_type == OrderType.SCHEDULED,
            Order.scheduled_collection_time.is_not(None),
            Order.order_date <= scheduled_cutoff_date,
        )
        if dialect_name == "postgresql":
            scheduled_stmt = scheduled_stmt.with_for_update(skip_locked=True)

        scheduled_result = await self.db.execute(scheduled_stmt)
        scheduled_orders = list(scheduled_result.scalars().all())
        stats["scheduled_examined"] = len(scheduled_orders)

        for order in scheduled_orders:
            try:
                # Re-check status — a concurrent staff action may have
                # advanced the order since the query snapshot.
                if order.status != OrderStatus.PENDING:
                    stats["skipped"] += 1
                    continue

                collection_utc = await self._scheduled_collection_utc(order)
                if collection_utc is None:
                    stats["skipped"] += 1
                    continue

                # Still inside the collection window (slot + grace) — leave
                # it for staff to confirm and prepare.
                if now <= collection_utc + timedelta(
                    minutes=SCHEDULED_EXPIRY_GRACE_MINUTES
                ):
                    continue

                if order.inventory_reserved:
                    await self._release_inventory(order, actor_id=None)

                reason = (
                    "Automatic expiry: scheduled collection time passed "
                    "without confirmation"
                )
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = now
                order.cancelled_by = None
                order.cancellation_reason = reason

                event = OrderEvent(
                    order_id=order.id,
                    event_type=OrderEventType.CANCELLED,
                    actor_id=None,
                    notes=reason,
                )
                self.db.add(event)
                await self._emit_notification(order, event)
                stats["scheduled_expired"] += 1
                logger.info(
                    "scheduled_order_auto_expired",
                    order_id=order.id,
                    order_number=order.order_number,
                    scheduled_collection_time=order.scheduled_collection_time,
                )
            except Exception:
                stats["failed"] += 1
                logger.exception(
                    "failed_to_expire_scheduled_order",
                    order_id=order.id,
                )
                continue

        # ------------------------------------------------------------------
        # Phase 3: auto-acceptance backstop (ORDER_AUTO_ACCEPT)
        # ------------------------------------------------------------------
        # Immediate orders still PENDING (online orders whose payment just
        # succeeded, or any order missed at checkout) are confirmed and
        # moved to PREPARING so they never sit invisible in the queue.
        if settings.ORDER_AUTO_ACCEPT:
            auto_stmt = select(Order).where(
                Order.status == OrderStatus.PENDING,
                Order.order_type == OrderType.IMMEDIATE,
            )
            if dialect_name == "postgresql":
                auto_stmt = auto_stmt.with_for_update(skip_locked=True)
            auto_result = await self.db.execute(auto_stmt)
            auto_orders = list(auto_result.scalars().all())

            for order in auto_orders:
                try:
                    if order.status != OrderStatus.PENDING:
                        stats["skipped"] += 1
                        continue
                    accepted = await self.auto_accept_order(
                        order_id=order.id,
                        notes="Auto-accepted",
                    )
                    if accepted.status == OrderStatus.PREPARING:
                        stats["auto_accepted"] += 1
                        logger.info(
                            "order_auto_accepted",
                            order_id=order.id,
                            order_number=order.order_number,
                        )
                except Exception:
                    stats["failed"] += 1
                    logger.exception(
                        "failed_to_auto_accept_order",
                        order_id=order.id,
                    )
                    continue

        # Flush all changes — caller is responsible for commit.
        # (Consistent with the rest of the service pattern; the background
        #  worker in main.py calls session.commit() after this returns.)
        await self.db.flush()
        logger.info(
            "expired_pickups_processed",
            examined=stats["examined"],
            processed=stats["processed"],
            skipped=stats["skipped"],
            failed=stats["failed"],
            scheduled_examined=stats["scheduled_examined"],
            scheduled_expired=stats["scheduled_expired"],
        )
        return stats
