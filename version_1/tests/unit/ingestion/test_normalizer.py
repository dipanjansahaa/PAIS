import pytest

from app.ingestion.normalizer import DocumentNormalizer


@pytest.fixture
def normalizer() -> DocumentNormalizer:
    return DocumentNormalizer()


def test_normalize_empty_text(
    normalizer: DocumentNormalizer,
) -> None:
    assert normalizer.normalize("") == ""


# def test_normalize_none_like_empty_input(
def test_normalize_empty_text(
    normalizer: DocumentNormalizer,
) -> None:
    # Runtime callers should normally provide str.
    # This verifies the current empty-input behavior.
    assert normalizer.normalize("") == ""


def test_normalize_windows_line_endings(
    normalizer: DocumentNormalizer,
) -> None:
    text = "First line\r\nSecond line\r\nThird line"

    result = normalizer.normalize(text)

    assert result == "First line\nSecond line\nThird line"


def test_normalize_old_mac_line_endings(
    normalizer: DocumentNormalizer,
) -> None:
    text = "First line\rSecond line\rThird line"

    result = normalizer.normalize(text)

    assert result == "First line\nSecond line\nThird line"


def test_remove_trailing_whitespace(
    normalizer: DocumentNormalizer,
) -> None:
    text = "First line   \nSecond line\t\nThird line"

    result = normalizer.normalize(text)

    assert result == "First line\nSecond line\nThird line"


def test_collapse_multiple_blank_lines(
    normalizer: DocumentNormalizer,
) -> None:
    text = (
        "First paragraph.\n"
        "\n"
        "\n"
        "\n"
        "Second paragraph."
    )

    result = normalizer.normalize(text)

    assert result == (
        "First paragraph.\n\n"
        "Second paragraph."
    )


def test_preserve_single_blank_line(
    normalizer: DocumentNormalizer,
) -> None:
    text = "First paragraph.\n\nSecond paragraph."

    result = normalizer.normalize(text)

    assert result == "First paragraph.\n\nSecond paragraph."


def test_strip_document_boundaries(
    normalizer: DocumentNormalizer,
) -> None:
    text = "\n\n  First line.\nSecond line.  \n\n"

    result = normalizer.normalize(text)

    assert result == "First line.\nSecond line."


def test_preserve_markdown_headings(
    normalizer: DocumentNormalizer,
) -> None:
    text = (
        "# Project Decision\n"
        "\n"
        "We decided to use PostgreSQL."
    )

    result = normalizer.normalize(text)

    assert result == (
        "# Project Decision\n\n"
        "We decided to use PostgreSQL."
    )


def test_preserve_markdown_lists(
    normalizer: DocumentNormalizer,
) -> None:
    text = (
        "# Technology Stack\n\n"
        "- FastAPI\n"
        "- PostgreSQL\n"
        "- Docker"
    )

    result = normalizer.normalize(text)

    assert result == (
        "# Technology Stack\n\n"
        "- FastAPI\n"
        "- PostgreSQL\n"
        "- Docker"
    )


def test_preserve_content_inside_paragraphs(
    normalizer: DocumentNormalizer,
) -> None:
    text = (
        "The project uses PostgreSQL for persistence. "
        "FastAPI provides the backend API."
    )

    result = normalizer.normalize(text)

    assert result == text


@pytest.mark.parametrize(
    "text",
    [
        "   Hello world   ",
        "\nHello world\n",
        "\n\nHello world\n\n",
        "\tHello world\t",
    ],
)
def test_normalize_document_boundaries(
    normalizer: DocumentNormalizer,
    text: str,
) -> None:
    result = normalizer.normalize(text)

    assert result == "Hello world"


def test_normalize_mixed_whitespace_and_blank_lines(
    normalizer: DocumentNormalizer,
) -> None:
    text = (
        "\r\n"
        "# Project Decision   \r\n"
        "\r\n"
        "\r\n"
        "We chose PostgreSQL.   \r\n"
        "\r\n"
        "\r\n"
        "- PostgreSQL\t\r\n"
        "- FastAPI   \r\n"
        "\r\n"
    )

    result = normalizer.normalize(text)

    assert result == (
        "# Project Decision\n\n"
        "We chose PostgreSQL.\n\n"
        "- PostgreSQL\n"
        "- FastAPI"
    )