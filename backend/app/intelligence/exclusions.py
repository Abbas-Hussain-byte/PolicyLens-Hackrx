"""Exclusions finder — extracts all exclusions, traps, and limitations."""

from app.core.retriever import retriever, chunks_to_source_clauses
from app.llm.groq import generate_json
from app.llm.prompts import EXCLUSIONS_PROMPT
from app.models.schemas import (
    ExclusionsResponse,
    ExclusionItem,
    ConfidenceScore,
)
import logging

logger = logging.getLogger(__name__)


async def find_exclusions(policy_id: str) -> ExclusionsResponse:
    """Find all exclusions in a policy.

    Uses targeted search for exclusion-related chunks, then LLM extraction.
    """
    # Search specifically for exclusion content
    exclusion_queries = [
        "exclusions not covered limitations restrictions",
        "excluded conditions exceptions not payable",
        "waiting period pre-existing condition limitation",
    ]

    all_results = []
    seen_chunks = set()
    for query in exclusion_queries:
        results = retriever.retrieve(query, policy_id, top_k=5)
        for chunk, score in results:
            cid = chunk.get("chunk_id", id(chunk))
            if cid not in seen_chunks:
                seen_chunks.add(cid)
                all_results.append((chunk, score))

    if not all_results:
        return ExclusionsResponse(
            exclusions=[],
            total=0,
            confidence=ConfidenceScore(retrieval_score=0.0, coverage_score=0.0, llm_confidence=0.1),
            sources=[],
        )

    # Format chunks
    chunks_text = "\n\n".join(
        f"[Section: {r.get('section_title', 'N/A')} | Page: {r.get('page_numbers', ['?'])[0]}]\n{r['text']}"
        for r, _ in all_results[:10]
    )
    sources = chunks_to_source_clauses(all_results[:10])

    prompt = EXCLUSIONS_PROMPT.format(chunks=chunks_text)
    result = await generate_json(prompt, temperature=0.2, max_tokens=3000)

    exclusions = []
    for exc in result.get("exclusions", []):
        page_val = exc.get("page")
        page_num = 0
        if page_val is not None:
            try:
                page_num = int(page_val)
            except (ValueError, TypeError):
                page_num = 0
        exclusions.append(ExclusionItem(
            title=exc.get("title", ""),
            description=exc.get("description", ""),
            section=exc.get("section", ""),
            page=page_num,
            risk_note=exc.get("risk_note", ""),
        ))

    return ExclusionsResponse(
        exclusions=exclusions,
        total=len(exclusions),
        confidence=ConfidenceScore(
            retrieval_score=min(all_results[0][1], 1.0) if all_results else 0.0,
            coverage_score=0.7,
            llm_confidence=0.75,
        ),
        sources=sources,
    )
