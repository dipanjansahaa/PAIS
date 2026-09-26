from __future__ import annotations

from abc import ABC, abstractmethod


class DocumentParserError(ValueError):
    """Raised when a document cannot be parsed."""


class DocumentParser(ABC):
    """Interface for document text extraction."""

    @abstractmethod
    def parse(self, content: bytes, mime_type: str) -> str:
        """Extract plain text from document bytes."""
        raise NotImplementedError


class PlainTextParser(DocumentParser):
    """Parser for plain-text documents such as TXT and Markdown."""

    SUPPORTED_MIME_TYPES = frozenset(
        {
            "text/plain",
            "text/markdown",
            "text/x-markdown",
        }
    )

    def parse(self, content: bytes, mime_type: str) -> str:
        normalized_mime_type = mime_type.strip().lower()

        if normalized_mime_type not in self.SUPPORTED_MIME_TYPES:
            raise DocumentParserError(
                f"Unsupported MIME type: {mime_type!r}. "
                f"Supported types: {sorted(self.SUPPORTED_MIME_TYPES)}"
            )

        if not content:
            raise DocumentParserError("Document content must not be empty.")

        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentParserError(
                "Document content must be valid UTF-8."
            ) from exc


def get_parser(mime_type: str) -> DocumentParser:
    """Return the appropriate parser for a MIME type."""
    normalized_mime_type = mime_type.strip().lower()

    if normalized_mime_type in PlainTextParser.SUPPORTED_MIME_TYPES:
        return PlainTextParser()

    raise DocumentParserError(
        f"No parser available for MIME type: {mime_type!r}."
    )