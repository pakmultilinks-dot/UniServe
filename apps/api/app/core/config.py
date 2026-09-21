"""Core configuration module.

Loads settings from environment variables with validation and safe defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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
    def DATABASE_URL(self) -> str:
        """Construct the async database URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Construct the synchronous database URL (for Alembic)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- JWT ----
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-strong-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- CORS ----
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]

    # ---- Logging ----
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: Literal["json", "console"] = "json"

    @field_validator("APP_SECRET_KEY", "JWT_SECRET_KEY")
    @classmethod
    def reject_default_secrets(cls, v: str, info: object) -> str:
        """Reject default secret keys in production."""
        if hasattr(info, "data") and info.data.get("APP_ENV") == "production":  # type: ignore[attr-defined]
            defaults = {"change-me-in-production", "change-me-in-production-use-a-strong-random-string"}
            if v in defaults:
                raise ValueError(f"Secret key must be changed for production. Got: {v[:10]}...")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


settings = get_settings()
