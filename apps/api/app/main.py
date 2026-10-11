"""UniServe — University Cafeteria Management API."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders

from app.api.router import api_router
from app.core.config import settings
from app.core.database import async_session_factory, engine
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
    ServiceUnavailableError,
    TokenExpiredError,
    TokenRevokedError,
    UniServeException,
    ValidationError,
)
from app.core.logging import setup_logging

logger = structlog.get_logger()

# Background worker interval in seconds (configurable)
_PICKUP_CHECK_INTERVAL = 60


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
    ServiceUnavailableError: 503,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown events."""
    setup_logging()
    logger.info("Starting UniServe API", env=settings.APP_ENV)

    # --- Background worker: automatic pickup expiry processing ---
    _shutdown_event = asyncio.Event()

    async def _pickup_expiry_worker() -> None:
        """Periodically process expired pickup deadlines.

        Runs every _PICKUP_CHECK_INTERVAL seconds until shutdown.
        Creates its own DB session to avoid leaking request-scoped state.
        """
        while not _shutdown_event.is_set():
            try:
                async with async_session_factory() as session:
                    from app.modules.orders.service import OrderService

                    service = OrderService(session)
                    stats = await service.process_expired_pickups()
                    await session.commit()
                    logger.debug(
                        "pickup_expiry_worker_tick",
                        **stats,
                    )
            except Exception:
                logger.exception("pickup_expiry_worker_error")
            # Wait for the interval or until shutdown is signalled
            try:
                await asyncio.wait_for(
                    _shutdown_event.wait(),
                    timeout=_PICKUP_CHECK_INTERVAL,
                )
                break  # Shutdown signalled
            except TimeoutError:
                pass  # Normal timeout — continue loop

    pickup_task = asyncio.create_task(_pickup_expiry_worker())
    logger.info("pickup_expiry_worker_started", interval=_PICKUP_CHECK_INTERVAL)

    # Startup complete
    yield

    # --- Shutdown: stop background worker ---
    logger.info("Shutting down UniServe API")
    _shutdown_event.set()
    pickup_task.cancel()
    with suppress(asyncio.CancelledError):
        await pickup_task
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

    # Security-headers middleware — defence-in-depth hardening for the static
    # food-image server (finding: served images lacked X-Content-Type-Options).
    # Pure ASGI middleware (safe with StaticFiles FileResponse streaming, which is
    # why BaseHTTPMiddleware is avoided). Adds nosniff to every response.
    # NOTE: the `Server: uvicorn` banner is injected by uvicorn's transport layer
    # (default_headers) AFTER the app returns, so it cannot be removed here — it is
    # classified as a low-risk INFO limitation instead (not a fake "fix").
    class SecurityHeadersMiddleware:
        """Pure ASGI middleware injecting X-Content-Type-Options: nosniff."""

        def __init__(self, app) -> None:
            self.app = app

        async def __call__(self, scope, receive, send) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            async def send_with_headers(message) -> None:
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(scope=message)
                    if "X-Content-Type-Options" not in headers:
                        headers["X-Content-Type-Options"] = "nosniff"
                await send(message)

            await self.app(scope, receive, send_with_headers)

    application.add_middleware(SecurityHeadersMiddleware)

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

    # Static files — food images served from app/static/food/
    import os as _os
    _static_dir = _os.path.join(_os.path.dirname(__file__), "static")
    if _os.path.isdir(_static_dir):
        application.mount("/api/v1/static", StaticFiles(directory=_static_dir), name="static")

    return application


app = create_application()
