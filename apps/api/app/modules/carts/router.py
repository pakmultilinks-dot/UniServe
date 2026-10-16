"""Cart module — API endpoints for shopping cart management."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, RequireCafeteriaScope
from app.modules.carts.schemas import (
    CartAddItemRequest,
    CartCheckoutRequest,
    CartItemResponse,
    CartResponse,
    CartUpdateQuantityRequest,
)
from app.modules.carts.service import CartService
from app.modules.orders.schemas import OrderResponse as OrderCheckoutResponse

router = APIRouter()


@router.get("/", response_model=CartResponse)
async def get_cart(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    """Get the user's active cart for a cafeteria."""
    service = CartService(db)
    cart = await service.get_or_create_cart(user_id=auth.user.id, cafeteria_id=cafeteria_id)
    items_details = await service.get_cart_items_with_details(cart.id)
    total = sum(i["subtotal"] for i in items_details)
    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        cafeteria_id=cart.cafeteria_id,
        status=cart.status.value,
        items=[CartItemResponse(**i) for i in items_details],
        total_amount=total,
        item_count=len(items_details),
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


@router.post("/items", response_model=CartItemResponse, status_code=201)
async def add_cart_item(
    cafeteria_id: str,
    body: CartAddItemRequest,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> CartItemResponse:
    """Add an item to the user's cart."""
    service = CartService(db)
    cart_item = await service.add_item(
        user_id=auth.user.id,
        cafeteria_id=cafeteria_id,
        menu_item_id=body.menu_item_id,
        quantity=body.quantity,
    )
    # Fetch with menu item details
    items = await service.get_cart_items_with_details(cart_item.cart_id)
    detail = next((i for i in items if i["id"] == cart_item.id), None)
    return (
        CartItemResponse(**detail)
        if detail
        else CartItemResponse(
            id=cart_item.id,
            menu_item_id=cart_item.menu_item_id,
            quantity=cart_item.quantity,
            price_snapshot=cart_item.price_snapshot,
            currency=cart_item.currency,
            subtotal=cart_item.price_snapshot * cart_item.quantity,
            created_at=cart_item.created_at,
            updated_at=cart_item.updated_at,
        )
    )


@router.put("/items/{cart_item_id}", response_model=CartItemResponse)
async def update_cart_item(
    cafeteria_id: str,
    cart_item_id: str,
    body: CartUpdateQuantityRequest,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> CartItemResponse | Response:
    """Update the quantity of a cart item."""
    service = CartService(db)
    cart = await service.get_or_create_cart(user_id=auth.user.id, cafeteria_id=cafeteria_id)
    cart_item = await service.update_item_quantity(
        cart_id=cart.id,
        cart_item_id=cart_item_id,
        quantity=body.quantity,
        user_id=auth.user.id,
    )
    if cart_item is None:
        # Quantity zero removed the item — a successful removal, not a 404.
        return Response(status_code=204)
    items = await service.get_cart_items_with_details(cart.id)
    detail = next((i for i in items if i["id"] == cart_item.id), None)
    return (
        CartItemResponse(**detail)
        if detail
        else CartItemResponse(
            id=cart_item.id,
            menu_item_id=cart_item.menu_item_id,
            quantity=cart_item.quantity,
            price_snapshot=cart_item.price_snapshot,
            currency=cart_item.currency,
            subtotal=cart_item.price_snapshot * cart_item.quantity,
            created_at=cart_item.created_at,
            updated_at=cart_item.updated_at,
        )
    )


@router.delete("/items/{cart_item_id}", status_code=204)
async def remove_cart_item(
    cafeteria_id: str,
    cart_item_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an item from the cart."""
    service = CartService(db)
    cart = await service.get_or_create_cart(user_id=auth.user.id, cafeteria_id=cafeteria_id)
    await service.remove_item(
        cart_id=cart.id,
        cart_item_id=cart_item_id,
        user_id=auth.user.id,
    )


@router.post("/checkout", response_model=OrderCheckoutResponse, status_code=201)
async def checkout(
    cafeteria_id: str,
    body: CartCheckoutRequest,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> OrderCheckoutResponse:
    """Checkout the cart and create an order."""
    from app.modules.orders.service import OrderService

    order_service = OrderService(db)
    order = await order_service.checkout(
        user_id=auth.user.id,
        cafeteria_id=cafeteria_id,
        payment_method=body.payment_method,
        order_type=body.order_type,
        scheduled_collection_time=body.scheduled_collection_time,
        note=body.note,
        idempotency_key=body.idempotency_key,
    )
    return OrderCheckoutResponse.model_validate(order)
