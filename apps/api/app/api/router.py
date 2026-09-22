"""API router — aggregates all versioned route modules."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

# Health check (always available)
api_router.include_router(health_router, prefix="/health", tags=["health"])

# Auth module
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# User management module
api_router.include_router(users_router, prefix="/users", tags=["users"])

# Future module routers:
# api_router.include_router(cafeterias_router, prefix="/cafeterias", tags=["cafeterias"])
# api_router.include_router(menus_router, prefix="/menus", tags=["menus"])
# api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
# api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
