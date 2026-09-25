"""Notification module — API endpoints for in-app notification management.

Endpoints:
- GET  /notifications            — List my notifications (paginated, optional unread filter)
- GET  /notifications/unread-count — Count of unread notifications
- PATCH /notifications/{id}/read  — Mark a single notification as read
- PATCH /notifications/read-all   — Mark all my notifications as read
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, get_current_user
from app.modules.notifications.schemas import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.notifications.service import NotificationService

router = APIRouter()


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
