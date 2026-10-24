"""Tests for personal-memory integration in QueryService."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.llm.models import LLMResponse
from app.query.context import ContextBuilder
from app.query.service import QueryService
from app.retrieval.models import RetrievalResult


class FakeSearchService:
    """Fake document search service."""

    def __init__(self, results=None):
        self.results = results or []

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
        return self.results


class FakeMemoryService:
    """Fake memory retrieval service."""

    def __init__(self, memories=None):
        self.memories = memories or []
        self.calls = []

    async def retrieve_memories(
        self,
        session,
        *,
        user_id,
        query=None,
        memory_types=None,
        limit=10,
        as_of=None,
    ):
        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "query": query,
                "limit": limit,
            }
        )
        return self.memories


class FakeLLMProvider:
    """Fake LLM provider that records the prompt."""

    def __init__(self):
        self.calls = []

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
            }
        )

        return LLMResponse(
            content="Your preferred language is Python. [M1]",
            model="test-model",
            usage=None,
            latency_ms=10.0,
            finish_reason="stop",
        )


def make_memory(
    *,
    content="I prefer Python for backend development.",
    memory_type="preference",
    sources=None,
):
    """Create a minimal memory-like object."""

    return SimpleNamespace(
        id=uuid4(),
        memory_type=memory_type,
        content=content,
        confidence=0.95,
        sources=sources or [],
    )


def make_document_result():
    """Create a document result with stable content."""

    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="The service uses PostgreSQL.",
        similarity=0.9,
        metadata={"source": "architecture.md"},
    )


@pytest.mark.asyncio
async def test_query_includes_relevant_memory_in_prompt():
    """Relevant personal memory should be supplied to the LLM."""

    user_id = uuid4()
    memory = make_memory()

    memory_service = FakeMemoryService([memory])
    llm_provider = FakeLLMProvider()

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
        memory_service=memory_service,
    )

    result = await service.query(
        object(),
        user_id=user_id,
        query="Which language do I prefer for backend development?",
    )

    assert len(memory_service.calls) == 1
    assert memory_service.calls[0]["user_id"] == user_id
    assert memory_service.calls[0]["query"] == "Which language do I prefer for backend development?"

    assert len(llm_provider.calls) == 1

    prompt = llm_provider.calls[0]["messages"][1].content

    assert "PERSONAL MEMORIES:" in prompt
    assert "I prefer Python for backend development." in prompt
    assert "[M1]" in prompt

    assert result.memories[0].citation_id == "M1"
    assert result.memories[0].memory_id == str(memory.id)


@pytest.mark.asyncio
async def test_query_preserves_document_citations_when_memory_exists():
    """Memory context must not change document citation identifiers."""

    document_result = make_document_result()
    memory = make_memory()

    llm_provider = FakeLLMProvider()

    service = QueryService(
        search_service=FakeSearchService([document_result]),
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
        memory_service=FakeMemoryService([memory]),
    )

    result = await service.query(
        object(),
        user_id=uuid4(),
        query="What does the system use, and what language do I prefer?",
    )

    assert len(result.sources) == 1
    assert result.sources[0].citation_id == "S1"
    assert result.sources[0].chunks[0].citation_id == "S1-C1"

    prompt = llm_provider.calls[0]["messages"][1].content

    assert "DOCUMENT SOURCES:" in prompt
    assert "[S1-C1]" in prompt
    assert "PERSONAL MEMORIES:" in prompt
    assert "[M1]" in prompt


@pytest.mark.asyncio
async def test_query_can_answer_from_memory_without_document_results():
    """Memory evidence should work when document retrieval is empty."""

    memory = make_memory()
    llm_provider = FakeLLMProvider()

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
        memory_service=FakeMemoryService([memory]),
    )

    result = await service.query(
        object(),
        user_id=uuid4(),
        query="Which language do I prefer?",
    )

    assert result.sources == ()
    assert len(result.memories) == 1
    assert result.answer == "Your preferred language is Python. [M1]"
    assert len(llm_provider.calls) == 1


@pytest.mark.asyncio
async def test_query_does_not_call_llm_without_document_or_memory_evidence():
    """No evidence should preserve the safe fallback behaviour."""

    llm_provider = FakeLLMProvider()

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
        memory_service=FakeMemoryService(),
    )

    result = await service.query(
        object(),
        user_id=uuid4(),
        query="What is my preferred language?",
    )

    assert result.sources == ()
    assert result.memories == ()
    assert result.model is None
    assert llm_provider.calls == []
    assert "don't have enough information" in result.answer


@pytest.mark.asyncio
async def test_query_without_memory_service_remains_compatible():
    """Existing callers without a memory service should still work."""

    document_result = make_document_result()
    llm_provider = FakeLLMProvider()

    service = QueryService(
        search_service=FakeSearchService([document_result]),
        context_builder=ContextBuilder(),
        llm_provider=llm_provider,
    )

    result = await service.query(
        object(),
        user_id=uuid4(),
        query="What database does the service use?",
    )

    assert len(result.sources) == 1
    assert result.memories == ()

    prompt = llm_provider.calls[0]["messages"][1].content

    assert "The service uses PostgreSQL." in prompt
    assert "(No relevant personal memories retrieved.)" in prompt


@pytest.mark.asyncio
async def test_query_preserves_memory_provenance():
    """Memory provenance should be available in the query result."""

    document_id = uuid4()
    chunk_id = uuid4()

    provenance = SimpleNamespace(
        source_kind="document",
        document_id=document_id,
        chunk_id=chunk_id,
        source_reference="architecture.md",
        evidence_text="The user prefers Python.",
    )

    memory = make_memory(sources=[provenance])

    service = QueryService(
        search_service=FakeSearchService(),
        context_builder=ContextBuilder(),
        llm_provider=FakeLLMProvider(),
        memory_service=FakeMemoryService([memory]),
    )

    result = await service.query(
        object(),
        user_id=uuid4(),
        query="Which language do I prefer?",
    )

    assert len(result.memories) == 1

    memory_result = result.memories[0]

    assert len(memory_result.sources) == 1

    source = memory_result.sources[0]

    assert source.source_kind == "document"
    assert source.document_id == str(document_id)
    assert source.chunk_id == str(chunk_id)
    assert source.source_reference == "architecture.md"
    assert source.evidence_text == "The user prefers Python."
