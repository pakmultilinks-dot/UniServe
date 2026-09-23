"""Inventory service — business logic for inventory tracking and adjustments."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationError
from app.modules.inventory.models import InventoryAdjustment, InventoryItem, InventoryUnit

logger = structlog.get_logger(__name__)


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
        """Create an inventory record for a menu item."""
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
        """Adjust inventory quantity and record the adjustment."""
        item = await self.get_inventory_item(inventory_item_id)

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
