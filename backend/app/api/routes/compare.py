"""Policy comparison routes."""

from fastapi import APIRouter, HTTPException
from app.intelligence.comparator import compare_policies
from app.models.schemas import CompareRequest, CompareResponse
from app.storage.faiss_store import faiss_store
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.post("/", response_model=CompareResponse)
async def compare(request: CompareRequest):
    """Compare multiple policies side by side."""
    # Validate all policies exist
    for pid in request.policy_ids:
        if not faiss_store.has_policy(pid):
            raise HTTPException(status_code=404, detail=f"Policy '{pid}' not found")

    try:
        return await compare_policies(request)
    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
