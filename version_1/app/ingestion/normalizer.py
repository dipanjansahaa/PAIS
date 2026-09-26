from __future__ import annotations

import re


class DocumentNormalizer:
    """Normalize extracted document text without changing its meaning."""

    _MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
    _TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)

    def normalize(self, text: str) -> str:
        """
        Normalize document text while preserving meaningful structure.

        The normalizer:
        - normalizes line endings
        - removes trailing spaces/tabs
        - collapses excessive blank lines
        - removes leading/trailing whitespace from the document

        Markdown structure such as headings and lists is preserved.
        """
        if not text:
            return ""

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        normalized = self._TRAILING_WHITESPACE.sub("", normalized)

        normalized = self._MULTIPLE_BLANK_LINES.sub("\n\n", normalized)

        return normalized.strip()