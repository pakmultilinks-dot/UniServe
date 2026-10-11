"""Auth module — authentication and authorization business logic.

Handles registration, login, OTP, PIN, password reset, and session management.
"""

import contextlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditEventType, log_audit_event
from app.core.config import settings
from app.core.database import async_session_factory
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

    async def _persist_challenge_state(
        self, challenge_id: str, values: dict[str, Any]
    ) -> None:
        """Persist OTP challenge state through an independent transaction.

        Failed verification attempts raise, and ``get_db`` rolls back the
        request session, so security-relevant challenge state (the failed-
        attempt counter, challenge consumption) cannot rely on the request
        transaction. It is applied here through a short-lived independent
        session using a single atomic UPDATE, so it survives across
        separate HTTP requests regardless of the request outcome.
        """
        async with async_session_factory() as independent_session:
            await independent_session.execute(
                update(OTPChallenge).where(OTPChallenge.id == challenge_id).values(**values)
            )
            await independent_session.commit()

    async def _persist_credential_state(
        self, user_id: str, values: dict[str, Any]
    ) -> None:
        """Persist user-credential security state through an independent transaction.

        Same rationale as ``_persist_challenge_state`` (Phase 38): a failed
        password/PIN login raises, and ``get_db`` rolls the request session
        back, discarding a flush-only increment of the failed-attempt counter
        and any lockout timestamp. The brute-force lockout control would
        therefore be unreachable in the production runtime. These counters are
        applied here through a short-lived independent session using a single
        atomic UPDATE, so they survive across separate HTTP requests
        regardless of the request outcome.
        """
        async with async_session_factory() as independent_session:
            await independent_session.execute(
                update(UserCredential).where(UserCredential.user_id == user_id).values(**values)
            )
            await independent_session.commit()

    async def _persist_audit_event(
        self,
        event_type: AuditEventType,
        user_id: str | None,
        description: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Persist a security audit event through an independent transaction.

        Failed-login / failed-PIN audit events are written on a path that
        raises, so the request-session write is rolled back and the event is
        lost (confirmed: no ``login_failed`` rows survive in production). The
        event is re-emitted here on an independent committed session so the
        security audit trail reflects real failed-authentication activity.
        """
        async with async_session_factory() as independent_session:
            await log_audit_event(
                session=independent_session,
                event_type=event_type,
                user_id=user_id,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await independent_session.commit()

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
            await self._persist_challenge_state(challenge.id, {"is_used": True})
            raise OTPError("Maximum OTP attempts reached. Please request a new one.")

        # Verify OTP. The failed-attempt increment must survive the request
        # transaction: a failed verification raises, and get_db rolls the
        # request session back, discarding a flush-only increment. Persist
        # it through an independent committed transaction instead.
        challenge.attempts += 1
        if not verify_otp(otp, challenge.otp_hash):
            await self._persist_challenge_state(
                challenge.id, {"attempts": OTPChallenge.attempts + 1}
            )
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
            # Persist the audit event independently: this branch raises, so a
            # request-session write would be rolled back and lost (Phase 63).
            await self._persist_audit_event(
                AuditEventType.LOGIN_FAILED,
                user.id,
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
            # Track failed attempt. The increment (and any lockout timestamp)
            # must survive the request rollback: get_db rolls the request
            # session back when this branch raises, so a flush-only update
            # would be discarded and the LOGIN_MAX_ATTEMPTS lockout would
            # never engage in the production runtime. Persist it through an
            # independent committed transaction (Phase 63).
            new_attempts = credential.password_failed_attempts + 1
            locked_until: datetime | None = None
            persist_values: dict[str, Any] = {
                "password_failed_attempts": new_attempts
            }

            # Lock account if max attempts exceeded
            if new_attempts >= settings.LOGIN_MAX_ATTEMPTS:
                locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.LOGIN_LOCKOUT_MINUTES
                )
                persist_values["password_locked_until"] = locked_until
                logger.warning(
                    "Account locked due to failed login attempts",
                    user_id=user.id,
                    attempts=new_attempts,
                )

            await self._persist_credential_state(user.id, persist_values)

            # Persist the audit trail independently as well (same rollback
            # rationale) so failed-authentication activity is recorded.
            if locked_until is not None:
                await self._persist_audit_event(
                    AuditEventType.LOGIN_FAILED,
                    user.id,
                    description=f"Account locked after {new_attempts} failed attempts",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            await self._persist_audit_event(
                AuditEventType.LOGIN_FAILED,
                user.id,
                description="Invalid password",
                ip_address=ip_address,
                user_agent=user_agent,
            )
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
            # Persist the failed-attempt counter (and any lockout) through an
            # independent committed transaction: this branch raises, and
            # get_db rolls the request session back, so a flush-only update
            # would be discarded and the PIN_MAX_FAILED_ATTEMPTS lockout
            # would never engage (Phase 63 — same defect class as the
            # password-login path, fixed for OTP in Phase 38).
            new_pin_attempts = credential.pin_failed_attempts + 1
            pin_persist_values: dict[str, Any] = {
                "pin_failed_attempts": new_pin_attempts
            }

            # Check if should lock
            if new_pin_attempts >= settings.PIN_MAX_FAILED_ATTEMPTS:
                pin_persist_values["pin_locked_until"] = datetime.now(UTC) + timedelta(
                    minutes=settings.PIN_LOCKOUT_MINUTES
                )
                logger.warning(
                    "PIN locked due to failed attempts",
                    user_id=user.id,
                    attempts=new_pin_attempts,
                )

            await self._persist_credential_state(user.id, pin_persist_values)

            if new_pin_attempts >= settings.PIN_MAX_FAILED_ATTEMPTS:
                await self._persist_audit_event(
                    AuditEventType.PIN_LOCKED,
                    user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            await self._persist_audit_event(
                AuditEventType.PIN_LOGIN_FAILED,
                user.id,
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

    # ---- Profile Update (Phase 55) ----

    async def update_profile(
        self,
        *,
        user_id: str,
        first_name: str,
        last_name: str,
    ) -> User:
        """Update the authenticated user's own profile name fields.

        Phase 55 — self-service profile editing. Strictly self-scoped:
        only first_name and last_name may change; email, university ID,
        role, status, and credentials are intentionally not editable
        here. No audit event is written by design (confirmed Phase 55
        decision — no new PostgreSQL enum value was added), and no
        sensitive values are logged.
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValidationError("User not found")

        user.first_name = first_name
        user.last_name = last_name
        await self.db.flush()
        await self.db.refresh(user)
        return user


# ---------------------------------------------------------------------------
# Session maintenance — Phase 60 (Workstream D)
# ---------------------------------------------------------------------------


async def reap_sessions(
    db: AsyncSession,
    *,
    revoked_grace_days: int = 7,
    inactive_grace_days: int = 1,
    protect_session_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Delete session rows that can no longer authenticate anything.

    Why: ``user_sessions`` has no automatic expiry (see the model
    docstring — users manage their own sessions), so rows accumulate
    forever. This function removes only rows that are **behaviorally
    dead** — it never changes token semantics and never touches
    sessions that could still refresh:

    * **Revoked residue** — ``revoked_at`` set more than
      ``revoked_grace_days`` ago. A revoked session already fails
      refresh (``refresh_tokens`` requires ``is_active``), so the row
      is pure audit residue after the grace window. The grace window
      exists so recently-revoked rows stay queryable for support
      ("logged out 2 hours ago" must still be visible).

    * **Dormant active residue** — ``is_active`` but
      ``last_activity_at`` older than
      ``JWT_REFRESH_TOKEN_EXPIRE_DAYS + inactive_grace_days``. The
      refresh JWT for such a session has definitively expired (its
      ``exp`` is bounded by ``JWT_REFRESH_TOKEN_EXPIRE_DAYS``), so a
      refresh attempt can only fail — the row is unusable residue.
      ``inactive_grace_days`` provides a buffer beyond the hard JWT
      lifetime.

    ``protect_session_id`` excludes one session from deletion (useful
    for scheduled runs that must never reap the operator's own current
    session). With ``dry_run=True`` only counts matching rows are
    returned — nothing is deleted (same predicates, zero drift between
    preview and apply). The caller must commit; this function only
    flushes.
    """
    now = datetime.now(UTC)
    revoked_cutoff = now - timedelta(days=revoked_grace_days)
    inactive_cutoff = now - timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS + inactive_grace_days
    )

    revoked_filters: list[Any] = [
        UserSession.revoked_at.is_not(None),
        UserSession.revoked_at < revoked_cutoff,
    ]
    stale_active_filters: list[Any] = [
        UserSession.is_active == True,  # noqa: E712 — boolean column
        UserSession.last_activity_at < inactive_cutoff,
        UserSession.revoked_at.is_(None),
    ]
    if protect_session_id is not None:
        revoked_filters.append(UserSession.id != protect_session_id)
        stale_active_filters.append(UserSession.id != protect_session_id)

    if dry_run:
        revoked_deleted = (
            await db.execute(select(func.count()).where(*revoked_filters))
        ).scalar_one()
        stale_deleted = (
            await db.execute(select(func.count()).where(*stale_active_filters))
        ).scalar_one()
    else:
        revoked_result = await db.execute(delete(UserSession).where(*revoked_filters))
        stale_result = await db.execute(
            delete(UserSession).where(*stale_active_filters)
        )
        revoked_deleted = revoked_result.rowcount or 0
        stale_deleted = stale_result.rowcount or 0

    return {
        "revoked_deleted": revoked_deleted,
        "stale_active_deleted": stale_deleted,
        "total_deleted": revoked_deleted + stale_deleted,
        "dry_run": dry_run,
    }
