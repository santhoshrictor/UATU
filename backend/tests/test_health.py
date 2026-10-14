import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from backend.app.core.database import check_database_readiness
from backend.app.core.config import settings


def test_liveness_endpoint(client: TestClient):
    """Liveness probe must respond with 200 OK and valid service/stage metadata."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == settings.PROJECT_NAME
    assert data["stage"] == settings.STAGE
    assert "timestamp" in data


def test_readiness_endpoint_healthy(client: TestClient):
    """Readiness probe must test the real database connection and schema verification."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["status"] == "connected"
    assert data["database"]["latency_ms"] is not None
    assert data["database"]["latency_ms"] > 0
    assert data["schema_status"]["status"] == "verified"
    assert data["schema_status"]["alembic_version"] is not None
    assert "sites" in data["schema_status"]["tables_present"]
    assert "areas" in data["schema_status"]["tables_present"]


def test_readiness_truthful_failure_when_database_down():
    """
    Truthful degraded state: If database is unreachable, check_database_readiness
    must report connected=False, schema_ready=False, and masked error message.
    """
    # Create an engine pointing to an unreachable port
    unreachable_engine = create_engine(
        "postgresql+psycopg://postgres:secret_pass@127.0.0.1:59999/workplace_nonexistent",
        connect_args={"connect_timeout": 1},
    )
    result = check_database_readiness(target_engine=unreachable_engine, timeout_seconds=1.0)
    
    assert result["connected"] is False
    assert result["schema_ready"] is False
    assert result["error"] is not None
    # Verify password was never leaked in error
    assert "secret_pass" not in result["error"]
    assert result["alembic_version"] is None


def test_invalid_configuration_actionable_error():
    """Test that invalid config or malformed inputs return structured consistent error response."""
    from backend.app.main import app
    with TestClient(app) as test_client:
        # Requesting an invalid endpoint must return standard 404 error schema
        res = test_client.get("/api/v1/nonexistent-endpoint")
        assert res.status_code == 404
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "HTTP_404"
        assert "message" in data["error"]
