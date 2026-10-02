"""Regression tests for production configuration fail-closed guards.

Phase 28A release-engineering rehearsal found that APP_DEBUG was not forced
off in production: an operator setting APP_ENV=production without
APP_DEBUG=false would expose /api/docs, /api/redoc and /api/openapi.json
(main.py gates those routes on settings.APP_DEBUG). The reject_default_secrets
validator already rejected default secret keys; this module locks in both
guards so production misconfiguration fails at startup instead of silently
degrading.

These tests construct Settings explicitly (no DB, no network) and never
weaken existing behaviour.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _prod_kwargs(**overrides: object) -> dict:
    """Base kwargs for a valid production Settings construction."""
    kwargs: dict = {
        "_env_file": None,
        "APP_ENV": "production",
        "APP_DEBUG": False,
        "APP_SECRET_KEY": "prod-secret-" + "a" * 32,
        "JWT_SECRET_KEY": "prod-jwt-" + "b" * 32,
        # Strong password so the DB-password production guard (added in
        # Phase 30 deployment preparation) does not trip on the base fixture.
        "POSTGRES_PASSWORD": "prod-db-pass-" + "c" * 32,
    }
    kwargs.update(overrides)
    return kwargs


class TestDebugProductionGuard:
    """APP_DEBUG=true must be rejected when APP_ENV=production."""

    def test_production_with_debug_true_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_prod_kwargs(APP_DEBUG=True))
        assert "APP_DEBUG must be false" in str(exc_info.value)

    def test_production_with_debug_false_is_allowed(self) -> None:
        settings = Settings(**_prod_kwargs(APP_DEBUG=False))
        assert settings.APP_ENV == "production"
        assert settings.APP_DEBUG is False

    def test_staging_allows_debug(self) -> None:
        # Guard is production-only; staging keeps flexibility.
        settings = Settings(
            **_prod_kwargs(APP_ENV="staging", APP_DEBUG=True)
        )
        assert settings.APP_DEBUG is True

    def test_development_default_debug_unchanged(self) -> None:
        # Non-production default behaviour must not change.
        settings = Settings(_env_file=None)
        assert settings.APP_ENV == "development"
        assert settings.APP_DEBUG is True


class TestSecretProductionGuard:
    """reject_default_secrets remains fail-closed (locked-in regression)."""

    @pytest.mark.parametrize(
        "field",
        ["APP_SECRET_KEY", "JWT_SECRET_KEY"],
    )
    def test_default_secret_rejected_in_production(self, field: str) -> None:
        defaults = {
            "APP_SECRET_KEY": "change-me-in-production",
            "JWT_SECRET_KEY": "change-me-in-production-use-a-strong-random-string",
        }
        overrides = {field: defaults[field]}
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_prod_kwargs(**overrides))
        assert "must be changed for production" in str(exc_info.value)

    def test_custom_secret_allowed_in_production(self) -> None:
        settings = Settings(**_prod_kwargs())
        assert settings.APP_SECRET_KEY.startswith("prod-secret-")


class TestDbPasswordProductionGuard:
    """Development/empty POSTGRES_PASSWORD must be rejected in production."""

    def test_dev_password_rejected_in_production(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_prod_kwargs(POSTGRES_PASSWORD="uniserve_dev_password"))
        assert "POSTGRES_PASSWORD must be set" in str(exc_info.value)

    def test_empty_password_rejected_in_production(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_prod_kwargs(POSTGRES_PASSWORD=""))
        assert "POSTGRES_PASSWORD must be set" in str(exc_info.value)

    def test_strong_password_allowed_in_production(self) -> None:
        settings = Settings(**_prod_kwargs())
        assert settings.POSTGRES_PASSWORD.startswith("prod-db-pass-")

    def test_dev_default_password_unchanged_in_development(self) -> None:
        # Guard is production-only; development defaults must not change.
        settings = Settings(_env_file=None)
        assert settings.APP_ENV == "development"
        assert settings.POSTGRES_PASSWORD == "uniserve_dev_password"


class TestPaymentFailClosedConfigIntrospection:
    """Payment config stays inspectable and fail-closed (no provider wiring)."""

    def test_default_provider_is_test_with_blank_credentials(self) -> None:
        settings = Settings(**_prod_kwargs())
        assert settings.PAYMENT_PROVIDER == "test"
        assert settings.PAYMENT_MERCHANT_ID == ""
        assert settings.PAYMENT_API_KEY == ""
        assert settings.PAYMENT_API_SECRET == ""
        assert settings.PAYMENT_WEBHOOK_SECRET == ""
