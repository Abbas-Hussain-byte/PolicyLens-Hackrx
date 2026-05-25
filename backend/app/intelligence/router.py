"""Adaptive query router — classifies queries into Tier 1/2/3.

Uses fast keyword heuristics first, falls back to LLM classification
only when uncertain. This keeps simple queries fast.
"""

from app.models.schemas import QueryTier
from app.llm.gemini import classify
from app.llm.prompts import ROUTER_PROMPT
import re
import logging

logger = logging.getLogger(__name__)

# ─── Fast Heuristic Patterns ─────────────────────────────────────────

# Tier 1: General insurance knowledge (no policy needed)
TIER1_PATTERNS = [
    r'(?i)what\s+is\s+(a|an|the)?\s*(deductible|premium|copay|coinsurance|hmo|ppo|epo|term\s+life|whole\s+life|annuity)',
    r'(?i)how\s+does\s+.*(insurance|coverage|claim|deductible)\s+work',
    r'(?i)explain\s+.*(insurance|deductible|premium|coverage|copay|term)',
    r'(?i)difference\s+between\s+.*(insurance|policy|plan|hmo|ppo)',
    r'(?i)types?\s+of\s+.*(insurance|coverage|policy|plan)',
    r'(?i)^(define|meaning\s+of)\s+',
]

# Tier 3: High-risk queries (need verification)
TIER3_PATTERNS = [
    r'(?i)(am\s+i|is\s+\w+)\s+(eligible|covered|qualified)',
    r'(?i)(will|would|can|could)\s+.*(claim|surgery|treatment|procedure)\s+(be\s+)?(covered|approved|denied|rejected)',
    r'(?i)(should\s+i|which\s+(policy|plan|insurance)\s+.*(choose|pick|select|better|best))',
    r'(?i)(pre.?existing|diabetes|hypertension|heart|cancer|chronic)',
    r'(?i)(deny|denied|reject|rejected|dispute|appeal)',
    r'(?i)(compare|comparison|versus|vs\.?)\s+.*(policy|plan|coverage)',
    r'(?i)(legal|lawsuit|sue|court|arbitrat)',
    r'(?i)(cancel|terminat|lapse|surrender)',
]


async def route_query(question: str, has_policy: bool = True) -> QueryTier:
    """Determine the appropriate tier for a query.

    Uses fast heuristics first, LLM classification only when uncertain.

    Args:
        question: The user's question.
        has_policy: Whether a policy document is uploaded.

    Returns:
        QueryTier enum value.
    """
    question = question.strip()

    # If no policy uploaded, can only do Tier 1
    if not has_policy:
        return QueryTier.FAST_INFO

    # Try fast heuristic classification
    tier = _heuristic_classify(question)
    if tier is not None:
        logger.info(f"Heuristic routed to {tier.value}: {question[:50]}")
        return tier

    # Fallback: use LLM for ambiguous queries
    try:
        prompt = ROUTER_PROMPT.format(question=question)
        result = await classify(prompt)
        result = result.strip().upper().replace(" ", "_")

        if "TIER_1" in result or "FAST" in result:
            tier = QueryTier.FAST_INFO
        elif "TIER_3" in result or "VERIFIED" in result:
            tier = QueryTier.VERIFIED
        else:
            tier = QueryTier.GROUNDED_QA  # Default: grounded is safest

        logger.info(f"LLM routed to {tier.value}: {question[:50]}")
        return tier

    except Exception as e:
        logger.error(f"Router LLM error, defaulting to GROUNDED_QA: {e}")
        return QueryTier.GROUNDED_QA


def _heuristic_classify(question: str) -> QueryTier | None:
    """Fast pattern-based classification. Returns None if uncertain."""
    # Check Tier 3 first (high risk takes priority)
    for pattern in TIER3_PATTERNS:
        if re.search(pattern, question):
            return QueryTier.VERIFIED

    # Check Tier 1
    for pattern in TIER1_PATTERNS:
        if re.search(pattern, question):
            return QueryTier.FAST_INFO

    # Check if question is very short and general
    words = question.split()
    if len(words) <= 5 and not any(
        kw in question.lower() for kw in ["my", "i ", "me ", "our", "this policy"]
    ):
        return QueryTier.FAST_INFO

    # Uncertain — return None to trigger LLM classification
    return None
