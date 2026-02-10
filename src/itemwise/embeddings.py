"""Embedding service for semantic search using Azure OpenAI."""

import logging
import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
EMBEDDING_DIMENSION = 1536

# Lazy-loaded client
_client: AzureOpenAI | None = None
_configured: bool | None = None


def _get_client() -> AzureOpenAI | None:
    """Get or create the Azure OpenAI client for embeddings."""
    global _client, _configured
    if _configured is not None:
        return _client

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        logger.warning(
            "AZURE_OPENAI_ENDPOINT not set — embeddings will return zero vectors"
        )
        _configured = False
        return None

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    _client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )
    _configured = True
    logger.info(f"Initialized Azure OpenAI embedding client for {endpoint}")
    return _client


def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for the given text.

    Args:
        text: Text to generate embedding for

    Returns:
        List of floats representing the embedding vector (1536 dimensions)
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text")

    client = _get_client()
    if client is None:
        return [0.0] * EMBEDDING_DIMENSION

    response = client.embeddings.create(input=text, model=MODEL_NAME)
    return response.data[0].embedding


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts (batch processing).

    Args:
        texts: List of texts to generate embeddings for

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    client = _get_client()
    if client is None:
        return [[0.0] * EMBEDDING_DIMENSION for _ in texts]

    response = client.embeddings.create(input=texts, model=MODEL_NAME)
    return [item.embedding for item in response.data]


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
