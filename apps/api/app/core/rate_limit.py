"""IP-based rate limiting for authentication endpoints.

B15: per-account lockouts existed, but there was no IP or global throttle,
so password spraying across many accounts was unthrottled. This module
provides a lightweight in-memory sliding-window limiter suitable for the
single-container $0 deployment. (A multi-worker deployment should back
this with Redis; the interface is deliberately small to allow that swap.)

Limits are intentionally conservative on auth endpoints: legitimate users
rarely hit them, while sprayers are stopped quickly.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.exceptions import RateLimitError


class SlidingWindowLimiter:
    """Thread-safe in-memory sliding-window rate limiter.

    Tracks per-key event timestamps in a deque; old entries are evicted
    lazily on each check, so memory stays bounded by (keys * limit).
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True and record the hit if under the limit, else False."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            hits = self._hits[key]
            # Evict expired entries from the left (oldest first).
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            # Opportunistic cleanup: drop keys with no live entries.
            if not hits:
                del self._hits[key]
            return True

    def reset(self, key: str) -> None:
        """Clear a key's history (used by tests)."""
        with self._lock:
            self._hits.pop(key, None)


# Process-wide limiter instance. Auth routers share it.
_limiter = SlidingWindowLimiter()


def get_limiter() -> SlidingWindowLimiter:
    return _limiter


def _client_ip(request: Request) -> str:
    # Respect X-Forwarded-For when behind the Caddy reverse proxy; the
    # leftmost entry is the original client.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_auth_rate_limit(request: Request, endpoint: str) -> None:
    """Enforce per-IP rate limits on authentication endpoints.

    Raises RateLimitError (429) when the IP exceeds the limit.
    Called as a FastAPI dependency so it runs before the handler.

    Skipped when APP_ENV is "testing" so the test suite (which fires
    rapid auth attempts from one client) exercises the per-account
    lockouts, not the IP throttle.
    """
    from app.core.config import settings

    if settings.APP_ENV == "testing":
        return
    # endpoint -> (max attempts, window seconds)
    limits: dict[str, tuple[int, int]] = {
        "login": (20, 60),          # 20 logins/min per IP
        "pin_login": (10, 60),      # 10 PIN attempts/min per IP
        "otp_request": (5, 300),    # 5 OTP requests/5min per IP
        "otp_verify": (10, 300),    # 10 OTP verifications/5min per IP
        "password_reset": (5, 300), # 5 reset requests/5min per IP
    }
    limit, window = limits.get(endpoint, (30, 60))
    key = f"auth:{endpoint}:{_client_ip(request)}"
    if not _limiter.is_allowed(key, limit, window):
        raise RateLimitError(
            "Too many attempts. Please wait a moment and try again."
        )
