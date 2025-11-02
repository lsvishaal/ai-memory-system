"""
AI Memory Infrastructure System

A FastAPI-based REST API for managing vector embeddings and semantic search.
Provides health monitoring, dependency information, and Qdrant vector operations.

Stage 0-1 Implementation:
- FastAPI foundation with health checks
- Qdrant client integration
- Vector upsert and query endpoints
- Prometheus metrics instrumentation
"""
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional, Union
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from prometheus_fastapi_instrumentator import Instrumentator

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ai_memory")
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "384"))  # all-MiniLM-L6-v2 default


# Pydantic models for request/response validation
class VectorPoint(BaseModel):
    """Single vector point for upsertion."""
    id: Union[int, str, UUID] = Field(
        ..., 
        description="Unique identifier (integer or UUID string)",
        examples=[1, "550e8400-e29b-41d4-a716-446655440000"]
    )
    vector: List[float] = Field(
        ..., 
        description="Dense vector embedding (384 dimensions)",
        min_length=384,
        max_length=384,
        examples=[[0.1] * 384]
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata as key-value pairs",
        examples=[{"text": "example content", "category": "demo"}]
    )


class UpsertRequest(BaseModel):
    """Batch upsert request model."""
    points: List[VectorPoint] = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="List of vectors to insert/update (1-1000 vectors per request)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "points": [
                        {
                            "id": 1,
                            "vector": [0.1] * 384,
                            "payload": {"text": "Machine learning basics", "category": "AI"}
                        },
                        {
                            "id": 2,
                            "vector": [0.2] * 384,
                            "payload": {"text": "Neural networks explained", "category": "AI"}
                        }
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
        examples=[[0.15] * 384]
    )
    limit: int = Field(
        default=10, 
        ge=1, 
        le=100, 
        description="Maximum number of results to return (1-100)",
        examples=[10]
    )
    score_threshold: Optional[float] = Field(
        default=None, 
        ge=0.0, 
        le=1.0, 
        description="Minimum similarity score (0.0-1.0, optional)",
        examples=[0.7]
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vector": [0.15] * 384,
                    "limit": 5,
                    "score_threshold": 0.7
                }
            ]
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
    try:
        qdrant_client = QdrantClient(url=QDRANT_URL)
        
        # Test connection
        qdrant_client.get_collections()
        
        # Create collection if it doesn't exist
        try:
            qdrant_client.get_collection(COLLECTION_NAME)
        except (UnexpectedResponse, Exception):
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                )
            )
        
        print(f"✅ Connected to Qdrant at {QDRANT_URL}")
        print(f"✅ Collection '{COLLECTION_NAME}' ready")
    except Exception as e:
        print(f"⚠️  Qdrant connection failed: {e}")
        print(f"⚠️  API will start but vector operations will fail")
        qdrant_client = None
    
    yield
    
    # Shutdown: Cleanup
    if qdrant_client:
        qdrant_client.close()


# Initialize FastAPI app
app = FastAPI(
    title="AI Memory System",
    description="Vector database-powered memory system for AI applications",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Setup Prometheus metrics
Instrumentator().instrument(app).expose(app)


@app.get("/")
def read_root() -> Dict[str, Any]:
    """
    Root endpoint providing basic service information.
    Returns service status and current timestamp in ISO format.
    """
    return {
        "message": "AI Memory System API",
        "status": "healthy",
        "stage": "0-1",
        "description": "Vector database operations with Qdrant",
        "timestamp": datetime.now(UTC).isoformat()
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring and diagnostics.
    Returns service status, version, dependency information, and Qdrant connection status.
    Used by load balancers and monitoring systems to verify service availability.
    """
    qdrant_status = "disconnected"
    qdrant_info = None
    
    if qdrant_client:
        try:
            collections = qdrant_client.get_collections()
            qdrant_status = "connected"
            qdrant_info = {
                "collections_count": len(collections.collections),
                "url": QDRANT_URL
            }
        except Exception as e:
            qdrant_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if qdrant_client else "degraded",
        "service": "ai-memory-system",
        "version": "0.1.0",
        "dependencies": {
            "fastapi": "0.119+",
            "qdrant-client": "1.15+",
            "uvicorn": "0.37+",
            "prometheus": "enabled"
        },
        "qdrant": {
            "status": qdrant_status,
            "info": qdrant_info
        },
        "timestamp": datetime.now(UTC).isoformat()
    }


@app.post("/upsert", status_code=status.HTTP_200_OK)
def upsert_vectors(request: UpsertRequest) -> Dict[str, Any]:
    """
    Store vectors in the collection.
    
    Insert or update vectors with unique IDs and optional metadata.
    Accepts 1-1000 vectors per request. Each vector must be 384 dimensions.
    
    Returns the number of vectors stored and operation time.
    """
    if not qdrant_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected. Please try again later."
        )
    
    start_time = time.perf_counter()
    
    try:
        # Convert Pydantic models to Qdrant points
        points = [
            models.PointStruct(
                id=point.id,
                vector=point.vector,
                payload=point.payload or {}
            )
            for point in request.points
        ]
        
        # Upsert to Qdrant
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
        elapsed = time.perf_counter() - start_time
        
        return {
            "status": "success",
            "collection": COLLECTION_NAME,
            "upserted_count": len(points),
            "elapsed_ms": round(elapsed * 1000, 2)
        }
    
    except Exception as e:
        error_msg = str(e)
        
        # Provide helpful error messages
        if "dimension" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vector dimension mismatch. Expected 384 dimensions, check your input vectors."
            )
        elif "point id" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid vector ID. Use integers (0-4294967295) or UUID strings."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store vectors: {error_msg}"
            )


@app.post("/query", response_model=List[QueryResult])
def query_vectors(request: QueryRequest) -> List[QueryResult]:
    """
    Find similar vectors using semantic search.
    
    Provide a query vector to find the most similar stored vectors.
    Results are ranked by similarity score (1.0 = identical, 0.0 = opposite).
    
    Optionally filter results by minimum score threshold.
    """
    if not qdrant_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected. Please try again later."
        )
    
    try:
        # Query Qdrant
        search_result = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=request.vector,
            limit=request.limit,
            score_threshold=request.score_threshold
        )
        
        # Convert to response model
        results = [
            QueryResult(
                id=str(hit.id),
                score=hit.score,
                payload=hit.payload
            )
            for hit in search_result
        ]
        
        return results
    
    except Exception as e:
        error_msg = str(e)
        
        if "dimension" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vector dimension mismatch. Expected 384 dimensions, check your query vector."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Search failed: {error_msg}"
            )


@app.get("/collections")
def list_collections() -> Dict[str, Any]:
    """
    List all vector collections.
    
    Shows collection names and the number of vectors stored in each.
    """
    if not qdrant_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database is not connected. Please try again later."
        )
    
    try:
        collections = qdrant_client.get_collections()
        return {
            "collections": [
                {
                    "name": col.name,
                    "vectors_count": qdrant_client.count(col.name).count
                }
                for col in collections.collections
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
