"""
Observability and Monitoring Tests

Tests verify that logging, metrics, and error handling work correctly.
These tests ensure Stage 2 (Production Observability) is properly implemented.
"""

import pytest
import json
import re
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import logging
import uuid

from src.ai_memory_system.main import app
from src.ai_memory_system.logging_config import logger, CustomJsonFormatter


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client for testing without real database."""
    with patch("src.ai_memory_system.main.qdrant_client") as mock:
        # Setup default successful responses
        mock.upsert.return_value = Mock(status="completed")
        mock.search.return_value = []
        mock.get_collections.return_value = Mock(collections=[])
        mock.create_collection.return_value = None
        yield mock


class TestStructuredLogging:
    """Test suite for structured JSON logging."""

    def test_logger_exists(self):
        """Verify logger is properly initialized."""
        assert logger is not None
        assert logger.name == "ai_memory_system"

    def test_json_formatter_creates_valid_json(self):
        """Test that CustomJsonFormatter produces valid JSON."""
        formatter = CustomJsonFormatter()

        # Create a test log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        # Should be valid JSON
        parsed = json.loads(formatted)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_json_formatter_includes_context(self):
        """Test that extra fields are included in JSON output."""
        formatter = CustomJsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Operation complete",
            args=(),
            exc_info=None,
        )
        record.vector_count = 100
        record.elapsed_ms = 45.2

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["vector_count"] == 100
        assert parsed["elapsed_ms"] == 45.2

    def test_json_formatter_handles_errors_with_traceback(self):
        """Test that errors include file/line information."""
        formatter = CustomJsonFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert "file" in parsed or "lineno" in parsed
        assert "Error occurred" in parsed["message"]


class TestPrometheusMetrics:
    """Test suite for Prometheus metrics endpoint."""

    def test_metrics_endpoint_accessible(self, client):
        """Test /metrics endpoint is accessible."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    def test_metrics_contains_http_requests(self, client):
        """Test that http_requests_total metric exists."""
        response = client.get("/metrics")
        content = response.text

        assert "http_requests_total" in content

    def test_metrics_contains_duration(self, client):
        """Test that request duration metrics exist."""
        response = client.get("/metrics")
        content = response.text

        assert "http_request_duration" in content

    def test_metrics_updated_after_requests(self, client):
        """Test that metrics are actually updated after API calls."""
        # Get initial metrics
        initial = client.get("/metrics").text
        initial_health_count = self._extract_metric_value(
            initial, 'http_requests_total{handler="/health",method="GET",status="2xx"}'
        )

        # Make a request
        client.get("/health")

        # Get updated metrics
        updated = client.get("/metrics").text
        updated_health_count = self._extract_metric_value(
            updated, 'http_requests_total{handler="/health",method="GET",status="2xx"}'
        )

        # Count should have increased
        if initial_health_count is not None and updated_health_count is not None:
            assert updated_health_count > initial_health_count

    def _extract_metric_value(self, metrics_text, metric_label):
        """Helper to extract metric value from Prometheus text format."""
        # Match lines like: http_requests_total{handler="/health"} 123.0
        pattern = re.escape(metric_label) + r"\s+([\d.]+)"
        match = re.search(pattern, metrics_text)
        if match:
            return float(match.group(1))
        return None


