"""Policy comparison engine — compares 2-4 policies side by side."""

from app.core.retriever import retriever, chunks_to_source_clauses
from app.llm.groq import generate_json
from app.llm.prompts import COMPARISON_PROMPT, MULTILINGUAL_WRAPPER
from app.models.schemas import (
    CompareRequest,
    CompareResponse,
    ComparisonAspect,
    ConfidenceScore,
    SourceClause,
)
from app.storage.faiss_store import faiss_store
import json
import logging

logger = logging.getLogger(__name__)


async def compare_policies(request: CompareRequest) -> CompareResponse:
    """Compare multiple policies across specified aspects.

    Retrieves relevant chunks from each policy for each aspect,
    then uses LLM to generate a structured comparison.
    """
    all_sources: dict[str, list[SourceClause]] = {}

    # Build policy data for the prompt
    policy_sections = []
    for pid in request.policy_ids:
        # Retrieve chunks relevant to the comparison aspects
        aspect_query = " ".join(request.aspects)
        results = retriever.retrieve(aspect_query, pid, top_k=7)

        if results:
            chunks_text = "\n".join(f"- {r['text'][:300]}" for r, _ in results)
            policy_sections.append(f"POLICY '{pid}':\n{chunks_text}")
            all_sources[pid] = chunks_to_source_clauses(results[:3])
        else:
            policy_sections.append(f"POLICY '{pid}':\n(No relevant clauses found)")
            all_sources[pid] = []

    policy_data = "\n\n---\n\n".join(policy_sections)

    prompt = COMPARISON_PROMPT.format(
        policy_data=policy_data,
        aspects=", ".join(request.aspects),
    )

    if request.language != "en":
        prompt = MULTILINGUAL_WRAPPER.format(language=request.language, inner_prompt=prompt)

    result = await generate_json(prompt, temperature=0.3, max_tokens=3000)

    # Parse comparisons
    comparisons = []
    for comp in result.get("comparisons", []):
        findings = comp.get("findings", {})
        # Map policy IDs from generic names
        mapped_findings = {}
        for i, pid in enumerate(request.policy_ids):
            key = f"policy_{i+1}"
            if key in findings:
                mapped_findings[pid] = findings[key]
            elif pid in findings:
                mapped_findings[pid] = findings[pid]

        comparisons.append(ComparisonAspect(
            aspect=comp.get("aspect", ""),
            policies=mapped_findings if mapped_findings else findings,
            recommendation=comp.get("recommendation", ""),
        ))

    return CompareResponse(
        comparisons=comparisons,
        overall_recommendation=result.get("overall_recommendation", ""),
        confidence=ConfidenceScore(
            retrieval_score=0.7,
            coverage_score=0.6,
            llm_confidence=0.7,
        ),
        sources=all_sources,
    )
