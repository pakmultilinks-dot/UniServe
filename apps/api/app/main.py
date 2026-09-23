"""UniServe — University Cafeteria Management API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    AccountLockedError,
    AccountSuspendedError,
    AlreadyExistsException,
    AuthenticationError,
    AuthorizationError,
    EmailNotVerifiedError,
    NotFoundException,
    OTPError,
    PINError,
    PINLockedError,
    RateLimitError,
    TokenExpiredError,
    TokenRevokedError,
    UniServeException,
    ValidationError,
)
from app.core.logging import setup_logging

logger = structlog.get_logger()


# ---- Exception → HTTP status mapping ----

_EXCEPTION_STATUS_MAP: dict[type[UniServeException], int] = {
    NotFoundException: 404,
    AlreadyExistsException: 409,
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    AccountLockedError: 423,
    AccountSuspendedError: 403,
    EmailNotVerifiedError: 403,
    TokenExpiredError: 401,
    TokenRevokedError: 401,
    OTPError: 400,
    RateLimitError: 429,
    PINError: 400,
    PINLockedError: 423,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown events."""
    setup_logging()
    logger.info("Starting UniServe API", env=settings.APP_ENV)

    # Startup
    yield

    # Shutdown
    logger.info("Shutting down UniServe API")
    await engine.dispose()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        description="University Cafeteria Management and Online Ordering API",
        version="0.1.0",
        docs_url="/api/docs" if settings.APP_DEBUG else None,
        redoc_url="/api/redoc" if settings.APP_DEBUG else None,
        openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # ---- Global exception handler for UniServe exceptions ----
    @application.exception_handler(UniServeException)
    async def uniserve_exception_handler(request: Request, exc: UniServeException) -> JSONResponse:
        """Convert UniServe exceptions to structured JSON responses.

        Never leaks internal details — only returns the safe message and code.
        """
        status = _EXCEPTION_STATUS_MAP.get(type(exc), 400)
        logger.warning(
            "UniServe exception",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
            method=request.method,
            status_code=status,
        )
        return JSONResponse(
            status_code=status,
            content={"detail": exc.message, "code": exc.code},
        )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_application()
