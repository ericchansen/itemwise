"""Tests for the embeddings module (Azure OpenAI)."""

from unittest.mock import MagicMock, patch

import pytest

import itemwise.embeddings as emb_module
from itemwise.embeddings import (
    EMBEDDING_DIMENSION,
    generate_embedding,
    generate_embedding_cached,
    generate_embeddings,
    get_embedding_dimension,
)


def _make_embedding_response(embeddings: list[list[float]]):
    """Build a mock response matching the OpenAI SDK shape."""
    response = MagicMock()
    items = []
    for vec in embeddings:
        item = MagicMock()
        item.embedding = vec
        items.append(item)
    response.data = items
    return response


@pytest.fixture(autouse=True)
def mock_embeddings():
    """Override conftest mock_embeddings — we need real functions here."""
    yield


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset module-level client state and lru_cache between tests."""
    emb_module._client = None
    emb_module._configured = None
    generate_embedding_cached.cache_clear()
    yield
    emb_module._client = None
    emb_module._configured = None
    generate_embedding_cached.cache_clear()


# ── get_embedding_dimension ────────────────────────────────────────────


def test_get_embedding_dimension():
    assert get_embedding_dimension() == 1536


# ── generate_embedding ─────────────────────────────────────────────────


class TestGenerateEmbedding:
    def test_returns_list_of_floats_with_correct_dimension(self):
        fake_vec = [0.1] * EMBEDDING_DIMENSION
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _make_embedding_response(
            [fake_vec]
        )

        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"}):
            with patch(
                "itemwise.embeddings.DefaultAzureCredential"
            ), patch(
                "itemwise.embeddings.get_bearer_token_provider"
            ), patch(
                "itemwise.embeddings.AzureOpenAI", return_value=mock_client
            ):
                result = generate_embedding("hello world")

        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIMENSION
        assert all(isinstance(v, float) for v in result)

    def test_raises_value_error_for_empty_text(self):
        with pytest.raises(ValueError, match="empty text"):
            generate_embedding("")

    def test_raises_value_error_for_whitespace_only(self):
        with pytest.raises(ValueError, match="empty text"):
            generate_embedding("   ")

    def test_fallback_zero_vector_when_no_endpoint(self):
        with patch.dict("os.environ", {}, clear=False):
            # Ensure the var is absent
            with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": ""}, clear=False):
                # _configured is None so _get_client will re-evaluate
                result = generate_embedding("some text")

        assert result == [0.0] * EMBEDDING_DIMENSION


# ── generate_embeddings (batch) ────────────────────────────────────────


class TestGenerateEmbeddings:
    def test_returns_list_of_embedding_lists(self):
        vecs = [[0.1] * EMBEDDING_DIMENSION, [0.2] * EMBEDDING_DIMENSION]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _make_embedding_response(vecs)

        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"}):
            with patch(
                "itemwise.embeddings.DefaultAzureCredential"
            ), patch(
                "itemwise.embeddings.get_bearer_token_provider"
            ), patch(
                "itemwise.embeddings.AzureOpenAI", return_value=mock_client
            ):
                result = generate_embeddings(["hello", "world"])

        assert len(result) == 2
        assert all(len(v) == EMBEDDING_DIMENSION for v in result)

    def test_returns_empty_list_for_empty_input(self):
        assert generate_embeddings([]) == []

    def test_fallback_without_azure_endpoint(self):
        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": ""}, clear=False):
            result = generate_embeddings(["a", "b"])

        assert len(result) == 2
        assert all(v == [0.0] * EMBEDDING_DIMENSION for v in result)


# ── generate_embedding_cached ──────────────────────────────────────────


class TestGenerateEmbeddingCached:
    def test_returns_tuple(self):
        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": ""}, clear=False):
            result = generate_embedding_cached("test text")

        assert isinstance(result, tuple)
        assert len(result) == EMBEDDING_DIMENSION

    def test_caches_results(self):
        fake_vec = [0.5] * EMBEDDING_DIMENSION
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _make_embedding_response(
            [fake_vec]
        )

        # Inject mock client directly so _get_client() returns it
        emb_module._client = mock_client
        emb_module._configured = True

        first = generate_embedding_cached("cache me")
        second = generate_embedding_cached("cache me")

        assert first == second
        # Client was only called once thanks to caching
        mock_client.embeddings.create.assert_called_once()


# ── Client initialisation ─────────────────────────────────────────────


class TestClientInitialisation:
    def test_client_created_lazily_on_first_call(self):
        assert emb_module._client is None
        assert emb_module._configured is None

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _make_embedding_response(
            [[0.0] * EMBEDDING_DIMENSION]
        )

        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"}):
            with patch(
                "itemwise.embeddings.DefaultAzureCredential"
            ), patch(
                "itemwise.embeddings.get_bearer_token_provider"
            ), patch(
                "itemwise.embeddings.AzureOpenAI", return_value=mock_client
            ):
                generate_embedding("trigger init")

        assert emb_module._configured is True
        assert emb_module._client is mock_client

    def test_client_is_none_when_endpoint_not_set(self):
        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": ""}, clear=False):
            result = emb_module._get_client()

        assert result is None
        assert emb_module._configured is False
        assert emb_module._client is None
