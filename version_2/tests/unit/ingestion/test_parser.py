import pytest

from app.ingestion.parser import (
    DocumentParserError,
    PlainTextParser,
    get_parser,
)


def test_plain_text_parser_parses_txt() -> None:
    parser = PlainTextParser()

    content = b"Hello from PAIS."

    result = parser.parse(
        content=content,
        mime_type="text/plain",
    )

    assert result == "Hello from PAIS."


def test_plain_text_parser_parses_markdown() -> None:
    parser = PlainTextParser()

    content = (
        b"# Project Decision\n\n"
        b"We decided to use PostgreSQL.\n"
    )

    result = parser.parse(
        content=content,
        mime_type="text/markdown",
    )

    assert result == (
        "# Project Decision\n\n"
        "We decided to use PostgreSQL.\n"
    )


def test_plain_text_parser_supports_markdown_alias() -> None:
    parser = PlainTextParser()

    result = parser.parse(
        content=b"# PAIS",
        mime_type="text/x-markdown",
    )

    assert result == "# PAIS"


@pytest.mark.parametrize(
    "mime_type",
    [
        "TEXT/PLAIN",
        " Text/Plain ",
        "TEXT/MARKDOWN",
        " text/x-markdown ",
    ],
)
def test_plain_text_parser_normalizes_mime_type(
    mime_type: str,
) -> None:
    parser = PlainTextParser()

    result = parser.parse(
        content=b"PAIS",
        mime_type=mime_type,
    )

    assert result == "PAIS"


def test_plain_text_parser_rejects_unsupported_mime_type() -> None:
    parser = PlainTextParser()

    with pytest.raises(DocumentParserError, match="Unsupported MIME type"):
        parser.parse(
            content=b"some content",
            mime_type="application/pdf",
        )


def test_plain_text_parser_rejects_empty_content() -> None:
    parser = PlainTextParser()

    with pytest.raises(
        DocumentParserError,
        match="content must not be empty",
    ):
        parser.parse(
            content=b"",
            mime_type="text/plain",
        )


def test_plain_text_parser_rejects_invalid_utf8() -> None:
    parser = PlainTextParser()

    invalid_utf8 = b"\xff\xfe\xfa"

    with pytest.raises(
        DocumentParserError,
        match="valid UTF-8",
    ):
        parser.parse(
            content=invalid_utf8,
            mime_type="text/plain",
        )


def test_get_parser_returns_plain_text_parser_for_txt() -> None:
    parser = get_parser("text/plain")

    assert isinstance(parser, PlainTextParser)


def test_get_parser_returns_plain_text_parser_for_markdown() -> None:
    parser = get_parser("text/markdown")

    assert isinstance(parser, PlainTextParser)


def test_get_parser_rejects_unsupported_mime_type() -> None:
    with pytest.raises(
        DocumentParserError,
        match="No parser available",
    ):
        get_parser("application/pdf")