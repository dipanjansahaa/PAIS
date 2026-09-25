from app.embeddings.factory import get_embedding_provider
from app.embeddings.providers.local import LocalEmbeddingProvider


def test_get_embedding_provider() -> None:
    provider = get_embedding_provider()

    assert isinstance(provider, LocalEmbeddingProvider)
    assert provider.model_name == "BAAI/bge-small-en-v1.5"
    assert provider.dimension == 384