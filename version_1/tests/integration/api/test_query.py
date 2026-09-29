"""Integration tests for the query API."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.api.v1.query import get_query_service
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.project import Project
from app.database.models.user import User
from app.llm.models import LLMResponse
from app.main import app
from app.query.context import ContextBuilder
from app.query.service import QueryService
from app.api.v1.search import get_search_service


class FakeQueryLLM:
    """Deterministic LLM used to test grounded generation."""

    def __init__(self) -> None:
        self.messages = []

    async def generate(
        self,
        messages,
        *,
        temperature: float = 0.0,
        response_schema=None,
    ) -> LLMResponse:
        self.messages.append(messages)

        user_message = messages[-1]

        assert user_message.role == "user"
        assert "SOURCES:" in user_message.content
        assert "QUESTION:" in user_message.content

        return LLMResponse(
            content="PAIS uses PostgreSQL with pgvector. [S1-C1]",
            model="integration-test-model",
            usage=None,
            latency_ms=1.0,
            finish_reason="stop",
        )


@pytest_asyncio.fixture
async def query_api_client(
    db_session: AsyncSession,
):
    """Create an API client using the real query service and test DB."""

    test_user = User(
        email=f"query-test-{uuid4()}@example.com",
        display_name="Query Integration User",
    )

    db_session.add(test_user)
    await db_session.flush()

    fake_llm = FakeQueryLLM()

    query_service = QueryService(
        search_service=get_search_service(),
        context_builder=ContextBuilder(),
        llm_provider=fake_llm,
    )

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    def override_get_query_service():
        return query_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_query_service] = (
        override_get_query_service
    )

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, test_user, fake_llm

    app.dependency_overrides.clear()

    await db_session.delete(test_user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_query_endpoint_runs_real_retrieval_and_generation(
    query_api_client,
    db_session: AsyncSession,
):
    """Query should retrieve real DB context and generate from it."""

    client, test_user, fake_llm = query_api_client

    document = Document(
        user_id=test_user.id,
        title="PAIS Architecture",
        source_type="notes",
        mime_type="text/plain",
        file_name="pais-architecture.txt",
        content_hash=f"query-{uuid4()}",
        raw_text=(
            "PAIS uses PostgreSQL with pgvector for persistent "
            "storage and vector retrieval."
        ),
    )

    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content=(
            "PAIS uses PostgreSQL with pgvector for persistent "
            "storage and vector retrieval."
        ),
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add(chunk)
    await db_session.commit()

    response = await client.post(
        "/api/v1/query",
        json={
            "query": "What database does PAIS use?",
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == "What database does PAIS use?"
    assert data["answer"] == (
        "PAIS uses PostgreSQL with pgvector. [S1-C1]"
    )
    assert data["model"] == "integration-test-model"
    assert data["latency_ms"] == 1.0
    assert data["truncated"] is False

    assert len(data["sources"]) >= 1

    source = data["sources"][0]

    assert source["citation_id"] == "S1"
    assert source["document_id"] == str(document.id)

    assert len(source["chunks"]) >= 1

    result_chunk = source["chunks"][0]

    assert result_chunk["citation_id"] == "S1-C1"
    assert result_chunk["chunk_id"] == str(chunk.id)
    assert result_chunk["document_id"] == str(document.id)

    assert (
        "PostgreSQL with pgvector"
        in result_chunk["content"]
    )

    assert len(fake_llm.messages) == 1

    generation_prompt = fake_llm.messages[0][-1].content

    assert "PostgreSQL with pgvector" in generation_prompt
    assert "S1-C1" in generation_prompt
    assert "What database does PAIS use?" in generation_prompt


@pytest.mark.asyncio
async def test_query_endpoint_preserves_user_isolation(
    db_session: AsyncSession,
):
    """Query results should only contain the authenticated user's data."""

    user_a = User(
        email=f"query-user-a-{uuid4()}@example.com",
        display_name="Query User A",
    )

    user_b = User(
        email=f"query-user-b-{uuid4()}@example.com",
        display_name="Query User B",
    )

    db_session.add_all([user_a, user_b])
    await db_session.flush()

    document_a = Document(
        user_id=user_a.id,
        title="User A Database Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="user-a.txt",
        content_hash=f"user-a-{uuid4()}",
        raw_text="User A uses PostgreSQL for PAIS.",
    )

    document_b = Document(
        user_id=user_b.id,
        title="User B Database Notes",
        source_type="notes",
        mime_type="text/plain",
        file_name="user-b.txt",
        content_hash=f"user-b-{uuid4()}",
        raw_text="User B uses PostgreSQL for another system.",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="User A uses PostgreSQL for PAIS.",
        embedding=[1.0] + [0.0] * 383,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="User B uses PostgreSQL for another system.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.commit()

    fake_llm = FakeQueryLLM()

    query_service = QueryService(
        search_service=get_search_service(),
        context_builder=ContextBuilder(),
        llm_provider=fake_llm,
    )

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user_a

    def override_get_query_service():
        return query_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )
    app.dependency_overrides[get_query_service] = (
        override_get_query_service
    )

    try:
        transport = ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/query",
                json={
                    "query": "PostgreSQL PAIS",
                    "top_k": 10,
                },
            )

        assert response.status_code == 200

        data = response.json()

        result_document_ids = {
            chunk["document_id"]
            for source in data["sources"]
            for chunk in source["chunks"]
        }

        assert str(document_a.id) in result_document_ids
        assert str(document_b.id) not in result_document_ids

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_query_endpoint_respects_project_filter(
    db_session: AsyncSession,
):
    """Query should preserve the existing project retrieval filter."""

    user = User(
        email=f"query-project-{uuid4()}@example.com",
        display_name="Query Project User",
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
        title="Project A Database",
        source_type="notes",
        mime_type="text/plain",
        file_name="project-a.txt",
        content_hash=f"project-a-{uuid4()}",
        raw_text="Project A uses PostgreSQL.",
    )

    document_b = Document(
        user_id=user.id,
        project_id=project_b.id,
        title="Project B Database",
        source_type="notes",
        mime_type="text/plain",
        file_name="project-b.txt",
        content_hash=f"project-b-{uuid4()}",
        raw_text="Project B uses PostgreSQL.",
    )

    db_session.add_all([document_a, document_b])
    await db_session.flush()

    chunk_a = DocumentChunk(
        document_id=document_a.id,
        chunk_index=0,
        content="Project A uses PostgreSQL.",
        embedding=[1.0] + [0.0] * 383,
    )

    chunk_b = DocumentChunk(
        document_id=document_b.id,
        chunk_index=0,
        content="Project B uses PostgreSQL.",
        embedding=[1.0] + [0.0] * 383,
    )

    db_session.add_all([chunk_a, chunk_b])
    await db_session.commit()

    fake_llm = FakeQueryLLM()

    query_service = QueryService(
        search_service=get_search_service(),
        context_builder=ContextBuilder(),
        llm_provider=fake_llm,
    )

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user

    def override_get_query_service():
        return query_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )
    app.dependency_overrides[get_query_service] = (
        override_get_query_service
    )

    try:
        transport = ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/query",
                json={
                    "query": "PostgreSQL",
                    "top_k": 10,
                    "project_id": str(project_a.id),
                },
            )

        assert response.status_code == 200

        data = response.json()

        result_document_ids = {
            chunk["document_id"]
            for source in data["sources"]
            for chunk in source["chunks"]
        }

        assert str(document_a.id) in result_document_ids
        assert str(document_b.id) not in result_document_ids

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_query_endpoint_returns_insufficient_information_without_generation(
    query_api_client,
):
    """Query should not call the LLM when retrieval returns no sources."""

    client, _, fake_llm = query_api_client

    response = await client.post(
        "/api/v1/query",
        json={
            "query": "this-query-has-no-matching-pais-knowledge-9f81",
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sources"] == []
    assert data["model"] is None
    assert data["latency_ms"] is None
    assert data["truncated"] is False

    assert (
        data["answer"]
        == (
            "I don't have enough information in the available "
            "sources to answer this question."
        )
    )

    assert fake_llm.messages == []