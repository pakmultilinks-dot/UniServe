"""Cart service — business logic for shopping cart management.

Handles:
- Cart creation and retrieval (one active cart per user per cafeteria)
- Cart item management (add, update quantity, remove)
- Cart expiry
- Price snapshot preservation
- Cafeteria/menu item/inventory validation
"""

from datetime import date
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    NotFoundException,
    ValidationError,
)
from app.modules.carts.models import Cart, CartItem, CartStatus
from app.modules.menus.models import DailyMenuStatus, MenuItem
from app.modules.menus.service import get_effective_unit_price

logger = structlog.get_logger(__name__)


class CartService:
    """Service for shopping cart operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_cart(
        self,
        *,
        user_id: str,
        cafeteria_id: str,
    ) -> Cart:
        """Get the user's active cart for a cafeteria, or create one.

        Enforces one active cart per user per cafeteria.
        """
        result = await self.db.execute(
            select(Cart).where(
                Cart.user_id == user_id,
                Cart.cafeteria_id == cafeteria_id,
                Cart.status == CartStatus.ACTIVE,
            )
        )
        cart = result.scalar_one_or_none()

        if cart is not None:
            return cart

        # Create new cart
        cart = Cart(
            user_id=user_id,
            cafeteria_id=cafeteria_id,
            status=CartStatus.ACTIVE,
        )
        self.db.add(cart)
        await self.db.flush()
        logger.info("cart_created", cart_id=cart.id, user_id=user_id, cafeteria_id=cafeteria_id)
        return cart

    async def get_cart(self, cart_id: str) -> Cart:
        """Get a cart by ID with items eagerly loaded."""
        result = await self.db.execute(
            select(Cart).where(Cart.id == cart_id).options(selectinload(Cart.items))
        )
        cart = result.scalar_one_or_none()
        if cart is None:
            raise NotFoundException("Cart", cart_id)
        return cart

    async def add_item(
        self,
        *,
        user_id: str,
        cafeteria_id: str,
        menu_item_id: str,
        quantity: int,
    ) -> CartItem:
        """Add an item to the user's cart.

        Validates:
        - Menu item belongs to the cafeteria
        - Menu item is active and available
        - Quantity is positive
        - Sufficient inventory exists
        - Published menu includes the item

        If the item already exists in the cart, increases its quantity.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        # Validate menu item
        menu_item = await self._get_valid_menu_item(menu_item_id, cafeteria_id)

        # Validate inventory
        await self._validate_inventory(menu_item_id, cafeteria_id, quantity)

        # Get or create cart
        cart = await self.get_or_create_cart(user_id=user_id, cafeteria_id=cafeteria_id)

        # Check if item already in cart
        existing_result = await self.db.execute(
            select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.menu_item_id == menu_item_id,
            )
        )
        existing_item = existing_result.scalar_one_or_none()

        if existing_item is not None:
            new_qty = existing_item.quantity + quantity
            await self._validate_inventory(menu_item_id, cafeteria_id, new_qty)
            existing_item.quantity = new_qty
            await self.db.flush()
            logger.info(
                "cart_item_quantity_increased",
                cart_id=cart.id,
                menu_item_id=menu_item_id,
                new_quantity=new_qty,
            )
            return existing_item

        cart_item = CartItem(
            cart_id=cart.id,
            menu_item_id=menu_item_id,
            quantity=quantity,
            price_snapshot=await get_effective_unit_price(
                self.db, menu_item=menu_item, cafeteria_id=cafeteria_id
            ),
            currency=menu_item.currency,
        )
        self.db.add(cart_item)
        await self.db.flush()
        logger.info(
            "cart_item_added",
            cart_id=cart.id,
            menu_item_id=menu_item_id,
            quantity=quantity,
            price=cart_item.price_snapshot,
        )
        return cart_item

    async def update_item_quantity(
        self,
        *,
        cart_id: str,
        cart_item_id: str,
        quantity: int,
        user_id: str,
    ) -> CartItem:
        """Update the quantity of a cart item.

        If quantity becomes zero, removes the item.
        """
        cart = await self.get_cart(cart_id)
        if cart.user_id != user_id:
            raise ValidationError("Cart does not belong to this user")
        if cart.status != CartStatus.ACTIVE:
            raise ValidationError("Cannot modify an expired cart")

        result = await self.db.execute(
            select(CartItem).where(
                CartItem.id == cart_item_id,
                CartItem.cart_id == cart_id,
            )
        )
        cart_item = result.scalar_one_or_none()
        if cart_item is None:
            raise NotFoundException("Cart Item", cart_item_id)

        if quantity <= 0:
            await self.db.delete(cart_item)
            await self.db.flush()
            logger.info("cart_item_removed", cart_id=cart_id, cart_item_id=cart_item_id)
            # Return a dummy — the item is deleted
            raise NotFoundException("Cart Item", cart_item_id)

        # Validate inventory for the new total
        await self._validate_inventory(cart_item.menu_item_id, cart.cafeteria_id, quantity)

        cart_item.quantity = quantity
        await self.db.flush()
        logger.info(
            "cart_item_quantity_updated",
            cart_id=cart_id,
            cart_item_id=cart_item_id,
            new_quantity=quantity,
        )
        return cart_item

    async def remove_item(
        self,
        *,
        cart_id: str,
        cart_item_id: str,
        user_id: str,
    ) -> None:
        """Remove an item from the cart."""
        cart = await self.get_cart(cart_id)
        if cart.user_id != user_id:
            raise ValidationError("Cart does not belong to this user")
        if cart.status != CartStatus.ACTIVE:
            raise ValidationError("Cannot modify an expired cart")

        result = await self.db.execute(
            select(CartItem).where(
                CartItem.id == cart_item_id,
                CartItem.cart_id == cart_id,
            )
        )
        cart_item = result.scalar_one_or_none()
        if cart_item is None:
            raise NotFoundException("Cart Item", cart_item_id)

        await self.db.delete(cart_item)
        await self.db.flush()
        logger.info("cart_item_removed", cart_id=cart_id, cart_item_id=cart_item_id)

    async def get_cart_items_with_details(self, cart_id: str) -> list[dict[str, Any]]:
        """Get cart items with menu item details for response."""
        result = await self.db.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart_id)
            .options(selectinload(CartItem.menu_item))
        )
        items = result.scalars().all()
        details = []
        for item in items:
            mi = item.menu_item
            details.append(
                {
                    "id": item.id,
                    "menu_item_id": item.menu_item_id,
                    "quantity": item.quantity,
                    "price_snapshot": item.price_snapshot,
                    "currency": item.currency,
                    "subtotal": item.price_snapshot * item.quantity,
                    "item_name": mi.name if mi else None,
                    "item_available": (mi.is_available and mi.is_active) if mi else None,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
            )
        return details

    async def expire_cart(self, cart_id: str) -> None:
        """Mark a cart as expired."""
        cart = await self.get_cart(cart_id)
        if cart.status == CartStatus.ACTIVE:
            cart.status = CartStatus.EXPIRED
            await self.db.flush()
            logger.info("cart_expired", cart_id=cart_id)

    async def expire_carts_for_cafeteria(self, cafeteria_id: str) -> int:
        """Expire all active carts for a cafeteria.

        Called when the cafeteria closes for the day.
        Returns the number of carts expired.
        """
        result = await self.db.execute(
            select(Cart).where(
                Cart.cafeteria_id == cafeteria_id,
                Cart.status == CartStatus.ACTIVE,
            )
        )
        carts = result.scalars().all()
        count = 0
        for cart in carts:
            cart.status = CartStatus.EXPIRED
            count += 1
        if count > 0:
            await self.db.flush()
            logger.info("cafeteria_carts_expired", cafeteria_id=cafeteria_id, count=count)
        return count

    # ---- Private helpers ----

    async def _get_valid_menu_item(self, menu_item_id: str, cafeteria_id: str) -> MenuItem:
        """Validate that a menu item is available and belongs to the cafeteria."""
        result = await self.db.execute(select(MenuItem).where(MenuItem.id == menu_item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Menu Item", menu_item_id)

        if item.cafeteria_id != cafeteria_id:
            raise ValidationError("Menu item does not belong to this cafeteria")

        if not item.is_active:
            raise ValidationError("Menu item is not active")

        if not item.is_available:
            raise ValidationError("Menu item is not available")

        # Check published menu for today
        from app.modules.menus.models import DailyMenu, DailyMenuItem

        today = date.today()
        pub_result = await self.db.execute(
            select(DailyMenu).where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == today,
                DailyMenu.status == DailyMenuStatus.PUBLISHED,
            )
        )
        daily_menu = pub_result.scalar_one_or_none()
        if daily_menu is not None:
            dmi_result = await self.db.execute(
                select(DailyMenuItem).where(
                    DailyMenuItem.daily_menu_id == daily_menu.id,
                    DailyMenuItem.menu_item_id == menu_item_id,
                    DailyMenuItem.is_available_today == True,  # noqa: E712
                )
            )
            if dmi_result.scalar_one_or_none() is None:
                raise ValidationError("Menu item is not on today's published menu")

        return item

    async def _validate_inventory(
        self, menu_item_id: str, cafeteria_id: str, required_quantity: int
    ) -> None:
        """Validate sufficient inventory exists for the requested quantity."""
        from app.modules.inventory.models import InventoryItem

        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == menu_item_id,
                InventoryItem.cafeteria_id == cafeteria_id,
            )
        )
        inv = result.scalar_one_or_none()
        if inv is None:
            # A menu item with no inventory record is not orderable. Fail at
            # add-to-cart with a clean user-facing error (no raw UUIDs — the
            # checkout path previously leaked them, Phase 42 P1). The item
            # stays unavailable until staff explicitly restocks it.
            raise ValidationError("This item is currently unavailable")
        if inv.quantity < required_quantity:
            raise ValidationError(
                f"Insufficient inventory: available={inv.quantity}, requested={required_quantity}"
            )
