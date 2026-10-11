"""Menus service — business logic for menu items, daily menus, and favorites."""

import os
import uuid
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
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import (
    DailyMenu,
    DailyMenuItem,
    DailyMenuStatus,
    MenuCategory,
    MenuFavorite,
    MenuItem,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Menu image storage (Phase 48)
# ---------------------------------------------------------------------------
# Persisted references are HOST-INDEPENDENT relative paths of the form
# "/api/v1/static/food/<file>". Web and mobile resolvers attach the
# configured API origin at render time, so the same database value works on
# the dev machine (localhost), a physical Android device on the LAN
# (192.168.x.x), and production hosts — without storing environment-specific
# URLs (localhost / 127.0.0.1 / api.localhost) in the database.
MENU_IMAGE_URL_PREFIX = "/api/v1/static/food/"

# app/modules/menus/service.py -> app/static/food
MENU_IMAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "food")
)

# Generous enough for normal cafeteria food photos (phone camera JPEGs are
# typically 1–4 MB), small enough to bound abuse.
MAX_MENU_IMAGE_BYTES = 5 * 1024 * 1024


def detect_menu_image_format(content: bytes) -> tuple[str, str] | None:
    """Return ``(mime_type, extension)`` from magic bytes, or None.

    The stored extension is derived from the DETECTED content — never from
    the client-supplied filename — which enforces content/extension
    consistency by construction.
    """
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if len(content) >= 12 and content[0:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def resolve_static_image_path(url: str | None) -> str | None:
    """Map a persisted static-food URL to an absolute path inside MENU_IMAGE_DIR.

    Returns None for non-local references (external URLs, empty values) and
    for anything that would escape the storage directory (path traversal):
    only a single path segment that stays inside MENU_IMAGE_DIR is accepted.
    """
    if not url or not url.startswith(MENU_IMAGE_URL_PREFIX):
        return None
    name = url[len(MENU_IMAGE_URL_PREFIX) :]
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    path = os.path.abspath(os.path.join(MENU_IMAGE_DIR, name))
    if os.path.dirname(path) != MENU_IMAGE_DIR:
        return None
    return path


async def get_effective_unit_price(
    db: AsyncSession,
    *,
    menu_item: MenuItem,
    cafeteria_id: str,
) -> int:
    """Resolve the server-authoritative unit price for an item today.

    The effective price is today's published daily-menu ``special_price``
    when one is set for this item (and it is available today), otherwise
    the menu item's base price. Cart/checkout previously ignored
    ``special_price`` and always charged the base price (Phase 42 P2-1:
    listed Rs 110 was charged Rs 120).

    Date convention matches ``CartService._get_valid_menu_item`` and
    ``OrderService._validate_published_menu`` (server-local ``date.today()``).
    """
    result = await db.execute(
        select(DailyMenuItem)
        .join(DailyMenu, DailyMenu.id == DailyMenuItem.daily_menu_id)
        .where(
            DailyMenu.cafeteria_id == cafeteria_id,
            DailyMenu.menu_date == date.today(),
            DailyMenu.status == DailyMenuStatus.PUBLISHED,
            DailyMenuItem.menu_item_id == menu_item.id,
            DailyMenuItem.is_available_today == True,  # noqa: E712
        )
    )
    daily_item = result.scalars().first()
    if daily_item is not None and daily_item.special_price is not None:
        return daily_item.special_price
    return menu_item.price


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

        # Every menu item needs an inventory record to be orderable ΓÇö the
        # checkout reservation path hard-fails when one is missing (P1).
        existing = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.menu_item_id == item.id,
                InventoryItem.cafeteria_id == cafeteria_id,
            )
        )
        if existing.scalar_one_or_none() is None:
            self.db.add(
                InventoryItem(
                    cafeteria_id=cafeteria_id,
                    menu_item_id=item.id,
                    quantity=0,
                    unit=InventoryUnit.PORTIONS,
                    low_threshold=10,
                )
            )
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

    # ---- Menu item images (Phase 48) ----

    async def _cleanup_orphan_image(self, url: str | None) -> None:
        """Delete a local static image file only when nothing references it.

        Called AFTER the referring row has been updated and flushed, so a
        file still referenced by another menu item (shared image) is never
        removed. External URLs and unknown paths are ignored.
        """
        path = resolve_static_image_path(url)
        if path is None or not os.path.isfile(path):
            return
        result = await self.db.execute(
            select(MenuItem.id).where(MenuItem.image_url == url).limit(2)
        )
        remaining = list(result.scalars().all())
        if len(remaining) == 0:
            try:
                os.remove(path)
                logger.info("menu_image_orphan_removed", file=os.path.basename(path))
            except OSError:
                logger.warning(
                    "menu_image_orphan_remove_failed", file=os.path.basename(path)
                )

    async def set_menu_item_image(
        self,
        menu_item_id: str,
        *,
        content: bytes,
        declared_content_type: str | None = None,
    ) -> MenuItem:
        """Upload/replace a menu item's image (Phase 48).

        Validates size, MIME type (magic bytes) and content/declared-type
        consistency, writes a freshly generated filename (the client
        filename is never used as a path), persists the host-independent
        reference, and safely removes the previous file when unreferenced.
        """
        item = await self.get_menu_item(menu_item_id)

        if not content:
            raise ValidationError("Image file is required")
        if len(content) > MAX_MENU_IMAGE_BYTES:
            raise ValidationError(
                f"Image must be {MAX_MENU_IMAGE_BYTES // (1024 * 1024)}MB or smaller"
            )

        detected = detect_menu_image_format(content)
        if detected is None:
            raise ValidationError(
                "Unsupported image type. Upload a JPEG, PNG, or WebP image."
            )
        mime, ext = detected

        declared = (declared_content_type or "").split(";")[0].strip().lower()
        if declared:
            if not declared.startswith("image/"):
                raise ValidationError(
                    "Unsupported image type. Upload a JPEG, PNG, or WebP image."
                )
            if declared != mime:
                raise ValidationError(
                    "File content does not match its declared image type"
                )

        os.makedirs(MENU_IMAGE_DIR, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(MENU_IMAGE_DIR, filename)
        with open(path, "wb") as f:
            f.write(content)

        old_url = item.image_url
        item.image_url = f"{MENU_IMAGE_URL_PREFIX}{filename}"
        await self.db.flush()
        # Old file is removed only when no other menu item references it.
        await self._cleanup_orphan_image(old_url)

        logger.info("menu_item_image_uploaded", item_id=item.id, file=filename)
        return item

    async def remove_menu_item_image(self, menu_item_id: str) -> MenuItem:
        """Remove a menu item's image (Phase 48) — the item stays usable."""
        item = await self.get_menu_item(menu_item_id)
        old_url = item.image_url
        item.image_url = None
        await self.db.flush()
        await self._cleanup_orphan_image(old_url)
        logger.info("menu_item_image_removed", item_id=menu_item_id)
        return item

    # ---- Daily Menus ----

    async def create_daily_menu(
        self,
        *,
        cafeteria_id: str,
        menu_date: date,
        created_by: str | None = None,
    ) -> DailyMenu:
        """Create a new daily menu draft."""
        # Check if one already exists for this cafeteria and date.
        # ARCHIVED menus are excluded so a replacement draft can be created
        # after unpublishing (one active menu per cafeteria/date is enforced).
        existing = await self.db.execute(
            select(DailyMenu).where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == menu_date,
                DailyMenu.status != DailyMenuStatus.ARCHIVED,
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

    async def unpublish_daily_menu(self, daily_menu_id: str) -> DailyMenu:
        """Unpublish (archive) a published daily menu (manager/admin).

        ARCHIVED removes the menu from published-menu lookups
        (``get_published_menu_for_date`` / effective unit-price resolution)
        without deleting its items, so historical orders stay auditable.
        A new draft can then be created for the same date — one menu per
        cafeteria/date is still enforced at creation, and archived menus
        do not block it. Published menus remain immutable until archived;
        archived menus cannot be modified further.
        """
        daily_menu = await self.get_daily_menu(daily_menu_id)
        if daily_menu.status != DailyMenuStatus.PUBLISHED:
            raise ValidationError("Only published menus can be unpublished")

        daily_menu.status = DailyMenuStatus.ARCHIVED
        await self.db.flush()
        logger.info("daily_menu_unpublished", menu_id=daily_menu_id)

        # Re-fetch with eager-loaded items to avoid MissingGreenlet in Pydantic
        return await self.get_daily_menu(daily_menu_id)
    async def copy_daily_menu(
        self,
        *,
        cafeteria_id: str,
        source_date: date,
        target_date: date,
        created_by: str | None = None,
    ) -> DailyMenu:
        """Copy the previous day's daily menu into a new draft (Phase 56).

        Creates a NEW draft for ``target_date`` carrying over the source
        menu's junction rows (special price, availability, display order,
        notes). The source menu itself is never modified. Copying refuses
        to overwrite: if the target date already has a non-archived menu
        (draft or published), an explicit conflict error is raised instead
        of silently merging or replacing it. Only currently-active menu
        items are copied — inactive catalog items must not leak into new
        menus. Order history is untouched: it references its own snapshots.
        """
        if source_date == target_date:
            raise ValidationError("Source date and target date must be different")

        # Source: any non-archived menu (published or draft) on the source date.
        source_result = await self.db.execute(
            select(DailyMenu)
            .where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == source_date,
                DailyMenu.status != DailyMenuStatus.ARCHIVED,
            )
            .options(selectinload(DailyMenu.items).selectinload(DailyMenuItem.menu_item))
        )
        source = source_result.scalars().first()
        if source is None:
            raise NotFoundException(
                "Daily Menu", f"cafeteria={cafeteria_id} date={source_date}"
            )

        # Target must be free — never silently overwrite a draft/published menu.
        target_result = await self.db.execute(
            select(DailyMenu).where(
                DailyMenu.cafeteria_id == cafeteria_id,
                DailyMenu.menu_date == target_date,
                DailyMenu.status != DailyMenuStatus.ARCHIVED,
            )
        )
        target_existing = target_result.scalars().first()
        if target_existing is not None:
            if target_existing.status == DailyMenuStatus.PUBLISHED:
                raise AlreadyExistsException(
                    "Daily Menu",
                    f"cafeteria={cafeteria_id} date={target_date} already has a "
                    "PUBLISHED menu — unpublish it first or choose another date",
                )
            raise AlreadyExistsException(
                "Daily Menu",
                f"cafeteria={cafeteria_id} date={target_date} already has a "
                "DRAFT menu — edit it directly or choose another date",
            )

        new_menu = DailyMenu(
            cafeteria_id=cafeteria_id,
            menu_date=target_date,
            status=DailyMenuStatus.DRAFT,
            created_by=created_by,
        )
        self.db.add(new_menu)
        await self.db.flush()

        copied = 0
        for src in source.items:
            # Only active catalog items may appear on new menus; historical
            # orders keep their own snapshots and remain unaffected.
            if src.menu_item is not None and src.menu_item.is_active is False:
                continue
            self.db.add(
                DailyMenuItem(
                    daily_menu_id=new_menu.id,
                    menu_item_id=src.menu_item_id,
                    special_price=src.special_price,
                    is_available_today=src.is_available_today,
                    display_order=src.display_order,
                    notes=src.notes,
                )
            )
            copied += 1
        await self.db.flush()
        logger.info(
            "daily_menu_copied",
            source_menu_id=source.id,
            target_menu_id=new_menu.id,
            items_copied=copied,
        )

        # Re-fetch with eager-loaded items to avoid MissingGreenlet in Pydantic
        return await self.get_daily_menu(new_menu.id)
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

    async def list_favorites(
        self, user_id: str, *, exclude_faculty_cafeteria: bool = False
    ) -> list[MenuFavorite]:
        """List a user's favorite menu items with menu_item eagerly loaded.

        When exclude_faculty_cafeteria is True, favorites belonging to the
        faculty cafeteria are filtered out (non-faculty users).
        """
        query = (
            select(MenuFavorite)
            .where(MenuFavorite.user_id == user_id)
            .options(selectinload(MenuFavorite.menu_item))
            .order_by(MenuFavorite.created_at.desc())
        )
        if exclude_faculty_cafeteria:
            from app.modules.cafeterias.models import Cafeteria, CafeteriaType

            query = (
                query.join(MenuItem, MenuItem.id == MenuFavorite.menu_item_id)
                .join(Cafeteria, Cafeteria.id == MenuItem.cafeteria_id)
                .where(Cafeteria.type != CafeteriaType.FACULTY)  # noqa: E712
            )
        result = await self.db.execute(query)
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
        exclude_faculty_cafeteria: bool = False,
    ) -> list[MenuItem]:
        """Search menu items across cafeterias."""
        query = select(MenuItem).where(MenuItem.is_active == True)  # noqa: E712
        if cafeteria_id is not None:
            query = query.where(MenuItem.cafeteria_id == cafeteria_id)
        if exclude_faculty_cafeteria:
            # Non-faculty users must not discover faculty-cafeteria items.
            from app.modules.cafeterias.models import Cafeteria, CafeteriaType

            query = (
                query.join(Cafeteria, Cafeteria.id == MenuItem.cafeteria_id)
                .where(Cafeteria.type != CafeteriaType.FACULTY)  # noqa: E712
            )
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
