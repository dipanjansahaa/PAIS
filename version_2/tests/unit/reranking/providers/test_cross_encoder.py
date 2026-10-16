from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from app.reranking.providers.local import LocalCrossEncoderReranker
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
def mock_cross_encoder():
    with patch(
        "app.reranking.providers.local.CrossEncoder"
    ) as mock_class:
        mock_model = MagicMock()
        mock_class.return_value = mock_model

        yield mock_class, mock_model


@pytest.fixture
def reranker(mock_cross_encoder):
    _, _ = mock_cross_encoder

    return LocalCrossEncoderReranker(
        model_name="test-reranker",
        device="cpu",
        batch_size=2,
    )


@pytest.mark.asyncio
async def test_empty_query_raises_value_error(reranker):
    candidates = [
        build_candidate("Some document")
    ]

    with pytest.raises(
        ValueError,
        match="Query must not be empty.",
    ):
        await reranker.rerank(
            query="   ",
            candidates=candidates,
            top_k=5,
        )


@pytest.mark.asyncio
async def test_invalid_top_k_raises_value_error(reranker):
    candidates = [
        build_candidate("Some document")
    ]

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero.",
    ):
        await reranker.rerank(
            query="test query",
            candidates=candidates,
            top_k=0,
        )


@pytest.mark.asyncio
async def test_empty_candidates_returns_empty_list(reranker, mock_cross_encoder):
    _, mock_model = mock_cross_encoder

    results = await reranker.rerank(
        query="test query",
        candidates=[],
        top_k=5,
    )

    assert results == []
    mock_model.predict.assert_not_called()


@pytest.mark.asyncio
async def test_score_ordering(reranker, mock_cross_encoder):
    _, mock_model = mock_cross_encoder

    candidates = [
        build_candidate("First candidate"),
        build_candidate("Second candidate"),
        build_candidate("Third candidate"),
    ]

    mock_model.predict.return_value = [
        0.20,
        0.95,
        0.60,
    ]

    results = await reranker.rerank(
        query="test query",
        candidates=candidates,
        top_k=3,
    )

    assert [result.content for result in results] == [
        "Second candidate",
        "Third candidate",
        "First candidate",
    ]

    assert [result.similarity for result in results] == [
        0.95,
        0.60,
        0.20,
    ]


@pytest.mark.asyncio
async def test_top_k_limits_results(reranker, mock_cross_encoder):
    _, mock_model = mock_cross_encoder

    candidates = [
        build_candidate("First candidate"),
        build_candidate("Second candidate"),
        build_candidate("Third candidate"),
        build_candidate("Fourth candidate"),
    ]

    mock_model.predict.return_value = [
        0.20,
        0.95,
        0.60,
        0.80,
    ]

    results = await reranker.rerank(
        query="test query",
        candidates=candidates,
        top_k=2,
    )

    assert len(results) == 2

    assert [result.content for result in results] == [
        "Second candidate",
        "Fourth candidate",
    ]

    assert [result.similarity for result in results] == [
        0.95,
        0.80,
    ]


@pytest.mark.asyncio
async def test_metadata_is_preserved(reranker, mock_cross_encoder):
    _, mock_model = mock_cross_encoder

    metadata = {
        "source": "evaluation",
        "section": "retrieval",
        "page": 3,
    }

    candidate = build_candidate(
        "Important retrieval information",
        similarity=0.25,
        metadata=metadata,
    )

    mock_model.predict.return_value = [0.91]

    results = await reranker.rerank(
        query="retrieval information",
        candidates=[candidate],
        top_k=5,
    )

    assert len(results) == 1

    result = results[0]

    assert result.chunk_id == candidate.chunk_id
    assert result.document_id == candidate.document_id
    assert result.content == candidate.content
    assert result.metadata == metadata

    # The original retrieval score should be replaced
    # by the reranker score.
    assert result.similarity == 0.91


@pytest.mark.asyncio
async def test_cross_encoder_receives_query_candidate_pairs(
    reranker,
    mock_cross_encoder,
):
    _, mock_model = mock_cross_encoder

    candidates = [
        build_candidate("PostgreSQL database"),
        build_candidate("Docker deployment"),
    ]

    mock_model.predict.return_value = [
        0.90,
        0.30,
    ]

    await reranker.rerank(
        query="How is the database configured?",
        candidates=candidates,
        top_k=5,
    )

    mock_model.predict.assert_called_once_with(
        [
            [
                "How is the database configured?",
                "PostgreSQL database",
            ],
            [
                "How is the database configured?",
                "Docker deployment",
            ],
        ],
        batch_size=2,
        show_progress_bar=False,
    )


@pytest.mark.asyncio
async def test_deterministic_tie_ordering(reranker, mock_cross_encoder):
    _, mock_model = mock_cross_encoder

    candidates = [
        build_candidate("zebra"),
        build_candidate("alpha"),
        build_candidate("middle"),
    ]

    # All candidates receive the same score.
    mock_model.predict.return_value = [
        0.50,
        0.50,
        0.50,
    ]

    results = await reranker.rerank(
        query="test query",
        candidates=candidates,
        top_k=3,
    )

    # The implementation uses chunk_id as the tie-breaker.
    expected = sorted(
        candidates,
        key=lambda candidate: str(candidate.chunk_id),
    )

    assert [result.chunk_id for result in results] == [
        candidate.chunk_id
        for candidate in expected
    ]