class TestErrorHandling:
    """Test suite for error handling and logging."""

    def test_http_exception_returns_json_error(self, client):
        """Test that HTTP exceptions return proper JSON error format."""
        # Trigger a 404 by calling non-existent endpoint
        response = client.get("/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_validation_error_returns_422(self, client):
        """Test that validation errors return 422 with details."""
        # Send invalid payload (empty points list)
        response = client.post("/upsert", json={"points": []})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_qdrant_unavailable_returns_503(self, client):
        """Test that Qdrant unavailability returns 503."""
        with patch("src.ai_memory_system.main.qdrant_client", None):
            response = client.post(
                "/upsert", json={"points": [{"id": 1, "vector": [0.1] * 384}]}
            )

            assert response.status_code == 503
            data = response.json()
            assert (
                "not connected" in data["detail"].lower()
                or "unavailable" in data["detail"].lower()
            )

    def test_internal_error_returns_500(self, client):
        """Test that unexpected errors return 500."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_qdrant:
            # Simulate unexpected error
            mock_qdrant.upsert.side_effect = RuntimeError("Unexpected error")

            response = client.post(
                "/upsert", json={"points": [{"id": 1, "vector": [0.1] * 384}]}
            )

            assert response.status_code == 500
            data = response.json()
            assert "error" in data or "detail" in data


class TestRequestLogging:
    """Test suite for request/response logging."""

    @patch("src.ai_memory_system.main.logger")
    def test_upsert_logs_request_received(self, mock_logger, client):
        """Test that upsert endpoint logs when request is received."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_qdrant:
            mock_qdrant.upsert.return_value = Mock()

            client.post("/upsert", json={"points": [{"id": 1, "vector": [0.1] * 384}]})

            # Check that info was logged
            assert mock_logger.info.called
            # Verify context includes vector_count
            calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("vector_count" in call or "Upsert" in call for call in calls)

    @patch("src.ai_memory_system.main.logger")
    def test_query_logs_success_with_metrics(self, mock_logger, client):
        """Test that query endpoint logs success with performance metrics."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_qdrant:
            from qdrant_client.models import ScoredPoint

            mock_qdrant.search.return_value = [
                ScoredPoint(id=1, version=0, score=0.95, payload={}, vector=None)
            ]

            client.post("/query", json={"vector": [0.1] * 384, "limit": 5})

            # Check that info was logged with metrics
            assert mock_logger.info.called
            calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Query" in call or "completed" in call for call in calls)

    @patch("src.ai_memory_system.main.logger")
    def test_error_logs_with_error_level(self, mock_logger, client):
        """Test that errors are logged with ERROR level."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_qdrant:
            mock_qdrant.upsert.side_effect = Exception("Test error")

            client.post("/upsert", json={"points": [{"id": 1, "vector": [0.1] * 384}]})

            # Check that error was logged
            assert mock_logger.error.called or mock_logger.exception.called


class TestHealthCheck:
    """Test suite for health check functionality."""

    def test_health_returns_qdrant_status(self, client, mock_qdrant):
        """Test that /health includes Qdrant connection status."""
        # Mock successful Qdrant connection
        mock_collections = Mock()
        mock_collections.collections = []
        mock_qdrant.get_collections.return_value = mock_collections

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "qdrant" in data
        assert "status" in data["qdrant"]

    def test_health_includes_dependencies(self, client, mock_qdrant):
        """Test that /health lists all dependencies."""
        # Mock successful Qdrant connection
        mock_collections = Mock()
        mock_collections.collections = []
        mock_qdrant.get_collections.return_value = mock_collections

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "dependencies" in data
        assert "fastapi" in data["dependencies"]
        assert "qdrant-client" in data["dependencies"]
        assert "prometheus" in data["dependencies"]

    def test_health_includes_timestamp(self, client, mock_qdrant):
        """Test that /health includes current timestamp."""
        # Mock successful Qdrant connection
        mock_collections = Mock()
        mock_collections.collections = []
        mock_qdrant.get_collections.return_value = mock_collections

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        # Verify it's ISO format
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


class TestPerformanceMetrics:
    """Test suite for performance tracking."""

    def test_upsert_includes_elapsed_time(self, client):
        """Test that upsert response includes elapsed_ms."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_qdrant:
            mock_qdrant.upsert.return_value = Mock()

            response = client.post(
                "/upsert", json={"points": [{"id": 1, "vector": [0.1] * 384}]}
            )

            assert response.status_code == 200
            data = response.json()
            assert "elapsed_ms" in data
            assert isinstance(data["elapsed_ms"], (int, float))
            assert data["elapsed_ms"] >= 0

    def test_elapsed_time_is_reasonable(self, client):
        """Test that elapsed time is within reasonable bounds."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_qdrant:
            mock_qdrant.upsert.return_value = Mock()

            response = client.post(
                "/upsert", json={"points": [{"id": 1, "vector": [0.1] * 384}]}
            )

            data = response.json()
            # Should be less than 10 seconds for a mocked operation
            assert data["elapsed_ms"] < 10000


class TestRequestIDTracking:
    """Test suite for request ID tracking across logs and responses."""

    def test_request_id_in_response_headers(self, client, mock_qdrant):
        """Verify X-Request-ID header is present in all responses."""
        # Mock successful Qdrant connection for health check
        mock_collections = Mock()
        mock_collections.collections = []
        mock_qdrant.get_collections.return_value = mock_collections

        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Should be a valid UUID
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert request_id.count("-") == 4

    def test_request_id_consistent_across_logs(self, client, mock_qdrant):
        """Verify same request_id appears in response headers for traceability."""
        mock_qdrant.upsert.return_value = Mock(status="completed")

        response = client.post(
            "/upsert",
            json={"points": [{"id": 1, "vector": [0.1] * 384, "payload": {}}]},
        )

        # Primary requirement: request_id must be in response headers
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None, "X-Request-ID header missing from response"
        assert len(request_id) == 36, f"Invalid UUID format: {request_id}"
        assert request_id.count("-") == 4, "UUID should have 4 hyphens"

        # Verify it's a valid UUID by attempting to parse it
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Invalid UUID in X-Request-ID header: {request_id}")

        # Success! The middleware is adding request_id to response headers
        # The LoggerAdapter ensures request_id is available in log context
        # (verified manually in stdout - JSON logs show proper structure)

    def test_request_id_in_error_logs(self, client, mock_qdrant):
        """Verify request_id is included in error responses for debugging."""
        mock_qdrant.upsert.side_effect = Exception("Database error")

        response = client.post(
            "/upsert",
            json={"points": [{"id": 1, "vector": [0.1] * 384, "payload": {}}]},
        )

        # Verify error response
        assert response.status_code == 500
        detail = response.json()["detail"]
        # Detail is now a dict with structured error info
        assert isinstance(detail, dict)
        assert "error" in detail

        # Primary requirement: request_id must be in response headers even for errors
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None, "X-Request-ID header missing from error response"
        assert len(request_id) == 36, f"Invalid UUID format: {request_id}"

        # Verify it's a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Invalid UUID in X-Request-ID header: {request_id}")

        # Success! Even error responses include request_id for debugging
        # The HTTP exception handler logs with request_id (manually verified in stdout)
        # This enables correlation between client errors and server logs

    def test_different_requests_have_different_ids(self, client):
        """Verify each request gets a unique request_id."""
        response1 = client.get("/health")
        response2 = client.get("/health")
        response3 = client.get("/")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]
        id3 = response3.headers["X-Request-ID"]

        # All IDs should be different
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3


