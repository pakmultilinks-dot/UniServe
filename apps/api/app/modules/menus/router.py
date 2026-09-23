"""Menus module — API endpoints for menu items, daily menus, and favorites."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireCafeteriaScope,
    RequireRole,
    get_current_user,
)
from app.modules.menus.models import DailyMenuStatus, MenuCategory
from app.modules.menus.schemas import (
    DailyMenuAddItemRequest,
    DailyMenuCreateRequest,
    DailyMenuListResponse,
    DailyMenuResponse,
    FavoriteAddRequest,
    FavoriteListResponse,
    FavoriteResponse,
    MenuItemCreateRequest,
    MenuItemListResponse,
    MenuItemResponse,
    MenuItemUpdateRequest,
)
from app.modules.menus.service import MenuService
from app.modules.users.models import Role

# ---- Menu Items Router (nested under cafeterias) ----

menu_items_router = APIRouter()

# ---- Daily Menus Router (nested under cafeterias) ----

daily_menus_router = APIRouter()

# ---- Favorites Router (standalone) ----

favorites_router = APIRouter()

# ---- Search Router (standalone) ----

search_router = APIRouter()


# ===================================================================
# Menu Items
# ===================================================================


@menu_items_router.post("/", response_model=MenuItemResponse, status_code=201)
async def create_menu_item(
    cafeteria_id: str,
    body: MenuItemCreateRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """Create a menu item (manager/admin, cafeteria-scoped)."""
    service = MenuService(db)
    item = await service.create_menu_item(
        cafeteria_id=cafeteria_id,
        name=body.name,
        description=body.description,
        category=body.category,
        price=body.price,
        currency=body.currency,
        image_url=body.image_url,
        dietary_info=body.dietary_info,
        allergens=body.allergens,
    )
    return MenuItemResponse.model_validate(item)


@menu_items_router.get("/", response_model=MenuItemListResponse)
async def list_menu_items(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
    category: MenuCategory | None = None,
    is_available: bool | None = None,
    search: str | None = None,
) -> MenuItemListResponse:
    """List menu items for a cafeteria (scoped access)."""
    service = MenuService(db)
    items = await service.list_menu_items(
        cafeteria_id=cafeteria_id,
        category=category,
        is_available=is_available,
        search=search,
    )
    return MenuItemListResponse(
        items=[MenuItemResponse.model_validate(i) for i in items],
        total=len(items),
    )


@menu_items_router.get("/{menu_item_id}", response_model=MenuItemResponse)
async def get_menu_item(
    cafeteria_id: str,
    menu_item_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """Get a menu item by ID."""
    service = MenuService(db)
    item = await service.get_menu_item(menu_item_id)
    return MenuItemResponse.model_validate(item)


@menu_items_router.put("/{menu_item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    cafeteria_id: str,
    menu_item_id: str,
    body: MenuItemUpdateRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """Update a menu item (manager/admin)."""
    service = MenuService(db)
    item = await service.update_menu_item(
        menu_item_id,
        name=body.name,
        description=body.description,
        category=body.category,
        price=body.price,
        currency=body.currency,
        image_url=body.image_url,
        dietary_info=body.dietary_info,
        allergens=body.allergens,
        is_available=body.is_available,
        is_active=body.is_active,
    )
    return MenuItemResponse.model_validate(item)


@menu_items_router.delete("/{menu_item_id}", status_code=204)
async def delete_menu_item(
    cafeteria_id: str,
    menu_item_id: str,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a menu item (admin only)."""
    service = MenuService(db)
    await service.delete_menu_item(menu_item_id)


# ===================================================================
# Daily Menus
# ===================================================================


