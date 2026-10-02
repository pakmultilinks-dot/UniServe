"""Tests — SMTP email provider (Phase 36 launch-gap closure).

Scope: transport-level behavior only —
- Provider factory selection (environment-driven)
- Fail-closed behavior when SMTP is unconfigured (no fake success)
- TLS mode handling (starttls / ssl) and explicit starttls upgrade
- SMTP failures return False and never raise into the auth flow
- Production Settings reject plaintext SMTP (startup fail-closed)

OTP security semantics (hashing, expiry, attempt limits) live in the
auth service and are covered there — not duplicated here.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.core.email import (
    DevelopmentEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)


def _provider_settings(**overrides):
    """SMTP-only settings stand-in — transport tests do not need full Settings."""
    values = dict(
        SMTP_HOST="smtp.example.com",
        SMTP_PORT=587,
        SMTP_USERNAME="smtp-user",
        SMTP_PASSWORD="smtp-pass",
        SMTP_FROM_EMAIL="noreply@example.com",
        SMTP_TLS_MODE="starttls",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _production_settings(**overrides):
    """Full Settings with valid production overrides + SMTP values."""
    base = dict(
        APP_ENV="production",
        APP_DEBUG=False,
        APP_SECRET_KEY="prod-secret-" + "x" * 40,
        JWT_SECRET_KEY="prod-jwt-" + "x" * 40,
        POSTGRES_PASSWORD="prod-db-password-123456",
        SMTP_HOST="smtp.example.com",
        SMTP_FROM_EMAIL="noreply@example.com",
        SMTP_TLS_MODE="starttls",
    )
    base.update(overrides)
    from app.core.config import Settings

    return Settings(**base)


# ---------------------------------------------------------------------------
# Factory — environment-driven selection
# ---------------------------------------------------------------------------


class TestEmailProviderFactory:
    """Development/testing log OTPs; staging/production use SMTP."""

    def test_development_uses_dev_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "development")
        assert isinstance(get_email_provider(), DevelopmentEmailProvider)

    def test_testing_uses_dev_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "testing")
        assert isinstance(get_email_provider(), DevelopmentEmailProvider)

    def test_production_uses_smtp_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "production")
        assert isinstance(get_email_provider(), SMTPEmailProvider)

    def test_staging_uses_smtp_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "staging")
        assert isinstance(get_email_provider(), SMTPEmailProvider)


# ---------------------------------------------------------------------------
# SMTP transport — send success, failure, fail-closed, TLS modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSMTPEmailProvider:
    """Transport behavior: delivery, failure reporting, TLS modes."""

    async def test_send_otp_success_starttls(self):
        """starttls mode: upgrades connection, logs in, sends, returns True."""
        provider = SMTPEmailProvider(settings_obj=_provider_settings())
        mock_client = MagicMock()
        smtp_cls = MagicMock()
        smtp_cls.return_value.__enter__.return_value = mock_client

        with patch("app.core.email.smtplib.SMTP", smtp_cls):
            result = await provider.send_otp(
                "student@example.edu.pk", "123456", "login"
            )

        assert result is True
        smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=30)
        # Explicit TLS upgrade with the system trust store
        mock_client.starttls.assert_called_once()
        assert mock_client.starttls.call_args.kwargs.get("context") is not None
        mock_client.login.assert_called_once_with("smtp-user", "smtp-pass")
        mock_client.send_message.assert_called_once()

        message = mock_client.send_message.call_args[0][0]
        assert message["From"] == "noreply@example.com"
        assert message["To"] == "student@example.edu.pk"
        assert "login" in message["Subject"]
        assert "123456" in message.get_content()

    async def test_send_failure_returns_false_without_raising(self):
        """SMTP transaction failure is reported — never raises into auth."""
        provider = SMTPEmailProvider(settings_obj=_provider_settings())
        mock_client = MagicMock()
        mock_client.send_message.side_effect = OSError("connection refused")
        smtp_cls = MagicMock()
        smtp_cls.return_value.__enter__.return_value = mock_client

        with patch("app.core.email.smtplib.SMTP", smtp_cls):
            result = await provider.send_otp(
                "student@example.edu.pk", "123456", "login"
            )

        assert result is False

    async def test_unconfigured_production_fails_closed(self):
        """Missing SMTP_HOST → False; no SMTP transaction attempted."""
        provider = SMTPEmailProvider(settings_obj=_provider_settings(SMTP_HOST=""))

        with patch("app.core.email.smtplib.SMTP") as smtp_cls:
            result = await provider.send_otp(
                "student@example.edu.pk", "123456", "login"
            )

        assert result is False
        smtp_cls.assert_not_called()

    async def test_missing_from_address_fails_closed(self):
        """Missing SMTP_FROM_EMAIL → False; no SMTP transaction attempted."""
        provider = SMTPEmailProvider(
            settings_obj=_provider_settings(SMTP_FROM_EMAIL="")
        )

        with patch("app.core.email.smtplib.SMTP") as smtp_cls:
            result = await provider.send_password_reset(
                "student@example.edu.pk", "654321"
            )

        assert result is False
        smtp_cls.assert_not_called()

    async def test_ssl_mode_uses_smtp_ssl_without_starttls(self):
        """ssl mode: implicit TLS via SMTP_SSL, no starttls upgrade."""
        provider = SMTPEmailProvider(
            settings_obj=_provider_settings(SMTP_TLS_MODE="ssl", SMTP_PORT=465)
        )
        mock_client = MagicMock()
        ssl_cls = MagicMock()
        ssl_cls.return_value.__enter__.return_value = mock_client

        with patch("app.core.email.smtplib.SMTP_SSL", ssl_cls), patch(
            "app.core.email.smtplib.SMTP"
        ) as smtp_cls:
            result = await provider.send_password_reset(
                "student@example.edu.pk", "654321"
            )

        assert result is True
        ssl_cls.assert_called_once()
        assert ssl_cls.call_args.args[:2] == ("smtp.example.com", 465)
        smtp_cls.assert_not_called()
        mock_client.starttls.assert_not_called()
        mock_client.send_message.assert_called_once()

        message = mock_client.send_message.call_args[0][0]
        assert "654321" in message.get_content()

    async def test_no_auth_mode_skips_login(self):
        """No SMTP_USERNAME configured → connection without login."""
        provider = SMTPEmailProvider(
            settings_obj=_provider_settings(SMTP_USERNAME="", SMTP_PASSWORD="")
        )
        mock_client = MagicMock()
        smtp_cls = MagicMock()
        smtp_cls.return_value.__enter__.return_value = mock_client

        with patch("app.core.email.smtplib.SMTP", smtp_cls):
            result = await provider.send_otp(
                "student@example.edu.pk", "123456", "login"
            )

        assert result is True
        mock_client.login.assert_not_called()
        mock_client.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# Settings validation — plaintext SMTP rejected in production
# ---------------------------------------------------------------------------


class TestSMTPConfigValidation:
    """Startup fail-closed: production requires SMTP TLS."""

    def test_production_rejects_plaintext_smtp(self):
        with pytest.raises(ValidationError) as exc_info:
            _production_settings(SMTP_TLS_MODE="none")
        assert "SMTP_TLS_MODE" in str(exc_info.value)

    def test_production_allows_starttls_and_ssl(self):
        assert _production_settings(SMTP_TLS_MODE="starttls").SMTP_TLS_MODE == "starttls"
        assert _production_settings(SMTP_TLS_MODE="ssl").SMTP_TLS_MODE == "ssl"

    def test_development_allows_plaintext_smtp(self):
        """Development may use plaintext SMTP (e.g., local mail catcher)."""
        from app.core.config import Settings

        dev = Settings(
            APP_ENV="development",
            SMTP_HOST="localhost",
            SMTP_FROM_EMAIL="dev@example.com",
            SMTP_TLS_MODE="none",
        )
        assert dev.SMTP_TLS_MODE == "none"
