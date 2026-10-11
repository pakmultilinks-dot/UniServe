"""Notification API schemas — request/response models for the notifications endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# Phase 50 — Admin broadcast
# ---------------------------------------------------------------------------


class BroadcastAudience(str, Enum):
    """Supported broadcast audiences.

    Targeting is resolved server-side against active, non-deleted users:
    - all_users: every active user (any role)
    - <role> values: users with that exact role
    - cafeteria: active users assigned to the given cafeteria
      (CafeteriaAssignment — cafeteria managers/staff)
    """

    ALL_USERS = "all_users"
    STUDENTS = "students"
    FACULTY = "faculty"
    CAFETERIA_STAFF = "cafeteria_staff"
    CAFETERIA_MANAGERS = "cafeteria_managers"
    UNIVERSITY_ADMINS = "university_admins"
    CAFETERIA = "cafeteria"


class BroadcastCreateRequest(BaseModel):
    """Request to send a University Admin broadcast (in-app announcement)."""

    title: str = Field(..., min_length=1, max_length=255, description="Notification title")
    message: str = Field(..., min_length=1, max_length=5000, description="Notification message body")
    audience: BroadcastAudience = Field(..., description="Target audience")
    cafeteria_id: str | None = Field(
        None, max_length=36, description="Required iff audience='cafeteria'; rejected otherwise"
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique key to prevent duplicate broadcasts (payments convention)",
    )


class BroadcastResponse(BaseModel):
    """Result of a broadcast send — truthful only after backend persistence."""

    id: str
    title: str
    message: str
    audience: str
    cafeteria_id: str | None = None
    recipient_count: int
    created_at: datetime
    duplicate: bool = False

    model_config = {"from_attributes": True}


class BroadcastListResponse(BaseModel):
    """Paginated broadcast history (University Admin only)."""

    items: list[BroadcastResponse]
    total: int


class BroadcastAudienceCountResponse(BaseModel):
    """Preview: how many active recipients an audience currently resolves to."""

    audience: str
    cafeteria_id: str | None = None
    recipient_count: int
