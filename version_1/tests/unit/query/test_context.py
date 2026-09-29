"""Unit tests for query context construction."""

from uuid import uuid4

import pytest

from app.query.context import ContextBuilder
from app.retrieval.models import RetrievalResult


def make_result(
    *,
    document_id=None,
    content="Test content",
    similarity=0.5,
):
    """Create a RetrievalResult for context tests."""

    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=document_id or uuid4(),
        content=content,
        similarity=similarity,
        metadata={"source": "test"},
    )


def test_context_builder_returns_empty_context_for_no_results():
    """Empty retrieval should produce empty context."""

    builder = ContextBuilder()

    context = builder.build([])

    assert context.text == ""
    assert context.sources == ()
    assert context.estimated_tokens == 0
    assert context.truncated is False


def test_context_builder_preserves_retrieval_order():
    """Context should preserve the incoming retrieval order."""

    document_id = uuid4()

    first = make_result(
        document_id=document_id,
        content="First result",
    )
    second = make_result(
        document_id=document_id,
        content="Second result",
    )

    builder = ContextBuilder()

    context = builder.build([first, second])

    assert context.text.index("First result") < (
        context.text.index("Second result")
    )

    assert context.sources[0].chunks[0].content == "First result"
    assert context.sources[0].chunks[1].content == "Second result"


def test_context_builder_deduplicates_chunks():
    """Duplicate chunk IDs should only appear once."""

    document_id = uuid4()
    chunk_id = uuid4()

    first = RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content="Same chunk",
        similarity=0.9,
        metadata={"source": "test"},
    )

    duplicate = RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content="Same chunk",
        similarity=0.8,
        metadata={"source": "test"},
    )

    builder = ContextBuilder()

    context = builder.build([first, duplicate])

    assert len(context.sources) == 1
    assert len(context.sources[0].chunks) == 1
    assert context.sources[0].chunks[0].content == "Same chunk"


def test_context_builder_groups_chunks_by_document():
    """Chunks from the same document should share one source."""

    document_id = uuid4()

    first = make_result(
        document_id=document_id,
        content="Chunk one",
    )
    second = make_result(
        document_id=document_id,
        content="Chunk two",
    )

    other_document_id = uuid4()

    third = make_result(
        document_id=other_document_id,
        content="Chunk three",
    )

    builder = ContextBuilder()

    context = builder.build([first, second, third])

    assert len(context.sources) == 2

    assert context.sources[0].document_id == str(document_id)
    assert len(context.sources[0].chunks) == 2

    assert (
        context.sources[1].document_id
        == str(other_document_id)
    )
    assert len(context.sources[1].chunks) == 1


def test_context_builder_creates_stable_citation_ids():
    """Sources and chunks should receive deterministic citation IDs."""

    document_id = uuid4()

    result = make_result(
        document_id=document_id,
        content="Important information",
    )

    builder = ContextBuilder()

    context = builder.build([result])

    assert context.sources[0].citation_id == "S1"
    assert context.sources[0].chunks[0].citation_id == "S1-C1"


def test_context_builder_preserves_provenance_fields():
    """Context chunks should retain retrieval provenance."""

    document_id = uuid4()
    chunk_id = uuid4()

    result = RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content="Important information",
        similarity=0.91,
        metadata={"source": "architecture.md"},
    )

    builder = ContextBuilder()

    context = builder.build([result])

    chunk = context.sources[0].chunks[0]

    assert chunk.chunk_id == str(chunk_id)
    assert chunk.document_id == str(document_id)
    assert chunk.similarity == 0.91
    assert chunk.metadata == {"source": "architecture.md"}


def test_context_builder_respects_token_budget():
    """Context builder should stop before exceeding its token budget."""

    first = make_result(
        content="a" * 20,
    )
    second = make_result(
        content="b" * 20,
    )

    builder = ContextBuilder(max_context_tokens=5)

    context = builder.build([first, second])

    assert context.truncated is True
    assert context.estimated_tokens <= 5
    assert "a" * 20 in context.text
    assert "b" * 20 not in context.text


def test_context_builder_rejects_invalid_token_budget():
    """Context builder should reject a non-positive token budget."""

    with pytest.raises(
        ValueError,
        match="max_context_tokens must be greater than zero",
    ):
        ContextBuilder(max_context_tokens=0)