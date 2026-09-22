"""Users module — API endpoints for user management.

Admin and Manager operations for user lifecycle management.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditEventType, log_audit_event
from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    RequireRole,
    get_current_user,
)
from app.core.exceptions import (
    AlreadyExistsException,
    AuthorizationError,
    NotFoundException,
    ValidationError,
)
from app.core.security import generate_otp, hash_password
from app.modules.auth.schemas import (
    AccountRecoveryRequest,
    AuthResponse,
    ChangeUserRoleRequest,
    CreateUserByAdminRequest,
    CreateUserResponse,
    SuspendUserRequest,
    UserSummary,
)
from app.modules.users.models import (
    AccountStatus,
    CafeteriaAssignment,
    Role,
    User,
    UserCategory,
    UserCredential,
)

router = APIRouter()


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


# ---- List Users (Admin only) ----


@router.get("/", response_model=list[UserSummary])
async def list_users(
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
    role: str | None = None,
    status: str | None = None,
):
    """List all users (university admin only)."""
    query = select(User).where(User.status != AccountStatus.DELETED)
    if role:
        query = query.where(User.role == Role(role))
    if status:
        query = query.where(User.status == AccountStatus(status))
    query = query.order_by(User.created_at.desc())
    result = await db.execute(query)
    return [UserSummary.model_validate(u) for u in result.scalars().all()]


# ---- Get User ----


@router.get("/{user_id}", response_model=UserSummary)
async def get_user(
    user_id: str,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Get user details (university admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User", user_id)
    return UserSummary.model_validate(user)


# ---- Create User (Admin/Manager) ----


@router.post("/", response_model=CreateUserResponse, status_code=201)
async def create_user(
    request: Request,
    body: CreateUserByAdminRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin/manager).

    Managers can only create staff within their assigned cafeteria.
    University Admin can create any user type.
    """
    ip, ua = _get_client_info(request)

    # Role-based restrictions
    if auth.user.role == Role.CAFETERIA_MANAGER:
        if body.role == Role.UNIVERSITY_ADMIN:
            raise AuthorizationError("Managers cannot create University Admin accounts")
        if body.role in (Role.STUDENT, Role.FACULTY):
            raise AuthorizationError("Managers cannot create student or faculty accounts")
        if body.role in (Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF):
            if not body.cafeteria_id:
                raise ValidationError("cafeteria_id is required for staff/manager roles")
            # Verify manager is assigned to this cafeteria
            assignment_result = await db.execute(
                select(CafeteriaAssignment).where(
                    CafeteriaAssignment.user_id == auth.user.id,
                    CafeteriaAssignment.cafeteria_id == body.cafeteria_id,
                )
            )
            if not assignment_result.scalar_one_or_none():
                raise AuthorizationError("You are not assigned to this cafeteria")

    # Check duplicate university ID
    existing_id = await db.execute(select(User).where(User.university_id == body.university_id))
    if existing_id.scalar_one_or_none():
        raise AlreadyExistsException("User with this University ID")

    # Check duplicate email
    existing_email = await db.execute(
        select(User).where(User.university_email == body.university_email.lower().strip())
    )
    if existing_email.scalar_one_or_none():
        raise AlreadyExistsException("User with this email")

    # Determine category from role
    category_map = {
        Role.STUDENT: UserCategory.STUDENT,
        Role.FACULTY: UserCategory.FACULTY,
        Role.CAFETERIA_STAFF: UserCategory.FACULTY,  # Default for staff
        Role.CAFETERIA_MANAGER: UserCategory.FACULTY,
        Role.UNIVERSITY_ADMIN: UserCategory.FACULTY,
    }
    category = category_map.get(body.role, UserCategory.FACULTY)

    # Create user (auto-verified since created by admin)
    user = User(
        first_name=body.first_name,
        last_name=body.last_name,
        university_id=body.university_id,
        university_email=body.university_email.lower().strip(),
        category=category,
        role=body.role,
        status=AccountStatus.ACTIVE,
        email_verified=True,
    )
    db.add(user)
    await db.flush()

    # Generate temporary password
    temp_password = generate_otp() + "Aa1!"  # Temporary password meeting requirements
    credential = UserCredential(
        user_id=user.id,
        password_hash=hash_password(temp_password),
        password_changed_at=datetime.now(UTC),
    )
    db.add(credential)

    # Assign cafeteria if needed
    if body.cafeteria_id and body.role in (Role.CAFETERIA_STAFF, Role.CAFETERIA_MANAGER):
        assignment = CafeteriaAssignment(
            user_id=user.id,
            cafeteria_id=body.cafeteria_id,
            role=body.role,
            assigned_by=auth.user.id,
        )
        db.add(assignment)

    await log_audit_event(
        session=db,
        event_type=AuditEventType.USER_REGISTERED,
        user_id=user.id,
        description=f"User created by {auth.user.role.value}: {user.university_email}",
        ip_address=ip,
        user_agent=ua,
    )

    return CreateUserResponse(
        user=UserSummary.model_validate(user),
        temporary_password=temp_password,
    )


