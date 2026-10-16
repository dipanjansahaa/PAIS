from app.core.config import settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.providers.local import LocalEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    """Create the configured embedding provider."""

    return LocalEmbeddingProvider(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        normalize_embeddings=settings.embedding_normalize,
    )