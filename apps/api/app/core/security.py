"""Core security utilities.

Password hashing, JWT token management, OTP generation and verification.
"""

import hashlib
import hmac
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---- Password Hashing ----

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64MB
    argon2__time_cost=3,
    argon2__parallelism=4,
    argon2__salt_len=16,
    argon2__hash_len=32,
)


def hash_password(password: str) -> str:
    """Hash a password using Argon2/bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ---- PIN Hashing ----
# PINs are short — use a different hashing strategy with stronger salt
PIN_HASH_ROUNDS = 100_000  # High iteration count for 4-digit PINs


def hash_pin(pin: str) -> str:
    """Hash a PIN using PBKDF2-HMAC-SHA256 with strong salt."""
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), PIN_HASH_ROUNDS)
    return f"{salt}${dk.hex()}"


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verify a PIN against a hash."""
    try:
        salt, expected_hex = hashed_pin.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", plain_pin.encode(), salt.encode(), PIN_HASH_ROUNDS)
        return hmac.compare_digest(dk.hex(), expected_hex)
    except (ValueError, AttributeError):
        return False


# ---- OTP Generation ----


def generate_otp() -> str:
    """Generate a cryptographically secure OTP."""
    chars = string.digits
    return "".join(secrets.choice(chars) for _ in range(settings.OTP_LENGTH))


def hash_otp(otp: str) -> str:
    """Hash an OTP for secure storage."""
    return pwd_context.hash(otp)


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Verify an OTP against its hash."""
    return pwd_context.verify(plain_otp, hashed_otp)


# ---- JWT Token Management ----


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        subject: Token subject (typically user ID)
        expires_delta: Custom expiration time
        extra_claims: Additional claims to include
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    subject: str,
    session_id: str,
    jti: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token bound to a specific session.

    Args:
        subject: Token subject (typically user ID)
        session_id: The session ID this refresh token is bound to
        jti: Unique token ID for reuse detection
        expires_delta: Custom expiration time
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
        "sid": session_id,
        "jti": jti or secrets.token_hex(18),
    }

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Returns the token payload dict or None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
