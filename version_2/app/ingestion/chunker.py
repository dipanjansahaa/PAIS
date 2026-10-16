from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A chunk of normalized document text."""

    index: int
    content: str


class DocumentChunker:
    """Split normalized document text into overlapping chunks."""

    def __init__(
        self,
        chunk_size: int = 2000,
        chunk_overlap: int = 300,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must not be negative.")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[TextChunk]:
        """Split text into overlapping chunks."""
        normalized_text = text.strip()

        if not normalized_text:
            return []

        paragraphs = self._split_paragraphs(normalized_text)

        chunks: list[TextChunk] = []
        current = ""

        for paragraph in paragraphs:
            # A single paragraph is larger than the configured chunk size.
            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(
                        TextChunk(
                            index=len(chunks),
                            content=current,
                        )
                    )
                    current = ""

                long_chunks = self._split_long_text(paragraph)

                for chunk in long_chunks:
                    chunks.append(
                        TextChunk(
                            index=len(chunks),
                            content=chunk,
                        )
                    )

                continue

            if not current:
                current = paragraph
                continue

            candidate = f"{current}\n\n{paragraph}"

            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content=current,
                )
            )

            overlap = self._get_overlap(current)

            if overlap:
                current = f"{overlap}\n\n{paragraph}"
            else:
                current = paragraph

            # The overlap + paragraph itself may exceed the limit.
            if len(current) > self.chunk_size:
                long_chunks = self._split_long_text(current)

                for chunk in long_chunks[:-1]:
                    chunks.append(
                        TextChunk(
                            index=len(chunks),
                            content=chunk,
                        )
                    )

                current = long_chunks[-1]

        if current:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content=current,
                )
            )

        return chunks

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        return [
            paragraph.strip()
            for paragraph in text.split("\n\n")
            if paragraph.strip()
        ]

    def _get_overlap(self, text: str) -> str:
        if self.chunk_overlap == 0:
            return ""

        if len(text) <= self.chunk_overlap:
            return text

        return text[-self.chunk_overlap :].lstrip()

    def _split_long_text(self, text: str) -> list[str]:
        """Split a long paragraph using fixed-size overlapping windows."""
        chunks: list[str] = []

        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            # With zero overlap this becomes simply `start = end`.
            start = end - self.chunk_overlap

        return chunks