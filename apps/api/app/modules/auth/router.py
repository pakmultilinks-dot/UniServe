"""Auth module — API endpoints for authentication and authorization."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, get_current_user
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    LoginResponse,
    OTPResendRequest,
    OTPResponse,
    OTPVerifyRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PINChangeRequest,
    PINDisableRequest,
    PINLoginRequest,
    PINSetupRequest,
    ProfileUpdateRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    SessionListResponse,
    SessionResponse,
    TokenPair,
    UserSummary,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import CafeteriaAssignment, Role, User
from app.core.rate_limit import check_auth_rate_limit

router = APIRouter()


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract IP address and user agent from request."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


# ---- IP rate-limit guards (B15) ----
# Applied as dependencies so they run before the handler. Each returns
# None; they raise RateLimitError (429) when the IP is over the limit.

async def _limit_register(request: Request) -> None:
    check_auth_rate_limit(request, "otp_request")


async def _limit_otp_verify(request: Request) -> None:
    check_auth_rate_limit(request, "otp_verify")


async def _limit_otp_resend(request: Request) -> None:
    check_auth_rate_limit(request, "otp_request")


async def _limit_login(request: Request) -> None:
    check_auth_rate_limit(request, "login")


async def _limit_pin_login(request: Request) -> None:
    check_auth_rate_limit(request, "pin_login")


async def _limit_password_reset(request: Request) -> None:
    check_auth_rate_limit(request, "password_reset")


# ---- Registration ----


@router.post("/register", response_model=RegisterResponse, status_code=201,
             dependencies=[Depends(_limit_register)])
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new university user."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    user = await service.register(
        first_name=body.first_name,
        last_name=body.last_name,
        university_id=body.university_id,
        university_email=body.university_email,
        password=body.password,
        ip_address=ip,
        user_agent=ua,
    )
    return RegisterResponse(
        user_id=user.id,
        university_email=user.university_email,
        category=user.category,
    )


# ---- OTP ----


@router.post("/otp/verify", response_model=OTPResponse,
             dependencies=[Depends(_limit_otp_verify)])
async def verify_otp(
    body: OTPVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify an OTP code."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.verify_otp(
        user_id=body.user_id,
        otp=body.otp,
        purpose=body.purpose,
        ip_address=ip,
        user_agent=ua,
    )
    return OTPResponse(message=result["message"])


@router.post("/otp/resend", response_model=OTPResponse,
             dependencies=[Depends(_limit_otp_resend)])
async def resend_otp(
    body: OTPResendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resend an OTP code."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.resend_otp(
        user_id=body.user_id,
        purpose=body.purpose,
        ip_address=ip,
        user_agent=ua,
    )
    return OTPResponse(
        message=result["message"],
        expires_in_seconds=result.get("expires_in_seconds"),
    )


# ---- Login ----


@router.post("/login", response_model=LoginResponse,
             dependencies=[Depends(_limit_login)])
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login with university email and password."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    user, tokens = await service.login(
        email=body.university_email,
        password=body.password,
        ip_address=ip,
        user_agent=ua,
    )
    return LoginResponse(
        tokens=TokenPair(**tokens),
        user=UserSummary.model_validate(user),
    )


@router.post("/pin/login", response_model=LoginResponse,
             dependencies=[Depends(_limit_pin_login)])
async def pin_login(
    body: PINLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login with PIN (convenience authentication)."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    user, tokens = await service.pin_login(
        user_id=body.user_id,
        pin=body.pin,
        ip_address=ip,
        user_agent=ua,
    )
    return LoginResponse(
        tokens=TokenPair(**tokens),
        user=UserSummary.model_validate(user),
    )


# ---- Token Refresh ----


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using a valid refresh token."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    tokens = await service.refresh_tokens(
        refresh_token=body.refresh_token,
        ip_address=ip,
        user_agent=ua,
    )
    return TokenPair(**tokens)


# ---- Current User ----


@router.get("/me", response_model=UserSummary)
async def get_current_user_info(
    auth: AuthContext = Depends(get_current_user),
):
    """Get current authenticated user information."""
    return UserSummary.model_validate(auth.user)


@router.patch("/me", response_model=UserSummary)
async def update_current_user_info(
    body: ProfileUpdateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current authenticated user's own profile.

    Phase 55 — self-service profile editing. Accepts first/last name
    only; everything else about the account is immutable here. Strictly
    self-scoped: the target user is always the authenticated user.
    Returns the updated user summary so clients can refresh local state.
    """
    service = AuthService(db)
    user = await service.update_profile(
        user_id=auth.user.id,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    return UserSummary.model_validate(user)


@router.get("/me/cafeterias")
async def get_my_cafeterias(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the cafeteria IDs the current user is assigned to.

    P3-3 — lets the web console default cafeteria selectors to the
    staff member's / manager's actual assignment instead of an arbitrary
    first cafeteria from the unfiltered list.

    - University Admin: empty list (admin may select any cafeteria;
      there is no single "assigned" cafeteria).
    - Cafeteria staff / manager: their assigned cafeteria IDs.
    - Students / faculty: empty list (no dashboard assignments).

    Read-only, scoped strictly to the authenticated user's own
    assignments — it leaks nothing about other users or cafeterias
    beyond what GET /cafeterias already returns for these roles.
    """
    if auth.user.role in (Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF):
        result = await db.execute(
            select(CafeteriaAssignment.cafeteria_id).where(
                CafeteriaAssignment.user_id == auth.user.id
            )
        )
        cafeteria_ids = list(result.scalars().all())
    else:
        cafeteria_ids = []
    return {"cafeteria_ids": cafeteria_ids}


# ---- Sessions ----


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active sessions for the current user."""
    service = AuthService(db)
    sessions = await service.get_sessions(
        user_id=auth.user.id,
        current_session_id=auth.session_id,
    )
    return SessionListResponse(sessions=[SessionResponse(**s) for s in sessions])


# ---- Logout ----


@router.post("/logout", response_model=AuthResponse)
async def logout(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout from current device."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.logout(
        user_id=auth.user.id,
        session_id=auth.session_id,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])


@router.post("/logout-all", response_model=AuthResponse)
async def logout_all(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout from all devices."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.logout_all(
        user_id=auth.user.id,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])


