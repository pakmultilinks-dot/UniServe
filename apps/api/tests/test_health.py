"""Health endpoint smoke tests."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Verify the basic health endpoint returns healthy."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "uniserve-api"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_check_returns_json(client):
    """Verify the health endpoint returns proper JSON content type."""
    response = await client.get("/api/v1/health")
    assert response.headers["content-type"] == "application/json"