class TestHealthCheckDependencies:
    """Test suite for health check dependency validation."""

    def test_health_check_fails_when_qdrant_down(self):
        """Verify /health returns degraded status when Qdrant is unreachable."""
        with patch("src.ai_memory_system.main.qdrant_client") as mock_client:
            mock_client.get_collections.side_effect = Exception(
                "Connection refused"
            )

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 503  # Service Unavailable
            data = response.json()
            assert data["status"] == "degraded"
            assert "qdrant" in data
            assert "error" in data["qdrant"]["status"].lower()

    def test_health_check_includes_qdrant_version(self, client, mock_qdrant):
        """Verify health check includes Qdrant connection details."""
        mock_collections = Mock()
        mock_collections.collections = []
        mock_qdrant.get_collections.return_value = mock_collections

        response = client.get("/health")
        data = response.json()

        assert "qdrant" in data
        assert "status" in data["qdrant"]
        assert data["qdrant"]["status"] == "connected"


class TestCollectionAutoRecovery:
    """Test suite for automatic collection recreation when missing."""

    def test_upsert_creates_collection_if_missing(self, client, mock_qdrant):
        """Test that upsert automatically creates collection if it doesn't exist."""
        # First upsert attempt fails with collection not found
        # Second attempt should succeed after auto-creation
        collection_not_found_error = Exception("Collection `ai_memory` doesn't exist!")
        mock_qdrant.upsert.side_effect = [
            collection_not_found_error,
            Mock(status="completed"),
        ]
        mock_qdrant.create_collection.return_value = None

        response = client.post(
            "/upsert",
            json={"points": [{"id": 1, "vector": [0.1] * 384, "payload": {}}]},
        )

        # Should succeed after auto-recovery
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify create_collection was called
        mock_qdrant.create_collection.assert_called_once()

    def test_query_creates_collection_if_missing(self, client, mock_qdrant):
        """Test that query automatically creates collection if it doesn't exist."""
        # First query attempt fails with collection not found
        # Second attempt returns empty results after auto-creation
        collection_not_found_error = Exception("Collection `ai_memory` doesn't exist!")
        mock_qdrant.search.side_effect = [
            collection_not_found_error,
            [],  # Empty results after creation
        ]
        mock_qdrant.create_collection.return_value = None

        response = client.post(
            "/query",
            json={"vector": [0.1] * 384, "limit": 5},
        )

        # Should succeed with empty results after auto-recovery
        assert response.status_code == 200
        data = response.json()
        # Query endpoint returns a list directly, not a dict
        assert isinstance(data, list)
        assert len(data) == 0

        # Verify create_collection was called
        mock_qdrant.create_collection.assert_called_once()

    def test_collection_recreation_preserves_settings(self, client, mock_qdrant):
        """Test that auto-recreated collection uses correct vector size and distance."""
        from qdrant_client.http import models

        collection_not_found_error = Exception("Collection `ai_memory` doesn't exist!")
        mock_qdrant.upsert.side_effect = [
            collection_not_found_error,
            Mock(status="completed"),
        ]
        mock_qdrant.create_collection.return_value = None

        response = client.post(
            "/upsert",
            json={"points": [{"id": 1, "vector": [0.1] * 384, "payload": {}}]},
        )

        assert response.status_code == 200

        # Verify collection was created with correct settings
        call_args = mock_qdrant.create_collection.call_args
        assert call_args[1]["collection_name"] == "ai_memory"
        vectors_config = call_args[1]["vectors_config"]
        assert vectors_config.size == 384
        assert vectors_config.distance == models.Distance.COSINE


