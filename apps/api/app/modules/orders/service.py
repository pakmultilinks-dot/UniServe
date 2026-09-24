"""Order service — business logic for order creation, lifecycle, and collection.

Handles:
- Checkout (cart → order conversion)
- Order numbering (sequential, globally unique)
- Inventory reservation (immediate: at checkout; scheduled: at preparation)
- Cancellation rules (user before deadline, manager anytime)
- Collection via order number or QR token
- Order events (audit trail)
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
                from app.modules.payments.service import PaymentService
                from app.modules.payments.providers.test_provider import (
                    TestPaymentProvider,
                )

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

        Validates:
        - Order exists and belongs to the cafeteria
        - Order is READY
        - Not already collected
        - QR token is valid (if applicable)
        """
        order = await self.get_order(order_id)

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
