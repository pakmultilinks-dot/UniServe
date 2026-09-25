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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    ValidationError,
)
from app.modules.carts.models import Cart, CartStatus
from app.modules.menus.models import DailyMenuStatus
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


class OrderService:
    """Service for order operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
    ) -> Order:
        """Convert a cart into an order.

        Server is authoritative: validates everything, calculates total
        server-side, creates order items from cart snapshots.
        """
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

        # 4. Validate published menu for today
        await self._validate_published_menu(cafeteria_id)

        # 5. Validate each cart item against current inventory and menu
        from app.modules.carts.service import CartService

        cart_service = CartService(self.db)
        total_amount = 0
        order_items_data = []

        for ci in cart.items:
            # Re-validate menu item
            mi = await cart_service._get_valid_menu_item(ci.menu_item_id, cafeteria_id)
            # Re-validate inventory
            await cart_service._validate_inventory(ci.menu_item_id, cafeteria_id, ci.quantity)

            subtotal = ci.price_snapshot * ci.quantity
            total_amount += subtotal
            order_items_data.append(
                {
                    "menu_item_id": ci.menu_item_id,
                    "item_name": mi.name,
                    "unit_price": ci.price_snapshot,
                    "quantity": ci.quantity,
                    "subtotal": subtotal,
                    "currency": ci.currency,
                }
            )

        # 6. Allocate order number (atomic)
        order_number = await self._allocate_order_number()

        # 7. Create order
        order = Order(
            order_number=order_number,
            user_id=user_id,
            cafeteria_id=cafeteria_id,
            order_type=parsed_order_type,
            payment_method=PaymentMethod(payment_method),
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            currency="PKR",
            order_date=date.today(),
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

        # 10. Handle inventory reservation
        if parsed_order_type == OrderType.IMMEDIATE:
            if PaymentMethod(payment_method) == PaymentMethod.CASH:
                # Cash: reserve inventory immediately, create cash payment record
                await self._reserve_inventory(order, cart.items, user_id)
                from app.modules.payments.providers.test_provider import (
                    TestPaymentProvider,
                )
                from app.modules.payments.service import PaymentService

                payment_svc = PaymentService(self.db, TestPaymentProvider())
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
    ) -> list[Order]:
        """List orders for a cafeteria (manager/staff view)."""
        query = (
            select(Order)
            .where(Order.cafeteria_id == cafeteria_id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        )
        if status is not None:
            query = query.where(Order.status == status)
        if order_date is not None:
            query = query.where(Order.order_date == order_date)
        result = await self.db.execute(query)
        return list(result.scalars().all())

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

            # Verify ownership
            if user_id and order.user_id != user_id:
                raise ValidationError("Order does not belong to this user")

            # Scheduled cancellation deadline check
            if order.order_type == OrderType.SCHEDULED and order.scheduled_collection_time:
                self._check_scheduled_cancellation_deadline(order)

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
        order = await self.get_order(order_id)

        valid_transitions = {
            OrderStatus.PENDING: OrderStatus.PREPARING,
            OrderStatus.PREPARING: OrderStatus.READY,
            OrderStatus.READY: OrderStatus.COMPLETED,
        }

        expected_next = valid_transitions.get(order.status)
        if expected_next is None or expected_next.value != new_status:
            raise ValidationError(f"Invalid status transition: {order.status.value} → {new_status}")

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

        # For scheduled orders: reserve inventory when preparation starts
        if (
            new_status == "preparing"
            and not order.inventory_reserved
            and order.order_type == OrderType.SCHEDULED
        ):
            await self._reserve_inventory_for_order(order, actor_id)

        await self.db.flush()
        logger.info(
            "order_status_updated",
            order_id=order.id,
            old_status=order.status.value,
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
        order = await self.get_order(order_id)

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
        order = await self.get_order(order_id)

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
        order = await self.get_order(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValidationError(
                f"Cannot start preparation for order in {order.status.value} status"
            )

        if order.confirmed_at is None:
            raise ValidationError("Order must be confirmed before starting preparation")

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

        order = await self.get_order(order_id)

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
                from datetime import date as dt_date

                local_closing = datetime.combine(dt_date.today(), dt_time(hour, minute), tzinfo=tz)
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
        """
        order = await self.get_order(order_id)

        if order.status != OrderStatus.READY:
            raise ValidationError(
                f"Cannot mark uncollected: order is in {order.status.value} status"
            )

        # Idempotency: skip if already processed
        if order.uncollected_at is not None:
            return order

        now = datetime.now(UTC)
        order.uncollected_at = now

        # Record no-show
        from app.modules.orders.noshow import record_no_show

        await record_no_show(
            db=self.db,
            user_id=order.user_id,
            order_id=order.id,
            cafeteria_id=order.cafeteria_id,
        )

        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.UNCOLLECTED,
            actor_id=actor_id,
            notes=notes,
        )
        self.db.add(event)
        await self.db.flush()
        logger.info(
            "order_uncollected",
            order_id=order.id,
            user_id=order.user_id,
        )
        return order

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

        # Remove item
        await self.db.delete(target_item)
        await self.db.flush()

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
            notes=f"Cancelled item: {target_item.item_name}. {reason or ''}",
        )
        self.db.add(event)
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
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.menu_item_id,
                InventoryItem.cafeteria_id == order.cafeteria_id,
            )
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
                raise ValidationError(f"No inventory record for item {ci.menu_item_id}")

            if inv.quantity < ci.quantity:
                raise ValidationError(
                    f"Insufficient inventory for {ci.menu_item_id}: "
                    f"available={inv.quantity}, requested={ci.quantity}"
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
                raise ValidationError(f"No inventory record for item {oi.menu_item_id}")
            if inv.quantity < oi.quantity:
                raise ValidationError(
                    f"Insufficient inventory for {oi.menu_item_id}: "
                    f"available={inv.quantity}, requested={oi.quantity}"
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

        Called by the payment service when an online payment succeeds.
        Reads from OrderItems (already created at checkout).
        """
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
                .with_for_update()
            )
            inv = inv_result.scalar_one_or_none()
            if inv is None:
                raise ValidationError(f"No inventory record for item {oi.menu_item_id}")
            if inv.quantity < oi.quantity:
                raise ValidationError(
                    f"Insufficient inventory for {oi.menu_item_id}: "
                    f"available={inv.quantity}, requested={oi.quantity}"
                )
            inv.quantity -= oi.quantity

        order.inventory_reserved = True
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType.INVENTORY_RESERVED,
            notes="Reserved after successful online payment",
        )
        self.db.add(event)
        logger.info("online_payment_inventory_reserved", order_id=order.id)

    async def _release_inventory(self, order: Order, actor_id: str) -> None:
        """Release reserved inventory when an order is cancelled."""
        from app.modules.inventory.models import InventoryItem

        result = await self.db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        order_items = result.scalars().all()

        for oi in order_items:
            inv_result = await self.db.execute(
                select(InventoryItem).where(
                    InventoryItem.menu_item_id == oi.menu_item_id,
                    InventoryItem.cafeteria_id == order.cafeteria_id,
                )
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
        local_today = date.today()
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

    def _check_scheduled_cancellation_deadline(self, order: Order) -> None:
        """Check if a scheduled order can still be cancelled by the user.

        User can cancel until 30 minutes before scheduled collection time.
        """
        if not order.scheduled_collection_time:
            return

        parts = order.scheduled_collection_time.split(":")
        collection_hour = int(parts[0])
        collection_minute = int(parts[1])

        collection_dt = datetime.combine(
            order.order_date,
            datetime.min.time().replace(hour=collection_hour, minute=collection_minute),
            tzinfo=UTC,
        )
        deadline = collection_dt - timedelta(minutes=CANCELLATION_DEADLINE_MINUTES)
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

        Finds READY orders where pickup_deadline <= now and uncollected_at is NULL.
        Uses SELECT FOR UPDATE SKIP LOCKED to handle concurrent workers safely
        on PostgreSQL. On other dialects (SQLite), locking is skipped.

        Returns processing statistics: {examined, processed, skipped, failed}.
        """
        stats = {"examined": 0, "processed": 0, "skipped": 0, "failed": 0}
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
        )
        return stats