@daily_menus_router.post("/", response_model=DailyMenuResponse, status_code=201)
async def create_daily_menu(
    cafeteria_id: str,
    body: DailyMenuCreateRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Create a daily menu draft (manager/admin)."""
    service = MenuService(db)
    menu = await service.create_daily_menu(
        cafeteria_id=cafeteria_id,
        menu_date=body.menu_date,
        created_by=auth.user.id,
    )
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.get("/", response_model=DailyMenuListResponse)
async def list_daily_menus(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
    status: DailyMenuStatus | None = None,
) -> DailyMenuListResponse:
    """List daily menus for a cafeteria."""
    service = MenuService(db)
    menus = await service.list_daily_menus(
        cafeteria_id=cafeteria_id,
        status=status,
    )
    return DailyMenuListResponse(
        menus=[DailyMenuResponse.model_validate(m) for m in menus],
        total=len(menus),
    )


@daily_menus_router.get("/today", response_model=DailyMenuResponse | None)
async def get_todays_menu(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse | None:
    """Get today's published menu for a cafeteria."""
    service = MenuService(db)
    menu = await service.get_published_menu_for_date(
        cafeteria_id=cafeteria_id,
        menu_date=date.today(),
    )
    if menu is None:
        return None
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.get("/{daily_menu_id}", response_model=DailyMenuResponse)
async def get_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Get a daily menu by ID."""
    service = MenuService(db)
    menu = await service.get_daily_menu(daily_menu_id)
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.post("/{daily_menu_id}/items", response_model=DailyMenuResponse)
async def add_item_to_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    body: DailyMenuAddItemRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Add a menu item to a daily menu (must be DRAFT)."""
    service = MenuService(db)
    await service.add_item_to_daily_menu(
        daily_menu_id,
        menu_item_id=body.menu_item_id,
        special_price=body.special_price,
        is_available_today=body.is_available_today,
        display_order=body.display_order,
        notes=body.notes,
    )
    menu = await service.get_daily_menu(daily_menu_id)
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.delete(
    "/{daily_menu_id}/items/{menu_item_id}", response_model=DailyMenuResponse
)
async def remove_item_from_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    menu_item_id: str,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Remove a menu item from a daily menu (must be DRAFT)."""
    service = MenuService(db)
    await service.remove_item_from_daily_menu(daily_menu_id, menu_item_id)
    menu = await service.get_daily_menu(daily_menu_id)
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.patch("/{daily_menu_id}/publish", response_model=DailyMenuResponse)
async def publish_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Publish a daily menu (manager/admin)."""
    service = MenuService(db)
    menu = await service.publish_daily_menu(daily_menu_id)
    return DailyMenuResponse.model_validate(menu)


# ===================================================================
# Favorites
# ===================================================================


@favorites_router.post("/", response_model=FavoriteResponse, status_code=201)
async def add_favorite(
    body: FavoriteAddRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteResponse:
    """Add a menu item to favorites."""
    service = MenuService(db)
    fav = await service.add_favorite(auth.user.id, body.menu_item_id)
    return FavoriteResponse.model_validate(fav)


@favorites_router.get("/", response_model=FavoriteListResponse)
async def list_favorites(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteListResponse:
    """List user's favorite menu items."""
    service = MenuService(db)
    favs = await service.list_favorites(auth.user.id)
    return FavoriteListResponse(
        favorites=[FavoriteResponse.model_validate(f) for f in favs],
        total=len(favs),
    )


@favorites_router.delete("/{menu_item_id}", status_code=204)
async def remove_favorite(
    menu_item_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a menu item from favorites."""
    service = MenuService(db)
    await service.remove_favorite(auth.user.id, menu_item_id)


# ===================================================================
# Search
# ===================================================================


@search_router.get("/", response_model=MenuItemListResponse)
async def search_menu_items(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    cafeteria_id: str | None = None,
    category: MenuCategory | None = None,
    search: str | None = None,
    is_available: bool | None = True,
) -> MenuItemListResponse:
    """Search menu items across cafeterias."""
    service = MenuService(db)
    items = await service.search_menu_items(
        cafeteria_id=cafeteria_id,
        category=category,
        search=search,
        is_available=is_available,
    )
    return MenuItemListResponse(
        items=[MenuItemResponse.model_validate(i) for i in items],
        total=len(items),
    )
