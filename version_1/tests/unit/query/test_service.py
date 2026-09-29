"""Unit tests for QueryService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.llm.models import LLMResponse, TokenUsage
from app.query.context import ContextBuilder
from app.query.models import QueryResult
from app.query.service import QueryService
from app.retrieval.models import RetrievalResult


class FakeSearchService:
    """Fake search service for QueryService unit tests."""

    def __init__(
        self,
        results: list[RetrievalResult] | None = None,
    ) -> None:
        self.results = results or []
        self.calls: list[dict] = []

    async def search(
        self,
        session,
        *,
        user_id,
        query,
        top_k=5,
        project_id=None,
        document_id=None,
        source_type=None,
    ):
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "query": query,
                "top_k": top_k,
                "project_id": project_id,
                "document_id": document_id,
                "source_type": source_type,
            }
        )

        return self.results


class FakeLLMProvider:
    """Fake LLM provider for QueryService unit tests."""

    def __init__(
        self,
        response: LLMResponse,
    ) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def generate(
        self,
        messages,
        *,
        temperature=0.0,
        response_schema=None,
    ):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "response_schema": response_schema,
            }
        )

        return self.response


def make_result(
    *,
    content="PostgreSQL is the primary database.",
) -> RetrievalResult:
    """Create a retrieval result for service tests."""

    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        similarity=0.91,
        metadata={"source": "architecture.md"},
    )


def make_llm_response(
    *,
    content="PostgreSQL is used as the primary database. [S1-C1]",
) -> LLMResponse:
    """Create a normalized LLM response."""

    return LLMResponse(
        content=content,
        model="test-model",
        usage=TokenUsage(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
        ),
        latency_ms=125.0,
        finish_reason="stop",
    )


@pytest.mark.asyncio
async def test_query_returns_grounded_answer_and_sources():
    """QueryService should combine retrieval, context, and generation."""

    result = make_result()

    search_service = FakeSearchService(
        results=[result],
    )

    llm_provider = FakeLLMProvider(
        response=make_llm_response(),
    )

    service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
    )

    user_id = uuid4()
    session = object()

    response = await service.query(
        session,
        user_id=user_id,
        query="What database does the system use?",
    )

    assert isinstance(response, QueryResult)
    assert response.query == "What database does the system use?"
    assert response.answer == (
        "PostgreSQL is used as the primary database. [S1-C1]"
    )

    assert len(response.sources) == 1
    assert response.sources[0].document_id == str(result.document_id)

    assert response.model == "test-model"
    assert response.latency_ms == 125.0
    assert response.truncated is False


@pytest.mark.asyncio
async def test_query_passes_filters_to_search_service():
    """QueryService should preserve retrieval scope filters."""

    search_service = FakeSearchService(
        results=[make_result()],
    )

    llm_provider = FakeLLMProvider(
        response=make_llm_response(),
    )

    service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
    )

    user_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    session = object()

    await service.query(
        session,
        user_id=user_id,
        query="database architecture",
        top_k=10,
        project_id=project_id,
        document_id=document_id,
        source_type="markdown",
    )

    assert len(search_service.calls) == 1

    call = search_service.calls[0]

    assert call["session"] is session
    assert call["user_id"] == user_id
    assert call["query"] == "database architecture"
    assert call["top_k"] == 10
    assert call["project_id"] == project_id
    assert call["document_id"] == document_id
    assert call["source_type"] == "markdown"


@pytest.mark.asyncio
async def test_query_passes_grounded_context_to_llm():
    """LLM should receive the retrieved context and user question."""

    search_service = FakeSearchService(
        results=[
            make_result(
                content="PAIS uses PostgreSQL with pgvector.",
            )
        ],
    )

    llm_provider = FakeLLMProvider(
        response=make_llm_response(),
    )

    service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
    )

    await service.query(
        object(),
        user_id=uuid4(),
        query="What database does PAIS use?",
        temperature=0.2,
    )

    assert len(llm_provider.calls) == 1

    call = llm_provider.calls[0]

    assert call["temperature"] == 0.2

    messages = call["messages"]

    assert len(messages) == 2
    assert messages[0].role == "system"
    assert "only the supplied sources" in messages[0].content

    assert messages[1].role == "user"
    assert "PAIS uses PostgreSQL with pgvector." in messages[1].content
    assert "What database does PAIS use?" in messages[1].content


@pytest.mark.asyncio
async def test_query_does_not_call_llm_without_retrieved_sources():
    """QueryService should not generate from model knowledge alone."""

    search_service = FakeSearchService(
        results=[],
    )

    llm_provider = FakeLLMProvider(
        response=make_llm_response(),
    )

    service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
    )

    response = await service.query(
        object(),
        user_id=uuid4(),
        query="What is the secret project?",
    )

    assert response.answer == (
        "I don't have enough information in the available "
        "sources to answer this question."
    )

    assert response.sources == ()
    assert response.model is None
    assert response.latency_ms is None

    assert llm_provider.calls == []


@pytest.mark.asyncio
async def test_query_rejects_empty_query():
    """QueryService should reject whitespace-only queries."""

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=FakeLLMProvider(
            response=make_llm_response(),
        ),
    )

    with pytest.raises(
        ValueError,
        match="Query must not be empty",
    ):
        await service.query(
            object(),
            user_id=uuid4(),
            query="   ",
        )


@pytest.mark.asyncio
async def test_query_rejects_zero_top_k():
    """QueryService should reject zero top_k."""

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=FakeLLMProvider(
            response=make_llm_response(),
        ),
    )

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await service.query(
            object(),
            user_id=uuid4(),
            query="database",
            top_k=0,
        )


@pytest.mark.asyncio
async def test_query_rejects_negative_top_k():
    """QueryService should reject negative top_k."""

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=FakeLLMProvider(
            response=make_llm_response(),
        ),
    )

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await service.query(
            object(),
            user_id=uuid4(),
            query="database",
            top_k=-1,
        )


@pytest.mark.asyncio
async def test_query_propagates_llm_response_metadata():
    """QueryService should preserve normalized provider metadata."""

    search_service = FakeSearchService(
        results=[make_result()],
    )

    llm_response = make_llm_response()

    llm_provider = FakeLLMProvider(
        response=llm_response,
    )

    service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
    )

    response = await service.query(
        object(),
        user_id=uuid4(),
        query="What database is used?",
    )

    assert response.model == llm_response.model
    assert response.latency_ms == llm_response.latency_ms


@pytest.mark.asyncio
async def test_query_preserves_truncated_context_state():
    """QueryResult should expose context truncation state."""

    search_service = FakeSearchService(
        results=[
            make_result(content="a" * 20),
            make_result(content="b" * 20),
        ],
    )

    llm_provider = FakeLLMProvider(
        response=make_llm_response(),
    )

    service = QueryService(
        search_service=search_service,
        context_builder=ContextBuilder(
            max_context_tokens=5,
        ),
        llm_provider=llm_provider,
    )

    response = await service.query(
        object(),
        user_id=uuid4(),
        query="What does the system say?",
    )

    assert response.truncated is True