# ---- Password ----


@router.post("/password/change", response_model=AuthResponse)
async def change_password(
    request: Request,
    body: PasswordChangeRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password (requires current password)."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.change_password(
        user_id=auth.user.id,
        current_password=body.current_password,
        new_password=body.new_password,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])


@router.post("/password/reset/request", response_model=AuthResponse,
             dependencies=[Depends(_limit_password_reset)])
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset OTP."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.request_password_reset(
        email=body.university_email,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])


@router.post("/password/reset/confirm", response_model=AuthResponse,
             dependencies=[Depends(_limit_password_reset)])
async def confirm_password_reset(
    body: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset with OTP."""
    ip, ua = _get_client_info(request)

    # Resolve user from email
    from sqlalchemy import select as sa_select

    user_result = await db.execute(
        sa_select(User).where(User.university_email == body.university_email.lower().strip())
    )
    user = user_result.scalar_one_or_none()
    if not user:
        # Anti-enumeration: the request endpoint always returns a generic
        # message, so the confirm endpoint must not reveal whether the email
        # exists either. Return the same generic shape without doing anything.
        return AuthResponse(
            message="If your email is registered and the code is valid, your password has been reset."
        )

    service = AuthService(db)
    reset_result = await service.reset_password(
        user_id=user.id,
        otp=body.otp,
        new_password=body.new_password,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=reset_result["message"])


# ---- PIN Management ----


@router.post("/pin/enable", response_model=AuthResponse)
async def enable_pin(
    request: Request,
    body: PINSetupRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable PIN authentication."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.enable_pin(
        user_id=auth.user.id,
        current_password=body.current_password,
        pin=body.pin,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])


@router.post("/pin/change", response_model=AuthResponse)
async def change_pin(
    request: Request,
    body: PINChangeRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change existing PIN."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.change_pin(
        user_id=auth.user.id,
        current_pin=body.current_pin,
        new_pin=body.new_pin,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])


@router.post("/pin/disable", response_model=AuthResponse)
async def disable_pin(
    request: Request,
    body: PINDisableRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable PIN authentication."""
    ip, ua = _get_client_info(request)
    service = AuthService(db)
    result = await service.disable_pin(
        user_id=auth.user.id,
        current_password=body.current_password,
        ip_address=ip,
        user_agent=ua,
    )
    return AuthResponse(message=result["message"])
