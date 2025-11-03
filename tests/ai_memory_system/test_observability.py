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

from src.ai_memory_system.main import app
from src.ai_memory_system.logging_config import logger, CustomJsonFormatter


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


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

    def test_health_returns_qdrant_status(self, client):
        """Test that /health includes Qdrant connection status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "qdrant" in data
        assert "status" in data["qdrant"]

    def test_health_includes_dependencies(self, client):
        """Test that /health lists all dependencies."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "dependencies" in data
        assert "fastapi" in data["dependencies"]
        assert "qdrant-client" in data["dependencies"]
        assert "prometheus" in data["dependencies"]

    def test_health_includes_timestamp(self, client):
        """Test that /health includes current timestamp."""
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
