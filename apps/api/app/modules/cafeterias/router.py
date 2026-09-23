"""Cafeterias module — API endpoints for cafeteria management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireCafeteriaScope,
    RequireRole,
)
from app.modules.cafeterias.models import CafeteriaType
from app.modules.cafeterias.schemas import (
    CafeteriaCreateRequest,
    CafeteriaListResponse,
    CafeteriaResponse,
    CafeteriaUpdateRequest,
    OperationalStatusUpdateRequest,
)
from app.modules.cafeterias.service import CafeteriaService
from app.modules.users.models import Role

router = APIRouter()


# ---- Create Cafeteria (Admin only) ----


@router.post("/", response_model=CafeteriaResponse, status_code=201)
async def create_cafeteria(
    body: CafeteriaCreateRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaResponse:
    """Create a new cafeteria (university admin only)."""
    service = CafeteriaService(db)
    cafeteria = await service.create_cafeteria(
        name=body.name,
        cafeteria_type=body.type,
        description=body.description,
        phone=body.phone,
        email=body.email,
        location=body.location,
        operating_hours=body.operating_hours,
        timezone=body.timezone,
    )
    return CafeteriaResponse.model_validate(cafeteria)


# ---- List Cafeterias ----


@router.get("/", response_model=CafeteriaListResponse)
async def list_cafeterias(
    auth: AuthContext = Depends(
        RequireRole(
            Role.UNIVERSITY_ADMIN,
            Role.CAFETERIA_MANAGER,
            Role.CAFETERIA_STAFF,
            Role.STUDENT,
            Role.FACULTY,
        )
    ),
    db: AsyncSession = Depends(get_db),
    is_active: bool | None = None,
    cafeteria_type: CafeteriaType | None = None,
) -> CafeteriaListResponse:
    """List all cafeterias (authenticated users)."""
    service = CafeteriaService(db)
    cafeterias = await service.list_cafeterias(
        is_active=is_active,
        cafeteria_type=cafeteria_type,
    )
    return CafeteriaListResponse(
        cafeterias=[CafeteriaResponse.model_validate(c) for c in cafeterias],
        total=len(cafeterias),
    )


# ---- Get Cafeteria ----


@router.get("/{cafeteria_id}", response_model=CafeteriaResponse)
async def get_cafeteria(
    cafeteria_id: str,
    auth: AuthContext = Depends(RequireCafeteriaScope()),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaResponse:
    """Get a cafeteria by ID (cafeteria-scoped access)."""
    service = CafeteriaService(db)
    cafeteria = await service.get_cafeteria(cafeteria_id)
    return CafeteriaResponse.model_validate(cafeteria)


# ---- Update Cafeteria (Admin only) ----


@router.put("/{cafeteria_id}", response_model=CafeteriaResponse)
async def update_cafeteria(
    cafeteria_id: str,
    body: CafeteriaUpdateRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaResponse:
    """Update cafeteria details (university admin only)."""
    service = CafeteriaService(db)
    cafeteria = await service.update_cafeteria(
        cafeteria_id,
        name=body.name,
        description=body.description,
        phone=body.phone,
        email=body.email,
        location=body.location,
        operating_hours=body.operating_hours,
        timezone=body.timezone,
        is_active=body.is_active,
    )
    return CafeteriaResponse.model_validate(cafeteria)


# ---- Update Operational Status (Manager/Admin) ----


@router.patch("/{cafeteria_id}/status", response_model=CafeteriaResponse)
async def update_operational_status(
    cafeteria_id: str,
    body: OperationalStatusUpdateRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> CafeteriaResponse:
    """Update cafeteria operational status (manager/admin only)."""
    service = CafeteriaService(db)
    cafeteria = await service.update_operational_status(
        cafeteria_id,
        body.status,
    )
    return CafeteriaResponse.model_validate(cafeteria)