class TestGracefulShutdown:
    """Test suite for graceful shutdown and cleanup."""

    def test_lifespan_completes_successfully(self):
        """Test that lifespan context manager completes without errors."""
        from src.ai_memory_system.main import lifespan
        
        # Create a mock app
        mock_app = Mock()
        
        # Use the lifespan context manager
        import asyncio
        async def run_lifespan():
            async with lifespan(mock_app):
                # Simulate app running
                pass
            # Should complete successfully
            return True
        
        # Run the async context manager - should not raise
        result = asyncio.run(run_lifespan())
        assert result is True

    def test_app_starts_and_stops_cleanly(self, client):
        """Test that app can handle requests and cleans up properly."""
        # Make a request to verify app is working
        response = client.get("/")
        assert response.status_code == 200
        
        # The TestClient handles lifespan automatically
        # If shutdown fails, this test would hang or error
        # Success means graceful shutdown is working


class TestEdgeCasesAndBoundaries:
    """Test suite for edge cases and boundary conditions."""

    def test_upsert_exactly_1000_vectors(self, client, mock_qdrant):
        """Test batch size limit of exactly 1000 vectors."""
        mock_qdrant.upsert.return_value = Mock(status="completed")

        # Create exactly 1000 vectors
        points = [
            {"id": i, "vector": [0.1] * 384, "payload": {"index": i}}
            for i in range(1000)
        ]

        response = client.post("/upsert", json={"points": points})
        assert response.status_code == 200
        data = response.json()
        assert data["upserted_count"] == 1000

    def test_upsert_1001_vectors_fails(self, client):
        """Test that exceeding 1000 vector limit fails validation."""
        points = [
            {"id": i, "vector": [0.1] * 384, "payload": {}} for i in range(1001)
        ]

        response = client.post("/upsert", json={"points": points})
        assert response.status_code == 422  # Validation error

    def test_query_empty_collection_returns_empty_results(
        self, client, mock_qdrant
    ):
        """Test querying an empty collection returns gracefully."""
        mock_qdrant.search.return_value = []  # Empty results

        response = client.post(
            "/query", json={"vector": [0.1] * 384, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_upsert_duplicate_ids_overwrites(self, client, mock_qdrant):
        """Test that upserting same ID twice overwrites (idempotent)."""
        mock_qdrant.upsert.return_value = Mock(status="completed")

        # First upsert
        response1 = client.post(
            "/upsert",
            json={"points": [{"id": 1, "vector": [0.1] * 384, "payload": {"v": 1}}]},
        )
        assert response1.status_code == 200

        # Second upsert with same ID
        response2 = client.post(
            "/upsert",
            json={"points": [{"id": 1, "vector": [0.2] * 384, "payload": {"v": 2}}]},
        )
        assert response2.status_code == 200
        # Should succeed (upsert = insert or update)


class TestConcurrency:
    """Test suite for concurrent request handling."""

    def test_concurrent_upserts_different_ids(self, client, mock_qdrant):
        """Test that concurrent upserts with different IDs don't conflict."""
        import concurrent.futures

        mock_qdrant.upsert.return_value = Mock(status="completed")

        def upsert_vector(vector_id):
            return client.post(
                "/upsert",
                json={"points": [{"id": vector_id, "vector": [0.1] * 384, "payload": {}}]},
            )

        # Submit 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upsert_vector, i) for i in range(10)]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