# ---- Suspend User ----


@router.post("/{user_id}/suspend", response_model=UserSummary)
async def suspend_user(
    request: Request,
    user_id: str,
    body: SuspendUserRequest,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """Suspend a user account."""
    ip, ua = _get_client_info(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User", user_id)

    # Managers can only suspend users within their cafeteria
    if auth.user.role == Role.CAFETERIA_MANAGER:
        if user.role in (Role.UNIVERSITY_ADMIN, Role.CAFETERIA_MANAGER):
            raise AuthorizationError("Managers cannot suspend other managers or admins")
        # Check if staff is in manager's cafeteria
        if user.role == Role.CAFETERIA_STAFF:
            assignment_result = await db.execute(
                select(CafeteriaAssignment).where(
                    CafeteriaAssignment.user_id == user.id,
                )
            )
            assignment = assignment_result.scalar_one_or_none()
            if not assignment:
                raise AuthorizationError("Cannot suspend users outside your cafeteria")

            # Verify manager's cafeteria
            manager_assignment = await db.execute(
                select(CafeteriaAssignment).where(
                    CafeteriaAssignment.user_id == auth.user.id,
                    CafeteriaAssignment.cafeteria_id == assignment.cafeteria_id,
                )
            )
            if not manager_assignment.scalar_one_or_none():
                raise AuthorizationError("Cannot suspend users outside your cafeteria")

    user.status = AccountStatus.SUSPENDED

    # Revoke all active sessions
    from sqlalchemy import update

    from app.modules.users.models import UserSession

    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_active == True)
        .values(is_active=False, revoked_at=datetime.now(UTC))
    )

    await log_audit_event(
        session=db,
        event_type=AuditEventType.ACCOUNT_SUSPENDED,
        user_id=user_id,
        description=f"Account suspended by {auth.user.role.value}. Reason: {body.reason}",
        ip_address=ip,
        user_agent=ua,
    )

    return UserSummary.model_validate(user)


# ---- Activate User ----


@router.post("/{user_id}/activate", response_model=UserSummary)
async def activate_user(
    request: Request,
    user_id: str,
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Activate a suspended user account (admin only)."""
    ip, ua = _get_client_info(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User", user_id)

    user.status = AccountStatus.ACTIVE

    await log_audit_event(
        session=db,
        event_type=AuditEventType.ACCOUNT_ACTIVATED,
        user_id=user_id,
        description=f"Account activated by {auth.user.role.value}",
        ip_address=ip,
        user_agent=ua,
    )

    return UserSummary.model_validate(user)


# ---- Delete Account (Self) ----


@router.delete("/me", status_code=204)
async def delete_own_account(
    request: Request,
    password: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request account deletion (self-service)."""
    ip, ua = _get_client_info(request)

    # Verify password
    from sqlalchemy import select

    from app.core.security import verify_password
    from app.modules.users.models import UserCredential

    cred_result = await db.execute(
        select(UserCredential).where(UserCredential.user_id == auth.user.id)
    )
    credential = cred_result.scalar_one_or_none()
    if not credential or not credential.password_hash:
        raise AuthorizationError("Invalid password")
    if not verify_password(password, credential.password_hash):
        raise AuthorizationError("Invalid password")

    # Soft delete
    auth.user.status = AccountStatus.DELETED
    auth.user.deleted_at = datetime.now(UTC)

    # Revoke all sessions
    from sqlalchemy import update

    from app.modules.users.models import UserSession

    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == auth.user.id, UserSession.is_active == True)
        .values(is_active=False, revoked_at=datetime.now(UTC))
    )

    await log_audit_event(
        session=db,
        event_type=AuditEventType.ACCOUNT_DELETED,
        user_id=auth.user.id,
        description="Account deleted by user",
        ip_address=ip,
        user_agent=ua,
    )


