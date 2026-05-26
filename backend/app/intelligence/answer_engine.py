"""Main answer engine — the heart of PolicyLens AI.

Orchestrates the full query pipeline:
1. Route the query (Tier 1/2/3)
2. Retrieve relevant chunks (Tier 2/3)
3. Generate grounded answer
4. Score confidence
5. Verify if needed (Tier 3)
6. Adapt reading level
7. Handle multilingual
"""

import time
import json
from app.intelligence.router import route_query
from app.core.retriever import retriever, chunks_to_source_clauses
from app.llm.groq import generate_json, generate
from app.llm.prompts import (
    ANSWER_ENGINE_PROMPT,
    FAST_INFO_PROMPT,
    VERIFIER_PROMPT,
    SIMPLIFIER_PROMPT,
    MULTILINGUAL_WRAPPER,
    AMBIGUITY_PROMPT,
    QUERY_REWRITER_PROMPT,
)
from app.models.schemas import (
    QueryRequest,
    QueryResponse,
    QueryTier,
    ConfidenceScore,
    SourceClause,
    AmbiguityInfo,
    ReadingLevel,
)
import logging

logger = logging.getLogger(__name__)


async def process_query(request: QueryRequest) -> QueryResponse:
    """Process a user query through the full intelligence pipeline.

    Args:
        request: QueryRequest with question, policy_id, reading_level, language.

    Returns:
        QueryResponse with grounded answer, confidence, sources, etc.
    """
    start_time = time.time()
    question = request.question.strip()

    # 1. Route the query
    tier = await route_query(question, has_policy=bool(request.policy_id))

    # 2. Process based on tier
    if tier == QueryTier.FAST_INFO:
        response = await _handle_fast_info(question, request)
    elif tier == QueryTier.VERIFIED:
        response = await _handle_verified(question, request)
    else:
        response = await _handle_grounded(question, request)

    # 3. Adapt reading level if not standard
    if request.reading_level != ReadingLevel.STANDARD and response.answer:
        response.answer = await _adapt_reading_level(response.answer, request.reading_level)

    # Set metadata
    response.tier = tier
    response.reading_level = request.reading_level
    response.language = request.language
    response.latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"Query processed: tier={tier.value}, confidence={response.confidence.overall:.2f}, "
        f"latency={response.latency_ms}ms"
    )

    return response


async def _rewrite_query(question: str) -> str:
    """Rewrite conversational user queries into retrieval-friendly search terms."""
    try:
        prompt = QUERY_REWRITER_PROMPT.format(question=question)
        rewritten = await generate(prompt, temperature=0.1, json_mode=False, max_tokens=100)
        rewritten = rewritten.strip()
        if rewritten:
            logger.info(f"Query rewritten: '{question}' -> '{rewritten}'")
            return rewritten
    except Exception as e:
        logger.warning(f"Failed to rewrite query: {e}")
    return question


async def _handle_fast_info(question: str, request: QueryRequest) -> QueryResponse:
    """Tier 1: Fast informational — no retrieval needed."""
    prompt = FAST_INFO_PROMPT.format(question=question)

    if request.language != "en":
        prompt = MULTILINGUAL_WRAPPER.format(
            language=request.language, inner_prompt=prompt
        )

    result = await generate_json(prompt, temperature=0.4)

    answer = result.get("answer", "")
    llm_conf = float(result.get("confidence", 0.7))

    # If the LLM says this requires a policy, upgrade to Tier 2
    if result.get("requires_policy", False) and request.policy_id:
        return await _handle_grounded(question, request)

    return QueryResponse(
        answer=answer,
        tier=QueryTier.FAST_INFO,
        confidence=ConfidenceScore(
            retrieval_score=1.0,  # No retrieval needed
            coverage_score=0.8,
            llm_confidence=llm_conf,
        ),
        sources=[],
    )


async def _handle_grounded(question: str, request: QueryRequest) -> QueryResponse:
    """Tier 2: Grounded Q&A — retrieval + single LLM pass."""
    # Rewrite user query into optimized search terms
    search_query = await _rewrite_query(question)
    
    # Retrieve relevant chunks using search terms
    results = retriever.retrieve(search_query, request.policy_id, top_k=5)

    if not results:
        return _no_evidence_response()

    # Build context from retrieved chunks
    chunks_text = _format_chunks(results)
    sources = chunks_to_source_clauses(results)

    # Get retrieval score (best chunk similarity)
    retrieval_score = results[0][1] if results else 0.0

    # Generate answer
    prompt = ANSWER_ENGINE_PROMPT.format(chunks=chunks_text, question=question)

    if request.language != "en":
        prompt = MULTILINGUAL_WRAPPER.format(
            language=request.language, inner_prompt=prompt
        )

    result = await generate_json(prompt, temperature=0.3)

    answer = result.get("answer", "")
    llm_conf = float(result.get("confidence", 0.5))
    ambiguity_notes = result.get("ambiguity_notes")

    # Compute coverage score
    coverage = _compute_coverage(question, chunks_text)

    # Build source references from LLM response
    llm_sources = result.get("source_references", [])
    if llm_sources:
        for src in llm_sources:
            page_val = src.get("page")
            page_num = 0
            if page_val is not None:
                try:
                    page_num = int(page_val)
                except (ValueError, TypeError):
                    page_num = 0
            sources.append(SourceClause(
                section_title=src.get("section", ""),
                page_number=page_num,
                text=src.get("quote", "")[:300],
                relevance_score=0.0,
            ))
        # Deduplicate by keeping unique section titles
        seen = set()
        unique_sources = []
        for s in sources:
            key = (s.section_title, s.page_number)
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)
            if len(unique_sources) >= 5:
                break
        sources = unique_sources

    ambiguity = None
    if ambiguity_notes and ambiguity_notes != "null" and ambiguity_notes != "None":
        ambiguity = AmbiguityInfo(
            found=True,
            details=[ambiguity_notes] if isinstance(ambiguity_notes, str) else ambiguity_notes,
            risk_level="medium",
        )

    return QueryResponse(
        answer=answer,
        tier=QueryTier.GROUNDED_QA,
        confidence=ConfidenceScore(
            retrieval_score=min(retrieval_score, 1.0),
            coverage_score=coverage,
            llm_confidence=llm_conf,
        ),
        sources=sources,
        ambiguity=ambiguity,
    )


