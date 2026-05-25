"""Embedding engine using Gemini Embedding API.

Replaces local sentence-transformers with the free Gemini text-embedding-004
model to eliminate torch/transformers dependencies (~3.5GB).
"""

from google import genai
from google.genai import types
import numpy as np
from app.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)

# Singleton client
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini client (singleton)."""
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set. Get a free key at aistudio.google.com")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def embed_texts(texts: list[str], batch_size: int = 100) -> np.ndarray:
    """Embed a list of texts into vectors using Gemini Embedding API.

    Args:
        texts: List of text strings to embed.
        batch_size: Batch size for API calls (max 100 per call).

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    if not texts:
        return np.array([], dtype=np.float32)

    client = _get_client()
    all_embeddings = []

    # Process in batches (Gemini supports up to 100 texts per request)
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        logger.info(f"Embedding batch {i // batch_size + 1} ({len(batch)} texts)...")

        contents = [
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in batch
        ]
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=contents,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=settings.embedding_dimension,
            ),
        )

        for embedding in result.embeddings:
            all_embeddings.append(embedding.values)

    embeddings = np.array(all_embeddings, dtype=np.float32)

    # Normalize for cosine similarity via dot product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid division by zero
    embeddings = embeddings / norms

    logger.info(f"Embedded {len(texts)} texts → shape {embeddings.shape}")
    return embeddings


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string using Gemini Embedding API.

    Args:
        query: The query text.

    Returns:
        numpy array of shape (embedding_dim,)
    """
    client = _get_client()

    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=[query],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.embedding_dimension,
        ),
    )

    embedding = np.array(result.embeddings[0].values, dtype=np.float32)

    # Normalize
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding


def get_embedding_dimension() -> int:
    """Get the dimension of the embedding vectors."""
    return settings.embedding_dimension


def get_model():
    """Compatibility shim — returns the client (no local model to load)."""
    return _get_client()
