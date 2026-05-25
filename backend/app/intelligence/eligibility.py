"""Eligibility checker — determines if a condition/situation is covered."""

from app.core.retriever import retriever, chunks_to_source_clauses
from app.llm.gemini import generate_json
from app.llm.prompts import ELIGIBILITY_PROMPT, MULTILINGUAL_WRAPPER
from app.models.schemas import (
    EligibilityRequest,
    EligibilityResponse,
    ConfidenceScore,
)
import logging

logger = logging.getLogger(__name__)


async def check_eligibility(request: EligibilityRequest) -> EligibilityResponse:
    """Check eligibility for a condition against a policy.

    Searches for relevant eligibility/exclusion/waiting period clauses,
    then uses LLM to assess eligibility with grounding.
    """
    # Targeted retrieval — search for eligibility-related chunks
    query = f"eligibility coverage {request.condition} {request.details} pre-existing waiting period exclusion"
    results = retriever.retrieve(query, request.policy_id, top_k=7)

    if not results:
        return EligibilityResponse(
            eligible=None,
            explanation="I couldn't find eligibility information in your policy for this condition. Please consult your insurance provider.",
            confidence=ConfidenceScore(retrieval_score=0.0, coverage_score=0.0, llm_confidence=0.1),
            sources=[],
        )

    # Format chunks
    chunks_text = "\n\n".join(
        f"[Section: {r.get('section_title', 'N/A')} | Page: {r.get('page_numbers', ['?'])[0]}]\n{r['text']}"
        for r, _ in results
    )
    sources = chunks_to_source_clauses(results)
    retrieval_score = results[0][1] if results else 0.0

    prompt = ELIGIBILITY_PROMPT.format(
        chunks=chunks_text,
        condition=request.condition,
        details=request.details or "Not specified",
    )

    if request.language != "en":
        prompt = MULTILINGUAL_WRAPPER.format(language=request.language, inner_prompt=prompt)

    result = await generate_json(prompt, temperature=0.2)

    eligible = result.get("eligible")
    if isinstance(eligible, str):
        eligible = eligible.lower() == "true" if eligible.lower() in ("true", "false") else None

    return EligibilityResponse(
        eligible=eligible,
        explanation=result.get("explanation", "Unable to determine eligibility."),
        conditions=result.get("conditions", []),
        waiting_period=result.get("waiting_period", ""),
        confidence=ConfidenceScore(
            retrieval_score=min(retrieval_score, 1.0),
            coverage_score=0.7,
            llm_confidence=float(result.get("confidence", 0.5)),
        ),
        sources=sources,
    )
