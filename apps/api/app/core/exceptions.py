"""Custom exception classes for the UniServe API.

Provides consistent error handling with proper HTTP status codes.
"""

from typing import Any


class UniServeException(Exception):  # noqa: N818
    """Base exception for UniServe application."""

    def __init__(self, message: str = "An unexpected error occurred", code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ServiceUnavailableError(UniServeException):
    """Service is temporarily unavailable — required backend not configured."""

    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message=message, code="SERVICE_UNAVAILABLE")


class NotFoundException(UniServeException):
    """Resource not found."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        detail = f"{resource} not found" + (f": {identifier}" if identifier else "")
        super().__init__(message=detail, code="NOT_FOUND")


class AlreadyExistsException(UniServeException):
    """Resource already exists (conflict)."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        detail = f"{resource} already exists" + (f": {identifier}" if identifier else "")
        super().__init__(message=detail, code="ALREADY_EXISTS")


class AuthenticationError(UniServeException):
    """Authentication failed."""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message=message, code="AUTHENTICATION_ERROR")


class AuthorizationError(UniServeException):
    """Authorization failed — insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, code="AUTHORIZATION_ERROR")


class TokenExpiredError(UniServeException):
    """Token has expired."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(message=message, code="TOKEN_EXPIRED")


class TokenRevokedError(UniServeException):
    """Token has been revoked."""

    def __init__(self, message: str = "Token has been revoked"):
        super().__init__(message=message, code="TOKEN_REVOKED")


class OTPError(UniServeException):
    """OTP verification failed."""

    def __init__(self, message: str = "Invalid or expired OTP"):
        super().__init__(message=message, code="OTP_ERROR")


class RateLimitError(UniServeException):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Too many attempts. Please try again later."):
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")


class AccountLockedError(UniServeException):
    """Account is temporarily locked."""

    def __init__(self, message: str = "Account temporarily locked. Try again later."):
        super().__init__(message=message, code="ACCOUNT_LOCKED")


class AccountSuspendedError(UniServeException):
    """Account is suspended."""

    def __init__(self, message: str = "Account has been suspended"):
        super().__init__(message=message, code="ACCOUNT_SUSPENDED")


class EmailNotVerifiedError(UniServeException):
    """Email address is not verified."""

    def __init__(self, message: str = "Email address is not verified"):
        super().__init__(message=message, code="EMAIL_NOT_VERIFIED")


class InvalidEmailDomainError(UniServeException):
    """Email does not match any recognized university pattern."""

    def __init__(self, message: str = "Email does not match a recognized university domain"):
        super().__init__(message=message, code="INVALID_EMAIL_DOMAIN")


class ValidationError(UniServeException):
    """Input validation failed."""

    def __init__(self, message: str = "Validation error", details: Any = None):
        super().__init__(message=message, code="VALIDATION_ERROR")
        self.details = details


class PINError(UniServeException):
    """PIN authentication failed."""

    def __init__(self, message: str = "Invalid PIN"):
        super().__init__(message=message, code="PIN_ERROR")


class PINLockedError(UniServeException):
    """PIN authentication is temporarily locked."""

    def __init__(self, message: str = "PIN authentication locked. Try again later."):
        super().__init__(message=message, code="PIN_LOCKED")
