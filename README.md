# AI Memory System

Production-grade vector database infrastructure for AI applications with semantic search, RAG capabilities, and scalable memory management.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.119+-green.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.15+-red.svg)](https://qdrant.tech/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- 🚀 **FastAPI** - High-performance async REST API
- 🧠 **Vector Search** - Semantic similarity search with Qdrant
- 📊 **Embeddings** - Sentence Transformers (384-dimensional vectors)
- 🐳 **Docker Ready** - Multi-stage builds with orchestration
- ✅ **Type Safe** - Full type hints with mypy validation
- 🧪 **Tested** - Comprehensive test suite with pytest

## Quick Start

```bash
# Install just command runner (one-time setup)
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin

# Install dependencies
just install

# Generate seed embeddings (1,000 vectors)
just seed

# Run development server
just dev

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Commands

```bash
# Development
just dev            # Start dev server with hot reload
just seed           # Generate embeddings
just install        # Install dependencies

# Testing
just test           # Run tests
just test-cov       # Run tests with coverage

# Code Quality
just lint           # Run linter
just fmt            # Format code
just typecheck      # Type checking
just check          # Run all checks

# Docker
just docker-up      # Start services
just docker-down    # Stop services
just docker-logs    # View logs
just docker-health  # Check health

# Utilities
just clean          # Clean cache files
just                # Show all commands
```

## Project Structure

```
ai-memory-system/
├── src/ai_memory_system/
│   ├── __init__.py
│   └── main.py              # FastAPI application
├── tests/
│   └── test_main.py         # Test suite
├── scripts/
│   └── seed.py              # Embedding generator
├── data/
│   └── seed_embeddings.json # 1,000 test vectors (12 MB)
├── docker-compose.yml       # Service orchestration
├── Dockerfile               # Multi-stage build
├── justfile                 # Task runner
└── pyproject.toml           # Dependencies
```

## API Endpoints

### `GET /`
Service information and health status

```json
{
  "message": "AI Memory System API",
  "status": "healthy",
  "timestamp": "2025-10-15T16:00:00Z"
}
```

### `GET /health`
Detailed health check with dependencies

```json
{
  "status": "healthy",
  "service": "ai-memory-system",
  "version": "0.1.0",
  "dependencies": {
    "fastapi": "0.119+",
    "qdrant-client": "1.15+",
    "sentence-transformers": "5.1+",
    "uvicorn": "0.37+"
  }
}
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
| Python | 3.11+ | Runtime |
| UV | 0.4+ | Package manager |
| FastAPI | 0.119+ | Web framework |
| Qdrant | 1.15+ | Vector database |
| Sentence Transformers | 5.1+ | Embeddings |
| Docker | Latest | Containerization |
| Just | 1.43+ | Task runner |

## Development

### Prerequisites

- Python 3.11+
- UV package manager
- Just command runner
- Docker (optional, for containerization)

### Setup

```bash
# Clone repository
git clone https://github.com/lsvishaal/ai-memory-system
cd ai-memory-system

# Install dependencies
just install

# Generate test data
just seed

# Run tests
just test

# Start development
just dev
```

### Code Quality

```bash
# Lint check
just lint

# Format code
just fmt

# Type check
just typecheck

# Run all checks
just check
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
just test

# With coverage report
just test-cov

# Coverage report available at htmlcov/index.html
```

Current coverage: **100%** (all endpoints)

## Metrics

| Metric | Value |
|--------|-------|
| Embeddings | 1,000 vectors |
| Dimensions | 384 (all-MiniLM-L6-v2) |
| Data Size | 12 MB |
| Tests | 4/4 passing |
| Coverage | 100% |
| Docker Image | ~200 MB |

## License

MIT

## Links

- **Repository**: https://github.com/lsvishaal/ai-memory-system
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **Just Manual**: https://just.systems/man/
