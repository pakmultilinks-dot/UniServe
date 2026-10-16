"""Security audit event logging.

Records important authentication and authorization events for security monitoring.
These events are stored in the database and should not contain sensitive data.
"""

import enum
from datetime import UTC, datetime

import structlog
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, StrEnum

logger = structlog.get_logger(__name__)


class AuditEventType(str, enum.Enum):
    """Security audit event types."""

    # Registration
    USER_REGISTERED = "user_registered"
    EMAIL_VERIFICATION_REQUESTED = "email_verification_requested"
    EMAIL_VERIFIED = "email_verified"

    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"

    # Password
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_OTP_VERIFIED = "password_reset_otp_verified"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"

    # PIN
    PIN_ENABLED = "pin_enabled"
    PIN_DISABLED = "pin_disabled"
    PIN_CHANGED = "pin_changed"
    PIN_LOGIN_SUCCESS = "pin_login_success"
    PIN_LOGIN_FAILED = "pin_login_failed"
    PIN_LOCKED = "pin_locked"

    # Account management
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_ACTIVATED = "account_activated"
    ACCOUNT_RECOVERED = "account_recovered"
    ACCOUNT_DELETED = "account_deleted"

    # Role management
    ROLE_CHANGED = "role_changed"
    CAFETERIA_SCOPE_CHANGED = "cafeteria_scope_changed"

    # Sessions
    SESSION_CREATED = "session_created"
    SESSION_REVOKED = "session_revoked"

    # Security
    RATE_LIMITED = "rate_limited"
    AUTHORIZATION_FAILED = "authorization_failed"


class SecurityAuditEvent(Base):
    """Security audit event record.

    Stores important security-related events for monitoring and compliance.
    Sensitive data (passwords, tokens, OTPs) must NEVER be stored here.
    """

    __tablename__ = "security_audit_events"
    __table_args__ = (
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_ip_address", "ip_address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        StrEnum(AuditEventType, name="audit_event_type"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # Extra context as JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


async def log_audit_event(
    session,
    event_type: AuditEventType,
    user_id: str | None = None,
    description: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata_json: str | None = None,
) -> None:
    """Log a security audit event.

    This is a fire-and-forget operation — audit logging failures must not
    break the main application flow.
    """
    try:
        event = SecurityAuditEvent(
            user_id=user_id,
            event_type=event_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata_json,
        )
        session.add(event)
        await session.flush()

        logger.info(
            "Security audit event",
            event_type=event_type.value,
            user_id=user_id,
            ip_address=ip_address,
        )
    except Exception as exc:
        # Audit logging must not break the application
        logger.error(
            "Failed to log audit event",
            event_type=event_type.value,
            error=str(exc),
        )
