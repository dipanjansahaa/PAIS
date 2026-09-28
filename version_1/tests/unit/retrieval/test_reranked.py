from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.retrieval.models import RetrievalResult
from app.retrieval.reranked import RerankedRetriever


def build_result(content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        similarity=0.5,
        metadata=None,
    )


@pytest.fixture
def base_retriever():
    retriever = AsyncMock()

    retriever.search.return_value = [
        build_result("candidate 1"),
        build_result("candidate 2"),
        build_result("candidate 3"),
    ]

    return retriever


@pytest.fixture
def reranking_service():
    service = AsyncMock()

    service.rerank.return_value = [
        build_result("candidate 2"),
    ]

    return service


@pytest.fixture
def retriever(base_retriever, reranking_service):
    return RerankedRetriever(
        base_retriever=base_retriever,
        reranking_service=reranking_service,
        candidate_k=20,
    )


@pytest.mark.asyncio
async def test_uses_candidate_k_before_reranking(
    retriever,
    base_retriever,
    reranking_service,
):
    user_id = uuid4()

    results = await retriever.search(
        session="session",
        query="test query",
        top_k=5,
        user_id=user_id,
    )

    base_retriever.search.assert_awaited_once_with(
        session="session",
        query="test query",
        top_k=20,
        user_id=user_id,
        project_id=None,
        document_id=None,
        source_type=None,
    )

    reranking_service.rerank.assert_awaited_once()

    assert len(results) == 1


@pytest.mark.asyncio
async def test_passes_final_top_k_to_reranker(
    retriever,
    reranking_service,
):
    await retriever.search(
        session="session",
        query="test query",
        top_k=5,
        user_id=uuid4(),
    )

    reranking_service.rerank.assert_awaited_once()

    call_kwargs = reranking_service.rerank.await_args.kwargs

    assert call_kwargs["query"] == "test query"
    assert call_kwargs["top_k"] == 5


@pytest.mark.asyncio
async def test_empty_query_raises_value_error(retriever):
    with pytest.raises(
        ValueError,
        match="Query must not be empty.",
    ):
        await retriever.search(
            session="session",
            query="   ",
            top_k=5,
        )


@pytest.mark.asyncio
async def test_invalid_top_k_raises_value_error(retriever):
    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero.",
    ):
        await retriever.search(
            session="session",
            query="test query",
            top_k=0,
        )


def test_invalid_candidate_k_raises_value_error(
    base_retriever,
    reranking_service,
):
    with pytest.raises(
        ValueError,
        match="candidate_k must be greater than zero.",
    ):
        RerankedRetriever(
            base_retriever=base_retriever,
            reranking_service=reranking_service,
            candidate_k=0,
        )