"""
AI Memory Infrastructure System

A FastAPI-based REST API for managing vector embeddings and semantic search.
Provides health monitoring and dependency information endpoints.
"""
from fastapi import FastAPI
from datetime import datetime, UTC
from typing import Dict, Any

app = FastAPI(
    title="AI Memory System",
    description="Vector database-powered memory system for AI applications",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.get("/")
def read_root() -> Dict[str, Any]:
    """
    Root endpoint providing basic service information.
    Returns service status and current timestamp in ISO format.
    """
    return {
        "message": "AI Memory System API",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat()
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring and diagnostics.
    Returns service status, version, and dependency information.
    Used by load balancers and monitoring systems to verify service availability.
    """
    return {
        "status": "healthy",
        "service": "ai-memory-system",
        "version": "0.1.0",
        "dependencies": {
            "fastapi": "0.119+",
            "qdrant-client": "1.15+",
            "sentence-transformers": "5.1+",
            "uvicorn": "0.37+"
        },
        "timestamp": datetime.now(UTC).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
