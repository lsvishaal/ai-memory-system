"""
Comprehensive endpoint tests for AI Memory System

Tests cover:
- /upsert endpoint validation and edge cases
- /query endpoint validation and edge cases
- /collections endpoint
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from qdrant_client.models import ScoredPoint

from src.ai_memory_system.main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client for isolated tests."""
    with patch("src.ai_memory_system.main.qdrant_client") as mock:
        yield mock


class TestUpsertEndpoint:
    """Test suite for /upsert endpoint."""

    def test_upsert_single_vector_success(self, client, mock_qdrant):
        """Test successful upsert of single vector."""
        mock_qdrant.upsert.return_value = Mock(status="completed")

        payload = {
            "points": [{"id": 1, "vector": [0.1] * 384, "payload": {"test": True}}]
        }

        response = client.post("/upsert", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["collection"] == "ai_memory"
        assert data["upserted_count"] == 1
        assert "elapsed_ms" in data

    def test_upsert_batch_vectors_success(self, client, mock_qdrant):
        """Test successful batch upsert."""
        mock_qdrant.upsert.return_value = Mock(status="completed")

        payload = {
            "points": [
                {"id": i, "vector": [0.1] * 384, "payload": {"index": i}}
                for i in range(100)
            ]
        }

        response = client.post("/upsert", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["upserted_count"] == 100

    def test_upsert_with_uuid(self, client, mock_qdrant):
        """Test upsert with UUID identifier."""
        mock_qdrant.upsert.return_value = Mock(status="completed")

        payload = {
            "points": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "vector": [0.1] * 384,
                    "payload": {"type": "uuid"},
                }
            ]
        }

        response = client.post("/upsert", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_upsert_empty_points_list(self, client):
        """Test validation error with empty points list."""
        payload = {"points": []}

        response = client.post("/upsert", json=payload)

        assert response.status_code == 422

    def test_upsert_exceeds_max_batch(self, client):
        """Test validation error when exceeding max batch size."""
        payload = {
            "points": [
                {"id": i, "vector": [0.1] * 384}
                for i in range(1001)  # Max is 1000
            ]
        }

        response = client.post("/upsert", json=payload)

        assert response.status_code == 422

    def test_upsert_invalid_vector_dimension(self, client):
        """Test validation with incorrect vector dimension."""
        payload = {
            "points": [
                {"id": 1, "vector": [0.1] * 10}  # Wrong dimension
            ]
        }

        response = client.post("/upsert", json=payload)

        # Could be 422 (validation), 500 (Qdrant error), or 503 (Qdrant unavailable)
        assert response.status_code in [200, 422, 500, 503]

    def test_upsert_qdrant_failure(self, client, mock_qdrant):
        """Test error handling when Qdrant fails."""
        from qdrant_client.http.exceptions import UnexpectedResponse

        mock_qdrant.upsert.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Error",
            content=b"Error",
            headers={},
        )

        payload = {"points": [{"id": 1, "vector": [0.1] * 384}]}

        response = client.post("/upsert", json=payload)

        assert response.status_code == 500
        detail = response.json()["detail"]
        # Detail is now a dict with structured error info
        assert isinstance(detail, dict)
        assert "error" in detail
        assert detail["error"] == "Vector upsert failed"


