"""Embedding service for semantic search using sentence-transformers."""

import logging
import os

# IMPORTANT: Set offline mode BEFORE any huggingface imports
# This prevents slow network calls to check for model updates
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Model name - small, fast, and free
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Lazy-loaded model instance
_model: Optional["SentenceTransformer"] = None  # noqa: F821 - lazy import for startup performance


def _get_model() -> "SentenceTransformer":  # noqa: F821 - lazy import for startup performance
    """Get or initialize the sentence transformer model (lazy loading)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        from sentence_transformers import SentenceTransformer

        try:
            _model = SentenceTransformer(MODEL_NAME)
        except Exception as e:
            # If offline mode fails (model not cached), try online
            logger.warning(f"Offline load failed, trying online: {e}")
            os.environ["HF_HUB_OFFLINE"] = "0"
            os.environ["TRANSFORMERS_OFFLINE"] = "0"
            _model = SentenceTransformer(MODEL_NAME)
            # Restore offline mode for future loads
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        logger.info("Embedding model loaded successfully")
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for the given text.

    Args:
        text: Text to generate embedding for

    Returns:
        List of floats representing the embedding vector (384 dimensions)
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text")

    model = _get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts (batch processing).

    Args:
        texts: List of texts to generate embeddings for

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]


@lru_cache(maxsize=1000)
def generate_embedding_cached(text: str) -> tuple[float, ...]:
    """Generate embedding with caching (returns tuple for hashability).

    Useful for repeated searches with the same query.

    Args:
        text: Text to generate embedding for

    Returns:
        Tuple of floats (cached)
    """
    return tuple(generate_embedding(text))


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings produced by the model."""
    return EMBEDDING_DIMENSION
