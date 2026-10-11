"""Tests for IP-based auth rate limiting (B15)."""

import pytest

from app.core.rate_limit import SlidingWindowLimiter, check_auth_rate_limit
from app.core.exceptions import RateLimitError


class TestSlidingWindowLimiter:
    def test_allows_up_to_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            assert lim.is_allowed("k", 5, 60) is True

    def test_blocks_over_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.is_allowed("k", 5, 60)
        assert lim.is_allowed("k", 5, 60) is False

    def test_keys_are_independent(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.is_allowed("a", 5, 60)
        assert lim.is_allowed("b", 5, 60) is True

    def test_reset_clears_history(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.is_allowed("k", 5, 60)
        lim.reset("k")
        assert lim.is_allowed("k", 5, 60) is True


class FakeClient:
    host = "1.2.3.4"


class FakeRequest:
    headers = {}
    client = FakeClient()


class TestCheckAuthRateLimit:
    def test_login_limit_enforced(self, monkeypatch):
        from app.core import rate_limit
        from app.core.config import settings

        # The suite runs with APP_ENV=testing (limiter disabled); force it
        # on for this test.
        monkeypatch.setattr(settings, "APP_ENV", "development")

        req = FakeRequest()
        # 20 logins allowed per minute per IP
        for _ in range(20):
            check_auth_rate_limit(req, "login")
        with pytest.raises(RateLimitError):
            check_auth_rate_limit(req, "login")
        # Clean up so other tests are unaffected
        rate_limit.get_limiter().reset("auth:login:1.2.3.4")

    def test_unknown_endpoint_gets_default(self, monkeypatch):
        from app.core import rate_limit
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_ENV", "development")

        req = FakeRequest()
        for _ in range(30):
            check_auth_rate_limit(req, "nonexistent_endpoint")
        with pytest.raises(RateLimitError):
            check_auth_rate_limit(req, "nonexistent_endpoint")
        rate_limit.get_limiter().reset("auth:nonexistent_endpoint:1.2.3.4")

    def test_skipped_in_testing_env(self):
        # With APP_ENV=testing (the suite default), no limit is enforced.
        req = FakeRequest()
        for _ in range(50):
            check_auth_rate_limit(req, "login")  # must not raise
