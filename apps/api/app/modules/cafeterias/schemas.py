"""Cafeteria module — Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.cafeterias.models import CafeteriaType, OperationalStatus

# ---- Request Schemas ----


class CafeteriaCreateRequest(BaseModel):
    """Request to create a new cafeteria (admin only)."""

    name: str = Field(..., min_length=1, max_length=255)
    type: CafeteriaType
    description: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    location: str | None = None
    operating_hours: str | None = None
    timezone: str = Field("Asia/Karachi", max_length=50)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Basic timezone validation."""
        if "/" not in v and v not in ("UTC", "GMT"):
            raise ValueError(
                "Invalid timezone format. Expected format: Region/City (e.g., Asia/Karachi)"
            )
        return v


class CafeteriaUpdateRequest(BaseModel):
    """Request to update cafeteria details (admin only)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    location: str | None = None
    operating_hours: str | None = None
    timezone: str | None = Field(None, max_length=50)
    is_active: bool | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None and "/" not in v and v not in ("UTC", "GMT"):
            raise ValueError("Invalid timezone format")
        return v


class OperationalStatusUpdateRequest(BaseModel):
    """Request to update cafeteria operational status (manager/admin)."""

    status: OperationalStatus


# ---- Response Schemas ----


class CafeteriaResponse(BaseModel):
    """Cafeteria detail response."""

    id: str
    name: str
    type: CafeteriaType
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    operating_hours: str | None = None
    timezone: str
    operational_status: OperationalStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CafeteriaListResponse(BaseModel):
    """List of cafeterias."""

    cafeterias: list[CafeteriaResponse]
    total: int
