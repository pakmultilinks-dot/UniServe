"""User domain models.

Defines user identity, credentials, sessions, and OTP challenges.
"""

import enum
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, StrEnum

# ---- User Category (derived from email) ----


class UserCategory(str, enum.Enum):
    """University user category — derived from email pattern."""

    STUDENT = "student"
    FACULTY = "faculty"


# ---- Role Model ----


class Role(str, enum.Enum):
    """System roles for authorization."""

    STUDENT = "student"
    FACULTY = "faculty"
    CAFETERIA_STAFF = "cafeteria_staff"
    CAFETERIA_MANAGER = "cafeteria_manager"
    UNIVERSITY_ADMIN = "university_admin"


# ---- Account Status ----


class AccountStatus(str, enum.Enum):
    """Account lifecycle status."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


# ---- User ----


class User(Base):
    """University user — the core identity record.

    Every person in the system has exactly one User record.
    University ID and email are immutable after registration.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("university_id", name="uq_user_university_id"),
        UniqueConstraint("university_email", name="uq_user_university_email"),
        Index("idx_user_category", "category"),
        Index("idx_user_status", "status"),
        Index("idx_user_role", "role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    university_id: Mapped[str] = mapped_column(String(50), nullable=False)
    university_email: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[UserCategory] = mapped_column(
        StrEnum(UserCategory, name="user_category", create_type=False), nullable=False
    )
    role: Mapped[Role] = mapped_column(StrEnum(Role, name="user_role", create_type=False), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        StrEnum(AccountStatus, name="account_status", create_type=False),
        default=AccountStatus.PENDING_VERIFICATION,
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Ordering suspension (Phase 6)
    ordering_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ordering_suspended_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ordering_suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_show_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    credential: Mapped[Optional["UserCredential"]] = relationship(
        "UserCredential", back_populates="user", uselist=False, lazy="joined"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", lazy="selectin"
    )
    cafeteria_assignment: Mapped[Optional["CafeteriaAssignment"]] = relationship(
        "CafeteriaAssignment",
        back_populates="user",
        uselist=False,
        lazy="joined",
        foreign_keys="CafeteriaAssignment.user_id",
    )

    def __repr__(self) -> str:
        return f"<User {self.university_email} ({self.role.value})>"


# ---- User Credential ----


class UserCredential(Base):
    """Stores password and PIN hashes for a user.

    Separated from User to isolate authentication data from profile data.
    """

    __tablename__ = "user_credentials"
    __table_args__ = (Index("idx_credential_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pin_failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    password_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="credential")


# ---- User Session ----


class UserSession(Base):
    """Active user session — tied to a device.

    Sessions are created on login and can be individually revoked.
    No automatic inactivity expiry — users manage their own sessions.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_session_user_id", "user_id"),
        Index("idx_session_is_active", "is_active"),
        Index("idx_session_refresh_token_jti", "refresh_token_jti"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    device_info: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")


# ---- OTP Challenge ----


class OTPPurpose(str, enum.Enum):
    """Purpose of the OTP challenge."""

    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class OTPChallenge(Base):
    """OTP verification challenge.

    Tracks OTP generation, verification attempts, and expiration.
    OTPs are stored as hashes — never in plaintext.
    """

    __tablename__ = "otp_challenges"
    __table_args__ = (
        Index("idx_otp_user_id", "user_id"),
        Index("idx_otp_purpose", "purpose"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[OTPPurpose] = mapped_column(
        StrEnum(OTPPurpose, name="otp_purpose", create_type=False), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---- Cafeteria Assignment ----


class CafeteriaAssignment(Base):
    """Links a user to a specific cafeteria with a role scope.

    Used for Manager and Staff who belong to exactly one cafeteria.
    Students and Faculty don't need explicit assignments — their access
    is determined by their category and cafeteria type rules.
    """

    __tablename__ = "cafeteria_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_cafeteria_assignment_user"),
        Index("idx_cafeteria_assignment_cafeteria", "cafeteria_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(StrEnum(Role, name="user_role", create_type=False), nullable=False)
    assigned_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="cafeteria_assignment", foreign_keys=[user_id]
    )
