"""Unit tests for the SearchService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.retrieval.models import RetrievalResult
from app.retrieval.service import SearchService


class FakeRetriever:
    """Fake retriever used to isolate SearchService tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def search(
        self,
        session,
        *,
        user_id,
        query: str,
        top_k: int = 5,
        project_id=None,
        document_id=None,
        source_type=None,
    ) -> list[RetrievalResult]:
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

        return [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="PostgreSQL is used as the primary database.",
                similarity=0.032,
                metadata={"source": "test"},
            )
        ]


@pytest.mark.asyncio
async def test_search_returns_retriever_results():
    """SearchService should return results from the configured retriever."""

    retriever = FakeRetriever()
    service = SearchService(retriever)

    user_id = uuid4()
    session = object()

    results = await service.search(
        session,
        user_id=user_id,
        query="What database does the system use?",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].content == (
        "PostgreSQL is used as the primary database."
    )
    assert results[0].similarity == 0.032


@pytest.mark.asyncio
async def test_search_passes_parameters_to_retriever():
    """SearchService should forward search parameters unchanged."""

    retriever = FakeRetriever()
    service = SearchService(retriever)

    user_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    session = object()

    await service.search(
        session,
        user_id=user_id,
        query="database architecture",
        top_k=10,
        project_id=project_id,
        document_id=document_id,
        source_type="markdown",
    )

    assert len(retriever.calls) == 1

    call = retriever.calls[0]

    assert call["session"] is session
    assert call["user_id"] == user_id
    assert call["query"] == "database architecture"
    assert call["top_k"] == 10
    assert call["project_id"] == project_id
    assert call["document_id"] == document_id
    assert call["source_type"] == "markdown"


@pytest.mark.asyncio
async def test_search_rejects_empty_query():
    """SearchService should reject whitespace-only queries."""

    retriever = FakeRetriever()
    service = SearchService(retriever)

    with pytest.raises(ValueError, match="Query must not be empty"):
        await service.search(
            object(),
            user_id=uuid4(),
            query="   ",
        )


@pytest.mark.asyncio
async def test_search_rejects_zero_top_k():
    """SearchService should reject non-positive top_k."""

    retriever = FakeRetriever()
    service = SearchService(retriever)

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await service.search(
            object(),
            user_id=uuid4(),
            query="database",
            top_k=0,
        )


@pytest.mark.asyncio
async def test_search_rejects_negative_top_k():
    """SearchService should reject negative top_k."""

    retriever = FakeRetriever()
    service = SearchService(retriever)

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        await service.search(
            object(),
            user_id=uuid4(),
            query="database",
            top_k=-1,
        )