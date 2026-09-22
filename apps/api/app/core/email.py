"""Email provider abstraction.

Provides a pluggable email delivery mechanism. In development, OTPs are
logged to the console or returned for testing. In production, integrate
a real email provider (SMTP, SendGrid, AWS SES, etc.).
"""

from abc import ABC, abstractmethod

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


class ProductionEmailProvider(EmailProvider):
    """Production email provider — placeholder for real integration.

    Replace this with actual SMTP/SES/SendGrid integration when deploying.
    """

    async def send_otp(self, to_email: str, otp: str, purpose: str) -> bool:
        logger.info(
            "OTP email sent (production mode)",
            email=to_email,
            purpose=purpose,
            otp_hash=hash(otp),  # Log hash, not the actual OTP
        )
        # TODO: Implement real email sending (SMTP/SES/SendGrid)
        # For now, this is a placeholder
        logger.warning("Production email provider not yet configured — OTP not delivered")
        return False

    async def send_password_reset(self, to_email: str, otp: str) -> bool:
        logger.info("Password reset email sent (production mode)", email=to_email)
        # TODO: Implement real email sending
        logger.warning("Production email provider not yet configured — email not delivered")
        return False


def get_email_provider() -> EmailProvider:
    """Factory function to get the appropriate email provider.

    Returns DevelopmentEmailProvider in development/testing,
    ProductionEmailProvider in production.
    """
    from app.core.config import settings

    if settings.APP_ENV in ("development", "testing"):
        return DevelopmentEmailProvider()
    return ProductionEmailProvider()
