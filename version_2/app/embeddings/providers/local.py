from __future__ import annotations

import asyncio

from sentence_transformers import SentenceTransformer

from app.embeddings.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by a local SentenceTransformer model."""

    QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    # def __init__(
    #     self,
    #     model_name: str = "BAAI/bge-base-en-v1.5",
    #     device: str = "cpu",
    #     batch_size: int = 32,
    #     normalize_embeddings: bool = True,
    # ) -> None:
    def __init__(
        self,
        model_name: str,
        device: str,
        batch_size: int,
        normalize_embeddings: bool,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._normalize_embeddings = normalize_embeddings

        self._model = SentenceTransformer(
            model_name,
            device=device,
        )

        # dimension = self._model.get_sentence_embedding_dimension()
        dimension = self._model.get_embedding_dimension()

        if dimension is None:
            raise RuntimeError(
                f"Unable to determine embedding dimension for model: {model_name}"
            )

        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate normalized embeddings for document chunks."""

        if not texts:
            return []

        embeddings = await asyncio.to_thread(
            self._encode,
            texts,
        )

        return embeddings

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Generate a normalized embedding for a search query."""

        if not text.strip():
            raise ValueError("Query text must not be empty.")

        query = f"{self.QUERY_INSTRUCTION}{text}"

        embeddings = await asyncio.to_thread(
            self._encode,
            [query],
        )

        return embeddings[0]

    def _encode(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Run synchronous model inference."""

        embeddings = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()