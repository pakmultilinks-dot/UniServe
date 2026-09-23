"""Inventory module — Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.inventory.models import InventoryUnit

# ---- Request Schemas ----


class InventoryItemCreateRequest(BaseModel):
    """Request to create an inventory record for a menu item."""

    menu_item_id: str
    quantity: int = Field(0, ge=0)
    unit: InventoryUnit
    low_threshold: int = Field(10, ge=0)


class InventoryAdjustmentRequest(BaseModel):
    """Request to adjust inventory quantity."""

    inventory_item_id: str
    adjustment_quantity: int  # positive = restock, negative = consumption
    reason: str | None = Field(None, max_length=500)


# ---- Response Schemas ----


class InventoryItemResponse(BaseModel):
    """Inventory item detail response."""

    id: str
    cafeteria_id: str
    menu_item_id: str
    quantity: int
    unit: InventoryUnit
    low_threshold: int
    is_low: bool = False  # computed field
    last_restocked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryAdjustmentResponse(BaseModel):
    """Inventory adjustment detail response."""

    id: str
    inventory_item_id: str
    adjustment_quantity: int
    reason: str | None = None
    adjusted_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryListResponse(BaseModel):
    """List of inventory items."""

    items: list[InventoryItemResponse]
    total: int
