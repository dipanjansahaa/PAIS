import pytest

from app.embeddings.providers.local import LocalEmbeddingProvider


@pytest.fixture
def provider() -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider(
        model_name="BAAI/bge-small-en-v1.5",
        device="cpu",
        batch_size=2,
        normalize_embeddings=True,
    )


def test_local_embedding_provider_metadata(
    provider: LocalEmbeddingProvider,
) -> None:
    assert provider.model_name == "BAAI/bge-small-en-v1.5"
    assert provider.dimension == 384


@pytest.mark.asyncio
async def test_embed_documents(
    provider: LocalEmbeddingProvider,
) -> None:
    texts = [
        "PAIS is a personal intelligence system.",
        "Documents are stored in PostgreSQL.",
    ]

    embeddings = await provider.embed_documents(texts)

    assert len(embeddings) == 2
    assert all(len(embedding) == provider.dimension for embedding in embeddings)


@pytest.mark.asyncio
async def test_embed_query(
    provider: LocalEmbeddingProvider,
) -> None:
    embedding = await provider.embed_query(
        "Where are documents stored?"
    )

    assert len(embedding) == provider.dimension


@pytest.mark.asyncio
async def test_empty_documents(
    provider: LocalEmbeddingProvider,
) -> None:
    embeddings = await provider.embed_documents([])

    assert embeddings == []


@pytest.mark.asyncio
async def test_empty_query(
    provider: LocalEmbeddingProvider,
) -> None:
    with pytest.raises(ValueError, match="Query text must not be empty"):
        await provider.embed_query("   ")