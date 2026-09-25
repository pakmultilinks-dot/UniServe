"""Phase 2 — Authentication and authorization tables.

Creates: users, user_credentials, user_sessions, otp_challenges,
cafeterias, cafeteria_assignments, security_audit_events.

Revision ID: 0001
Revises: 0000
Create Date: 2025-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = "0000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- Cafeterias ----
    op.create_table(
        "cafeterias",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("type", sa.Enum("student", "faculty", name="cafeteria_type"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_cafeteria_type", "cafeterias", ["type"])
    op.create_index("idx_cafeteria_is_active", "cafeterias", ["is_active"])

    # ---- Users ----
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column("university_id", sa.String(50), nullable=False),
        sa.Column("university_email", sa.String(255), nullable=False),
        sa.Column("category", sa.Enum("student", "faculty", name="user_category"), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "student",
                "faculty",
                "cafeteria_staff",
                "cafeteria_manager",
                "university_admin",
                name="user_role",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending_verification", "active", "suspended", "deleted", name="account_status"
            ),
            nullable=False,
            server_default="pending_verification",
        ),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("university_id", name="uq_user_university_id"),
        sa.UniqueConstraint("university_email", name="uq_user_university_email"),
    )
    op.create_index("idx_user_category", "users", ["category"])
    op.create_index("idx_user_status", "users", ["status"])
    op.create_index("idx_user_role", "users", ["role"])

    # ---- User Credentials ----
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("pin_hash", sa.Text(), nullable=True),
        sa.Column("pin_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pin_failed_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pin_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_credential_user_id", "user_credentials", ["user_id"])

    # ---- User Sessions ----
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("refresh_token_jti", sa.String(36), nullable=False, unique=True),
        sa.Column("device_info", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_session_user_id", "user_sessions", ["user_id"])
    op.create_index("idx_session_is_active", "user_sessions", ["is_active"])
    op.create_index("idx_session_refresh_token_jti", "user_sessions", ["refresh_token_jti"])

    # ---- OTP Challenges ----
    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("otp_hash", sa.Text(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("email_verification", "password_reset", name="otp_purpose"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_otp_user_id", "otp_challenges", ["user_id"])
    op.create_index("idx_otp_purpose", "otp_challenges", ["purpose"])

    # ---- Cafeteria Assignments ----
    op.create_table(
        "cafeteria_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "cafeteria_id",
            sa.String(36),
            sa.ForeignKey("cafeterias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum(
                "student",
                "faculty",
                "cafeteria_staff",
                "cafeteria_manager",
                "university_admin",
                name="user_role",
            ),
            nullable=False,
        ),
        sa.Column(
            "assigned_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", name="uq_cafeteria_assignment_user"),
    )
    op.create_index("idx_cafeteria_assignment_cafeteria", "cafeteria_assignments", ["cafeteria_id"])

    # ---- Security Audit Events ----
    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "user_registered",
                "email_verification_requested",
                "email_verified",
                "login_success",
                "login_failed",
                "logout",
                "logout_all",
                "password_changed",
                "password_reset_requested",
                "password_reset_completed",
                "pin_enabled",
                "pin_disabled",
                "pin_changed",
                "pin_login_success",
                "pin_login_failed",
                "pin_locked",
                "account_suspended",
                "account_activated",
                "account_recovered",
                "account_deleted",
                "role_changed",
                "cafeteria_scope_changed",
                "session_created",
                "session_revoked",
                "rate_limited",
                "authorization_failed",
                name="audit_event_type",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_audit_user_id", "security_audit_events", ["user_id"])
    op.create_index("idx_audit_event_type", "security_audit_events", ["event_type"])
    op.create_index("idx_audit_created_at", "security_audit_events", ["created_at"])
    op.create_index("idx_audit_ip_address", "security_audit_events", ["ip_address"])


def downgrade() -> None:
    op.drop_table("security_audit_events")
    op.drop_table("cafeteria_assignments")
    op.drop_table("otp_challenges")
    op.drop_table("user_sessions")
    op.drop_table("user_credentials")
    op.drop_table("users")
    op.drop_table("cafeterias")

    sa.Enum(name="audit_event_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="otp_purpose").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cafeteria_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="account_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_category").drop(op.get_bind(), checkfirst=True)
