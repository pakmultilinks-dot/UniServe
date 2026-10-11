"""Inventory service — business logic for inventory tracking and adjustments."""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationError
from app.modules.inventory.models import InventoryAdjustment, InventoryItem, InventoryUnit

logger = structlog.get_logger(__name__)


async def backfill_missing_inventory_records(db: AsyncSession) -> dict[str, int]:
    """Create zero-stock inventory records for menu items missing one (P1).

    Menu items created before the Phase 41 auto-inventory fix (or seeded
    directly into the DB) have no ``inventory_items`` row, which made
    checkout fail with a raw-UUID error. Mirrors ``MenuService.create_menu_item``:
    quantity=0, unit=PORTIONS, low_threshold=10 — the item stays unavailable
    until staff explicitly restock it.

    Idempotent: only creates records where none exists; never touches
    existing rows. Returns counts for logging/reporting.
    """
    from app.modules.menus.models import MenuItem

    result = await db.execute(select(MenuItem))
    menu_items = list(result.scalars().all())

    created = 0
    for mi in menu_items:
        existing = await db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == mi.id,
                InventoryItem.cafeteria_id == mi.cafeteria_id,
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(
                InventoryItem(
                    cafeteria_id=mi.cafeteria_id,
                    menu_item_id=mi.id,
                    quantity=0,
                    unit=InventoryUnit.PORTIONS,
                    low_threshold=10,
                )
            )
            created += 1

    await db.flush()
    logger.info(
        "inventory_records_backfilled",
        menu_items_scanned=len(menu_items),
        records_created=created,
    )
    return {"menu_items_scanned": len(menu_items), "records_created": created}


class InventoryService:
    """Service for inventory management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_inventory_item(
        self,
        *,
        cafeteria_id: str,
        menu_item_id: str,
        quantity: int = 0,
        unit: InventoryUnit,
        low_threshold: int = 10,
    ) -> InventoryItem:
        """Create an inventory record for a menu item.

        Upsert semantics: exactly one record per (menu_item_id, cafeteria_id) ΓÇö
        menu-item creation now auto-creates a zero-stock record (P1 fix), so an
        explicit POST (seed scripts) updates stock instead of duplicating rows
        (duplicates would break checkout's scalar_one_or_none reservation).
        """
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == menu_item_id,
                InventoryItem.cafeteria_id == cafeteria_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.quantity = quantity
            existing.unit = unit
            existing.low_threshold = low_threshold
            await self.db.flush()
            logger.info(
                "inventory_item_updated",
                inventory_id=existing.id,
                cafeteria_id=cafeteria_id,
                menu_item_id=menu_item_id,
            )
            return existing

        item = InventoryItem(
            cafeteria_id=cafeteria_id,
            menu_item_id=menu_item_id,
            quantity=quantity,
            unit=unit,
            low_threshold=low_threshold,
        )
        self.db.add(item)
        await self.db.flush()
        logger.info(
            "inventory_item_created",
            inventory_id=item.id,
            cafeteria_id=cafeteria_id,
            menu_item_id=menu_item_id,
        )
        return item

    async def get_inventory_item(self, inventory_item_id: str) -> InventoryItem:
        """Get an inventory item by ID."""
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == inventory_item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Inventory Item", inventory_item_id)
        return item

    async def list_inventory_items(
        self,
        *,
        cafeteria_id: str,
        low_only: bool = False,
    ) -> list[InventoryItem]:
        """List inventory items for a cafeteria."""
        query = select(InventoryItem).where(InventoryItem.cafeteria_id == cafeteria_id)
        if low_only:
            query = query.where(InventoryItem.quantity <= InventoryItem.low_threshold)
        query = query.order_by(InventoryItem.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def adjust_inventory(
        self,
        *,
        inventory_item_id: str,
        adjustment_quantity: int,
        adjusted_by: str | None = None,
        reason: str | None = None,
    ) -> InventoryAdjustment:
        """Adjust inventory quantity and record the adjustment.

        Uses SELECT FOR UPDATE on PostgreSQL so concurrent adjustments cannot
        lose updates or drive the quantity negative (read-modify-write race).
        Row locking is a no-op on SQLite (tests/dev), matching the orders
        service convention.
        """
        # Lock the inventory row for the read-modify-write cycle.
        stmt = select(InventoryItem).where(InventoryItem.id == inventory_item_id)
        dialect_name = self.db.bind.dialect.name if self.db.bind else ""
        if dialect_name == "postgresql":
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Inventory Item", inventory_item_id)

        new_quantity = item.quantity + adjustment_quantity
        if new_quantity < 0:
            raise ValidationError(
                f"Insufficient inventory: current={item.quantity}, adjustment={adjustment_quantity}"
            )

        item.quantity = new_quantity
        if adjustment_quantity > 0:
            from datetime import UTC, datetime

            item.last_restocked_at = datetime.now(UTC)

        adjustment = InventoryAdjustment(
            inventory_item_id=inventory_item_id,
            adjustment_quantity=adjustment_quantity,
            adjusted_by=adjusted_by,
            reason=reason,
        )
        self.db.add(adjustment)
        await self.db.flush()
        logger.info(
            "inventory_adjusted",
            inventory_item_id=inventory_item_id,
            adjustment=adjustment_quantity,
            new_quantity=new_quantity,
        )
        return adjustment

    async def get_low_stock_items(self, cafeteria_id: str) -> list[InventoryItem]:
        """Get inventory items below their low-stock threshold."""
        return await self.list_inventory_items(cafeteria_id=cafeteria_id, low_only=True)

    async def reserve_for_order(self, order: Any) -> None:
        """Reserve inventory for an order's items (post online-payment).

        B20: extracted from OrderService._reserve_inventory_for_online_payment
        so payments/service.py no longer imports OrderService. The inventory
        reservation is an inventory concern; the order flag + event stay with
        the caller (orders module) via the returned item count.

        Uses row-level locks, matching the other reservation paths.
        Raises ValidationError when an item is unavailable or short.
        """
        from app.modules.orders.models import OrderEvent, OrderEventType, OrderItem

        result = await self.db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
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
                # Clean user-facing error — never leak raw UUIDs.
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
            notes="Reserved after successful online payment",
        )
        self.db.add(event)
        logger.info("online_payment_inventory_reserved", order_id=order.id)
