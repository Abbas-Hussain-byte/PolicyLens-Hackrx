"""Health check route."""

from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.config import settings
from app.storage.faiss_store import faiss_store
from app.llm.gemini import check_connection

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Check service health and connectivity."""
    gemini_ok = await check_connection()

    return HealthResponse(
        status="ok" if gemini_ok else "degraded",
        version="1.0.0",
        gemini_connected=gemini_ok,
        policies_loaded=len(faiss_store.list_policies()),
        embedding_model=settings.embedding_model,
    )


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "PolicyLens AI",
        "description": "Fast, Trusted Insurance Intelligence Platform",
        "version": "1.0.0",
        "docs": "/docs",
    }
