"""API router — aggregates all versioned route modules."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.auth.router import router as auth_router

# Phase 3 routers
from app.modules.cafeterias.router import router as cafeterias_router
from app.modules.carts.router import router as carts_router
from app.modules.inventory.router import router as inventory_router
from app.modules.menus.router import (
    daily_menus_router,
    favorites_router,
    menu_items_router,
    search_router,
)
from app.modules.orders.router import router as orders_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

# Health check (always available)
api_router.include_router(health_router, prefix="/health", tags=["health"])

# Auth module
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# User management module
api_router.include_router(users_router, prefix="/users", tags=["users"])

# Cafeteria management
api_router.include_router(cafeterias_router, prefix="/cafeterias", tags=["cafeterias"])

# Menu items (nested under cafeterias)
api_router.include_router(
    menu_items_router,
    prefix="/cafeterias/{cafeteria_id}/menu-items",
    tags=["menu-items"],
)

# Daily menus (nested under cafeterias)
api_router.include_router(
    daily_menus_router,
    prefix="/cafeterias/{cafeteria_id}/daily-menus",
    tags=["daily-menus"],
)

# Inventory (nested under cafeterias)
api_router.include_router(
    inventory_router,
    prefix="/cafeterias/{cafeteria_id}/inventory",
    tags=["inventory"],
)

# Favorites (standalone, user-scoped)
api_router.include_router(favorites_router, prefix="/favorites", tags=["favorites"])

# Menu search (standalone)
api_router.include_router(search_router, prefix="/menu-search", tags=["menu-search"])

# Carts (user-scoped, cafeteria-scoped)
api_router.include_router(
    carts_router,
    prefix="/cafeterias/{cafeteria_id}/cart",
    tags=["carts"],
)

# Orders
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])

# Payments (Phase 5)
from app.modules.payments.router import router as payments_router
from app.modules.refunds.router import router as refunds_router

api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
api_router.include_router(refunds_router, prefix="/refunds", tags=["refunds"])
