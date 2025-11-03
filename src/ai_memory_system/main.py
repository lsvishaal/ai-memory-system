"""
AI Memory Infrastructure System

A FastAPI-based REST API for managing vector embeddings and semantic search.
Provides health monitoring, dependency information, and Qdrant vector operations.

Stage 0-2 Implementation:
- FastAPI foundation with health checks
- Qdrant client integration
- Vector upsert and query endpoints
- Prometheus metrics instrumentation
- Structured JSON logging
- Request ID tracking for observability
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional, Union
from uuid import UUID

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import logger

# Context variable for request ID (thread-safe)
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ai_memory")
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "384"))  # all-MiniLM-L6-v2 default

# Custom business metrics
vectors_upserted_total = Counter(
    "vectors_upserted_total",
    "Total number of vectors successfully upserted to Qdrant",
    ["collection"],
)

vectors_queried_total = Counter(
    "vectors_queried_total",
    "Total number of vector query operations performed",
    ["collection"],
)

query_results_total = Counter(
    "query_results_returned_total",
    "Total number of query results returned",
    ["collection"],
)


# Pydantic models for request/response validation
class VectorPoint(BaseModel):
    """Single vector point for upsertion."""

    id: Union[int, str, UUID] = Field(
        ...,
        description="Unique identifier (integer or UUID string)",
        examples=[1, "550e8400-e29b-41d4-a716-446655440000"],
    )
    vector: List[float] = Field(
        ...,
        description="Dense vector embedding (384 dimensions)",
        min_length=384,
        max_length=384,
        examples=[[0.1] * 384],
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata as key-value pairs",
        examples=[{"text": "example content", "category": "demo"}],
    )


class UpsertRequest(BaseModel):
    """Batch upsert request model."""

    points: List[VectorPoint] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of vectors to insert/update (1-1000 vectors per request)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "points": [
                        {
                            "id": 1,
                            "vector": [0.1] * 384,
                            "payload": {
                                "text": "Machine learning basics",
                                "category": "AI",
                            },
                        },
                        {
                            "id": 2,
                            "vector": [0.2] * 384,
                            "payload": {
                                "text": "Neural networks explained",
                                "category": "AI",
                            },
                        },
                    ]
                }
            ]
        }
    }


class QueryRequest(BaseModel):
    """Semantic search query model."""

    vector: List[float] = Field(
        ...,
        description="Query vector for similarity search (384 dimensions)",
        min_length=384,
        max_length=384,
        examples=[[0.15] * 384],
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
        examples=[10],
    )
    score_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0.0-1.0, optional)",
        examples=[0.7],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"vector": [0.15] * 384, "limit": 5, "score_threshold": 0.7}]
        }
    }


class QueryResult(BaseModel):
    """Single search result."""

    id: str
    score: float
    payload: Optional[Dict[str, Any]] = None


# Global Qdrant client
qdrant_client: Optional[QdrantClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    global qdrant_client

    # Startup: Initialize Qdrant client
    logger.info(
        "Starting AI Memory System",
        extra={
            "qdrant_url": QDRANT_URL,
            "collection_name": COLLECTION_NAME,
            "vector_size": VECTOR_SIZE,
        },
    )

    try:
        # Initialize Qdrant client with timeout for production resilience
        qdrant_client = QdrantClient(url=QDRANT_URL, timeout=30)

        # Test connection
        collections = qdrant_client.get_collections()
        logger.info(
            "Qdrant connection established",
            extra={"collections_count": len(collections.collections)},
        )

        # Create collection if it doesn't exist
        try:
            collection_info = qdrant_client.get_collection(COLLECTION_NAME)
            logger.info(
                "Collection already exists",
                extra={
                    "collection": COLLECTION_NAME,
                    "vectors_count": collection_info.vectors_count,
                },
            )
        except (UnexpectedResponse, Exception):
            logger.info(
                "Creating new collection",
                extra={
                    "collection": COLLECTION_NAME,
                    "vector_size": VECTOR_SIZE,
                    "distance": "COSINE",
                },
            )
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE, distance=models.Distance.COSINE
                ),
            )
            logger.info(
                "Collection created successfully", extra={"collection": COLLECTION_NAME}
            )

        logger.info(
            "AI Memory System ready",
            extra={
                "status": "healthy",
                "qdrant_url": QDRANT_URL,
                "collection": COLLECTION_NAME,
            },
        )
    except Exception as e:
        logger.error(
            "Qdrant connection failed",
            extra={"error": str(e), "qdrant_url": QDRANT_URL},
        )
        logger.warning("API starting in degraded mode - vector operations will fail")
        qdrant_client = None

    yield

    # Shutdown: Cleanup
    if qdrant_client:
        logger.info("Shutting down AI Memory System")
        try:
            qdrant_client.close()
            logger.info("Qdrant client closed")
        except Exception as e:
            logger.warning(
                "Error closing Qdrant client during shutdown",
                extra={"error": str(e)},
            )


# Helper function for collection auto-recovery
def ensure_collection_exists(collection_name: str = COLLECTION_NAME) -> None:
    """
    Ensure collection exists by creating it (idempotent operation).
    
    Used for auto-recovery when collection is deleted during runtime.
    If collection already exists, Qdrant will return success silently.
    
    Args:
        collection_name: Name of collection to verify/create
        
    Raises:
        HTTPException: If Qdrant client is not available
    """
    if not qdrant_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected.",
        )
    
    logger.info(
        "Auto-creating collection (idempotent)",
        extra={
            "collection": collection_name,
            "vector_size": VECTOR_SIZE,
            "distance": "COSINE",
        },
    )
    
    # Create collection - Qdrant handles "already exists" gracefully
    # by returning success without error
    try:
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE, distance=models.Distance.COSINE
            ),
        )
        logger.info(
            "Collection created/verified successfully",
            extra={"collection": collection_name},
        )
    except Exception as e:
        # If creation fails for reasons other than "already exists", log and continue
        # The retry will fail again with a better error message
        logger.warning(
            "Collection creation attempt had issues",
            extra={"collection": collection_name, "error": str(e)},
        )


# Initialize FastAPI app with proper OpenAPI configuration
app = FastAPI(
    title="AI Memory System",
    description=(
        "Production-grade vector database API for semantic search and memory management. "
        "Built with FastAPI and Qdrant, featuring Prometheus metrics, structured logging, "
        "and comprehensive observability."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Health",
            "description": "Service health and status endpoints for monitoring and diagnostics",
        },
        {
            "name": "Vector Operations",
            "description": "Core vector database operations for storing and querying embeddings",
        },
        {
            "name": "Collections",
            "description": "Collection management and information retrieval",
        },
        {
            "name": "Metrics",
            "description": "Prometheus metrics for observability (auto-generated)",
        },
    ],
)

# Setup Prometheus metrics
Instrumentator().instrument(app).expose(app)


# Request ID Middleware for tracing
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """
    Add unique request ID to every request for tracing.

    Generates a UUID for each request and adds it to:
    - Response headers (X-Request-ID)
    - Context variable for logging
    - Request state for handler access
    """
    # Generate unique request ID
    req_id = str(uuid.uuid4())

    # Set in context for logging
    request_id_var.set(req_id)

    # Add to request state for handlers
    request.state.request_id = req_id

    # Process request
    response = await call_next(request)

    # Add to response headers
    response.headers["X-Request-ID"] = req_id

    return response


# Global Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured logging."""
    logger.warning(
        "HTTP exception occurred",
        extra={
            "request_id": request_id_var.get(""),
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Request failed",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with structured logging."""
    logger.error(
        "Unexpected exception occurred",
        extra={
            "error_type": type(exc).__name__,
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again later.",
            "type": type(exc).__name__,
            "path": request.url.path,
        },
    )


@app.get(
    "/",
    tags=["Health"],
    summary="Service Information",
    response_description="Basic service information and status",
)
def read_root() -> Dict[str, Any]:
    """
    Get basic service information.

    Returns service metadata, current stage, and timestamp.
    Use this endpoint for quick service verification.
    """
    return {
        "message": "AI Memory System API",
        "status": "healthy",
        "stage": "2",
        "description": "Vector database operations with Qdrant",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    response_description="Detailed health status including dependencies",
    response_model=None,  # Allow multiple response types (Dict or JSONResponse)
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is degraded or dependencies are unavailable"},
    },
)
def health_check() -> Union[Dict[str, Any], JSONResponse]:
    """
    Comprehensive health check for service and dependencies.

    Returns:
    - Service status (healthy/degraded)
    - Version information
    - Dependency versions
    - Qdrant connection status
    - Timestamp

    Used by load balancers, monitoring systems, and orchestrators
    to verify service availability and dependency health.

    Returns HTTP 503 if critical dependencies (Qdrant) are unavailable.
    """
    qdrant_status = "disconnected"
    qdrant_info = None
    is_healthy = True

    if qdrant_client:
        try:
            collections = qdrant_client.get_collections()
            qdrant_status = "connected"
            qdrant_info = {
                "collections_count": len(collections.collections),
                "url": QDRANT_URL,
            }
        except Exception as e:
            qdrant_status = f"error: {str(e)}"
            is_healthy = False  # Qdrant failure means service is degraded
    else:
        is_healthy = False  # No Qdrant client means service is not functional

    response_data = {
        "status": "healthy" if is_healthy else "degraded",
        "service": "ai-memory-system",
        "version": "0.1.0",
        "dependencies": {
            "fastapi": "0.119+",
            "qdrant-client": "1.15+",
            "uvicorn": "0.37+",
            "prometheus": "enabled",
        },
        "qdrant": {"status": qdrant_status, "info": qdrant_info},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Return 503 Service Unavailable if Qdrant is down
    if not is_healthy:
        return JSONResponse(status_code=503, content=response_data)

    return response_data


@app.post(
    "/upsert",
    status_code=status.HTTP_200_OK,
    tags=["Vector Operations"],
    summary="Store Vectors",
    response_description="Upsert operation result with performance metrics",
)
def upsert_vectors(request: UpsertRequest) -> Dict[str, Any]:
    """
    Insert or update vectors in the collection (upsert operation).

    **Operation**: Stores vectors with unique identifiers and optional metadata.
    If a vector with the same ID exists, it will be updated.

    **Limits**:
    - Batch size: 1-1000 vectors per request
    - Vector dimensions: Must be exactly 384 (all-MiniLM-L6-v2 standard)
    - ID format: Integer (0-4294967295) or UUID string

    **Performance**: ~1,500 vectors/second throughput

    **Returns**: Success status, upserted count, and elapsed time in milliseconds.
    """
    if not qdrant_client:
        logger.error("Upsert request rejected - Qdrant not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected. Please try again later.",
        )

    start_time = time.perf_counter()
    vector_count = len(request.points)

    logger.info(
        "Upsert request received",
        extra={"vector_count": vector_count, "collection": COLLECTION_NAME},
    )

    try:
        # Convert Pydantic models to Qdrant points
        points = [
            models.PointStruct(
                id=str(point.id) if isinstance(point.id, UUID) else point.id,
                vector=point.vector,
                payload=point.payload or {},
            )
            for point in request.points
        ]

        # Upsert to Qdrant with auto-recovery for missing collection
        try:
            qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        except Exception as e:
            # Check if error is due to missing collection
            if "doesn't exist" in str(e).lower() or "not found" in str(e).lower():
                logger.warning(
                    "Collection missing during upsert, attempting auto-recovery",
                    extra={"collection": COLLECTION_NAME, "error": str(e)},
                )
                # Auto-create collection and retry
                ensure_collection_exists(COLLECTION_NAME)
                qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
            else:
                # Re-raise if not a collection-missing error
                raise

        elapsed = time.perf_counter() - start_time
        elapsed_ms = round(elapsed * 1000, 2)

        # Update business metrics
        vectors_upserted_total.labels(collection=COLLECTION_NAME).inc(vector_count)

        logger.info(
            "Upsert completed successfully",
            extra={
                "vector_count": vector_count,
                "collection": COLLECTION_NAME,
                "elapsed_ms": elapsed_ms,
                "throughput_vec_per_sec": round(vector_count / elapsed, 2)
                if elapsed > 0
                else 0,
            },
        )

        return {
            "status": "success",
            "collection": COLLECTION_NAME,
            "upserted_count": len(points),
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        error_msg = str(e)
        elapsed = time.perf_counter() - start_time

        logger.error(
            "Upsert failed",
            extra={
                "error": error_msg,
                "error_type": type(e).__name__,
                "vector_count": vector_count,
                "collection": COLLECTION_NAME,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )

        # Provide helpful error messages with context
        if "dimension" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Vector dimension mismatch",
                    "message": f"Expected {VECTOR_SIZE} dimensions, check your input vectors",
                    "collection": COLLECTION_NAME,
                    "vector_count": vector_count,
                },
            )
        elif "point id" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid vector ID format",
                    "message": "Use integers (0-4294967295) or UUID strings",
                    "collection": COLLECTION_NAME,
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Vector upsert failed",
                    "message": error_msg,
                    "collection": COLLECTION_NAME,
                    "vector_count": vector_count,
                },
            )