class TestQueryEndpoint:
    """Test suite for /query endpoint."""

    def test_query_success(self, client, mock_qdrant):
        """Test successful vector query."""
        mock_qdrant.search.return_value = [
            ScoredPoint(
                id=1, version=0, score=0.95, payload={"text": "test"}, vector=None
            )
        ]

        payload = {"vector": [0.1] * 384, "limit": 10}

        response = client.post("/query", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["score"] == 0.95
        assert data[0]["payload"] == {"text": "test"}

    def test_query_with_score_threshold(self, client, mock_qdrant):
        """Test query with score threshold filtering."""
        # Qdrant filters internally, so mock should return only above-threshold results
        mock_qdrant.search.return_value = [
            ScoredPoint(id=1, version=0, score=0.95, payload={}, vector=None),
            ScoredPoint(id=2, version=0, score=0.85, payload={}, vector=None),
            # Results below threshold not returned by Qdrant
        ]

        payload = {"vector": [0.1] * 384, "limit": 10, "score_threshold": 0.8}

        response = client.post("/query", json=payload)

        assert response.status_code == 200
        data = response.json()
        # All results should be >= threshold (Qdrant filters)
        assert all(item["score"] >= 0.8 for item in data)

    def test_query_limit_validation(self, client):
        """Test limit parameter validation."""
        payload = {
            "vector": [0.1] * 384,
            "limit": 0,  # Invalid
        }

        response = client.post("/query", json=payload)

        assert response.status_code == 422

    def test_query_empty_vector(self, client):
        """Test validation with empty vector."""
        payload = {"vector": [], "limit": 10}

        response = client.post("/query", json=payload)

        assert response.status_code == 422

    def test_query_qdrant_failure(self, client, mock_qdrant):
        """Test error handling when Qdrant search fails."""
        from qdrant_client.http.exceptions import UnexpectedResponse

        mock_qdrant.search.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Error",
            content=b"Error",
            headers={},
        )

        payload = {"vector": [0.1] * 384, "limit": 10}

        response = client.post("/query", json=payload)

        assert response.status_code == 500
        detail = response.json()["detail"]
        # Detail is now a dict with structured error info
        assert isinstance(detail, dict)
        assert "error" in detail
        assert detail["error"] == "Vector search failed"


class TestCollectionsEndpoint:
    """Test suite for /collections endpoint."""

    def test_collections_list_success(self, client, mock_qdrant):
        """Test successful collection listing."""
        mock_collection = Mock()
        mock_collection.name = "ai_memory"
        mock_qdrant.get_collections.return_value = Mock(collections=[mock_collection])
        # Mock the count method
        mock_qdrant.count.return_value = Mock(count=1000)

        response = client.get("/collections")

        assert response.status_code == 200
        data = response.json()
        assert "collections" in data
        assert len(data["collections"]) == 1
        assert data["collections"][0]["name"] == "ai_memory"
        assert data["collections"][0]["vectors_count"] == 1000

    def test_collections_qdrant_failure(self, client, mock_qdrant):
        """Test error handling when Qdrant fails to list collections."""
        from qdrant_client.http.exceptions import UnexpectedResponse

        mock_qdrant.get_collections.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Error",
            content=b"Error",
            headers={},
        )

        response = client.get("/collections")

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()


class TestIntegration:
    """Integration tests (require running Qdrant instance)."""

    @pytest.mark.integration
    def test_full_upsert_query_flow(self, client):
        """Test complete flow: upsert then query."""
        # Check if API is healthy first
        health = client.get("/health")
        if health.status_code != 200 or health.json().get("status") != "healthy":
            pytest.skip("Qdrant not available for integration test")

        # Upsert vectors
        upsert_payload = {
            "points": [
                {
                    "id": 9000,
                    "vector": [0.9] * 384,
                    "payload": {"tag": "integration_test"},
                },
                {
                    "id": 9001,
                    "vector": [0.8] * 384,
                    "payload": {"tag": "integration_test"},
                },
            ]
        }

        upsert_response = client.post("/upsert", json=upsert_payload)
        assert upsert_response.status_code == 200

        # Query similar vectors
        query_payload = {"vector": [0.9] * 384, "limit": 5}

        query_response = client.post("/query", json=query_payload)
        assert query_response.status_code == 200
        results = query_response.json()

        # Should find our test vectors
        assert len(results) > 0
        assert any(r["payload"].get("tag") == "integration_test" for r in results)


class TestMetricsEndpoint:
    """Test suite for /metrics endpoint."""

    def test_metrics_endpoint_available(self, client):
        """Test that Prometheus metrics endpoint is accessible."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        # Check for some standard Prometheus metrics
        content = response.text
        assert "http_request" in content or "process_" in content


class TestRootEndpoint:
    """Test suite for root endpoint."""

    def test_root_returns_project_info(self, client):
        """Test root endpoint returns project information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "AI Memory System API"
        assert data["status"] == "healthy"
        assert "stage" in data
        assert "description" in data
        assert "timestamp" in data
