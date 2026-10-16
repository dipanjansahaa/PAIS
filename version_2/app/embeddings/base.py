from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Application-level interface for embedding providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the embedding model identifier."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        raise NotImplementedError

    @abstractmethod
    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings for multiple documents."""
        raise NotImplementedError

    @abstractmethod
    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Generate an embedding for a single query."""
        raise NotImplementedError