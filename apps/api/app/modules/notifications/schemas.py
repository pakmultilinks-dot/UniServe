"""Notification API schemas — request/response models for the notifications endpoints."""

from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Single notification as returned by the API."""

    id: str
    notification_type: str
    title: str
    body: str
    order_id: str | None = None
    cafeteria_id: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    is_read: bool
    delivery_status: str
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread notification count."""

    unread_count: int


class MarkReadResponse(BaseModel):
    """Response after marking a notification as read."""

    id: str
    is_read: bool
    read_at: datetime


class MarkAllReadResponse(BaseModel):
    """Response after marking all notifications as read."""

    marked_count: int
