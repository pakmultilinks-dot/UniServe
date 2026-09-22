"""Auth module — authentication and authorization business logic.

Handles registration, login, OTP, PIN, password reset, and session management.
"""

import contextlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditEventType, log_audit_event
from app.core.config import settings
from app.core.email import get_email_provider
from app.core.exceptions import (
    AccountLockedError,
    AccountSuspendedError,
    AlreadyExistsException,
    AuthenticationError,
    EmailNotVerifiedError,
    OTPError,
    PINError,
    PINLockedError,
    RateLimitError,
    TokenRevokedError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_otp,
    hash_password,
    hash_pin,
    verify_otp,
    verify_password,
    verify_pin,
)
from app.core.university import classify_university_email
from app.modules.users.models import (
    AccountStatus,
    OTPChallenge,
    OTPPurpose,
    Role,
    User,
    UserCategory,
    UserCredential,
    UserSession,
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (UTC). SQLite returns naive datetimes.

    Returns None if input is None; returns a guaranteed-aware datetime otherwise.
    Callers that know the value is non-None can assert the result.
    """
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _ensure_aware_nn(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware, guaranteeing non-None return.

    Use for database fields that are known to be non-NULL (NOT NULL columns).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime.

    This is the single source of truth for 'now' in comparisons,
    making it easy to override in tests if needed.
    """
    return datetime.now(UTC)


logger = structlog.get_logger(__name__)


class AuthService:
    """Authentication business logic service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_provider = get_email_provider()

    # ---- Registration ----

    async def register(
        self,
        first_name: str,
        last_name: str,
        university_id: str,
        university_email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Register a new university user.

        Steps:
        1. Validate email is a recognized university email
        2. Derive user category from email pattern
        3. Check for duplicate university ID and email
        4. Create user, credential, and send OTP
        """
        # Validate university email
        classification = classify_university_email(university_email)
        if not classification.is_university_email:
            raise ValidationError("Email does not match any recognized university email pattern")

        # Derive category from email (authoritative)
        category = UserCategory(classification.category)

        # Check duplicate university ID
        existing_id = await self.db.execute(select(User).where(User.university_id == university_id))
        if existing_id.scalar_one_or_none():
            raise AlreadyExistsException("User with this University ID")

        # Check duplicate email
        existing_email = await self.db.execute(
            select(User).where(User.university_email == university_email.lower().strip())
        )
        if existing_email.scalar_one_or_none():
            raise AlreadyExistsException("User with this email")

        # Create user
        user = User(
            first_name=first_name,
            last_name=last_name,
            university_id=university_id,
            university_email=university_email.lower().strip(),
            category=category,
            role=Role.STUDENT if category == UserCategory.STUDENT else Role.FACULTY,
            status=AccountStatus.PENDING_VERIFICATION,
            email_verified=False,
        )
        self.db.add(user)
        await self.db.flush()  # Get user.id

        # Create credential
        credential = UserCredential(
            user_id=user.id,
            password_hash=hash_password(password),
        )
        self.db.add(credential)

        # Send email verification OTP
        await self._create_and_send_otp(
            user_id=user.id,
            purpose=OTPPurpose.EMAIL_VERIFICATION,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()

        # Audit event
        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.USER_REGISTERED,
            user_id=user.id,
            description=f"New user registered: {user.university_email}",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("User registered", user_id=user.id, email=user.university_email)
        return user

    # ---- OTP ----

    async def _create_and_send_otp(
        self,
        user_id: str,
        purpose: OTPPurpose,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OTPChallenge:
        """Create and send an OTP for the given purpose."""
        # Check resend cooldown
        recent_otp = await self.db.execute(
            select(OTPChallenge)
            .where(
                OTPChallenge.user_id == user_id,
                OTPChallenge.purpose == purpose,
                OTPChallenge.created_at
                >= datetime.now(UTC) - timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS),
            )
            .order_by(OTPChallenge.created_at.desc())
            .limit(1)
        )
        recent = recent_otp.scalar_one_or_none()
        if recent and not recent.is_used:
            elapsed = (_utcnow() - _ensure_aware_nn(recent.created_at)).total_seconds()
            remaining = settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed
            if remaining > 0:
                raise RateLimitError(
                    f"Please wait {int(remaining)} seconds before requesting a new OTP"
                )

        # Invalidate any existing unused OTPs for this purpose
        await self.db.execute(
            update(OTPChallenge)
            .where(
                OTPChallenge.user_id == user_id,
                OTPChallenge.purpose == purpose,
                OTPChallenge.is_used == False,
            )
            .values(is_used=True)
        )

        # Generate new OTP
        otp = generate_otp()
        otp_challenge = OTPChallenge(
            user_id=user_id,
            otp_hash=hash_otp(otp),
            purpose=purpose,
            max_attempts=settings.OTP_MAX_ATTEMPTS,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        )
        self.db.add(otp_challenge)
        await self.db.flush()

        # Resolve user email for sending
        user_result = await self.db.execute(select(User.university_email).where(User.id == user_id))
        user_email = user_result.scalar_one_or_none()

        # Send via email provider
        purpose_label = (
            "email verification" if purpose == OTPPurpose.EMAIL_VERIFICATION else "password reset"
        )
        if user_email:
            await self.email_provider.send_otp(
                to_email=user_email,
                otp=otp,
                purpose=purpose_label,
            )
        else:
            logger.warning("Could not resolve email for OTP sending", user_id=user_id)

        # Audit
        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.EMAIL_VERIFICATION_REQUESTED
            if purpose == OTPPurpose.EMAIL_VERIFICATION
            else AuditEventType.PASSWORD_RESET_REQUESTED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return otp_challenge

    async def resend_otp(
        self,
        user_id: str,
        purpose: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Resend an OTP for email verification or password reset."""
        # Load user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValidationError("User not found")

        otp_purpose = OTPPurpose(purpose)

        # Check max resend limit
        resend_count = await self.db.execute(
            select(func.count(OTPChallenge.id)).where(
                OTPChallenge.user_id == user_id,
                OTPChallenge.purpose == otp_purpose,
                OTPChallenge.created_at
                >= datetime.now(UTC) - timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
            )
        )
        count = resend_count.scalar()
        if count and count >= settings.OTP_MAX_RESENDS:
            raise RateLimitError("Maximum OTP resend attempts reached")

        await self._create_and_send_otp(
            user_id=user_id,
            purpose=otp_purpose,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "message": "OTP sent successfully",
            "expires_in_seconds": settings.OTP_EXPIRE_MINUTES * 60,
        }

    async def verify_otp(
        self,
        user_id: str,
        otp: str,
        purpose: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Verify an OTP code."""
        # Load user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValidationError("User not found")

        otp_purpose = OTPPurpose(purpose)

        # Find the latest active OTP for this purpose
        otp_result = await self.db.execute(
            select(OTPChallenge)
            .where(
                OTPChallenge.user_id == user_id,
                OTPChallenge.purpose == otp_purpose,
                OTPChallenge.is_used == False,
            )
            .order_by(OTPChallenge.created_at.desc())
            .limit(1)
        )
        challenge = otp_result.scalar_one_or_none()

        if not challenge:
            raise OTPError("No active OTP found. Please request a new one.")

        # Check expiration
        if _utcnow() > _ensure_aware_nn(challenge.expires_at):
            challenge.is_used = True
            raise OTPError("OTP has expired. Please request a new one.")

        # Check attempts
        if challenge.attempts >= challenge.max_attempts:
            challenge.is_used = True
            raise OTPError("Maximum OTP attempts reached. Please request a new one.")

        # Verify OTP
        challenge.attempts += 1
        if not verify_otp(otp, challenge.otp_hash):
            await self.db.flush()
            raise OTPError("Invalid OTP. Please try again.")

        # Mark as verified
        challenge.is_verified = True
        challenge.is_used = True
        challenge.verified_at = datetime.now(UTC)

        # Handle purpose-specific actions
        if otp_purpose == OTPPurpose.EMAIL_VERIFICATION:
            user.email_verified = True
            user.status = AccountStatus.ACTIVE
            await log_audit_event(
                session=self.db,
                event_type=AuditEventType.EMAIL_VERIFIED,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        elif otp_purpose == OTPPurpose.PASSWORD_RESET:
            await log_audit_event(
                session=self.db,
                event_type=AuditEventType.PASSWORD_RESET_REQUESTED,
                user_id=user.id,
                description="OTP verified for password reset",
                ip_address=ip_address,
                user_agent=user_agent,
            )

        await self.db.flush()

        return {"message": "OTP verified successfully"}

    # ---- Login ----

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user with email and password.

        Returns user and token pair.
        """
        # Load user with credential
        result = await self.db.execute(
            select(User).where(User.university_email == email.lower().strip())
        )
        user = result.scalar_one_or_none()

        # Always use generic message to prevent user enumeration
        if user is None:
            raise AuthenticationError("Invalid email or password")

        # Check credential exists
        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user.id)
        )
        credential = cred_result.scalar_one_or_none()

        if credential is None or credential.password_hash is None:
            raise AuthenticationError("Invalid email or password")

        # Check account lockout from failed password attempts
        if credential.password_locked_until and _utcnow() < _ensure_aware_nn(
            credential.password_locked_until
        ):
            await log_audit_event(
                session=self.db,
                event_type=AuditEventType.LOGIN_FAILED,
                user_id=user.id,
                description="Login blocked — account temporarily locked",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AccountLockedError(
                "Account temporarily locked due to too many failed login attempts"
            )

        # Clear lockout if expired
        if credential.password_locked_until and _utcnow() >= _ensure_aware_nn(
            credential.password_locked_until
        ):
            credential.password_failed_attempts = 0
            credential.password_locked_until = None

        # Verify password
        if not verify_password(password, credential.password_hash):
            # Track failed attempt
            credential.password_failed_attempts += 1

            # Lock account if max attempts exceeded
            if credential.password_failed_attempts >= settings.LOGIN_MAX_ATTEMPTS:
                credential.password_locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.LOGIN_LOCKOUT_MINUTES
                )
                await log_audit_event(
                    session=self.db,
                    event_type=AuditEventType.LOGIN_FAILED,
                    user_id=user.id,
                    description=f"Account locked after {credential.password_failed_attempts} failed attempts",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                logger.warning(
                    "Account locked due to failed login attempts",
                    user_id=user.id,
                    attempts=credential.password_failed_attempts,
                )

            # Log failed attempt
            await log_audit_event(
                session=self.db,
                event_type=AuditEventType.LOGIN_FAILED,
                user_id=user.id,
                description="Invalid password",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await self.db.flush()
            raise AuthenticationError("Invalid email or password")

        # Reset failed attempts on successful login
        credential.password_failed_attempts = 0
        credential.password_locked_until = None

        # Check account status
        if user.status == AccountStatus.SUSPENDED:
            raise AccountSuspendedError()
        if user.status == AccountStatus.DELETED:
            raise AuthenticationError("Invalid email or password")
        if user.status == AccountStatus.PENDING_VERIFICATION:
            raise EmailNotVerifiedError()

        # Create session and tokens
        tokens = await self._create_session(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Audit
        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("User logged in", user_id=user.id, email=user.university_email)
        return user, tokens

    # ---- PIN Login ----

    async def pin_login(
        self,
        user_id: str,
        pin: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user with PIN (convenience login)."""
        # Load user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationError("Invalid credentials")

        # Check account status
        if user.status != AccountStatus.ACTIVE:
            raise AuthenticationError("Invalid credentials")

        # Load credential
        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user.id)
        )
        credential = cred_result.scalar_one_or_none()

        if credential is None or not credential.pin_enabled or credential.pin_hash is None:
            raise PINError("PIN authentication is not enabled")

        # Check lockout
        if credential.pin_locked_until and _utcnow() < _ensure_aware_nn(
            credential.pin_locked_until
        ):
            raise PINLockedError("PIN authentication temporarily locked. Please try again later.")

        # Clear lockout if expired
        if credential.pin_locked_until and _utcnow() >= _ensure_aware_nn(
            credential.pin_locked_until
        ):
            credential.pin_failed_attempts = 0
            credential.pin_locked_until = None

        # Verify PIN
        if not verify_pin(pin, credential.pin_hash):
            credential.pin_failed_attempts += 1

            # Check if should lock
            if credential.pin_failed_attempts >= settings.PIN_MAX_FAILED_ATTEMPTS:
                credential.pin_locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.PIN_LOCKOUT_MINUTES
                )
                await log_audit_event(
                    session=self.db,
                    event_type=AuditEventType.PIN_LOCKED,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                logger.warning(
                    "PIN locked due to failed attempts",
                    user_id=user.id,
                    attempts=credential.pin_failed_attempts,
                )

            await log_audit_event(
                session=self.db,
                event_type=AuditEventType.PIN_LOGIN_FAILED,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise PINError("Invalid PIN")

        # Reset failed attempts on success
        credential.pin_failed_attempts = 0
        credential.pin_locked_until = None

        # Create session
        tokens = await self._create_session(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.PIN_LOGIN_SUCCESS,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return user, tokens

    # ---- PIN Management ----

    async def enable_pin(
        self,
        user_id: str,
        current_password: str,
        pin: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Enable PIN authentication for a user."""
        # Load user and credential
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or user.status != AccountStatus.ACTIVE:
            raise AuthenticationError("User not found or inactive")

        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credential = cred_result.scalar_one_or_none()
        if not credential or not credential.password_hash:
            raise AuthenticationError("No password credential found")

        # Verify current password
        if not verify_password(current_password, credential.password_hash):
            raise AuthenticationError("Invalid current password")

        # Set PIN
        credential.pin_hash = hash_pin(pin)
        credential.pin_enabled = True
        credential.pin_failed_attempts = 0
        credential.pin_locked_until = None

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.PIN_ENABLED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"message": "PIN authentication enabled successfully"}

    async def change_pin(
        self,
        user_id: str,
        current_pin: str,
        new_pin: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Change an existing PIN."""
        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credential = cred_result.scalar_one_or_none()

        if not credential or not credential.pin_enabled or not credential.pin_hash:
            raise PINError("PIN authentication is not enabled")

        # Verify current PIN
        if not verify_pin(current_pin, credential.pin_hash):
            raise PINError("Invalid current PIN")

        # Set new PIN
        credential.pin_hash = hash_pin(new_pin)
        credential.pin_failed_attempts = 0
        credential.pin_locked_until = None

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.PIN_CHANGED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"message": "PIN changed successfully"}

    async def disable_pin(
        self,
        user_id: str,
        current_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Disable PIN authentication."""
        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credential = cred_result.scalar_one_or_none()

        if not credential:
            raise AuthenticationError("No credential found")

        # Verify password
        if credential.password_hash and not verify_password(
            current_password, credential.password_hash
        ):
            raise AuthenticationError("Invalid password")

        credential.pin_enabled = False
        credential.pin_hash = None
        credential.pin_failed_attempts = 0
        credential.pin_locked_until = None

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.PIN_DISABLED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"message": "PIN authentication disabled"}

    # ---- Password Reset ----

    async def request_password_reset(
        self,
        email: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Request a password reset OTP."""
        result = await self.db.execute(
            select(User).where(User.university_email == email.lower().strip())
        )
        user = result.scalar_one_or_none()

        # Always return success to prevent user enumeration
        if not user or user.status == AccountStatus.DELETED:
            return {"message": "If your email is registered, you will receive a reset code."}

        # Check rate limiting
        recent_requests = await self.db.execute(
            select(func.count(OTPChallenge.id)).where(
                OTPChallenge.user_id == user.id,
                OTPChallenge.purpose == OTPPurpose.PASSWORD_RESET,
                OTPChallenge.created_at >= datetime.now(UTC) - timedelta(hours=1),
            )
        )
        count = recent_requests.scalar()
        if count and count >= settings.PASSWORD_RESET_MAX_REQUESTS:
            return {"message": "If your email is registered, you will receive a reset code."}

        with contextlib.suppress(Exception):
            # Don't leak error details from OTP sending
            await self._create_and_send_otp(
                user_id=user.id,
                purpose=OTPPurpose.PASSWORD_RESET,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return {"message": "If your email is registered, you will receive a reset code."}

    async def reset_password(
        self,
        user_id: str,
        otp: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Reset password using verified OTP."""
        # First verify the OTP
        await self.verify_otp(
            user_id=user_id,
            otp=otp,
            purpose="password_reset",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Update password
        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credential = cred_result.scalar_one_or_none()
        if not credential:
            raise ValidationError("User credentials not found")

        credential.password_hash = hash_password(new_password)
        credential.password_changed_at = datetime.now(UTC)

        # Revoke all sessions on password reset for security
        await self.db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
            )
            .values(is_active=False, revoked_at=datetime.now(UTC))
        )

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.PASSWORD_RESET_COMPLETED,
            user_id=user_id,
            description="Password reset completed — all sessions revoked",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"message": "Password reset successfully. Please log in again."}

    # ---- Password Change ----

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Change password (requires current password)."""
        cred_result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credential = cred_result.scalar_one_or_none()

        if not credential or not credential.password_hash:
            raise ValidationError("No password credential found")

        if not verify_password(current_password, credential.password_hash):
            raise AuthenticationError("Invalid current password")

        credential.password_hash = hash_password(new_password)
        credential.password_changed_at = datetime.now(UTC)

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.PASSWORD_CHANGED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"message": "Password changed successfully"}

    # ---- Session Management ----

    async def _create_session(
        self,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Create a new session and return token pair."""
        # Generate session ID and refresh token JTI
        session_id = str(secrets.token_hex(18))
        refresh_jti = str(secrets.token_hex(18))

        # Create session record
        session = UserSession(
            id=session_id,
            user_id=user.id,
            refresh_token_jti=refresh_jti,
            device_info=user_agent[:512] if user_agent else None,
            ip_address=ip_address,
            is_active=True,
        )
        self.db.add(session)

        # Generate tokens
        access_token = create_access_token(
            subject=user.id,
            extra_claims={"sid": session_id, "role": user.role.value},
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            session_id=session_id,
            jti=refresh_jti,
        )

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.SESSION_CREATED,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Refresh access token using a valid refresh token.

        Implements token rotation — new refresh token is issued on each refresh.
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationError("Invalid refresh token")

        session_id = payload.get("sid")
        if not session_id:
            raise AuthenticationError("Invalid refresh token")

        # Load session
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.is_active == True,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise TokenRevokedError("Session has been revoked")

        # Verify refresh token JTI matches
        token_jti = payload.get("jti")
        if token_jti and token_jti != session.refresh_token_jti:
            # Token reuse detected — revoke the session
            session.is_active = False
            session.revoked_at = datetime.now(UTC)
            raise TokenRevokedError("Refresh token reuse detected — session revoked")

        # Load user
        user_result = await self.db.execute(select(User).where(User.id == session.user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.status != AccountStatus.ACTIVE:
            session.is_active = False
            session.revoked_at = datetime.now(UTC)
            raise AuthenticationError("User account is not active")

        # Token rotation: invalidate old refresh token JTI, issue new one
        new_refresh_jti = str(secrets.token_hex(18))
        session.refresh_token_jti = new_refresh_jti
        session.last_activity_at = datetime.now(UTC)

        # Generate new tokens
        access_token = create_access_token(
            subject=user.id,
            extra_claims={"sid": session.id, "role": user.role.value},
        )
        new_refresh_token = create_refresh_token(
            subject=user.id,
            session_id=session.id,
            jti=new_refresh_jti,
        )

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def logout(
        self,
        user_id: str,
        session_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Logout from current device — revoke specific session."""
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.is_active == True,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False
            session.revoked_at = datetime.now(UTC)

            await log_audit_event(
                session=self.db,
                event_type=AuditEventType.LOGOUT,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return {"message": "Logged out successfully"}

    async def logout_all(
        self,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Logout from all devices — revoke all active sessions."""
        await self.db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
            )
            .values(is_active=False, revoked_at=datetime.now(UTC))
        )

        await log_audit_event(
            session=self.db,
            event_type=AuditEventType.LOGOUT_ALL,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"message": "Logged out from all devices"}

    async def get_sessions(
        self,
        user_id: str,
        current_session_id: str,
    ) -> list[dict[str, Any]]:
        """Get all active sessions for a user."""
        result = await self.db.execute(
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
            )
            .order_by(UserSession.last_activity_at.desc())
        )
        sessions = result.scalars().all()
        return [
            {
                "id": s.id,
                "device_info": s.device_info,
                "ip_address": s.ip_address,
                "created_at": s.created_at.isoformat(),
                "last_activity_at": s.last_activity_at.isoformat(),
                "is_current": s.id == current_session_id,
            }
            for s in sessions
        ]
