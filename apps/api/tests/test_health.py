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


@pytest.mark.asyncio
async def test_readiness_ready_with_schema(client):
    """Migrated database: readiness reports ready + schema present.

    Phase 28A: readiness now verifies a core application table in addition
    to connectivity, so a wiped schema cannot be reported as ready.
    """
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["schema"] == "present"
    assert data["service"] == "uniserve-api"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_degraded_when_schema_missing(client):
    """SELECT 1 success + missing core tables must report degraded.

    Regression guard for the Phase 28A disaster-recovery rehearsal: after a
    schema wipe the database server still answers SELECT 1, but the API is
    not operational. Readiness must surface that state as degraded.
    """
    from app.core.database import get_db
    from app.main import app

    class _SchemaMissingSession:
        """Fake session: SELECT 1 works, core-table query fails."""

        async def execute(self, statement, *_args, **_kwargs):
            if "users" in str(statement):
                raise RuntimeError('relation "users" does not exist')
            return None

    async def _fake_db():
        yield _SchemaMissingSession()

    app.dependency_overrides[get_db] = _fake_db
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "connected"
    assert data["schema"] == "missing"


@pytest.mark.asyncio
async def test_readiness_degraded_when_db_disconnected(client):
    """Database connectivity failure must report degraded (unchanged)."""
    from app.core.database import get_db
    from app.main import app

    class _DisconnectedSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

    async def _fake_db():
        yield _DisconnectedSession()

    app.dependency_overrides[get_db] = _fake_db
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "disconnected"