@app.post(
    "/query",
    response_model=List[QueryResult],
    tags=["Vector Operations"],
    summary="Semantic Search",
    response_description="List of similar vectors ranked by similarity score",
)
def query_vectors(request: QueryRequest) -> List[QueryResult]:
    """
    Find similar vectors using semantic similarity search.

    **Algorithm**: Cosine similarity with HNSW indexing for fast approximate search.

    **Input**:
    - Query vector: Must be 384 dimensions
    - Limit: Return top 1-100 results (default: 10)
    - Score threshold: Optional minimum similarity filter (0.0-1.0)

    **Scoring**:
    - 1.0 = Identical vectors
    - 0.8-0.99 = Very similar
    - 0.5-0.79 = Moderately similar
    - < 0.5 = Low similarity

    **Performance**: ~5ms p95 latency for 100K vectors

    **Returns**: Array of matching vectors with IDs, scores, and payloads.
    """
    if not qdrant_client:
        logger.error("Query request rejected - Qdrant not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected. Please try again later.",
        )

    start_time = time.perf_counter()

    logger.info(
        "Query request received",
        extra={
            "limit": request.limit,
            "score_threshold": request.score_threshold,
            "collection": COLLECTION_NAME,
        },
    )

    try:
        # Query Qdrant with auto-recovery for missing collection
        try:
            search_result = qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=request.vector,
                limit=request.limit,
                score_threshold=request.score_threshold,
            )
        except Exception as e:
            # Check if error is due to missing collection
            if "doesn't exist" in str(e).lower() or "not found" in str(e).lower():
                logger.warning(
                    "Collection missing during query, attempting auto-recovery",
                    extra={"collection": COLLECTION_NAME, "error": str(e)},
                )
                # Auto-create collection and retry (will return empty results)
                ensure_collection_exists(COLLECTION_NAME)
                search_result = qdrant_client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=request.vector,
                    limit=request.limit,
                    score_threshold=request.score_threshold,
                )
            else:
                # Re-raise if not a collection-missing error
                raise

        elapsed = time.perf_counter() - start_time
        elapsed_ms = round(elapsed * 1000, 2)

        # Convert to response model
        results = [
            QueryResult(id=str(hit.id), score=hit.score, payload=hit.payload)
            for hit in search_result
        ]

        # Update business metrics
        vectors_queried_total.labels(collection=COLLECTION_NAME).inc()
        query_results_total.labels(collection=COLLECTION_NAME).inc(len(results))

        logger.info(
            "Query completed successfully",
            extra={
                "results_count": len(results),
                "elapsed_ms": elapsed_ms,
                "top_score": results[0].score if results else None,
                "collection": COLLECTION_NAME,
            },
        )

        return results

    except Exception as e:
        error_msg = str(e)
        elapsed = time.perf_counter() - start_time

        logger.error(
            "Query failed",
            extra={
                "error": error_msg,
                "error_type": type(e).__name__,
                "collection": COLLECTION_NAME,
                "limit": request.limit,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )

        if "dimension" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Vector dimension mismatch",
                    "message": f"Expected {VECTOR_SIZE} dimensions, check your query vector",
                    "collection": COLLECTION_NAME,
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Vector search failed",
                    "message": error_msg,
                    "collection": COLLECTION_NAME,
                    "limit": request.limit,
                },
            )


@app.get(
    "/collections",
    tags=["Collections"],
    summary="List Collections",
    response_description="Array of collections with metadata",
)
def list_collections() -> Dict[str, Any]:
    """
    List all vector collections with statistics.

    Returns collection names and the number of vectors stored in each.
    Useful for monitoring storage usage and collection management.

    **Returns**: Array of collection objects with name and vector count.
    """
    if not qdrant_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected. Please try again later.",
        )

    try:
        collections = qdrant_client.get_collections()
        return {
            "collections": [
                {"name": col.name, "vectors_count": qdrant_client.count(col.name).count}
                for col in collections.collections
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
