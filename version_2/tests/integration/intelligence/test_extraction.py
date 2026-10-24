"""Integration tests for structured intelligence extraction."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from app.api.v1.search import get_search_service
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.task import Task, TaskSource
from app.database.models.user import User
from app.intelligence.models import (
    IntelligenceSource,
    StructuredIntelligence,
    TaskCandidate,
)
from app.intelligence.persistence_service import (
    IntelligencePersistenceService,
)
from app.intelligence.service import (
    IntelligenceExtractionService,
)
from app.intelligence.workflow import IntelligenceWorkflowService
from app.llm.models import LLMResponse
from app.retrieval.service import SearchService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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


@pytest.mark.asyncio
async def test_workflow_persists_task_with_source_provenance(
    db_session: AsyncSession,
    extraction_user: User,
):
    """The workflow persists extracted tasks and their source chunks."""

    document = Document(
        user_id=extraction_user.id,
        title="Deployment Review",
        source_type="notes",
        mime_type="text/plain",
        file_name="deployment-review.txt",
        content_hash=f"workflow-{uuid4().hex}",
        raw_text="Review the API deployment plan before October 20.",
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Review the API deployment plan before October 20.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.flush()

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review the API deployment plan",
                priority="high",
                sources=[
                    IntelligenceSource(chunk_id=chunk.id),
                ],
            ),
        ],
    )

    # Mock only the extraction output. Persistence remains real.
    extraction_service = AsyncMock()
    extraction_service.extract.return_value = SimpleNamespace(
        intelligence=intelligence,
    )

    workflow = IntelligenceWorkflowService(
        extraction_service=extraction_service,
        persistence_service=IntelligencePersistenceService(),
    )

    result = await workflow.extract_and_persist(
        db_session,
        user_id=extraction_user.id,
        document_id=document.id,
    )

    assert result.tasks == 1

    await db_session.commit()

    persisted_task = await db_session.scalar(
        select(Task).where(
            Task.user_id == extraction_user.id,
            Task.description == "Review the API deployment plan",
        )
    )

    assert persisted_task is not None
    assert persisted_task.priority == "high"

    persisted_source = await db_session.scalar(
        select(TaskSource).where(
            TaskSource.task_id == persisted_task.id,
            TaskSource.chunk_id == chunk.id,
        )
    )

    assert persisted_source is not None


@pytest.mark.asyncio
async def test_workflow_does_not_extract_another_users_document(
    db_session: AsyncSession,
    extraction_user: User,
):
    """The workflow must not read chunks owned by another user."""

    other_user = User(
        email=f"other-user-{uuid4().hex}@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    await db_session.flush()

    document = Document(
        user_id=other_user.id,
        title="Another User's Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name=f"other-user-{uuid4().hex}.txt",
        content_hash=f"other-user-{uuid4().hex}",
        raw_text="Confidential project information.",
    )
    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Confidential project information.",
        embedding=[1.0] + [0.0] * 383,
    )
    db_session.add(chunk)
    await db_session.flush()

    extraction_service = AsyncMock()

    workflow = IntelligenceWorkflowService(
        extraction_service=extraction_service,
        persistence_service=IntelligencePersistenceService(),
    )

    result = await workflow.extract_and_persist(
        db_session,
        user_id=extraction_user.id,
        document_id=document.id,
    )

    assert result.tasks == 0
    extraction_service.extract.assert_not_awaited()

    await db_session.delete(other_user)
    await db_session.flush()


@pytest.mark.asyncio
async def test_workflow_returns_empty_result_when_document_has_no_chunks(
    db_session: AsyncSession,
    extraction_user: User,
):
    """A document without chunks should not trigger extraction."""

    document = Document(
        user_id=extraction_user.id,
        title="Empty Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name=f"empty-{uuid4().hex}.txt",
        content_hash=f"empty-{uuid4().hex}",
        raw_text="",
    )

    db_session.add(document)
    await db_session.flush()

    extraction_service = AsyncMock()
    persistence_service = AsyncMock()

    workflow = IntelligenceWorkflowService(
        extraction_service=extraction_service,
        persistence_service=persistence_service,
    )

    result = await workflow.extract_and_persist(
        db_session,
        user_id=extraction_user.id,
        document_id=document.id,
    )

    assert result.tasks == 0
    assert result.commitments == 0
    assert result.decisions == 0
    assert result.projects == 0
    assert result.people == 0
    assert result.risks == 0

    extraction_service.extract.assert_not_awaited()
    persistence_service.persist.assert_not_awaited()