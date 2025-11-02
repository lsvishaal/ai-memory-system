# AI Memory System

Production-grade vector database infrastructure for AI applications with semantic search, RAG capabilities, and scalable memory management.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.119+-green.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.15+-red.svg)](https://qdrant.tech/)
[![Tests](https://img.shields.io/badge/Tests-20%20passing-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-74%25-yellow.svg)](htmlcov/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Stage 1 Complete** ✅ — Vector operations, benchmarks, and comprehensive testing

## Features

- 🚀 **FastAPI** - High-performance async REST API
- 🧠 **Vector Search** - Semantic similarity search with Qdrant
- 📊 **Performance** - 1,500+ vectors/sec upsert, <6ms p95 query latency
- 🎯 **Scalable** - Tested with 100K+ vectors
- 🐳 **Docker Ready** - Optimized multi-stage builds (<350MB)
- ✅ **Type Safe** - Full type hints with mypy validation
- 🧪 **Tested** - 20 tests, 74% coverage with edge cases

## Quick Start

```bash
# Clone repository
git clone https://github.com/lsvishaal/ai-memory-system
cd ai-memory-system

# Start services (FastAPI + Qdrant)
docker compose up -d

# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
# Metrics at http://localhost:8000/metrics

# Run benchmarks
uv run python scripts/benchmark.py
```

### Performance Benchmarks

| Scale | Upsert (vectors/sec) | Query p95 (ms) | Vectors Stored |
|-------|---------------------|----------------|----------------|
| 1K    | 1,540               | 3.37           | 1,003          |
| 10K   | 1,578               | 3.98           | 10,003         |
| 100K  | 1,438               | 5.63           | 100,003        |

*Tested on: Docker Desktop (4 CPU, 8GB RAM), Qdrant in-memory mode*

**Key Metrics:**
- ✅ p95 latency < 100ms target (achieved: 5.63ms)
- ✅ Throughput > 1000 vectors/sec (achieved: 1,438-1,578)
- ✅ Handles 100K+ vectors efficiently

## Commands

```bash
# Development
uv run uvicorn src.ai_memory_system.main:app --reload  # Start dev server

# Testing
uv run pytest tests/ -v                # Run all tests
uv run pytest tests/ --cov            # With coverage
uv run python scripts/benchmark.py    # Run performance benchmarks

# Docker
docker compose up -d                  # Start services
docker compose down                   # Stop services
docker compose logs -f memory-api     # View API logs
docker compose restart memory-api     # Restart API

# Code Quality
uv run ruff check .                   # Lint
uv run ruff format .                  # Format
uv run mypy src/                      # Type check
```

## Project Structure

```
ai-memory-system/
├── src/ai_memory_system/
│   ├── __init__.py
│   └── main.py                    # FastAPI app with Qdrant integration
├── tests/
│   ├── test_main.py               # Basic endpoint tests
│   └── test_endpoints.py          # Comprehensive endpoint tests
├── scripts/
│   └── benchmark.py               # Performance benchmarking
├── .github/
│   ├── copilot-instructions.md    # Copilot behavior rules
│   └── copilot-instructions-docker.md  # Docker optimization guide
├── docker-compose.yml             # Service orchestration
├── Dockerfile                     # Optimized multi-stage build
└── pyproject.toml                 # Dependencies (UV managed)
```

## API Endpoints

### `POST /upsert`
Store vectors in batch (up to 1000 per request)

**Request:**
```json
{
  "points": [
    {
      "id": 1,
      "vector": [0.1, 0.2, ...],  // 384 dimensions
      "payload": {"text": "example", "metadata": "..."}
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "collection": "ai_memory",
  "upserted_count": 1,
  "elapsed_ms": 8.45
}
```

### `POST /query`
Semantic similarity search

**Request:**
```json
{
  "vector": [0.1, 0.2, ...],  // 384 dimensions
  "limit": 10,
  "score_threshold": 0.7  // optional
}
```

**Response:**
```json
[
  {
    "id": "1",
    "score": 0.95,
    "payload": {"text": "similar content"}
  }
]
```

### `GET /collections`
List all vector collections

```json
{
  "collections": [
    {
      "name": "ai_memory",
      "vectors_count": 100003
    }
  ]
}
```

### `GET /`
Service information

```json
{
  "message": "AI Memory System API",
  "status": "healthy",
  "stage": "0-1",
  "description": "Vector database operations with Qdrant",
  "timestamp": "2025-10-31T17:00:00Z"
}
```

### `GET /health`
Detailed health check with Qdrant status

```json
{
  "status": "healthy",
  "service": "ai-memory-system",
  "version": "0.1.0",
  "dependencies": {
    "fastapi": "0.119+",
    "qdrant-client": "1.15+",
    "uvicorn": "0.37+",
    "prometheus": "enabled"
  },
  "qdrant": {
    "status": "connected",
    "info": {
      "collections_count": 1,
      "url": "http://vector-db:6333"
    }
  }
}
```

### `GET /metrics`
Prometheus metrics for monitoring

```
http_request_duration_seconds_count{handler="/query"} 100
http_request_duration_seconds_sum{handler="/query"} 0.563
...
```

### `GET /docs`
Interactive API documentation (Swagger UI)

## Docker Deployment

```bash
# Build images
just docker-build

# Start services (FastAPI + Qdrant)
just docker-up

# Check health
just docker-health

# View logs
just docker-logs

# Stop services
just docker-down
```

### Services

- **FastAPI** - Port 8000 (REST API)
- **Qdrant** - Ports 6333 (HTTP), 6334 (gRPC)

## Technology Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12 | Runtime |
| UV | 0.5+ | Fast package manager (10-100x faster than pip) |
| FastAPI | 0.119+ | Async web framework |
| Qdrant | 1.15+ | Vector database |
| Pydantic | 2.0+ | Data validation |
| Prometheus | - | Metrics and monitoring |
| Docker | Latest | Containerization |
| Pytest | 8.4+ | Testing framework |

## Development

### Prerequisites

- Python 3.12
- UV package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker Desktop (for containerized deployment)

### Setup

```bash
# Clone repository
git clone https://github.com/lsvishaal/ai-memory-system
cd ai-memory-system

# Install dependencies
uv sync

# Start services
docker compose up -d

# Run tests
uv run pytest tests/ -v

# Run benchmarks
uv run python scripts/benchmark.py
```

### Code Quality

```bash
# Lint check
uv run ruff check .

# Format code
uv run ruff format .

# Type check
uv run mypy src/

# All checks
uv run ruff check . && uv run ruff format . && uv run mypy src/
```

## Environment Variables

Copy `.env.example` to `.env`:

```bash
ENVIRONMENT=production
LOG_LEVEL=info
QDRANT_URL=http://vector-db:6333
API_VERSION=v1
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# With coverage report
uv run pytest tests/ --cov=src/ai_memory_system --cov-report=html

# Run specific test file
uv run pytest tests/test_endpoints.py -v

# Run integration tests (requires running Qdrant)
uv run pytest tests/ -v -m integration

# Coverage report available at htmlcov/index.html
```

**Test Suite:**
- ✅ 20 tests passing
- ✅ 74% code coverage
- ✅ Happy path scenarios
- ✅ Edge cases and validation
- ✅ Error handling
- ✅ Mocked unit tests
- ✅ Integration tests (optional)

## Metrics & Performance

### Benchmark Results

Run benchmarks: `uv run python scripts/benchmark.py`

| Scale | Upsert Throughput | Query p50 | Query p95 | Query p99 | Memory Usage |
|-------|------------------|-----------|-----------|-----------|--------------|
| 1K    | 1,540 vec/s      | 2.85ms    | 3.37ms    | 39.2ms    | ~1 MB        |
| 10K   | 1,578 vec/s      | 3.55ms    | 3.98ms    | 4.36ms    | ~10 MB       |
| 100K  | 1,438 vec/s      | 4.66ms    | 5.63ms    | 6.12ms    | ~100 MB      |

**Achievement:**
- ✅ p95 latency: 5.63ms (target: <100ms) — **94% better**
- ✅ Throughput: 1,438 vec/s (target: >1000) — **44% better**
- ✅ Scalability: Linear performance up to 100K+ vectors

### Test Coverage

| Metric | Value |
|--------|-------|
| Tests | 20 passing, 1 skipped |
| Coverage | 74% (functional: 100%) |
| Edge Cases | Validation, errors, failures |
| Integration | Optional live tests |
| CI/CD | Ready for GitHub Actions |

### Docker Optimization

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Build Time | Timeout | 6.2s | **99% faster** |
| Image Size | ~2 GB | ~350 MB | **82% smaller** |
| Dependencies | 800 MB | 150 MB | **81% smaller** |
| Install Time | Timeout | 6.2s | **Success** |

## License

MIT

## Links

- **Repository**: https://github.com/lsvishaal/ai-memory-system
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **Just Manual**: https://just.systems/man/
