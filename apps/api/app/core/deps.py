"""FastAPI dependency injection for authentication and authorization.

Provides reusable dependencies for:
- Current user extraction from JWT
- Role-based access control
- Cafeteria scope enforcement
"""

from dataclasses import dataclass

import structlog
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.core.audit import AuditEventType, log_audit_event
from app.core.database import get_db
from app.core.exceptions import (
    AccountSuspendedError,
    AuthenticationError,
    AuthorizationError,
    TokenRevokedError,
)
from app.core.security import decode_token
from app.modules.cafeterias.models import CafeteriaType
from app.modules.users.models import (
    AccountStatus,
    CafeteriaAssignment,
    Role,
    User,
    UserSession,
)

logger = structlog.get_logger(__name__)


@dataclass
class AuthContext:
    """Authenticated user context.

    Contains the current user and their session information.
    This is the primary dependency for authenticated endpoints.
    """

    user: User
    session_id: str
    refresh_token_jti: str
    ip_address: str | None = None
    user_agent: str | None = None


async def _extract_token(authorization: str | None = Header(None)) -> str:
    """Extract Bearer token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header format")
    return authorization[7:]


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> AuthContext:
    """Extract and validate the current authenticated user.

    This is the main authentication dependency. It:
    1. Extracts the JWT from the Authorization header
    2. Validates the token
    3. Loads the user from the database
    4. Verifies the session is active
    5. Returns the AuthContext with user and session info
    """
    # Extract token
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header")

    token = authorization[7:]

    # Decode token
    payload = decode_token(token)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    # Verify token type
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    # Extract session ID
    session_id = payload.get("sid")
    if not session_id:
        raise AuthenticationError("Token missing session identifier")

    # Load user
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token subject")

    # Polling endpoints need identity/status and one active session, not the
    # password/PIN hashes and every historical session on each request.
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(raiseload(User.credential), raiseload(User.sessions))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    # Check account status
    if user.status == AccountStatus.SUSPENDED:
        raise AccountSuspendedError()
    if user.status == AccountStatus.DELETED:
        raise AuthenticationError("Account no longer exists")
    if user.status == AccountStatus.PENDING_VERIFICATION:
        raise AuthenticationError("Email not verified")

    # Verify session is active
    session_result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
            UserSession.is_active == True,
        )
    )
    session = session_result.scalar_one_or_none()

    if session is None:
        raise TokenRevokedError("Session has been revoked")

    # Extract request info
    ip_address = None
    user_agent_str = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent_str = request.headers.get("user-agent")

    return AuthContext(
        user=user,
        session_id=session.id,
        refresh_token_jti=session.refresh_token_jti,
        ip_address=ip_address,
        user_agent=user_agent_str,
    )


class RequireRole:
    """Dependency factory for role-based access control.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(RequireRole(Role.UNIVERSITY_ADMIN))])
        async def admin_endpoint():
            ...
    """

    def __init__(self, *allowed_roles: Role):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        auth: AuthContext = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        if auth.user.role not in self.allowed_roles:
            # Log authorization failure
            await log_audit_event(
                session=db,
                event_type=AuditEventType.AUTHORIZATION_FAILED,
                user_id=auth.user.id,
                description=f"Required roles: {[r.value for r in self.allowed_roles]}, actual: {auth.user.role.value}",
                ip_address=auth.ip_address,
                user_agent=auth.user_agent,
            )
            raise AuthorizationError(
                f"This action requires one of the following roles: "
                f"{', '.join(r.value for r in self.allowed_roles)}"
            )
        return auth


class RequireCafeteriaWriteScope:
    """Dependency combining role check + cafeteria scope for write operations.

    Enforces that:
    1. The user has one of the allowed roles (admin, manager, or staff).
    2. Managers/staff are assigned to the target cafeteria.
    3. Students and faculty can never perform mutations.

    Usage:
        @router.post("/cafeterias/{cafeteria_id}/items/",
            dependencies=[Depends(RequireCafeteriaWriteScope(
                Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER))])
        async def create_item(cafeteria_id: str):
            ...
    """

    def __init__(self, *allowed_roles: Role) -> None:
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        cafeteria_id: str,
        auth: AuthContext = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        # 1. Role check
        if auth.user.role not in self.allowed_roles:
            await log_audit_event(
                session=db,
                event_type=AuditEventType.AUTHORIZATION_FAILED,
                user_id=auth.user.id,
                description=(
                    f"Write access denied — required roles: "
                    f"{[r.value for r in self.allowed_roles]}, "
                    f"actual: {auth.user.role.value}"
                ),
                ip_address=auth.ip_address,
                user_agent=auth.user_agent,
            )
            raise AuthorizationError(
                f"This action requires one of the following roles: "
                f"{', '.join(r.value for r in self.allowed_roles)}"
            )

        # 2. University Admin has universal write access
        if auth.user.role == Role.UNIVERSITY_ADMIN:
            return auth

        # 3. Manager/Staff must be assigned to the target cafeteria
        if auth.user.role in (Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF):
            result = await db.execute(
                select(CafeteriaAssignment).where(
                    CafeteriaAssignment.user_id == auth.user.id,
                    CafeteriaAssignment.cafeteria_id == cafeteria_id,
                )
            )
            if result.scalar_one_or_none() is None:
                await log_audit_event(
                    session=db,
                    event_type=AuditEventType.AUTHORIZATION_FAILED,
                    user_id=auth.user.id,
                    description=(f"Write denied — not assigned to cafeteria: {cafeteria_id}"),
                    ip_address=auth.ip_address,
                    user_agent=auth.user_agent,
                )
                raise AuthorizationError("You are not assigned to this cafeteria")
            return auth

        # 4. Students and Faculty should never reach write endpoints
        raise AuthorizationError("Insufficient permissions for this action")


class RequireCafeteriaScope:
    """Dependency for cafeteria-scoped access control.

    Verifies that the authenticated user has access to the specified cafeteria.
    This enforces the cafeteria isolation rules:
    - Students: Student Cafeteria only
    - Faculty: Both cafeterias
    - Staff/Manager: Assigned cafeteria only
    - University Admin: All cafeterias

    Usage:
        @router.get("/cafeteria/{cafeteria_id}/menu",
            dependencies=[Depends(RequireCafeteriaScope())])
        async def get_menu(cafeteria_id: str):
            ...
    """

    async def __call__(
        self,
        cafeteria_id: str,
        auth: AuthContext = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        from app.modules.cafeterias.models import Cafeteria

        # Load cafeteria
        result = await db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria_id))
        cafeteria = result.scalar_one_or_none()

        if cafeteria is None:
            from app.core.exceptions import NotFoundException

            raise NotFoundException("Cafeteria", cafeteria_id)

        # University Admin has access to all cafeterias
        if auth.user.role == Role.UNIVERSITY_ADMIN:
            return auth

        # Check cafeteria type rules
        if cafeteria.type == CafeteriaType.FACULTY:
            # Faculty Cafeteria: only Faculty can access
            if auth.user.category.value != "faculty":
                await log_audit_event(
                    session=db,
                    event_type=AuditEventType.AUTHORIZATION_FAILED,
                    user_id=auth.user.id,
                    description=f"Attempted to access Faculty Cafeteria: {cafeteria_id}",
                    ip_address=auth.ip_address,
                    user_agent=auth.user_agent,
                )
                raise AuthorizationError(
                    "Access to Faculty Cafeteria is restricted to faculty members"
                )
        elif cafeteria.type == CafeteriaType.STUDENT:
            # Student Cafeteria: both students and faculty can access
            pass

        # Check if staff/manager is assigned to this cafeteria
        if auth.user.role in (Role.CAFETERIA_STAFF, Role.CAFETERIA_MANAGER):
            assignment_result = await db.execute(
                select(CafeteriaAssignment).where(
                    CafeteriaAssignment.user_id == auth.user.id,
                    CafeteriaAssignment.cafeteria_id == cafeteria_id,
                )
            )
            assignment = assignment_result.scalar_one_or_none()
            if assignment is None:
                await log_audit_event(
                    session=db,
                    event_type=AuditEventType.AUTHORIZATION_FAILED,
                    user_id=auth.user.id,
                    description=f"Staff/Manager not assigned to cafeteria: {cafeteria_id}",
                    ip_address=auth.ip_address,
                    user_agent=auth.user_agent,
                )
                raise AuthorizationError("You are not assigned to this cafeteria")

        return auth


# Convenience dependencies
require_admin = RequireRole(Role.UNIVERSITY_ADMIN)
require_manager = RequireRole(Role.CAFETERIA_MANAGER)
require_staff = RequireRole(Role.CAFETERIA_STAFF)
require_manager_or_staff = RequireRole(Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF)
require_manager_or_admin = RequireRole(Role.CAFETERIA_MANAGER, Role.UNIVERSITY_ADMIN)
require_authenticated = Depends(get_current_user)


async def verify_resource_cafeteria(
    *,
    resource_cafeteria_id: str,
    expected_cafeteria_id: str,
    resource_type: str,
    db: AsyncSession,
    auth: AuthContext | None = None,
) -> None:
    """Verify that a resource belongs to the expected cafeteria.

    Call this in endpoints that accept a resource ID (e.g. menu_item_id)
    to ensure the resource was not created under a different cafeteria
    than the one the user is authorized to manage.

    Raises AuthorizationError if the cafeteria IDs do not match.
    """
    if resource_cafeteria_id != expected_cafeteria_id:
        if auth is not None:
            await log_audit_event(
                session=db,
                event_type=AuditEventType.AUTHORIZATION_FAILED,
                user_id=auth.user.id,
                description=(
                    f"{resource_type} ownership mismatch — "
                    f"resource belongs to cafeteria {resource_cafeteria_id}, "
                    f"expected {expected_cafeteria_id}"
                ),
                ip_address=auth.ip_address,
                user_agent=auth.user_agent,
            )
        raise AuthorizationError(
            f"This {resource_type.lower()} does not belong to the specified cafeteria"
        )