async def _handle_verified(question: str, request: QueryRequest) -> QueryResponse:
    """Tier 3: Verified — retrieval + answer + verification pass."""
    # First, get a grounded answer
    grounded = await _handle_grounded(question, request)

    if not grounded.answer or grounded.confidence.overall < 0.2:
        return grounded  # Don't verify garbage

    # Run verification pass using search terms
    search_query = await _rewrite_query(question)
    results = retriever.retrieve(search_query, request.policy_id, top_k=7)
    chunks_text = _format_chunks(results)

    verify_prompt = VERIFIER_PROMPT.format(
        question=question,
        answer=grounded.answer,
        chunks=chunks_text,
    )

    try:
        verification = await generate_json(verify_prompt, temperature=0.2)

        verdict = verification.get("verdict", "UNVERIFIED")
        corrected = verification.get("corrected_answer")
        risk_warning = verification.get("risk_warning")

        # Use corrected answer if provided and answer was wrong
        if corrected and verdict == "UNVERIFIED":
            grounded.answer = corrected

        # Add verification metadata
        grounded.verification_status = verdict

        # Adjust confidence based on verification
        if verdict == "VERIFIED":
            grounded.confidence.llm_confidence = min(grounded.confidence.llm_confidence + 0.15, 1.0)
        elif verdict == "UNVERIFIED":
            grounded.confidence.llm_confidence = max(grounded.confidence.llm_confidence - 0.3, 0.1)

        # Add risk warning as ambiguity
        if risk_warning and risk_warning != "null":
            if grounded.ambiguity is None:
                grounded.ambiguity = AmbiguityInfo(found=True, details=[], risk_level="high")
            grounded.ambiguity.details.append(f"⚠️ {risk_warning}")
            grounded.ambiguity.risk_level = "high"

        # Run ambiguity detection for Tier 3
        try:
            ambiguity_prompt = AMBIGUITY_PROMPT.format(question=question, chunks=chunks_text)
            ambiguity_result = await generate_json(ambiguity_prompt, temperature=0.2)
            if ambiguity_result.get("ambiguities"):
                if grounded.ambiguity is None:
                    grounded.ambiguity = AmbiguityInfo(found=True, details=[], risk_level="low")
                for amb in ambiguity_result["ambiguities"]:
                    detail = f"'{amb.get('term', '')}': {amb.get('risk', '')}"
                    grounded.ambiguity.details.append(detail)
                grounded.ambiguity.risk_level = ambiguity_result.get("risk_level", "medium")
        except Exception as e:
            logger.warning(f"Ambiguity detection failed: {e}")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        grounded.verification_status = "VERIFICATION_FAILED"

    grounded.tier = QueryTier.VERIFIED
    return grounded


async def _adapt_reading_level(answer: str, level: ReadingLevel) -> str:
    """Adapt answer text to the requested reading level."""
    if level == ReadingLevel.STANDARD:
        return answer

    prompt = SIMPLIFIER_PROMPT.format(
        reading_level=level.value,
        text=answer,
    )

    try:
        result = await generate(prompt, temperature=0.4, json_mode=False, max_tokens=1024)
        return result if result else answer
    except Exception as e:
        logger.warning(f"Reading level adaptation failed: {e}")
        return answer


def _format_chunks(results: list[tuple[dict, float]]) -> str:
    """Format retrieved chunks for the prompt."""
    parts = []
    for i, (chunk, score) in enumerate(results, 1):
        section = chunk.get("section_title", "")
        pages = chunk.get("page_numbers", [])
        page_str = f"Page {pages[0]}" if pages else "Page unknown"
        header = f"[Clause {i}] {section} ({page_str})" if section else f"[Clause {i}] ({page_str})"
        parts.append(f"{header}\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


def _compute_coverage(question: str, chunks_text: str) -> float:
    """Compute how well the chunks cover the question's key terms."""
    # Extract meaningful words from question (skip stop words)
    stop_words = {"is", "are", "the", "a", "an", "in", "on", "of", "for", "to", "my", "i", "this", "what", "how", "does", "do", "can", "will", "would", "be", "and", "or", "it", "with"}
    question_words = [
        w.lower() for w in question.split()
        if w.lower() not in stop_words and len(w) > 2
    ]

    if not question_words:
        return 0.5

    chunks_lower = chunks_text.lower()
    found = sum(1 for w in question_words if w in chunks_lower)
    return min(found / len(question_words), 1.0)


def _no_evidence_response() -> QueryResponse:
    """Response when no evidence is found."""
    return QueryResponse(
        answer="I couldn't find relevant information in your uploaded policy to answer this question. "
               "The policy may not cover this topic, or the question may need to be rephrased. "
               "Please consult your insurance advisor for clarification.",
        tier=QueryTier.GROUNDED_QA,
        confidence=ConfidenceScore(
            retrieval_score=0.0,
            coverage_score=0.0,
            llm_confidence=0.1,
        ),
        sources=[],
    )
