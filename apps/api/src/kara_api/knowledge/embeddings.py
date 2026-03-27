import hashlib
from abc import ABC, abstractmethod
from typing import Protocol

import httpx

from kara_api.config import Settings


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider using the Embeddings API."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts with retry logic."""
        async with httpx.AsyncClient() as client:
            for attempt in range(3):
                try:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        json={"model": self.model, "input": texts},
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = await response.json()
                    # Sort by index to ensure correct order
                    embeddings_data = sorted(data["data"], key=lambda x: x["index"])
                    return [item["embedding"] for item in embeddings_data]
                except httpx.HTTPError as e:
                    if attempt == 2:
                        raise
                    # Exponential backoff: 1s, 2s, 4s
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0]


class OllamaEmbeddingProvider:
    """Ollama embedding provider for local embeddings."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.base_url = base_url
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts sequentially."""
        embeddings = []
        async with httpx.AsyncClient() as client:
            for text in texts:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = await response.json()
                embedding = data["embedding"]
                # Validate dimension
                if len(embedding) != 1536:
                    raise ValueError(
                        f"Expected 1536 dimensions, got {len(embedding)} from Ollama"
                    )
                embeddings.append(embedding)
        return embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0]


class FakeEmbeddingProvider:
    """Deterministic fake embedding provider for testing."""

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic fake embeddings."""
        return [self._hash_to_embedding(text) for text in texts]

    async def embed_single(self, text: str) -> list[float]:
        """Generate a deterministic fake embedding."""
        return self._hash_to_embedding(text)

    def _hash_to_embedding(self, text: str) -> list[float]:
        """Convert text to deterministic 1536-dim vector using hash."""
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Use hash bytes to seed deterministic float generation
        values = []
        for i in range(self.dimensions):
            # Create deterministic float in [-1, 1] from hash bytes
            byte_idx = (i * 2) % len(hash_bytes)
            byte_val = hash_bytes[byte_idx]
            # Normalize to [-1, 1]
            normalized = (byte_val / 128.0) - 1.0
            values.append(normalized)
        return values


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Factory function to get the configured embedding provider."""
    provider_name = settings.EMBEDDING_PROVIDER.lower()

    if provider_name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.LLM_API_KEY, model=settings.EMBEDDING_MODEL
        )
    elif provider_name == "ollama":
        return OllamaEmbeddingProvider(base_url=settings.OLLAMA_BASE_URL)
    elif provider_name == "fake":
        return FakeEmbeddingProvider()
    else:
        raise ValueError(f"Unknown embedding provider: {provider_name}")
