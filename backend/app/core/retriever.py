"""Hybrid retriever combining FAISS semantic search with BM25 keyword search.

Uses Reciprocal Rank Fusion (RRF) to merge results from both retrieval methods.
"""

import numpy as np
from rank_bm25 import BM25Okapi
from app.core.embedder import embed_query
from app.storage.faiss_store import faiss_store
from app.models.schemas import SourceClause
from app.config import settings
import logging
import re

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Combines FAISS vector search with BM25 keyword search."""

    def __init__(self, rrf_k: int = 60):
        """
        Args:
            rrf_k: RRF constant (higher = less impact of rank differences).
        """
        self.rrf_k = rrf_k
        # BM25 index cache: policy_id -> BM25Okapi
        self._bm25_cache: dict[str, tuple[BM25Okapi, list[dict]]] = {}

    def retrieve(
        self,
        query: str,
        policy_id: str,
        top_k: int = None,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ) -> list[tuple[dict, float]]:
        """Hybrid retrieve: semantic + keyword search with RRF fusion.

        Args:
            query: User's question.
            policy_id: Policy to search.
            top_k: Number of final results.
            semantic_weight: Weight for semantic search in RRF.
            keyword_weight: Weight for keyword search in RRF.

        Returns:
            List of (chunk_metadata, relevance_score) tuples, sorted by relevance.
        """
        k = top_k if top_k is not None else settings.top_k_retrieval
        # Fetch more candidates than needed, then fuse
        fetch_k = min(k * 3, 20)

        # 1. Semantic search via FAISS
        query_vec = embed_query(query)
        semantic_results = faiss_store.search(policy_id, query_vec, top_k=fetch_k)

        # 2. Keyword search via BM25
        bm25_results = self._bm25_search(query, policy_id, top_k=fetch_k)

        # 3. Fuse with RRF
        fused = self._rrf_fuse(
            semantic_results, bm25_results,
            semantic_weight, keyword_weight,
        )

        # Return top_k
        return fused[:k]

    def retrieve_for_comparison(
        self,
        query: str,
        policy_ids: list[str],
        top_k_per_policy: int = 5,
    ) -> dict[str, list[tuple[dict, float]]]:
        """Retrieve from multiple policies for comparison."""
        results = {}
        for pid in policy_ids:
            results[pid] = self.retrieve(query, pid, top_k=top_k_per_policy)
        return results

    def _bm25_search(
        self, query: str, policy_id: str, top_k: int = 10
    ) -> list[tuple[dict, float]]:
        """BM25 keyword search."""
        bm25, chunks = self._get_bm25_index(policy_id)
        if bm25 is None or not chunks:
            return []

        tokenized_query = _tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        # Get top indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((chunks[idx], float(scores[idx])))

        return results

    def _get_bm25_index(self, policy_id: str) -> tuple[BM25Okapi | None, list[dict]]:
        """Get or build BM25 index for a policy."""
        if policy_id in self._bm25_cache:
            return self._bm25_cache[policy_id]

        # Load chunks from FAISS store
        try:
            _, chunk_meta = faiss_store._load_policy(policy_id)
        except FileNotFoundError:
            return None, []

        if not chunk_meta:
            return None, []

        # Build BM25 index
        tokenized_docs = [_tokenize(c["text"]) for c in chunk_meta]
        bm25 = BM25Okapi(tokenized_docs)

        self._bm25_cache[policy_id] = (bm25, chunk_meta)
        return bm25, chunk_meta

    def _rrf_fuse(
        self,
        semantic_results: list[tuple[dict, float]],
        bm25_results: list[tuple[dict, float]],
        semantic_weight: float,
        keyword_weight: float,
    ) -> list[tuple[dict, float]]:
        """Reciprocal Rank Fusion to combine two result lists."""
        scores: dict[int, float] = {}
        chunk_map: dict[int, dict] = {}

        # Score semantic results
        for rank, (chunk, _score) in enumerate(semantic_results):
            cid = chunk.get("chunk_id", rank)
            scores[cid] = scores.get(cid, 0) + semantic_weight / (self.rrf_k + rank + 1)
            chunk_map[cid] = chunk

        # Score BM25 results
        for rank, (chunk, _score) in enumerate(bm25_results):
            cid = chunk.get("chunk_id", rank + 1000)  # offset to avoid ID collision
            # Check if same chunk by text overlap
            existing_id = self._find_matching_chunk(chunk, chunk_map)
            if existing_id is not None:
                cid = existing_id
            scores[cid] = scores.get(cid, 0) + keyword_weight / (self.rrf_k + rank + 1)
            chunk_map[cid] = chunk

        # Sort by fused score
        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        return [(chunk_map[cid], scores[cid]) for cid in sorted_ids if cid in chunk_map]

    def _find_matching_chunk(self, chunk: dict, chunk_map: dict[int, dict]) -> int | None:
        """Find if a chunk already exists in the map (by chunk_id)."""
        cid = chunk.get("chunk_id")
        if cid in chunk_map:
            return cid
        return None

    def invalidate_cache(self, policy_id: str) -> None:
        """Clear BM25 cache for a policy."""
        self._bm25_cache.pop(policy_id, None)


def _tokenize(text: str) -> list[str]:
    """Simple tokenization for BM25."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    # Remove very short tokens
    return [t for t in tokens if len(t) > 1]


def chunks_to_source_clauses(results: list[tuple[dict, float]]) -> list[SourceClause]:
    """Convert retrieval results to SourceClause objects for the API response."""
    sources = []
    for chunk_meta, score in results:
        sources.append(SourceClause(
            section_title=chunk_meta.get("section_title", ""),
            page_number=chunk_meta.get("page_numbers", [0])[0] if chunk_meta.get("page_numbers") else 0,
            text=chunk_meta.get("text", "")[:500],  # Truncate for response
            relevance_score=round(score, 3),
        ))
    return sources


# Singleton
retriever = HybridRetriever()
