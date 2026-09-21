"""Health check endpoint.

Provides basic health and readiness checks for the API.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()


@router.get("")
async def health_check() -> dict[str, str]:
    """Basic liveness check — confirms the API is running."""
    return {
        "status": "healthy",
        "service": "uniserve-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness check — confirms the API and database are operational."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error("Database readiness check failed", error=str(exc))
        db_status = "disconnected"

    return {
        "status": "ready" if db_status == "connected" else "degraded",
        "service": "uniserve-api",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
