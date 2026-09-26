import pytest
from sqlalchemy import select

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.embeddings.factory import get_embedding_provider
from app.ingestion.service import IngestionService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chunk_embedding_is_persisted(db_session):
    user = User(
        email="embedding-test@example.com",
        display_name="Embedding Test User",
    )

    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Embedding Test",
        source_type="text",
        content_hash="embedding-test-hash",
        raw_text="This is an embedding persistence test.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="This is a test chunk.",
        token_count=5,
        chunk_metadata={},
    )

    provider = get_embedding_provider()

    service = IngestionService(
        embedding_provider=provider,
    )

    await service.ingest_chunks(
        session=db_session,
        chunks=[chunk],
    )

    await db_session.flush()

    result = await db_session.execute(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk.id
        )
    )

    persisted_chunk = result.scalar_one()

    assert persisted_chunk.embedding is not None
    assert len(persisted_chunk.embedding) == 384