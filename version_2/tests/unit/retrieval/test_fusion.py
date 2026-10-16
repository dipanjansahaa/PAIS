from uuid import uuid4

import pytest

from app.retrieval.models import RetrievalResult
from app.retrieval.fusion import RRFFusion


def make_result(
    chunk_id=None,
    document_id=None,
    content="content",
    similarity=1.0,
):
    return RetrievalResult(
        chunk_id=chunk_id or uuid4(),
        document_id=document_id or uuid4(),
        content=content,
        similarity=similarity,
        metadata={"source": "test"},
    )


def test_rrf_fuses_results_from_multiple_retrievers():
    chunk_a = uuid4()
    chunk_b = uuid4()
    document_id = uuid4()

    vector_results = [
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
        make_result(
            chunk_id=chunk_b,
            document_id=document_id,
            content="Chunk B",
        ),
    ]

    lexical_results = [
        make_result(
            chunk_id=chunk_b,
            document_id=document_id,
            content="Chunk B",
        ),
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
    ]

    fusion = RRFFusion(k=60)

    results = fusion.fuse(
        [vector_results, lexical_results],
        top_k=5,
    )

    assert len(results) == 2

    assert {
        result.chunk_id
        for result in results
    } == {chunk_a, chunk_b}


def test_rrf_accumulates_scores_for_results_present_in_multiple_lists():
    chunk_a = uuid4()
    chunk_b = uuid4()
    document_id = uuid4()

    vector_results = [
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
        make_result(
            chunk_id=chunk_b,
            document_id=document_id,
            content="Chunk B",
        ),
    ]

    lexical_results = [
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
    ]

    fusion = RRFFusion(k=60)

    results = fusion.fuse(
        [vector_results, lexical_results],
        top_k=5,
    )

    assert results[0].chunk_id == chunk_a

    expected_score = (
        1 / (60 + 1)
        + 1 / (60 + 1)
    )

    assert results[0].similarity == pytest.approx(expected_score)


def test_rrf_deduplicates_results_across_retrievers():
    chunk_a = uuid4()
    document_id = uuid4()

    vector_results = [
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
    ]

    lexical_results = [
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
    ]

    fusion = RRFFusion()

    results = fusion.fuse(
        [vector_results, lexical_results],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_a


def test_rrf_deduplicates_duplicate_chunks_within_same_result_list():
    chunk_a = uuid4()
    document_id = uuid4()

    results_from_retriever = [
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A",
        ),
        make_result(
            chunk_id=chunk_a,
            document_id=document_id,
            content="Chunk A duplicate",
        ),
    ]

    fusion = RRFFusion(k=60)

    results = fusion.fuse(
        [results_from_retriever],
        top_k=5,
    )

    assert len(results) == 1

    expected_score = 1 / (60 + 1)

    assert results[0].similarity == pytest.approx(expected_score)


def test_rrf_respects_top_k():
    results = [
        make_result(),
        make_result(),
        make_result(),
        make_result(),
    ]

    fusion = RRFFusion()

    fused_results = fusion.fuse(
        [results],
        top_k=2,
    )

    assert len(fused_results) == 2


def test_rrf_ranks_by_combined_score():
    chunk_a = uuid4()
    chunk_b = uuid4()
    chunk_c = uuid4()
    document_id = uuid4()

    # A: rank 1 in vector + rank 3 in lexical
    vector_results = [
        make_result(chunk_id=chunk_a, document_id=document_id),
        make_result(chunk_id=chunk_b, document_id=document_id),
        make_result(chunk_id=chunk_c, document_id=document_id),
    ]

    lexical_results = [
        make_result(chunk_id=chunk_b, document_id=document_id),
        make_result(chunk_id=chunk_c, document_id=document_id),
        make_result(chunk_id=chunk_a, document_id=document_id),
    ]

    fusion = RRFFusion(k=60)

    results = fusion.fuse(
        [vector_results, lexical_results],
        top_k=3,
    )

    # B receives rank 2 + rank 1.
    # A receives rank 1 + rank 3.
    # C receives rank 3 + rank 2.
    assert results[0].chunk_id == chunk_b
    assert results[1].chunk_id == chunk_a
    assert results[2].chunk_id == chunk_c


def test_rrf_preserves_result_metadata():
    chunk_id = uuid4()
    document_id = uuid4()

    result = make_result(
        chunk_id=chunk_id,
        document_id=document_id,
        content="Important content",
    )

    fusion = RRFFusion()

    results = fusion.fuse(
        [[result]],
        top_k=1,
    )

    assert results[0].chunk_id == chunk_id
    assert results[0].document_id == document_id
    assert results[0].content == "Important content"
    assert results[0].metadata == {"source": "test"}


def test_rrf_rejects_invalid_k():
    with pytest.raises(ValueError, match="RRF k must be greater than zero"):
        RRFFusion(k=0)


def test_rrf_rejects_invalid_top_k():
    fusion = RRFFusion()

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        fusion.fuse([], top_k=0)