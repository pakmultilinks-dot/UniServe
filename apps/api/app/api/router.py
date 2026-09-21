"""API router — aggregates all versioned route modules."""

from fastapi import APIRouter

from app.api.health import router as health_router

api_router = APIRouter()

# Health check (always available)
api_router.include_router(health_router, prefix="/health", tags=["health"])

# Module routers will be registered here as they are implemented:
# api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# api_router.include_router(users_router, prefix="/users", tags=["users"])
# api_router.include_router(cafeterias_router, prefix="/cafeterias", tags=["cafeterias"])
# api_router.include_router(menus_router, prefix="/menus", tags=["menus"])
# api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
# api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
