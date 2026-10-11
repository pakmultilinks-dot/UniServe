"""Notification module — API endpoints for in-app notification management.

Endpoints:
- GET  /notifications            — List my notifications (paginated, optional unread filter)
- GET  /notifications/unread-count — Count of unread notifications
- PATCH /notifications/{id}/read  — Mark a single notification as read
- PATCH /notifications/read-all   — Mark all my notifications as read

Phase 50 — University Admin broadcast (all admin-only, RequireRole):
- POST /notifications/broadcast                 — Create + send an in-app broadcast
- GET  /notifications/broadcasts               — Broadcast history
- GET  /notifications/broadcasts/audience-count — Preview recipient count
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, RequireRole, get_current_user
from app.modules.notifications.schemas import (
    BroadcastAudience,
    BroadcastAudienceCountResponse,
    BroadcastCreateRequest,
    BroadcastListResponse,
    BroadcastResponse,
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.notifications.service import BroadcastService, NotificationService
from app.modules.users.models import Role

router = APIRouter()

# Phase 50 — broadcast endpoints are University Admin only (backend-enforced;
# the UI hiding them is never the security boundary).
_ADMIN_BROADCAST_ROLES = (Role.UNIVERSITY_ADMIN,)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Get the count of unread notifications for the current user."""
    svc = NotificationService(db)
    count = await svc.get_unread_count(user_id=auth.user.id)
    return UnreadCountResponse(unread_count=count)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False, description="Filter to unread notifications only"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """List notifications for the current user, newest first."""
    svc = NotificationService(db)
    notifications, total, unread_count = await svc.list_user_notifications(
        user_id=auth.user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(
    notification_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark a single notification as read."""
    svc = NotificationService(db)
    notification = await svc.mark_as_read(
        notification_id=notification_id,
        user_id=auth.user.id,
    )
    assert notification.read_at is not None, "mark_as_read must set read_at"
    return MarkReadResponse(
        id=notification.id,
        is_read=notification.is_read,
        read_at=notification.read_at,
    )


@router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
    """Mark all unread notifications as read for the current user."""
    svc = NotificationService(db)
    count = await svc.mark_all_as_read(user_id=auth.user.id)
    return MarkAllReadResponse(marked_count=count)


# ====================================================================
# Phase 50 — Admin broadcast (University Admin only)
# ====================================================================


@router.post("/broadcast", response_model=BroadcastResponse, status_code=201)
async def send_broadcast(
    body: BroadcastCreateRequest,
    response: Response,
    auth: AuthContext = Depends(RequireRole(*_ADMIN_BROADCAST_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> BroadcastResponse:
    """Create and send a real in-app broadcast to a supported audience.

    Recipients receive ordinary per-user Notification rows (type
    admin_announcement) in the existing notification center. Returns 201 on
    a new send; 200 with duplicate=true when the idempotency key was already
    sent (no new rows created).
    """
    svc = BroadcastService(db)
    broadcast, duplicate = await svc.create_broadcast(
        title=body.title,
        message=body.message,
        audience=body.audience,
        cafeteria_id=body.cafeteria_id,
        idempotency_key=body.idempotency_key,
        created_by=auth.user,
    )
    if duplicate:
        response.status_code = 200
    return BroadcastResponse(
        id=broadcast.id,
        title=broadcast.title,
        message=broadcast.message,
        audience=broadcast.audience,
        cafeteria_id=broadcast.cafeteria_id,
        recipient_count=broadcast.recipient_count,
        created_at=broadcast.created_at,
        duplicate=duplicate,
    )


@router.get("/broadcasts", response_model=BroadcastListResponse)
async def list_broadcasts(
    limit: int = Query(20, ge=1, le=50, description="Max broadcasts to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    auth: AuthContext = Depends(RequireRole(*_ADMIN_BROADCAST_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> BroadcastListResponse:
    """Broadcast history — newest first (University Admin only)."""
    svc = BroadcastService(db)
    broadcasts, total = await svc.list_broadcasts(limit=limit, offset=offset)
    items = [
        BroadcastResponse(
            id=b.id,
            title=b.title,
            message=b.message,
            audience=b.audience,
            cafeteria_id=b.cafeteria_id,
            recipient_count=b.recipient_count,
            created_at=b.created_at,
            duplicate=False,
        )
        for b in broadcasts
    ]
    return BroadcastListResponse(items=items, total=total)


@router.get("/broadcasts/audience-count", response_model=BroadcastAudienceCountResponse)
async def get_broadcast_audience_count(
    audience: BroadcastAudience = Query(..., description="Audience to preview"),
    cafeteria_id: str | None = Query(None, description="Required iff audience='cafeteria'"),
    auth: AuthContext = Depends(RequireRole(*_ADMIN_BROADCAST_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> BroadcastAudienceCountResponse:
    """Preview how many active recipients an audience resolves to."""
    svc = BroadcastService(db)
    count = await svc.count_audience(audience=audience, cafeteria_id=cafeteria_id)
    return BroadcastAudienceCountResponse(
        audience=audience.value,
        cafeteria_id=cafeteria_id,
        recipient_count=count,
    )
