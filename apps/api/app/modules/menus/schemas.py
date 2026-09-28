"""Menus module — Pydantic schemas for request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.menus.models import DailyMenuStatus, MenuCategory

# ---- Menu Item Schemas ----


class MenuItemCreateRequest(BaseModel):
    """Request to create a menu item (manager/admin)."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    category: MenuCategory
    price: int = Field(..., gt=0)  # Price in paisa (smallest currency unit)
    currency: str = Field("PKR", max_length=3)
    image_url: str | None = Field(None, max_length=512)
    dietary_info: str | None = None  # JSON string
    allergens: str | None = None  # JSON string
    preparation_time_minutes: int = Field(15, ge=0)


class MenuItemUpdateRequest(BaseModel):
    """Request to update a menu item (manager/admin)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category: MenuCategory | None = None
    price: int | None = Field(None, gt=0)
    currency: str | None = Field(None, max_length=3)
    image_url: str | None = Field(None, max_length=512)
    dietary_info: str | None = None
    allergens: str | None = None
    preparation_time_minutes: int | None = Field(None, ge=0)
    is_available: bool | None = None
    is_active: bool | None = None


class MenuItemResponse(BaseModel):
    """Menu item detail response."""

    id: str
    cafeteria_id: str
    name: str
    description: str | None = None
    category: MenuCategory
    price: int
    currency: str
    image_url: str | None = None
    dietary_info: str | None = None
    allergens: str | None = None
    preparation_time_minutes: int
    is_available: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MenuItemListResponse(BaseModel):
    """List of menu items."""

    items: list[MenuItemResponse]
    total: int


# ---- Daily Menu Schemas ----


class DailyMenuCreateRequest(BaseModel):
    """Request to create a daily menu draft (manager/admin)."""

    menu_date: date


class DailyMenuAddItemRequest(BaseModel):
    """Request to add a menu item to a daily menu."""

    menu_item_id: str
    special_price: int | None = Field(None, gt=0)
    is_available_today: bool = True
    display_order: int = Field(0, ge=0)
    notes: str | None = None


class DailyMenuRemoveItemRequest(BaseModel):
    """Request to remove a menu item from a daily menu."""

    menu_item_id: str


class DailyMenuItemResponse(BaseModel):
    """A single item on a daily menu."""

    id: str
    menu_item_id: str
    special_price: int | None = None
    is_available_today: bool
    display_order: int
    notes: str | None = None
    menu_item: MenuItemResponse | None = None

    model_config = {"from_attributes": True}


class DailyMenuResponse(BaseModel):
    """Daily menu detail response."""

    id: str
    cafeteria_id: str
    menu_date: date
    status: DailyMenuStatus
    published_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[DailyMenuItemResponse] = []

    model_config = {"from_attributes": True}


class DailyMenuListResponse(BaseModel):
    """List of daily menus."""

    menus: list[DailyMenuResponse]
    total: int


# ---- Favorite Schemas ----


class FavoriteAddRequest(BaseModel):
    """Request to add a menu item to favorites."""

    menu_item_id: str


class FavoriteResponse(BaseModel):
    """Favorite item response."""

    id: str
    menu_item_id: str
    menu_item: MenuItemResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteListResponse(BaseModel):
    """List of favorites."""

    favorites: list[FavoriteResponse]
    total: int
