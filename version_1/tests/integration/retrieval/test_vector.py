import pytest

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.base import EmbeddingProvider
from app.retrieval.vector import VectorRetriever


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for retrieval tests."""

    def __init__(self) -> None:
        self._dimension = 384

    @property
    def model_name(self) -> str:
        return "fake-retrieval-model"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [self._vector_for_text(text) for text in texts]

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self._vector_for_text(text)

    def _vector_for_text(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension

        if "database" in text.lower():
            vector[0] = 1.0
        else:
            vector[1] = 1.0

        return vector


@pytest.fixture
def retriever() -> VectorRetriever:
    return VectorRetriever(
        embedding_provider=FakeEmbeddingProvider(),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_rejects_empty_query(
    db_session,
    retriever,
):
    with pytest.raises(
        ValueError,
        match="Query must not be empty",
    ):
        await retriever.search(
            session=db_session,
            query="",
            top_k=5,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_rejects_whitespace_query(
    db_session,
    retriever,
):
    with pytest.raises(
        ValueError,
        match="Query must not be empty",
    ):
        await retriever.search(
            session=db_session,
            query="   ",
            top_k=5,
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("top_k", [0, -1, -5])
async def test_vector_retriever_rejects_invalid_top_k(
    db_session,
    retriever,
    top_k,
):
    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await retriever.search(
            session=db_session,
            query="database",
            top_k=top_k,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_returns_empty_list_when_no_embeddings_exist(
    db_session,
    retriever,
):
    results = await retriever.search(
        session=db_session,
        query="database",
        top_k=5,
    )

    assert results == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_respects_top_k_one(
    db_session,
    retriever,
):
    user = User(
        email="top-k-test@example.com",
        display_name="Top K Test User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Top K Test",
        source_type="text",
        content_hash="top-k-test-hash",
        raw_text=(
            "Database and deployment information."
        ),
    )

    db_session.add(document)
    await db_session.flush()

    relevant_chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="We decided to use PostgreSQL for the database.",
        token_count=9,
        chunk_metadata={"type": "decision"},
        embedding=[1.0] + [0.0] * 383,
    )

    less_relevant_chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=1,
        content="The application will be deployed using Docker.",
        token_count=8,
        chunk_metadata={"type": "deployment"},
        embedding=[0.0, 1.0] + [0.0] * 382,
    )

    db_session.add_all(
        [
            relevant_chunk,
            less_relevant_chunk,
        ]
    )

    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="What database did we decide to use?",
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].chunk_id == relevant_chunk.id
    assert results[0].similarity == pytest.approx(1.0)