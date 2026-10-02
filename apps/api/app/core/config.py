"""Core configuration module.

Loads settings from environment variables with validation and safe defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    APP_NAME: str = "UniServe"
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ---- Database ----
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "uniserve"
    POSTGRES_PASSWORD: str = "uniserve_dev_password"
    POSTGRES_DB: str = "uniserve_dev"

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        """Construct the async database URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:  # noqa: N802
        """Construct the synchronous database URL (for Alembic)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- JWT ----
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-strong-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ---- OTP ----
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_RESENDS: int = 3

    # ---- PIN ----
    PIN_LENGTH: int = 4
    PIN_MAX_FAILED_ATTEMPTS: int = 5
    PIN_LOCKOUT_MINUTES: int = 15

    # ---- Rate Limiting ----
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_LOCKOUT_MINUTES: int = 30
    PASSWORD_RESET_MAX_REQUESTS: int = 5

    # ---- Refund Policy ----
    REFUND_DEADLINE_HOURS: int = 72

    # ---- Phase 6: Order Operations ----
    PICKUP_WINDOW_MINUTES: int = 30
    DEFAULT_PREPARATION_TIME_MINUTES: int = 15
    DEFAULT_CAPACITY: int = 10

    # No-show policy
    NOSHOW_STUDENT_THRESHOLD: int = 3
    NOSHOW_STUDENT_WINDOW_DAYS: int = 30
    NOSHOW_STUDENT_SUSPENSION_DAYS: int = 7
    NOSHOW_FACULTY_THRESHOLD: int = 5
    NOSHOW_FACULTY_WINDOW_DAYS: int = 30
    NOSHOW_FACULTY_SUSPENSION_DAYS: int = 3

    # ---- Email University Rules ----
    # University email patterns mapped to user categories.
    # The system derives user category from email pattern matching.
    # Add new patterns here when the university email format changes.
    UNIVERSITY_EMAIL_PATTERNS: dict[str, list[str]] = {
        "student": [r"^fa\d{2}-.+@lgu\.edu\.pk$", r".+@student\.lgu\.edu\.pk$"],
        "faculty": [r"^[a-z].*@lgu\.edu\.pk$", r".+@faculty\.lgu\.edu\.pk$"],
    }

    # ---- Online Payment Provider ----
    # Provider-neutral configuration (backend-only — server env only).
    # "test" selects the mock provider (development/testing only; rejected
    # in production on the initiation endpoint). Set PAYMENT_PROVIDER to a
    # registered real provider name to enable online payments. Unknown
    # names fail closed (HTTP 503) — no silent fallback to the mock.
    # Credentials stay blank until a real provider is provisioned.
    PAYMENT_PROVIDER: str = "test"
    PAYMENT_ENVIRONMENT: str = "sandbox"  # sandbox | production (provider-side)
    PAYMENT_MERCHANT_ID: str = ""
    PAYMENT_API_KEY: str = ""
    PAYMENT_API_SECRET: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""
    PAYMENT_CALLBACK_URL: str = ""

    # ---- Email / SMTP (production OTP delivery) ----
    # Standard SMTP transport for OTP emails (see app/core/email.py).
    # Provider-neutral — no vendor SDK. Credentials come from the
    # environment only; never commit them to source or tracked env files.
    # In production, OTP delivery fails closed (emails report failure)
    # when SMTP_HOST or SMTP_FROM_EMAIL is absent — the external SMTP
    # account is a deployment prerequisite, not part of the application.
    # SMTP_TLS_MODE: "starttls" (default, normally port 587) |
    #   "ssl" (implicit TLS, normally port 465) |
    #   "none" (plaintext — rejected in production by validation below).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_TLS_MODE: Literal["starttls", "ssl", "none"] = "starttls"

    # ---- CORS ----
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]

    # ---- Logging ----
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: Literal["json", "console"] = "json"

    @field_validator("APP_SECRET_KEY", "JWT_SECRET_KEY")
    @classmethod
    def reject_default_secrets(cls, v: str, info: object) -> str:
        """Reject default or empty secret keys in production.

        Empty/whitespace values would otherwise be accepted (they are not in
        the defaults set) and produce a signing key that offers no protection
        whatsoever. Fail closed at startup, like the default-secret rule.
        """
        if hasattr(info, "data") and info.data.get("APP_ENV") == "production":
            defaults = {
                "change-me-in-production",
                "change-me-in-production-use-a-strong-random-string",
            }
            if v in defaults:
                raise ValueError(f"Secret key must be changed for production. Got: {v[:10]}...")
            if not v or not v.strip():
                raise ValueError(
                    "Secret keys must not be empty when APP_ENV=production. "
                    "Generate one with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
        return v

    @model_validator(mode="after")
    def reject_debug_in_production(self) -> "Settings":
        """Fail closed if APP_DEBUG is left on in production.

        APP_DEBUG gates exposure of /api/docs, /api/redoc and /api/openapi.json
        (see app.main). An operator who sets APP_ENV=production but forgets
        APP_DEBUG=false would otherwise publish the interactive API schema
        surface in production. Mirrors the reject_default_secrets posture:
        misconfiguration must fail at startup, not degrade silently.
        """
        if self.APP_ENV == "production" and self.APP_DEBUG:
            raise ValueError(
                "APP_DEBUG must be false when APP_ENV=production "
                "(debug mode exposes /api/docs, /api/redoc and /api/openapi.json). "
                "Set APP_DEBUG=false."
            )
        return self

    @model_validator(mode="after")
    def reject_dev_database_password_in_production(self) -> "Settings":
        """Fail closed if the development database password is used in production.

        The default POSTGRES_PASSWORD is the documented development credential.
        An operator who sets APP_ENV=production but leaves that default (or
        leaves the password empty) would ship a production database protected
        by a publicly known development secret. Mirrors the
        reject_default_secrets posture: misconfiguration must fail at startup,
        not degrade silently.
        """
        if self.APP_ENV == "production" and (
            self.POSTGRES_PASSWORD in ("uniserve_dev_password", "")
            or len(self.POSTGRES_PASSWORD) < 12
        ):
            raise ValueError(
                "POSTGRES_PASSWORD must be set to a strong value when "
                "APP_ENV=production (empty, the development default, and "
                "passwords shorter than 12 characters are rejected). "
                "Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return self

    @model_validator(mode="after")
    def reject_plaintext_smtp_in_production(self) -> "Settings":
        """Fail closed if SMTP runs without TLS in production.

        SMTP_TLS_MODE=none would transmit SMTP credentials and OTP codes
        in plaintext. Mirrors the other production fail-closed
        validators: misconfiguration must fail at startup, not degrade
        silently.
        """
        if self.APP_ENV == "production" and self.SMTP_TLS_MODE == "none":
            raise ValueError(
                "SMTP_TLS_MODE must be 'starttls' or 'ssl' when "
                "APP_ENV=production (plaintext SMTP would transmit "
                "credentials and OTP codes in the clear)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


settings = get_settings()
