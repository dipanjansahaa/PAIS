"""Integration tests for structured intelligence extraction."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.user import User
from app.intelligence.models import (
    IntelligenceSource,
    StructuredIntelligence,
    TaskCandidate,
)
from app.intelligence.service import (
    IntelligenceExtractionService,
)
from app.llm.models import LLMResponse
from app.retrieval.service import SearchService
from app.api.v1.search import get_search_service


class FakeStructuredLLM:
    """Deterministic structured LLM for integration tests."""

    def __init__(
        self,
        intelligence: StructuredIntelligence,
    ) -> None:
        self.intelligence = intelligence
        self.messages = []
        self.schema = None
        self.temperature = None

    async def generate(
        self,
        messages,
        *,
        schema,
        temperature=0.0,
    ):
        self.messages.append(messages)
        self.schema = schema
        self.temperature = temperature

        return (
            self.intelligence,
            LLMResponse(
                content="{}",
                model="integration-test-model",
                usage=None,
                latency_ms=2.0,
                finish_reason="stop",
            ),
        )


@pytest_asyncio.fixture
async def extraction_user(
    db_session: AsyncSession,
):
    """Create a user for extraction integration tests."""

    user = User(
        email=f"intelligence-{uuid4()}@example.com",
        display_name="Intelligence Integration User",
    )

    db_session.add(user)
    await db_session.flush()

    yield user

    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_retrieval_results_flow_into_structured_extraction(
    db_session: AsyncSession,
    extraction_user: User,
):
    """Real retrieval results should become grounded intelligence."""

    document = Document(
        user_id=extraction_user.id,
        title="Project Meeting Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="meeting-notes.txt",
        content_hash=f"intelligence-{uuid4()}",
        raw_text=(
            "The API review must be completed before Friday. "
            "The team will review the deployment plan afterward."
        ),
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content=(
            "The API review must be completed before Friday. "
            "The team will review the deployment plan afterward."
        ),
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.commit()

    search_service: SearchService = get_search_service()

    retrieval_results = await search_service.search(
        db_session,
        user_id=extraction_user.id,
        query="API review before Friday",
        top_k=5,
    )

    assert len(retrieval_results) >= 1

    retrieved_chunk_ids = {
        result.chunk_id
        for result in retrieval_results
    }

    assert chunk.id in retrieved_chunk_ids

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Complete the API review before Friday",
                sources=[
                    IntelligenceSource(
                        chunk_id=chunk.id,
                    ),
                ],
            ),
        ],
    )

    fake_llm = FakeStructuredLLM(
        intelligence,
    )

    extraction_service = IntelligenceExtractionService(
        structured_llm=fake_llm,
    )

    result = await extraction_service.extract(
        retrieval_results,
    )

    assert len(result.intelligence.tasks) == 1

    task = result.intelligence.tasks[0]

    assert (
        task.description
        == "Complete the API review before Friday"
    )

    assert task.sources[0].chunk_id == chunk.id

    assert result.model == "integration-test-model"
    assert result.latency_ms == 2.0

    assert fake_llm.schema is StructuredIntelligence

    assert len(fake_llm.messages) == 1

    generation_prompt = fake_llm.messages[0][-1].content

    assert str(chunk.id) in generation_prompt
    assert "API review must be completed before Friday" in (
        generation_prompt
    )


@pytest.mark.asyncio
async def test_extraction_only_accepts_sources_from_retrieval(
    db_session: AsyncSession,
    extraction_user: User,
):
    """Extraction provenance must originate from retrieved chunks."""

    document = Document(
        user_id=extraction_user.id,
        title="Architecture Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="architecture.txt",
        content_hash=f"architecture-{uuid4()}",
        raw_text="PAIS uses PostgreSQL with pgvector.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="PAIS uses PostgreSQL with pgvector.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.commit()

    search_service: SearchService = get_search_service()

    retrieval_results = await search_service.search(
        db_session,
        user_id=extraction_user.id,
        query="PostgreSQL pgvector",
        top_k=5,
    )

    assert any(
        result.chunk_id == chunk.id
        for result in retrieval_results
    )

    unknown_chunk_id = uuid4()

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Use PostgreSQL",
                sources=[
                    IntelligenceSource(
                        chunk_id=unknown_chunk_id,
                    ),
                ],
            ),
        ],
    )

    fake_llm = FakeStructuredLLM(
        intelligence,
    )

    extraction_service = IntelligenceExtractionService(
        structured_llm=fake_llm,
    )

    with pytest.raises(
        ValueError,
        match="unknown source chunk ID",
    ):
        await extraction_service.extract(
            retrieval_results,
        )