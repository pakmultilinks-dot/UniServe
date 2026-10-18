"""Menus module — API endpoints for menu items, daily menus, and favorites."""

import base64
import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireCafeteriaScope,
    RequireCafeteriaWriteScope,
    get_current_user,
    verify_resource_cafeteria,
)
from app.modules.menus.models import DailyMenuStatus, MenuCategory, MenuItem
from app.modules.menus.schemas import (
    CopyDailyMenuRequest,
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
from app.modules.menus.service import MenuService, resolve_static_image_path
from app.modules.users.models import Role

# ---- Menu Items Router (nested under cafeterias) ----

menu_items_router = APIRouter()

# ---- Daily Menus Router (nested under cafeterias) ----

daily_menus_router = APIRouter()

# ---- Favorites Router (standalone) ----

favorites_router = APIRouter()

# ---- Search Router (standalone) ----

search_router = APIRouter()

# ---- Static food images (DB-backed, survives Render redeploys) ----

static_images_router = APIRouter()

_EXT_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@static_images_router.get("/static/food/{filename}", include_in_schema=False)
async def serve_food_image(filename: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Serve a menu image from the DB (disk fallback).

    Registered in api_router, so this route is matched BEFORE the
    StaticFiles mount at /api/v1/static. Render's free plan has an
    ephemeral filesystem — the DB copy is authoritative; the disk file is
    only a fallback for images uploaded before migration 0014.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Not Found")

    url = f"/api/v1/static/food/{filename}"
    result = await db.execute(select(MenuItem).where(MenuItem.image_url == url).limit(1))
    item = result.scalar_one_or_none()
    if item is not None and item.image_data:
        header, _, b64 = item.image_data.partition(",")
        try:
            raw = base64.b64decode(b64)
        except (ValueError, TypeError):
            raw = b""
        if raw:
            mime = header.partition(":")[2].partition(";")[0] or "application/octet-stream"
            return Response(
                content=raw,
                media_type=mime,
                headers={"Cache-Control": "public, max-age=86400"},
            )

    path = resolve_static_image_path(url)
    if path is not None and os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            raw = f.read()
        return Response(
            content=raw,
            media_type=_EXT_CONTENT_TYPES.get(ext, "application/octet-stream"),
            headers={"Cache-Control": "public, max-age=86400"},
        )

    raise HTTPException(status_code=404, detail="Not Found")


def _can_view_all_cafeterias(auth: AuthContext) -> bool:
    """True when the user may see items from every cafeteria (incl. faculty).

    Students (and any other non-faculty, non-staff role) must never discover
    faculty-cafeteria items through unscoped search or favorites.
    """
    if auth.user.role in (
        Role.UNIVERSITY_ADMIN,
        Role.CAFETERIA_MANAGER,
        Role.CAFETERIA_STAFF,
    ):
        return True
    from app.modules.users.models import UserCategory

    return auth.user.category == UserCategory.FACULTY


# ===================================================================
# Menu Items
# ===================================================================


@menu_items_router.post("/", response_model=MenuItemResponse, status_code=201)
async def create_menu_item(
    cafeteria_id: str,
    body: MenuItemCreateRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
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
        preparation_time_minutes=body.preparation_time_minutes,
        initial_quantity=body.initial_quantity,
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
    """Get a menu item by ID (must belong to the path cafeteria)."""
    service = MenuService(db)
    item = await service.get_menu_item(menu_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="MenuItem",
        db=db,
        auth=auth,
    )
    return MenuItemResponse.model_validate(item)


@menu_items_router.put("/{menu_item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    cafeteria_id: str,
    menu_item_id: str,
    body: MenuItemUpdateRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """Update a menu item (manager/admin)."""
    service = MenuService(db)
    item = await service.get_menu_item(menu_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="MenuItem",
        db=db,
        auth=auth,
    )
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
        preparation_time_minutes=body.preparation_time_minutes,
        is_available=body.is_available,
        is_active=body.is_active,
    )
    return MenuItemResponse.model_validate(item)


@menu_items_router.delete("/{menu_item_id}", status_code=204)
async def delete_menu_item(
    cafeteria_id: str,
    menu_item_id: str,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a menu item.

    B21: aligned with create/update — cafeteria managers may delete within
    their own cafeteria scope (deletion is a soft-delete, so it is
    recoverable and audited like any other write).
    """
    service = MenuService(db)
    await service.delete_menu_item(menu_item_id)


# ---- Menu item images (Phase 48) ----
#
# Raw binary body (not multipart/form-data): the deployment does not
# install python-multipart and dependency changes are out of scope, and a
# single-file upload needs no multipart envelope. The client sends the
# image bytes with an image/jpeg | image/png | image/webp Content-Type;
# magic bytes decide the stored format, filenames are server-generated.


@menu_items_router.post("/{menu_item_id}/image", response_model=MenuItemResponse)
async def upload_menu_item_image(
    cafeteria_id: str,
    menu_item_id: str,
    request: Request,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """Upload or replace a menu item's image (manager/admin, scoped).

    Validates type (magic bytes + declared Content-Type), size (5MB),
    writes a server-generated filename under app/static/food/, persists a
    host-independent ``/api/v1/static/food/<file>`` reference, and removes
    the previous file only when no other menu item references it.
    """
    service = MenuService(db)
    item = await service.get_menu_item(menu_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="MenuItem",
        db=db,
        auth=auth,
    )
    content = await request.body()
    item = await service.set_menu_item_image(
        menu_item_id,
        content=content,
        declared_content_type=request.headers.get("content-type"),
    )
    return MenuItemResponse.model_validate(item)


@menu_items_router.delete("/{menu_item_id}/image", response_model=MenuItemResponse)
async def remove_menu_item_image(
    cafeteria_id: str,
    menu_item_id: str,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """Remove a menu item's image (manager/admin, scoped).

    Clears ``image_url``; the menu item itself remains fully usable and
    clients fall back to their existing placeholder behaviour.
    """
    service = MenuService(db)
    item = await service.get_menu_item(menu_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="MenuItem",
        db=db,
        auth=auth,
    )
    item = await service.remove_menu_item_image(menu_item_id)
    return MenuItemResponse.model_validate(item)


# ===================================================================
# Daily Menus
# ===================================================================


@daily_menus_router.post("/", response_model=DailyMenuResponse, status_code=201)
async def create_daily_menu(
    cafeteria_id: str,
    body: DailyMenuCreateRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
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


@daily_menus_router.post("/copy", response_model=DailyMenuResponse, status_code=201)
async def copy_daily_menu(
    cafeteria_id: str,
    body: CopyDailyMenuRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Copy a previous day's menu into a new draft (Phase 56, manager/admin).

    The target date must be free — an existing draft or published menu on
    the target date produces an explicit 409 conflict, never a silent
    overwrite. Inactive menu items are skipped; the source menu is untouched.
    """
    service = MenuService(db)
    menu = await service.copy_daily_menu(
        cafeteria_id=cafeteria_id,
        source_date=body.source_date,
        target_date=body.target_date,
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
    await verify_resource_cafeteria(
        resource_cafeteria_id=menu.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="DailyMenu",
        db=db,
        auth=auth,
    )
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.post("/{daily_menu_id}/items", response_model=DailyMenuResponse)
async def add_item_to_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    body: DailyMenuAddItemRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Add a menu item to a daily menu (must be DRAFT)."""
    service = MenuService(db)
    # Verify the daily menu belongs to the claimed cafeteria
    daily_menu = await service.get_daily_menu(daily_menu_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=daily_menu.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="DailyMenu",
        db=db,
        auth=auth,
    )
    # Verify the menu item belongs to the same cafeteria
    menu_item = await service.get_menu_item(body.menu_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=menu_item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="MenuItem",
        db=db,
        auth=auth,
    )
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
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Remove a menu item from a daily menu (must be DRAFT)."""
    service = MenuService(db)
    # Verify the daily menu belongs to the claimed cafeteria
    daily_menu = await service.get_daily_menu(daily_menu_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=daily_menu.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="DailyMenu",
        db=db,
        auth=auth,
    )
    await service.remove_item_from_daily_menu(daily_menu_id, menu_item_id)
    menu = await service.get_daily_menu(daily_menu_id)
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.patch("/{daily_menu_id}/publish", response_model=DailyMenuResponse)
async def publish_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Publish a daily menu (manager/admin)."""
    service = MenuService(db)
    # Verify the daily menu belongs to the claimed cafeteria
    daily_menu = await service.get_daily_menu(daily_menu_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=daily_menu.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="DailyMenu",
        db=db,
        auth=auth,
    )
    menu = await service.publish_daily_menu(daily_menu_id)
    return DailyMenuResponse.model_validate(menu)


@daily_menus_router.patch("/{daily_menu_id}/unpublish", response_model=DailyMenuResponse)
async def unpublish_daily_menu(
    cafeteria_id: str,
    daily_menu_id: str,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> DailyMenuResponse:
    """Unpublish (archive) a published daily menu (manager/admin).

    ARCHIVED removes the menu from published-menu lookups so a replacement
    draft can be created for the same date. Historical published menus remain
    auditable (items are preserved).
    """
    service = MenuService(db)
    # Verify the daily menu belongs to the claimed cafeteria
    daily_menu = await service.get_daily_menu(daily_menu_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=daily_menu.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="DailyMenu",
        db=db,
        auth=auth,
    )
    menu = await service.unpublish_daily_menu(daily_menu_id)
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
    # Students must not favorite items from the faculty cafeteria
    if not _can_view_all_cafeterias(auth):
        from sqlalchemy import select as sa_select

        from app.core.exceptions import AuthorizationError, NotFoundException
        from app.modules.cafeterias.models import Cafeteria, CafeteriaType

        item = await service.get_menu_item(body.menu_item_id)
        caf_result = await db.execute(
            sa_select(Cafeteria).where(Cafeteria.id == item.cafeteria_id)
        )
        cafeteria = caf_result.scalar_one_or_none()
        if cafeteria is None:
            raise NotFoundException("Cafeteria", item.cafeteria_id)
        if cafeteria.type == CafeteriaType.FACULTY:
            raise AuthorizationError("You cannot access this cafeteria")
    fav = await service.add_favorite(auth.user.id, body.menu_item_id)
    return FavoriteResponse.model_validate(fav)


@favorites_router.get("/", response_model=FavoriteListResponse)
async def list_favorites(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteListResponse:
    """List user's favorite menu items."""
    service = MenuService(db)
    favs = await service.list_favorites(
        auth.user.id,
        exclude_faculty_cafeteria=not _can_view_all_cafeterias(auth),
    )
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
    """Search menu items. Validates cafeteria access if cafeteria_id provided."""
    # If a specific cafeteria is requested, verify access
    if cafeteria_id:
        from sqlalchemy import select as sa_select

        from app.core.exceptions import AuthorizationError, NotFoundException
        from app.modules.cafeterias.models import Cafeteria, CafeteriaType

        caf_result = await db.execute(sa_select(Cafeteria).where(Cafeteria.id == cafeteria_id))
        caf = caf_result.scalar_one_or_none()
        if caf is None:
            raise NotFoundException("Cafeteria", cafeteria_id)
        if (
            auth.user.role in (Role.STUDENT, Role.FACULTY)
            and caf.type == CafeteriaType.FACULTY
            and auth.user.category.value != "faculty"
        ):
            raise AuthorizationError("You cannot access this cafeteria")

    service = MenuService(db)
    items = await service.search_menu_items(
        cafeteria_id=cafeteria_id,
        category=category,
        search=search,
        is_available=is_available,
        # Unscoped search must never surface faculty-cafeteria items
        # to users who cannot access the faculty cafeteria.
        exclude_faculty_cafeteria=(
            cafeteria_id is None and not _can_view_all_cafeterias(auth)
        ),
    )
    return MenuItemListResponse(
        items=[MenuItemResponse.model_validate(i) for i in items],
        total=len(items),
    )
