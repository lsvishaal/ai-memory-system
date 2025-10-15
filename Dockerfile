# syntax=docker/dockerfile:1.5

################################################################################
# Stage 1: Builder - Install dependencies with UV
################################################################################
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Set UV environment variables for optimal build
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (separate layer for optimal caching)
# Using readonly mounts to prevent accidental modifications
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,readonly \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    uv sync --frozen --no-install-project --no-dev

# Copy application source code
COPY . /app

# Install the project itself (keep editable for proper import paths)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

################################################################################
# Stage 2: Runtime - Minimal production image
################################################################################
FROM python:3.11-slim-bookworm AS runtime

# Combine apt-get, user creation, and cleanup in single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    groupadd -r app && useradd -r -g app -u 1000 app && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment and source code from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

# Place venv bin directory at front of PATH for automatic activation
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER app

# Expose FastAPI default port
EXPOSE 8000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Use uvicorn directly for production deployment
CMD ["uvicorn", "src.ai_memory_system.main:app", "--host", "0.0.0.0", "--port", "8000"]
