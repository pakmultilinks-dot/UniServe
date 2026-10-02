"""Inventory module — API endpoints for inventory management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireCafeteriaWriteScope,
    verify_resource_cafeteria,
)
from app.modules.inventory.schemas import (
    InventoryAdjustmentRequest,
    InventoryAdjustmentResponse,
    InventoryItemCreateRequest,
    InventoryItemResponse,
    InventoryListResponse,
)
from app.modules.inventory.service import InventoryService
from app.modules.users.models import Role

router = APIRouter()


# ---- Create Inventory Item (Manager/Admin) ----


@router.post("/", response_model=InventoryItemResponse, status_code=201)
async def create_inventory_item(
    cafeteria_id: str,
    body: InventoryItemCreateRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)
    ),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    """Create an inventory record for a menu item (manager/admin)."""
    service = InventoryService(db)
    # Verify the menu item belongs to the claimed cafeteria
    from app.modules.menus.service import MenuService

    menu_service = MenuService(db)
    menu_item = await menu_service.get_menu_item(body.menu_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=menu_item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="MenuItem",
        db=db,
        auth=auth,
    )
    item = await service.create_inventory_item(
        cafeteria_id=cafeteria_id,
        menu_item_id=body.menu_item_id,
        quantity=body.quantity,
        unit=body.unit,
        low_threshold=body.low_threshold,
    )
    response = InventoryItemResponse.model_validate(item)
    response.is_low = item.quantity <= item.low_threshold
    return response


# ---- List Inventory Items ----


@router.get("/", response_model=InventoryListResponse)
async def list_inventory_items(
    cafeteria_id: str,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(
            Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF
        )
    ),
    db: AsyncSession = Depends(get_db),
    low_only: bool = False,
) -> InventoryListResponse:
    """List inventory items for a cafeteria (staff/manager/admin only).

    Inventory quantities are internal operational data: the read surface
    uses the same role + cafeteria-assignment scope as the adjust endpoint
    and the inventory reports module.
    """
    service = InventoryService(db)
    items = await service.list_inventory_items(
        cafeteria_id=cafeteria_id,
        low_only=low_only,
    )
    response_items = []
    for item in items:
        resp = InventoryItemResponse.model_validate(item)
        resp.is_low = item.quantity <= item.low_threshold
        response_items.append(resp)
    return InventoryListResponse(items=response_items, total=len(response_items))


# ---- Adjust Inventory ----


@router.post("/adjust", response_model=InventoryAdjustmentResponse)
async def adjust_inventory(
    cafeteria_id: str,
    body: InventoryAdjustmentRequest,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(
            Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> InventoryAdjustmentResponse:
    """Adjust inventory quantity (manager/staff/admin)."""
    service = InventoryService(db)
    # Load the inventory item and verify it belongs to the claimed cafeteria
    inventory_item = await service.get_inventory_item(body.inventory_item_id)
    await verify_resource_cafeteria(
        resource_cafeteria_id=inventory_item.cafeteria_id,
        expected_cafeteria_id=cafeteria_id,
        resource_type="InventoryItem",
        db=db,
        auth=auth,
    )
    adjustment = await service.adjust_inventory(
        inventory_item_id=body.inventory_item_id,
        adjustment_quantity=body.adjustment_quantity,
        adjusted_by=auth.user.id,
        reason=body.reason,
    )
    return InventoryAdjustmentResponse.model_validate(adjustment)


# ---- Low Stock Items ----


@router.get("/low-stock", response_model=InventoryListResponse)
async def get_low_stock_items(
    cafeteria_id: str,
    auth: AuthContext = Depends(
        RequireCafeteriaWriteScope(
            Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> InventoryListResponse:
    """Get inventory items below their low-stock threshold (staff/manager/admin only)."""
    service = InventoryService(db)
    items = await service.get_low_stock_items(cafeteria_id)
    response_items = []
    for item in items:
        resp = InventoryItemResponse.model_validate(item)
        resp.is_low = item.quantity <= item.low_threshold
        response_items.append(resp)
    return InventoryListResponse(items=response_items, total=len(response_items))
