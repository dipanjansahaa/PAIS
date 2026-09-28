import pytest

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.base import EmbeddingProvider
from app.retrieval.vector import VectorRetriever
from app.database.models.project import Project


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
    user = User(
        email=None,
        display_name="Vector Empty Result User",
    )

    db_session.add(user)
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="database",
        top_k=5,
        user_id=user.id,
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
        user_id=user.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == relevant_chunk.id
    assert results[0].similarity == pytest.approx(1.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_filters_by_project_id(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Vector Project Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    project_a = Project(
        user_id=user.id,
        name="Project A",
    )

    project_b = Project(
        user_id=user.id,
        name="Project B",
    )

    db_session.add_all([project_a, project_b])
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        project_id=project_a.id,
        title="Project A Document",
        source_type="text",
        content_hash="vector-project-a",
        raw_text="PostgreSQL Project A",
    )

    document_b = Document(
        user_id=user.id,
        project_id=project_b.id,
        title="Project B Document",
        source_type="text",
        content_hash="vector-project-b",
        raw_text="PostgreSQL Project B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL is used by Project A.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL is used by Project B.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user.id,
        project_id=project_a.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_filters_by_document_id(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Vector Document Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        title="Document A",
        source_type="text",
        content_hash="vector-document-a",
        raw_text="PostgreSQL Document A",
    )

    document_b = Document(
        user_id=user.id,
        title="Document B",
        source_type="text",
        content_hash="vector-document-b",
        raw_text="PostgreSQL Document B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL is used in Document A.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL is used in Document B.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user.id,
        document_id=document_a.id,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_filters_by_source_type(
    db_session,
    retriever,
):
    user = User(
        email=None,
        display_name="Vector Source Type Filter User",
    )

    db_session.add(user)
    await db_session.flush()

    document_a = Document(
        user_id=user.id,
        title="Meeting Transcript",
        source_type="meeting_transcript",
        content_hash="vector-source-type-a",
        raw_text="PostgreSQL meeting transcript",
    )

    document_b = Document(
        user_id=user.id,
        title="Personal Note",
        source_type="note",
        content_hash="vector-source-type-b",
        raw_text="PostgreSQL personal note",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL was discussed in the meeting.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL was mentioned in my note.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user.id,
        source_type="meeting_transcript",
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a.id
    assert results[0].document_id == document_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_retriever_isolates_users(
    db_session,
    retriever,
):
    user_a = User(
        email=None,
        display_name="Vector User A",
    )

    user_b = User(
        email=None,
        display_name="Vector User B",
    )

    db_session.add_all([user_a, user_b])
    await db_session.flush()

    document_a = Document(
        user_id=user_a.id,
        title="User A Document",
        source_type="text",
        content_hash="vector-user-a",
        raw_text="PostgreSQL User A",
    )

    document_b = Document(
        user_id=user_b.id,
        title="User B Document",
        source_type="text",
        content_hash="vector-user-b",
        raw_text="PostgreSQL User B",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="PostgreSQL information belonging to User A.",
        embedding=[0.1] * 384,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="PostgreSQL information belonging to User B.",
        embedding=[0.1] * 384,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.flush()

    results = await retriever.search(
        session=db_session,
        query="PostgreSQL",
        top_k=5,
        user_id=user_a.id,
    )

    returned_ids = {
        result.chunk_id
        for result in results
    }

    assert chunk_a.id in returned_ids
    assert chunk_b.id not in returned_ids