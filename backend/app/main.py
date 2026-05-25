"""FastAPI main application — PolicyLens AI Backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import policies, query, compare, health
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PolicyLens AI",
    description="Fast, Trusted Insurance Intelligence Platform — API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(policies.router)
app.include_router(query.router)
app.include_router(compare.router)


@app.on_event("startup")
async def startup():
    """Verify connections on startup."""
    logger.info("🚀 PolicyLens AI starting up...")

    # Verify Gemini Embedding API connectivity
    try:
        from app.core.embedder import get_model
        get_model()  # Just creates the client — no heavy model download
        logger.info("✅ Gemini Embedding API client ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini client: {e}")

    # Check Gemini LLM connection
    try:
        from app.llm.gemini import check_connection
        ok = await check_connection()
        if ok:
            logger.info("✅ Gemini LLM API connected")
        else:
            logger.warning("⚠️ Gemini API not reachable — check your API key")
    except Exception as e:
        logger.warning(f"⚠️ Gemini connection check failed: {e}")

    # Log loaded policies
    from app.storage.faiss_store import faiss_store
    policies = faiss_store.list_policies()
    logger.info(f"📄 {len(policies)} policies loaded from disk")
    logger.info("🟢 PolicyLens AI ready")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
