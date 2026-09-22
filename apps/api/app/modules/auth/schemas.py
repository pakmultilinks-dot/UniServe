"""Auth module — Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.users.models import AccountStatus, Role, UserCategory

# ---- Registration ----


class RegisterRequest(BaseModel):
    """User registration request."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    university_id: str = Field(..., min_length=3, max_length=50)
    university_email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # User category is derived from email, but user can indicate preference
    # Server authoritative determination wins
    selected_category: UserCategory | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum strength requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class RegisterResponse(BaseModel):
    """Registration response."""

    message: str = "Registration successful. Please verify your email."
    user_id: str
    university_email: str
    category: UserCategory


# ---- OTP ----


class OTPVerifyRequest(BaseModel):
    """OTP verification request."""

    user_id: str
    otp: str = Field(..., min_length=6, max_length=6)
    purpose: str = Field(..., pattern="^(email_verification|password_reset)$")


class OTPResendRequest(BaseModel):
    """OTP resend request."""

    user_id: str
    purpose: str = Field(..., pattern="^(email_verification|password_reset)$")


class OTPResponse(BaseModel):
    """OTP operation response."""

    message: str
    expires_in_seconds: int | None = None


# ---- Login ----


class LoginRequest(BaseModel):
    """Login request."""

    university_email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class LoginResponse(BaseModel):
    """Login response with tokens and user info."""

    tokens: TokenPair
    user: "UserSummary"


# ---- PIN Login ----


class PINLoginRequest(BaseModel):
    """PIN-based login request."""

    user_id: str
    pin: str = Field(..., min_length=4, max_length=4)


class PINSetupRequest(BaseModel):
    """Enable or change PIN."""

    current_password: str = Field(..., min_length=1)
    pin: str = Field(..., min_length=4, max_length=4)
    confirm_pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def validate_pin_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("PIN must contain only digits")
        return v

    @field_validator("confirm_pin")
    @classmethod
    def validate_pin_match(cls, v: str, info) -> str:
        if "pin" in info.data and v != info.data["pin"]:
            raise ValueError("PINs do not match")
        return v


class PINDisableRequest(BaseModel):
    """Disable PIN authentication."""

    current_password: str = Field(..., min_length=1)


# ---- Password Reset ----


class PasswordResetRequest(BaseModel):
    """Request password reset OTP."""

    university_email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with OTP."""

    university_email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ---- Password Change ----


class PasswordChangeRequest(BaseModel):
    """Change password (requires current password)."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ---- Session/Token ----


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class SessionResponse(BaseModel):
    """Session information."""

    id: str
    device_info: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_activity_at: datetime
    is_current: bool = False


class SessionListResponse(BaseModel):
    """List of active sessions."""

    sessions: list[SessionResponse]


# ---- User Summary (for responses) ----


class UserSummary(BaseModel):
    """Summary of user information for API responses."""

    id: str
    first_name: str
    last_name: str
    university_id: str
    university_email: str
    category: UserCategory
    role: Role
    status: AccountStatus
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Generic auth response."""

    message: str


# ---- Admin/Manager User Management ----


class CreateUserByAdminRequest(BaseModel):
    """Admin/Manager creates a new user."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    university_id: str = Field(..., min_length=3, max_length=50)
    university_email: EmailStr
    role: Role
    cafeteria_id: str | None = None  # Required for staff/manager roles

    @field_validator("cafeteria_id")
    @classmethod
    def validate_cafeteria_required(cls, v, info):
        if (
            "role" in info.data
            and info.data["role"] in (Role.CAFETERIA_STAFF, Role.CAFETERIA_MANAGER)
            and v is None
        ):
            raise ValueError("cafeteria_id is required for staff and manager roles")
        return v


class ChangeUserRoleRequest(BaseModel):
    """Change a user's role."""

    role: Role
    cafeteria_id: str | None = None  # Required for staff/manager roles


class SuspendUserRequest(BaseModel):
    """Suspend a user account."""

    reason: str = Field(..., min_length=1, max_length=500)


class AccountRecoveryRequest(BaseModel):
    """Admin-assisted account recovery."""

    university_id: str = Field(..., min_length=3, max_length=50)
    reason: str = Field(..., min_length=1, max_length=500)


class AccountDeletionRequest(BaseModel):
    """Request account deletion."""

    password: str = Field(..., min_length=1)
    reason: str | None = Field(None, max_length=500)


# ---- PIN Change ----


class PINChangeRequest(BaseModel):
    """Change existing PIN."""

    current_pin: str = Field(..., min_length=4, max_length=4)
    new_pin: str = Field(..., min_length=4, max_length=4)
    confirm_pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("current_pin", "new_pin", "confirm_pin")
    @classmethod
    def validate_pin_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("PIN must contain only digits")
        return v

    @field_validator("confirm_pin")
    @classmethod
    def validate_pin_match(cls, v: str, info) -> str:
        if "new_pin" in info.data and v != info.data["new_pin"]:
            raise ValueError("PINs do not match")
        return v


# ---- Admin User Creation Response ----


class CreateUserResponse(BaseModel):
    """Response when admin creates a user — includes temporary password."""

    user: "UserSummary"
    temporary_password: str

    model_config = {"from_attributes": True}
