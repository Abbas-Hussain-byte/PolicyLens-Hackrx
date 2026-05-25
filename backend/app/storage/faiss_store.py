"""Numpy-based vector store with persistence.

Replaces FAISS with pure numpy dot-product search.
For insurance policy scale (~100-1000 chunks per policy),
numpy is equally fast and eliminates C-extension compilation issues.
"""

import numpy as np
import json
from pathlib import Path
from app.core.chunker import Chunk
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class FAISSStore:
    """Vector store using numpy (API-compatible replacement for FAISS)."""

    def __init__(self, index_dir: str | None = None):
        self.index_dir = Path(index_dir or settings.index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        # In-memory cache: policy_id -> (embeddings_array, chunks)
        self._cache: dict[str, tuple[np.ndarray, list[dict]]] = {}

    def add_policy(self, policy_id: str, embeddings: np.ndarray, chunks: list[Chunk]) -> None:
        """Add a policy's embeddings and chunks to the store.

        Args:
            policy_id: Unique policy identifier.
            embeddings: numpy array of shape (n_chunks, embedding_dim).
            chunks: List of Chunk objects (metadata).
        """
        if embeddings.shape[0] == 0:
            logger.warning(f"No embeddings to add for policy {policy_id}")
            return

        embeddings = embeddings.astype(np.float32)

        # Serialize chunk metadata
        chunk_meta = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "page_numbers": c.page_numbers,
                "section_title": c.section_title,
                "chunk_type": c.chunk_type,
                "policy_id": c.policy_id,
            }
            for c in chunks
        ]

        # Save to disk
        policy_dir = self.index_dir / policy_id
        policy_dir.mkdir(parents=True, exist_ok=True)
        np.save(str(policy_dir / "embeddings.npy"), embeddings)
        with open(policy_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunk_meta, f, ensure_ascii=False, indent=2)

        # Cache in memory
        self._cache[policy_id] = (embeddings, chunk_meta)
        logger.info(f"Stored {len(chunks)} chunks for policy {policy_id}")

    def search(
        self, policy_id: str, query_embedding: np.ndarray, top_k: int = 10
    ) -> list[tuple[dict, float]]:
        """Search for similar chunks using numpy dot product.

        Args:
            policy_id: Policy to search.
            query_embedding: Query vector of shape (embedding_dim,).
            top_k: Number of results.

        Returns:
            List of (chunk_metadata, similarity_score) tuples.
        """
        embeddings, chunk_meta = self._load_policy(policy_id)

        if embeddings.shape[0] == 0:
            return []

        # Dot product (cosine similarity for normalized vectors)
        query = query_embedding.reshape(1, -1).astype(np.float32)
        similarities = np.dot(embeddings, query.T).flatten()

        # Get top-k indices
        actual_k = min(top_k, len(similarities))
        top_indices = np.argsort(similarities)[::-1][:actual_k]

        results = []
        for idx in top_indices:
            if idx < len(chunk_meta):
                results.append((chunk_meta[idx], float(similarities[idx])))

        return results

    def search_multiple_policies(
        self, policy_ids: list[str], query_embedding: np.ndarray, top_k: int = 10
    ) -> dict[str, list[tuple[dict, float]]]:
        """Search across multiple policies."""
        results = {}
        for pid in policy_ids:
            try:
                results[pid] = self.search(pid, query_embedding, top_k)
            except Exception as e:
                logger.error(f"Failed to search policy {pid}: {e}")
                results[pid] = []
        return results

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy's index from disk and cache."""
        import shutil

        policy_dir = self.index_dir / policy_id
        if policy_dir.exists():
            shutil.rmtree(policy_dir)

        self._cache.pop(policy_id, None)
        logger.info(f"Deleted index for policy {policy_id}")
        return True

    def has_policy(self, policy_id: str) -> bool:
        """Check if a policy index exists."""
        return policy_id in self._cache or (self.index_dir / policy_id / "embeddings.npy").exists()

    def get_chunk_count(self, policy_id: str) -> int:
        """Get number of chunks for a policy."""
        try:
            _, chunks = self._load_policy(policy_id)
            return len(chunks)
        except Exception:
            return 0

    def list_policies(self) -> list[str]:
        """List all policy IDs with stored indices."""
        policies = []
        for d in self.index_dir.iterdir():
            if d.is_dir() and (d / "embeddings.npy").exists():
                policies.append(d.name)
        return policies

    def _load_policy(self, policy_id: str) -> tuple[np.ndarray, list[dict]]:
        """Load a policy's embeddings and chunks (from cache or disk)."""
        if policy_id in self._cache:
            return self._cache[policy_id]

        policy_dir = self.index_dir / policy_id
        embeddings_path = policy_dir / "embeddings.npy"
        chunks_path = policy_dir / "chunks.json"

        if not embeddings_path.exists():
            raise FileNotFoundError(f"No index found for policy {policy_id}")

        embeddings = np.load(str(embeddings_path))
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunk_meta = json.load(f)

        self._cache[policy_id] = (embeddings, chunk_meta)
        return embeddings, chunk_meta


# Singleton instance
faiss_store = FAISSStore()
