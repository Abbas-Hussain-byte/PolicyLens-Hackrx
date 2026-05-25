"""Query routes — Q&A, eligibility, exclusions, batch."""

from fastapi import APIRouter, HTTPException
from app.intelligence.answer_engine import process_query
from app.intelligence.eligibility import check_eligibility
from app.intelligence.exclusions import find_exclusions
from app.models.schemas import (
    QueryRequest,
    QueryResponse,
    EligibilityRequest,
    EligibilityResponse,
    ExclusionsResponse,
    BatchRequest,
    BatchResponse,
)
from app.storage.faiss_store import faiss_store
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """Ask a question about an uploaded policy.

    Automatically routes through the adaptive intelligence pipeline:
    - Tier 1 (Fast Info): General insurance questions
    - Tier 2 (Grounded Q&A): Policy-specific questions with source citations
    - Tier 3 (Verified): High-risk questions with verification pass
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Validate policy exists (for policy-specific questions)
    if request.policy_id and not faiss_store.has_policy(request.policy_id):
        raise HTTPException(status_code=404, detail="Policy not found. Please upload a policy first.")

    try:
        response = await process_query(request)
        return response
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


@router.post("/eligibility", response_model=EligibilityResponse)
async def check_eligibility_route(request: EligibilityRequest):
    """Check eligibility for a condition against a policy."""
    if not faiss_store.has_policy(request.policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")

    try:
        return await check_eligibility(request)
    except Exception as e:
        logger.error(f"Eligibility check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exclusions", response_model=ExclusionsResponse)
async def get_exclusions(policy_id: str):
    """Find all exclusions in a policy."""
    if not faiss_store.has_policy(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")

    try:
        return await find_exclusions(policy_id)
    except Exception as e:
        logger.error(f"Exclusions search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchResponse)
async def batch_query(request: BatchRequest):
    """Process multiple queries in batch (enterprise API)."""
    results = []
    failed = 0

    for item in request.queries:
        try:
            query_req = QueryRequest(
                question=item.question,
                policy_id=item.policy_id,
                reading_level=request.reading_level,
            )
            result = await process_query(query_req)
            results.append(result)
        except Exception as e:
            logger.error(f"Batch item failed: {e}")
            failed += 1

    return BatchResponse(
        results=results,
        total=len(request.queries),
        processed=len(results),
        failed=failed,
    )
