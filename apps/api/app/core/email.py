"""Email provider abstraction.

Provides a pluggable email delivery mechanism. In development, OTPs are
logged to the console or returned for testing. In production, emails are
delivered over standard SMTP (SMTPEmailProvider) using environment
configuration — no vendor SDK, no credentials in source code.
"""

import asyncio
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.message import EmailMessage

import structlog

logger = structlog.get_logger(__name__)


class EmailProvider(ABC):
    """Abstract email provider interface."""

    @abstractmethod
    async def send_otp(self, to_email: str, otp: str, purpose: str) -> bool:
        """Send an OTP email. Returns True if sent successfully."""
        ...

    @abstractmethod
    async def send_password_reset(self, to_email: str, otp: str) -> bool:
        """Send a password reset OTP email."""
        ...


class DevelopmentEmailProvider(EmailProvider):
    """Development email provider that logs OTPs to the console.

    This is safe for local development — no real emails are sent.
    OTPs are logged in structured format for easy debugging.
    """

    async def send_otp(self, to_email: str, otp: str, purpose: str) -> bool:
        logger.info(
            "OTP sent (development mode)",
            email=to_email,
            otp=otp,
            purpose=purpose,
        )
        return True

    async def send_password_reset(self, to_email: str, otp: str) -> bool:
        logger.info(
            "Password reset OTP sent (development mode)",
            email=to_email,
            otp=otp,
        )
        return True


class SMTPEmailProvider(EmailProvider):
    """Production email provider using standard SMTP.

    Transport: smtplib executed via asyncio.to_thread (smtplib is
    blocking). TLS behavior is explicit via settings.SMTP_TLS_MODE:

    - "starttls" (default): upgrade a plaintext connection (normally
      port 587) using the system trust store.
    - "ssl": implicit TLS from connect (normally port 465).
    - "none": plaintext — only reachable outside production; Settings
      validation rejects it when APP_ENV=production.

    Fail-closed contract: if SMTP_HOST or SMTP_FROM_EMAIL is empty, or
    the SMTP transaction fails, the provider logs the failure and
    returns False — it never pretends an email was delivered. The OTP
    security model (hashing, expiry, attempt limits) lives in the auth
    service and is untouched by this transport.

    Configuration comes exclusively from environment variables
    (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL,
    SMTP_TLS_MODE) — no credentials in source code.
    """

    def __init__(self, settings_obj: object | None = None) -> None:
        if settings_obj is None:
            from app.core.config import settings as settings_obj

        self._settings = settings_obj

    @property
    def _configured(self) -> bool:
        s = self._settings
        return bool(s.SMTP_HOST and s.SMTP_FROM_EMAIL)

    async def send_otp(self, to_email: str, otp: str, purpose: str) -> bool:
        subject = f"Your UniServe {purpose} code"
        body = (
            f"Your UniServe {purpose} code is: {otp}\n\n"
            "This code expires in 10 minutes. If you did not request it, "
            "you can safely ignore this email.\n"
        )
        return await self._send(to_email, subject, body, purpose=purpose)

    async def send_password_reset(self, to_email: str, otp: str) -> bool:
        subject = "Your UniServe password reset code"
        body = (
            f"Your UniServe password reset code is: {otp}\n\n"
            "This code expires in 10 minutes. If you did not request a "
            "password reset, you can safely ignore this email.\n"
        )
        return await self._send(to_email, subject, body, purpose="password reset")

    async def _send(
        self, to_email: str, subject: str, text: str, *, purpose: str
    ) -> bool:
        s = self._settings
        if not self._configured:
            # Fail closed: report failure instead of pretending delivery.
            # The external SMTP account is a deployment prerequisite.
            logger.error(
                "SMTP configuration incomplete — email not sent "
                "(set SMTP_HOST and SMTP_FROM_EMAIL)",
                to_email=to_email,
                purpose=purpose,
                smtp_host_configured=bool(s.SMTP_HOST),
                from_configured=bool(s.SMTP_FROM_EMAIL),
            )
            return False

        message = EmailMessage()
        message["From"] = s.SMTP_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text)

        try:
            await asyncio.to_thread(self._send_sync, message)
        except Exception as exc:  # noqa: BLE001 — transport errors must not raise into auth
            # Never raise into the auth flow — report failure; the OTP
            # security model decides what happens next.
            logger.error(
                "SMTP send failed — email not delivered",
                to_email=to_email,
                purpose=purpose,
                error=str(exc),
            )
            return False

        logger.info("Email sent via SMTP", to_email=to_email, purpose=purpose)
        return True

    def _send_sync(self, message: EmailMessage) -> None:
        """Blocking SMTP transaction — executed in a worker thread."""
        s = self._settings
        tls_mode = s.SMTP_TLS_MODE

        if tls_mode == "ssl":
            # Implicit TLS from connect (normally port 465).
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                s.SMTP_HOST, s.SMTP_PORT, context=context, timeout=30
            ) as client:
                if s.SMTP_USERNAME:
                    client.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
                client.send_message(message)
            return

        with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=30) as client:
            if tls_mode == "starttls":
                # Upgrade the connection; system trust store, no
                # certificate verification disabled anywhere.
                client.starttls(context=ssl.create_default_context())
            if s.SMTP_USERNAME:
                client.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
            client.send_message(message)


def get_email_provider() -> EmailProvider:
    """Factory function to get the appropriate email provider.

    Returns DevelopmentEmailProvider in development/testing (OTPs are
    logged to the console — never sent over the network). In
    staging/production returns SMTPEmailProvider, which delivers over
    standard SMTP and fails closed (reports failure) when SMTP
    configuration is absent.
    """
    from app.core.config import settings

    if settings.APP_ENV in ("development", "testing"):
        return DevelopmentEmailProvider()
    return SMTPEmailProvider()