# ---- Change User Role (Admin only) ----


@router.put("/{user_id}/role", response_model=UserSummary)
async def change_user_role(
    request: Request,
    user_id: str,
    body: "ChangeUserRoleRequest",
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role (university admin only).

    Managers and staff require a cafeteria_id assignment.
    """

    ip, ua = _get_client_info(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User", user_id)

    # Prevent changing own role
    if user.id == auth.user.id:
        raise AuthorizationError("Cannot change your own role")

    old_role = user.role
    user.role = body.role

    # Update category to match new role
    if body.role in (Role.STUDENT,):
        user.category = UserCategory.STUDENT
    elif body.role in (
        Role.FACULTY,
        Role.CAFETERIA_STAFF,
        Role.CAFETERIA_MANAGER,
        Role.UNIVERSITY_ADMIN,
    ):
        user.category = UserCategory.FACULTY

    # Handle cafeteria assignment for staff/manager roles
    if body.role in (Role.CAFETERIA_STAFF, Role.CAFETERIA_MANAGER):
        if not body.cafeteria_id:
            raise ValidationError("cafeteria_id is required for staff/manager roles")

        # Verify cafeteria exists
        from app.modules.cafeterias.models import Cafeteria

        caf_result = await db.execute(select(Cafeteria).where(Cafeteria.id == body.cafeteria_id))
        if not caf_result.scalar_one_or_none():
            raise NotFoundException("Cafeteria", body.cafeteria_id)

        # Remove existing assignment if any
        existing = await db.execute(
            select(CafeteriaAssignment).where(CafeteriaAssignment.user_id == user_id)
        )
        existing_assignment = existing.scalar_one_or_none()
        if existing_assignment:
            existing_assignment.cafeteria_id = body.cafeteria_id
            existing_assignment.role = body.role
        else:
            assignment = CafeteriaAssignment(
                user_id=user_id,
                cafeteria_id=body.cafeteria_id,
                role=body.role,
                assigned_by=auth.user.id,
            )
            db.add(assignment)
    elif body.role in (Role.STUDENT, Role.FACULTY, Role.UNIVERSITY_ADMIN):
        # Remove cafeteria assignment for non-staff/manager roles
        existing = await db.execute(
            select(CafeteriaAssignment).where(CafeteriaAssignment.user_id == user_id)
        )
        existing_assignment = existing.scalar_one_or_none()
        if existing_assignment:
            await db.delete(existing_assignment)

    await log_audit_event(
        session=db,
        event_type=AuditEventType.ROLE_CHANGED,
        user_id=user_id,
        description=f"Role changed from {old_role.value} to {body.role.value} by {auth.user.role.value}",
        ip_address=ip,
        user_agent=ua,
    )

    return UserSummary.model_validate(user)


# ---- Account Recovery (Admin only) ----


@router.post("/{user_id}/recover", response_model=AuthResponse)
async def recover_account(
    request: Request,
    user_id: str,
    body: "AccountRecoveryRequest",
    auth: AuthContext = Depends(RequireRole(Role.UNIVERSITY_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Admin-assisted account recovery.

    Resets the user's failed-attempt counters and unlocks the account
    if it was locked due to too many failed login or PIN attempts.
    """
    from app.modules.users.models import UserCredential

    ip, ua = _get_client_info(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User", user_id)

    # Verify university_id matches
    if user.university_id != body.university_id:
        raise ValidationError("University ID does not match the target user")

    # Load credential and reset lockout fields
    cred_result = await db.execute(select(UserCredential).where(UserCredential.user_id == user_id))
    credential = cred_result.scalar_one_or_none()
    if credential:
        credential.password_failed_attempts = 0
        credential.password_locked_until = None
        credential.pin_failed_attempts = 0
        credential.pin_locked_until = None

    # If user was suspended, reactivate
    if user.status == AccountStatus.SUSPENDED:
        user.status = AccountStatus.ACTIVE

    await log_audit_event(
        session=db,
        event_type=AuditEventType.ACCOUNT_RECOVERED,
        user_id=user_id,
        description=f"Account recovered by admin {auth.user.university_email}. Reason: {body.reason}",
        ip_address=ip,
        user_agent=ua,
    )

    return AuthResponse(message=f"Account for {user.university_email} has been recovered")
