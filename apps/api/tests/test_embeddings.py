from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kara_api.config import Settings
from kara_api.knowledge.embeddings import (
    FakeEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


class TestFakeEmbeddingProvider:
    """Test suite for FakeEmbeddingProvider."""

    async def test_embed_returns_1536_dims(self):
        """Test that embeddings have correct dimensions."""
        provider = FakeEmbeddingProvider()
        texts = ["hello", "world"]
        embeddings = await provider.embed(texts)

        assert len(embeddings) == 2
        assert all(len(e) == 1536 for e in embeddings)

    async def test_embed_is_deterministic(self):
        """Test that same text produces same embedding."""
        provider = FakeEmbeddingProvider()
        text = "consistent output"

        emb1 = await provider.embed_single(text)
        emb2 = await provider.embed_single(text)

        assert emb1 == emb2

    async def test_embed_is_different_for_different_text(self):
        """Test that different texts produce different embeddings."""
        provider = FakeEmbeddingProvider()
        emb1 = await provider.embed_single("text a")
        emb2 = await provider.embed_single("text b")

        assert emb1 != emb2

    async def test_embed_batch_works(self):
        """Test batch embedding processing."""
        provider = FakeEmbeddingProvider()
        texts = ["text1", "text2", "text3", "text4", "text5"]
        embeddings = await provider.embed(texts)

        assert len(embeddings) == 5
        # All should be deterministic and different
        assert embeddings[0] == (await provider.embed_single("text1"))
        assert embeddings[1] == (await provider.embed_single("text2"))
        # All should be different
        assert embeddings[0] != embeddings[1]

    async def test_embed_single_matches_embed_first_element(self):
        """Test that embed_single returns same as first element of embed."""
        provider = FakeEmbeddingProvider()
        text = "test text"

        single = await provider.embed_single(text)
        batch = await provider.embed([text])

        assert single == batch[0]


class TestOpenAIEmbeddingProvider:
    """Test suite for OpenAIEmbeddingProvider."""

    async def test_send_correct_request_format(self):
        """Test that OpenAI provider sends correct request format."""
        provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

        # Mock httpx.AsyncClient
        # Real httpx Response.json() is synchronous — model that faithfully.
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"index": 0, "embedding": [0.1] * 1536},
                {"index": 1, "embedding": [0.2] * 1536},
            ]
        }
        mock_response.raise_for_status = lambda: None

        with patch("kara_api.knowledge.embeddings.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            mock_client_class.return_value = mock_client

            texts = ["hello", "world"]
            embeddings = await provider.embed(texts)

            # Verify the request was made with correct parameters
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            # Check URL
            assert call_args[0][0] == "https://api.openai.com/v1/embeddings"

            # Check JSON payload
            assert call_args[1]["json"]["model"] == "text-embedding-3-small"
            assert call_args[1]["json"]["input"] == texts

            # Check authorization header
            assert "Authorization" in call_args[1]["headers"]
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"

            # Check returned embeddings
            assert len(embeddings) == 2
            assert embeddings[0] == [0.1] * 1536
            assert embeddings[1] == [0.2] * 1536

    async def test_embed_single_returns_single_embedding(self):
        """Test that embed_single returns a single embedding."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"index": 0, "embedding": [0.5] * 1536}]}
        mock_response.raise_for_status = lambda: None

        with patch("kara_api.knowledge.embeddings.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            mock_client_class.return_value = mock_client

            embedding = await provider.embed_single("test")

            assert embedding == [0.5] * 1536


class TestOllamaEmbeddingProvider:
    """Test suite for OllamaEmbeddingProvider."""

    async def test_ollama_validate_1536_dims(self):
        """Test that Ollama provider validates 1536 dimensions."""
        provider = OllamaEmbeddingProvider()

        # Mock successful response with correct dimensions
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1] * 1536}
        mock_response.raise_for_status = lambda: None

        with patch("kara_api.knowledge.embeddings.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            mock_client_class.return_value = mock_client

            embeddings = await provider.embed(["test"])
            assert len(embeddings[0]) == 1536

    async def test_ollama_raises_on_wrong_dims(self):
        """Test that Ollama provider raises on wrong dimensions."""
        provider = OllamaEmbeddingProvider()

        # Mock response with wrong dimensions
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1] * 768}  # Wrong size
        mock_response.raise_for_status = lambda: None

        with patch("kara_api.knowledge.embeddings.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Expected 1536 dimensions"):
                await provider.embed(["test"])


class TestEmbeddingProviderFactory:
    """Test suite for get_embedding_provider factory function."""

    def test_factory_returns_openai_provider(self):
        """Test that factory returns OpenAI provider when configured."""
        settings = Settings(EMBEDDING_PROVIDER="openai", LLM_API_KEY="key")
        provider = get_embedding_provider(settings)
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_factory_returns_ollama_provider(self):
        """Test that factory returns Ollama provider when configured."""
        settings = Settings(EMBEDDING_PROVIDER="ollama")
        provider = get_embedding_provider(settings)
        assert isinstance(provider, OllamaEmbeddingProvider)

    def test_factory_returns_fake_provider(self):
        """Test that factory returns Fake provider when configured."""
        settings = Settings(EMBEDDING_PROVIDER="fake")
        provider = get_embedding_provider(settings)
        assert isinstance(provider, FakeEmbeddingProvider)

    def test_factory_raises_on_unknown_provider(self):
        """Test that factory raises on unknown provider."""
        settings = Settings(EMBEDDING_PROVIDER="unknown")
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider(settings)

    def test_factory_uses_settings_values(self):
        """Test that factory passes correct settings to providers."""
        settings = Settings(
            EMBEDDING_PROVIDER="openai",
            EMBEDDING_MODEL="text-embedding-3-large",
            LLM_API_KEY="custom-key",
        )
        provider = get_embedding_provider(settings)
        assert isinstance(provider, OpenAIEmbeddingProvider)
        assert provider.model == "text-embedding-3-large"
        assert provider.api_key == "custom-key"

    def test_factory_uses_ollama_base_url(self):
        """Test that factory passes correct Ollama base URL."""
        settings = Settings(
            EMBEDDING_PROVIDER="ollama",
            OLLAMA_BASE_URL="http://custom.local:11434",
        )
        provider = get_embedding_provider(settings)
        assert isinstance(provider, OllamaEmbeddingProvider)
        assert provider.base_url == "http://custom.local:11434"
