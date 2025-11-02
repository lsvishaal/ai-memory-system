"""
API Endpoint Tests

Tests for FastAPI REST endpoints to ensure correct HTTP responses,
JSON structure validation, and proper content-type headers.
"""
from fastapi.testclient import TestClient
from src.ai_memory_system.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns expected service information."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["message"] == "AI Memory System API"
    assert data["status"] == "healthy"
    assert data["stage"] == "0-1"
    assert "timestamp" in data


def test_health_endpoint():
    """Verify health endpoint returns service status and dependencies."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    # Status can be "healthy" (Qdrant connected) or "degraded" (Qdrant disconnected)
    assert data["status"] in ["healthy", "degraded"]
    assert data["service"] == "ai-memory-system"
    assert data["version"] == "0.1.0"
    assert "dependencies" in data
    assert "fastapi" in data["dependencies"]
    assert "qdrant-client" in data["dependencies"]
    assert "qdrant" in data
    assert "timestamp" in data


def test_root_returns_json():
    """Verify root endpoint uses JSON content type."""
    response = client.get("/")
    assert response.headers["content-type"] == "application/json"


def test_health_returns_json():
    """Verify health endpoint uses JSON content type."""
    response = client.get("/health")
    assert response.headers["content-type"] == "application/json"
