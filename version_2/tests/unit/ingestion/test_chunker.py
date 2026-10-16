import pytest

from app.ingestion.chunker import DocumentChunker, TextChunk


def test_chunk_empty_text() -> None:
    chunker = DocumentChunker()

    assert chunker.chunk("") == []


def test_chunk_whitespace_only_text() -> None:
    chunker = DocumentChunker()

    assert chunker.chunk("   \n\n   ") == []


def test_chunk_short_text_returns_single_chunk() -> None:
    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=20,
    )

    result = chunker.chunk("This is a short document.")

    assert result == [
        TextChunk(
            index=0,
            content="This is a short document.",
        )
    ]


def test_chunk_preserves_paragraph_boundaries() -> None:
    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=10,
    )

    text = (
        "First paragraph.\n\n"
        "Second paragraph.\n\n"
        "Third paragraph."
    )

    result = chunker.chunk(text)

    assert len(result) == 1
    assert result[0].content == text


def test_chunk_creates_multiple_chunks() -> None:
    chunker = DocumentChunker(
        chunk_size=50,
        chunk_overlap=10,
    )

    text = (
        "First paragraph contains some useful information.\n\n"
        "Second paragraph contains more useful information.\n\n"
        "Third paragraph contains additional information."
    )

    result = chunker.chunk(text)

    assert len(result) > 1


def test_chunk_indexes_are_sequential() -> None:
    chunker = DocumentChunker(
        chunk_size=40,
        chunk_overlap=10,
    )

    text = (
        "First paragraph with some content.\n\n"
        "Second paragraph with some content.\n\n"
        "Third paragraph with some content."
    )

    result = chunker.chunk(text)

    assert [chunk.index for chunk in result] == list(
        range(len(result))
    )


def test_chunk_respects_chunk_size() -> None:
    chunker = DocumentChunker(
        chunk_size=50,
        chunk_overlap=10,
    )

    text = (
        "First paragraph with some content.\n\n"
        "Second paragraph with some content.\n\n"
        "Third paragraph with some content."
    )

    result = chunker.chunk(text)

    assert all(len(chunk.content) <= 50 for chunk in result)


def test_chunk_long_paragraph_is_split() -> None:
    chunker = DocumentChunker(
        chunk_size=50,
        chunk_overlap=10,
    )

    text = "A" * 150

    result = chunker.chunk(text)

    assert len(result) > 1
    assert all(len(chunk.content) <= 50 for chunk in result)


def test_chunk_long_paragraph_preserves_overlap() -> None:
    chunker = DocumentChunker(
        chunk_size=50,
        chunk_overlap=10,
    )

    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 5

    result = chunker.chunk(text)

    assert len(result) > 1

    first = result[0].content
    second = result[1].content

    assert second.startswith(first[-10:])


def test_zero_overlap_is_supported() -> None:
    chunker = DocumentChunker(
        chunk_size=20,
        chunk_overlap=0,
    )

    text = "A" * 50

    result = chunker.chunk(text)

    assert len(result) == 3
    assert all(len(chunk.content) <= 20 for chunk in result)


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [
        (0, 0),
        (-1, 0),
        (10, 10),
        (10, 11),
        (10, 20),
    ],
)
def test_invalid_chunk_configuration(
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    with pytest.raises(ValueError):
        DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )


def test_chunk_overlap_larger_than_text() -> None:
    chunker = DocumentChunker(
        chunk_size=20,
        chunk_overlap=15,
    )

    text = "A" * 35

    result = chunker.chunk(text)

    assert len(result) > 1
    assert all(len(chunk.content) <= 20 for chunk in result)


def test_chunk_overlap_plus_paragraph_never_exceeds_chunk_size() -> None:
    chunker = DocumentChunker(
        chunk_size=50,
        chunk_overlap=10,
    )

    text = (
        "A" * 40
        + "\n\n"
        + "B" * 45
    )

    result = chunker.chunk(text)

    assert all(len(chunk.content) <= 50 for chunk in result)


def test_small_chunk_size_is_supported() -> None:
    chunker = DocumentChunker(
        chunk_size=5,
        chunk_overlap=2,
    )

    result = chunker.chunk("abcdefghij")

    assert result
    assert all(len(chunk.content) <= 5 for chunk in result)


def test_chunk_preserves_unicode_text() -> None:
    chunker = DocumentChunker(
        chunk_size=20,
        chunk_overlap=5,
    )

    text = "Project সিদ্ধান্ত PostgreSQL ব্যবহার করবে।"

    result = chunker.chunk(text)

    reconstructed = "".join(
        chunk.content for chunk in result
    )

    assert "PostgreSQL" in reconstructed
    assert "সিদ্ধান্ত" in reconstructed


def test_all_chunks_respect_configured_size() -> None:
    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=20,
    )

    text = (
        "A" * 80
        + "\n\n"
        + "B" * 80
        + "\n\n"
        + "C" * 80
        + "\n\n"
        + "D" * 250
    )

    result = chunker.chunk(text)

    assert result
    assert all(
        0 < len(chunk.content) <= chunker.chunk_size
        for chunk in result
    )
    assert [chunk.index for chunk in result] == list(
        range(len(result))
    )