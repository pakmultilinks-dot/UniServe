"""Health check endpoint.

Provides basic health and readiness checks for the API.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Response
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
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness check — confirms the API, database connectivity AND schema.

    Phase 28A rehearsal demonstrated that `SELECT 1` alone stays successful
    after the database schema has been wiped while the server is alive, so a
    disaster state could still be reported as "ready". The readiness probe
    therefore also queries the core `users` table — created by both the
    Alembic migrations (0001) and metadata.create_all, in every environment
    the API actually runs in — so monitoring can distinguish "connected" from
    "operational". A wiped or never-migrated database fails this probe and is
    reported as degraded.
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error("Database readiness check failed", error=str(exc))
        response.status_code = 503
        return {
            "status": "degraded",
            "service": "uniserve-api",
            "database": "disconnected",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    try:
        await db.execute(text("SELECT 1 FROM users LIMIT 1"))
        schema_status = "present"
    except Exception as exc:
        logger.error(
            "Schema readiness check failed (core tables missing)", error=str(exc)
        )
        schema_status = "missing"

    if schema_status != "present":
        response.status_code = 503

    return {
        "status": "ready" if schema_status == "present" else "degraded",
        "service": "uniserve-api",
        "database": db_status,
        "schema": schema_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }
