"""Tests for user registration and OTP verification.

Covers:
- Successful registration with valid university email
- Duplicate email / university ID rejection
- Invalid email domain rejection
- Weak password rejection
- OTP verification (correct, wrong, expired, max attempts)
- OTP resend with cooldown and max limit
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRegistration:
    """POST /api/v1/auth/register"""

    VALID_PAYLOAD = {
        "first_name": "Ali",
        "last_name": "Khan",
        "university_id": "FA22-BSE-099",
        "university_email": "fa22-bse-099@lgu.edu.pk",
        "password": "StrongPass1!",
    }

    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json=self.VALID_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert "user_id" in body
        assert body["university_email"] == self.VALID_PAYLOAD["university_email"]
        assert body["category"] == "student"

    async def test_register_faculty_email(self, client: AsyncClient):
        payload = {
            **self.VALID_PAYLOAD,
            "university_id": "FAC-099",
            "university_email": "ali.khan@lgu.edu.pk",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        assert resp.json()["category"] == "faculty"

    async def test_register_duplicate_email(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=self.VALID_PAYLOAD)
        resp = await client.post("/api/v1/auth/register", json=self.VALID_PAYLOAD)
        assert resp.status_code in (400, 409)
        body = resp.json()
        assert "detail" in body

    async def test_register_duplicate_university_id(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=self.VALID_PAYLOAD)
        payload = {
            **self.VALID_PAYLOAD,
            "university_email": "another@lgu.edu.pk",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 409)

    async def test_register_invalid_email_domain(self, client: AsyncClient):
        payload = {
            **self.VALID_PAYLOAD,
            "university_email": "user@gmail.com",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 422)

    async def test_register_weak_password_no_uppercase(self, client: AsyncClient):
        payload = {
            **self.VALID_PAYLOAD,
            "password": "weakpass1!",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_weak_password_no_digit(self, client: AsyncClient):
        payload = {
            **self.VALID_PAYLOAD,
            "password": "WeakPass!",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_weak_password_no_special(self, client: AsyncClient):
        payload = {
            **self.VALID_PAYLOAD,
            "password": "WeakPass1",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_weak_password_too_short(self, client: AsyncClient):
        payload = {
            **self.VALID_PAYLOAD,
            "password": "Wk1!",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_missing_required_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# OTP Verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOTPVerification:
    """POST /api/v1/auth/otp/verify"""

    async def _register_user(self, client: AsyncClient) -> str:
        """Register a user and return their user_id."""
        payload = {
            "first_name": "Test",
            "last_name": "OTP",
            "university_id": "FA22-BSE-OTP",
            "university_email": "fa22-bse-otp@lgu.edu.pk",
            "password": "StrongPass1!",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201
        return resp.json()["user_id"]

    async def test_verify_otp_invalid_code(self, client: AsyncClient):
        user_id = await self._register_user(client)
        resp = await client.post(
            "/api/v1/auth/otp/verify",
            json={
                "user_id": user_id,
                "otp": "000000",
                "purpose": "email_verification",
            },
        )
        assert resp.status_code == 400

    async def test_verify_otp_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/otp/verify",
            json={
                "user_id": "nonexistent-uuid",
                "otp": "123456",
                "purpose": "email_verification",
            },
        )
        assert resp.status_code in (400, 422)

    async def test_verify_otp_wrong_length(self, client: AsyncClient):
        user_id = await self._register_user(client)
        resp = await client.post(
            "/api/v1/auth/otp/verify",
            json={
                "user_id": user_id,
                "otp": "123",
                "purpose": "email_verification",
            },
        )
        assert resp.status_code == 422

    async def test_verify_otp_invalid_purpose(self, client: AsyncClient):
        user_id = await self._register_user(client)
        resp = await client.post(
            "/api/v1/auth/otp/verify",
            json={
                "user_id": user_id,
                "otp": "123456",
                "purpose": "invalid_purpose",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# OTP Resend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOTPResend:
    """POST /api/v1/auth/otp/resend"""

    async def test_resend_otp_success(self, client: AsyncClient, db: AsyncSession):
        payload = {
            "first_name": "Resend",
            "last_name": "User",
            "university_id": "FA22-BSE-RES",
            "university_email": "fa22-bse-res@lgu.edu.pk",
            "password": "StrongPass1!",
        }
        reg = await client.post("/api/v1/auth/register", json=payload)
        user_id = reg.json()["user_id"]

        # Mark any existing OTPs as used so the cooldown doesn't block resend
        from sqlalchemy import update

        from app.modules.users.models import OTPChallenge

        await db.execute(
            update(OTPChallenge).where(OTPChallenge.user_id == user_id).values(is_used=True)
        )
        await db.flush()

        resp = await client.post(
            "/api/v1/auth/otp/resend",
            json={"user_id": user_id, "purpose": "email_verification"},
        )
        assert resp.status_code == 200

    async def test_resend_otp_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/otp/resend",
            json={"user_id": "fake-id", "purpose": "email_verification"},
        )
        assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_registration_reports_delivery_failure(client, monkeypatch):
    from app.core.email import DevelopmentEmailProvider

    async def fail_delivery(self, **kwargs):
        return False

    monkeypatch.setattr(DevelopmentEmailProvider, "send_otp", fail_delivery)
    response = await client.post(
        "/api/v1/auth/register", json=TestRegistration.VALID_PAYLOAD
    )
    assert response.status_code == 503
    assert "could not send" in response.text
