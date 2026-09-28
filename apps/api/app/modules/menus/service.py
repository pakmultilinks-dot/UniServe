"""Menus service — business logic for menu items, daily menus, and favorites."""

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    ValidationError,
)
from app.modules.menus.models import (
    DailyMenu,
    DailyMenuItem,
    DailyMenuStatus,
    MenuCategory,
    MenuFavorite,
    MenuItem,
)

logger = structlog.get_logger(__name__)


class MenuService:
    """Service for menu items, daily menus, and favorites."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- Menu Items ----

    async def create_menu_item(
        self,
        *,
        cafeteria_id: str,
        name: str,
        description: str | None = None,
        category: MenuCategory,
        price: int,
        currency: str = "PKR",
        image_url: str | None = None,
        dietary_info: str | None = None,
        allergens: str | None = None,
        preparation_time_minutes: int = 15,
    ) -> MenuItem:
        """Create a menu item within a cafeteria."""
        item = MenuItem(
            cafeteria_id=cafeteria_id,
            name=name,
            description=description,
            category=category,
            price=price,
            currency=currency,
            image_url=image_url,
            dietary_info=dietary_info,
            allergens=allergens,
            preparation_time_minutes=preparation_time_minutes,
            is_available=True,
            is_active=True,
        )
        self.db.add(item)
        await self.db.flush()
        logger.info("menu_item_created", item_id=item.id, cafeteria_id=cafeteria_id, name=name)
        return item

    async def list_menu_items(
        self,
        *,
        cafeteria_id: str,
        category: MenuCategory | None = None,
        is_available: bool | None = None,
        search: str | None = None,
    ) -> list[MenuItem]:
        """List menu items for a cafeteria with optional filters."""
        query = select(MenuItem).where(
            MenuItem.cafeteria_id == cafeteria_id,
            MenuItem.is_active == True,  # noqa: E712
        )
        if category is not None:
            query = query.where(MenuItem.category == category)
        if is_available is not None:
            query = query.where(MenuItem.is_available == is_available)
        if search:
            query = query.where(MenuItem.name.ilike(f"%{search}%"))
        query = query.order_by(MenuItem.category, MenuItem.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_menu_item(self, menu_item_id: str) -> MenuItem:
        """Get a single menu item by ID."""
        result = await self.db.execute(select(MenuItem).where(MenuItem.id == menu_item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException("Menu Item", menu_item_id)
        return item

    async def update_menu_item(
        self,
        menu_item_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        category: MenuCategory | None = None,
        price: int | None = None,
        currency: str | None = None,
        image_url: str | None = None,
        dietary_info: str | None = None,
        allergens: str | None = None,
        preparation_time_minutes: int | None = None,
        is_available: bool | None = None,
        is_active: bool | None = None,
    ) -> MenuItem:
        """Update a menu item."""
        item = await self.get_menu_item(menu_item_id)

        if name is not None:
            item.name = name
        if description is not None:
            item.description = description
        if category is not None:
            item.category = category
        if price is not None:
            item.price = price
        if currency is not None:
            item.currency = currency
        if image_url is not None:
            item.image_url = image_url
        if dietary_info is not None:
            item.dietary_info = dietary_info
        if allergens is not None:
            item.allergens = allergens
        if preparation_time_minutes is not None:
            item.preparation_time_minutes = preparation_time_minutes
        if is_available is not None:
            item.is_available = is_available
        if is_active is not None:
            item.is_active = is_active

        await self.db.flush()
        logger.info("menu_item_updated", item_id=menu_item_id)
        return item

    async def delete_menu_item(self, menu_item_id: str) -> None:
        """Soft-delete a menu item (set is_active=False)."""
        item = await self.get_menu_item(menu_item_id)
        item.is_active = False
        item.is_available = False
        await self.db.flush()
        logger.info("menu_item_deleted", item_id=menu_item_id)

    # ---- Daily Menus ----

    async def create_daily_menu(
        self,
        *,
        cafeteria_id: str,
        menu_date: date,
        created_by: str | None = None,
    ) -> DailyMenu:
        """Create a new daily menu draft."""
        # Check if one already exists for this cafeteria and date
        existing = await self.db.execute(
            select(DailyMenu).where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == menu_date,
            )
        )
        if existing.scalar_one_or_none():
            raise AlreadyExistsException("Daily Menu", f"cafeteria={cafeteria_id} date={menu_date}")

        daily_menu = DailyMenu(
            cafeteria_id=cafeteria_id,
            menu_date=menu_date,
            status=DailyMenuStatus.DRAFT,
            created_by=created_by,
        )
        self.db.add(daily_menu)
        await self.db.flush()
        logger.info("daily_menu_created", menu_id=daily_menu.id, date=str(menu_date))

        # Re-fetch with eager-loaded items to avoid MissingGreenlet in Pydantic
        return await self.get_daily_menu(daily_menu.id)

    async def get_daily_menu(self, daily_menu_id: str) -> DailyMenu:
        """Get a daily menu by ID with items eagerly loaded."""
        result = await self.db.execute(
            select(DailyMenu)
            .where(DailyMenu.id == daily_menu_id)
            .options(selectinload(DailyMenu.items).selectinload(DailyMenuItem.menu_item))
        )
        menu = result.scalar_one_or_none()
        if menu is None:
            raise NotFoundException("Daily Menu", daily_menu_id)
        return menu

    async def list_daily_menus(
        self,
        *,
        cafeteria_id: str,
        status: DailyMenuStatus | None = None,
    ) -> list[DailyMenu]:
        """List daily menus for a cafeteria with items eagerly loaded."""
        query = (
            select(DailyMenu)
            .where(DailyMenu.cafeteria_id == cafeteria_id)
            .options(selectinload(DailyMenu.items).selectinload(DailyMenuItem.menu_item))
        )
        if status is not None:
            query = query.where(DailyMenu.status == status)
        query = query.order_by(DailyMenu.menu_date.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_published_menu_for_date(
        self,
        *,
        cafeteria_id: str,
        menu_date: date,
    ) -> DailyMenu | None:
        """Get the published daily menu for a specific cafeteria and date."""
        result = await self.db.execute(
            select(DailyMenu)
            .where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == menu_date,
                DailyMenu.status == DailyMenuStatus.PUBLISHED,
            )
            .options(selectinload(DailyMenu.items).selectinload(DailyMenuItem.menu_item))
        )
        return result.scalar_one_or_none()

    async def add_item_to_daily_menu(
        self,
        daily_menu_id: str,
        *,
        menu_item_id: str,
        special_price: int | None = None,
        is_available_today: bool = True,
        display_order: int = 0,
        notes: str | None = None,
    ) -> DailyMenuItem:
        """Add a menu item to a daily menu (must be DRAFT)."""
        daily_menu = await self.get_daily_menu(daily_menu_id)
        if daily_menu.status != DailyMenuStatus.DRAFT:
            raise ValidationError("Cannot modify a published or archived menu")

        # Verify menu item exists
        await self.get_menu_item(menu_item_id)

        # Check if already added
        existing = await self.db.execute(
            select(DailyMenuItem).where(
                DailyMenuItem.daily_menu_id == daily_menu_id,
                DailyMenuItem.menu_item_id == menu_item_id,
            )
        )
        if existing.scalar_one_or_none():
            raise AlreadyExistsException("Daily Menu Item", menu_item_id)

        dmi = DailyMenuItem(
            daily_menu_id=daily_menu_id,
            menu_item_id=menu_item_id,
            special_price=special_price,
            is_available_today=is_available_today,
            display_order=display_order,
            notes=notes,
        )
        self.db.add(dmi)
        await self.db.flush()
        # Expire the items relationship so re-fetch picks up the new item
        self.db.expire(daily_menu, ["items"])
        logger.info(
            "item_added_to_daily_menu",
            daily_menu_id=daily_menu_id,
            menu_item_id=menu_item_id,
        )
        return dmi

    async def remove_item_from_daily_menu(
        self,
        daily_menu_id: str,
        menu_item_id: str,
    ) -> None:
        """Remove a menu item from a daily menu (must be DRAFT)."""
        daily_menu = await self.get_daily_menu(daily_menu_id)
        if daily_menu.status != DailyMenuStatus.DRAFT:
            raise ValidationError("Cannot modify a published or archived menu")

        result = await self.db.execute(
            select(DailyMenuItem).where(
                DailyMenuItem.daily_menu_id == daily_menu_id,
                DailyMenuItem.menu_item_id == menu_item_id,
            )
        )
        dmi = result.scalar_one_or_none()
        if dmi is None:
            raise NotFoundException("Daily Menu Item", menu_item_id)

        await self.db.delete(dmi)
        await self.db.flush()
        # Expire the relationship so the next load reflects the deletion
        self.db.expire(daily_menu, ["items"])
        logger.info(
            "item_removed_from_daily_menu",
            daily_menu_id=daily_menu_id,
            menu_item_id=menu_item_id,
        )

    async def publish_daily_menu(self, daily_menu_id: str) -> DailyMenu:
        """Publish a daily menu (manager/admin)."""
        daily_menu = await self.get_daily_menu(daily_menu_id)
        if daily_menu.status != DailyMenuStatus.DRAFT:
            raise ValidationError("Only draft menus can be published")

        # Must have at least one item
        items_result = await self.db.execute(
            select(DailyMenuItem).where(DailyMenuItem.daily_menu_id == daily_menu_id)
        )
        items = items_result.scalars().all()
        if not items:
            raise ValidationError("Cannot publish an empty menu")

        daily_menu.status = DailyMenuStatus.PUBLISHED
        daily_menu.published_at = datetime.now(UTC)
        await self.db.flush()
        logger.info("daily_menu_published", menu_id=daily_menu_id)

        # Re-fetch with eager-loaded items to avoid MissingGreenlet in Pydantic
        return await self.get_daily_menu(daily_menu_id)

    # ---- Favorites ----

    async def add_favorite(self, user_id: str, menu_item_id: str) -> MenuFavorite:
        """Add a menu item to user's favorites."""
        # Verify menu item exists
        await self.get_menu_item(menu_item_id)

        # Check for existing favorite
        existing = await self.db.execute(
            select(MenuFavorite).where(
                MenuFavorite.user_id == user_id,
                MenuFavorite.menu_item_id == menu_item_id,
            )
        )
        if existing.scalar_one_or_none():
            raise AlreadyExistsException("Favorite", menu_item_id)

        fav = MenuFavorite(user_id=user_id, menu_item_id=menu_item_id)
        self.db.add(fav)
        await self.db.flush()
        logger.info("favorite_added", user_id=user_id, menu_item_id=menu_item_id)

        # Refresh with eager-loaded menu_item for response
        await self.db.refresh(fav, ["menu_item"])
        return fav

    async def remove_favorite(self, user_id: str, menu_item_id: str) -> None:
        """Remove a menu item from user's favorites."""
        result = await self.db.execute(
            select(MenuFavorite).where(
                MenuFavorite.user_id == user_id,
                MenuFavorite.menu_item_id == menu_item_id,
            )
        )
        fav = result.scalar_one_or_none()
        if fav is None:
            raise NotFoundException("Favorite", menu_item_id)
        await self.db.delete(fav)
        await self.db.flush()
        logger.info("favorite_removed", user_id=user_id, menu_item_id=menu_item_id)

    async def list_favorites(self, user_id: str) -> list[MenuFavorite]:
        """List a user's favorite menu items with menu_item eagerly loaded."""
        result = await self.db.execute(
            select(MenuFavorite)
            .where(MenuFavorite.user_id == user_id)
            .options(selectinload(MenuFavorite.menu_item))
            .order_by(MenuFavorite.created_at.desc())
        )
        return list(result.scalars().all())

    async def check_favorite(self, user_id: str, menu_item_id: str) -> bool:
        """Check if a menu item is in user's favorites."""
        result = await self.db.execute(
            select(MenuFavorite).where(
                MenuFavorite.user_id == user_id,
                MenuFavorite.menu_item_id == menu_item_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # ---- Search ----

    async def search_menu_items(
        self,
        *,
        cafeteria_id: str | None = None,
        category: MenuCategory | None = None,
        search: str | None = None,
        is_available: bool | None = True,
    ) -> list[MenuItem]:
        """Search menu items across cafeterias."""
        query = select(MenuItem).where(MenuItem.is_active == True)  # noqa: E712
        if cafeteria_id is not None:
            query = query.where(MenuItem.cafeteria_id == cafeteria_id)
        if category is not None:
            query = query.where(MenuItem.category == category)
        if search:
            query = query.where(
                MenuItem.name.ilike(f"%{search}%") | MenuItem.description.ilike(f"%{search}%")
            )
        if is_available is not None:
            query = query.where(MenuItem.is_available == is_available)
        query = query.order_by(MenuItem.cafeteria_id, MenuItem.category, MenuItem.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())
