from uuid import uuid4

import pytest

from app.reranking.providers.fake import FakeReranker
from app.reranking.service import RerankingService
from app.retrieval.models import RetrievalResult


def build_candidate(
    content: str,
    *,
    similarity: float = 0.5,
    metadata: dict | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        similarity=similarity,
        metadata=metadata,
    )


@pytest.fixture
def service() -> RerankingService:
    return RerankingService(
        reranker=FakeReranker(),
    )


@pytest.mark.asyncio
async def test_empty_query_raises_value_error(service):
    candidates = [
        build_candidate("Some document"),
    ]

    with pytest.raises(
        ValueError,
        match="Query must not be empty.",
    ):
        await service.rerank(
            query="   ",
            candidates=candidates,
            top_k=5,
        )


@pytest.mark.asyncio
async def test_invalid_top_k_raises_value_error(service):
    candidates = [
        build_candidate("Some document"),
    ]

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero.",
    ):
        await service.rerank(
            query="test query",
            candidates=candidates,
            top_k=0,
        )


@pytest.mark.asyncio
async def test_negative_top_k_raises_value_error(service):
    candidates = [
        build_candidate("Some document"),
    ]

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero.",
    ):
        await service.rerank(
            query="test query",
            candidates=candidates,
            top_k=-1,
        )


@pytest.mark.asyncio
async def test_empty_candidates_returns_empty_list(service):
    results = await service.rerank(
        query="test query",
        candidates=[],
        top_k=5,
    )

    assert results == []


@pytest.mark.asyncio
async def test_metadata_is_preserved(service):
    metadata = {
        "source": "evaluation",
        "section": "retrieval",
        "page": 3,
    }

    candidate = build_candidate(
        "Important retrieval information",
        metadata=metadata,
    )

    results = await service.rerank(
        query="retrieval information",
        candidates=[candidate],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == candidate.chunk_id
    assert results[0].document_id == candidate.document_id
    assert results[0].content == candidate.content
    assert results[0].metadata == metadata


@pytest.mark.asyncio
async def test_deterministic_ordering(service):
    candidates = [
        build_candidate("zebra"),
        build_candidate("alpha"),
        build_candidate("middle"),
    ]

    first_results = await service.rerank(
        query="test query",
        candidates=candidates,
        top_k=3,
    )

    second_results = await service.rerank(
        query="test query",
        candidates=candidates,
        top_k=3,
    )

    first_ids = [result.chunk_id for result in first_results]
    second_ids = [result.chunk_id for result in second_results]

    assert first_ids == second_ids

    assert [result.content for result in first_results] == [
        "alpha",
        "middle",
        "zebra",
    ]


@pytest.mark.asyncio
async def test_reranking_respects_top_k(service):
    candidates = [
        build_candidate("delta"),
        build_candidate("alpha"),
        build_candidate("charlie"),
        build_candidate("bravo"),
    ]

    results = await service.rerank(
        query="test query",
        candidates=candidates,
        top_k=2,
    )

    assert len(results) == 2

    assert [result.content for result in results] == [
        "alpha",
        "bravo",
    ]