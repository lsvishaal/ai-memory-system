# AI Memory System - Task Runner
# https://github.com/lsvishaal/ai-memory-system

# Default recipe (show help)
default:
    @just --list

# === Development ===

# Install dependencies
install:
    uv sync

# Run development server with hot reload
dev:
    uv run uvicorn src.ai_memory_system.main:app --reload --host 0.0.0.0 --port 8000

# Generate seed embeddings
seed:
    uv run python scripts/seed.py

# === Testing ===

# Run all tests
test:
    uv run pytest tests/ -v

# Run tests with coverage
test-cov:
    uv run pytest tests/ --cov=src --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

# === Code Quality ===

# Run linter
lint:
    uv run ruff check .

# Format code
fmt:
    uv run ruff format .

# Type check
typecheck:
    uv run mypy src/

# Run all checks (lint + typecheck + test)
check: lint typecheck test

# === Docker ===

# Build Docker images
docker-build:
    docker compose build

# Start services
docker-up:
    docker compose up -d
    @echo "Services started:"
    @echo "  FastAPI: http://localhost:8000"
    @echo "  Qdrant:  http://localhost:6333"

# Stop services
docker-down:
    docker compose down

# Show service status
docker-ps:
    docker compose ps

# View logs
docker-logs:
    docker compose logs -f

# Check service health
docker-health:
    @echo "=== FastAPI ===" && curl -s http://localhost:8000/health | jq . || echo "Not running"
    @echo "\n=== Qdrant ===" && curl -s http://localhost:6333 | jq . || echo "Not running"

# Restart services
docker-restart:
    docker compose restart

# Open shell in API container
docker-shell:
    docker compose exec memory-api /bin/bash

# Run tests in Docker
docker-test:
    docker compose exec memory-api pytest tests/ -v

# Clean Docker resources
docker-clean:
    docker compose down -v
    docker system prune -f

# === Utilities ===

# Clean cache files
clean:
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
    @find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @echo "✓ Cache cleaned"
