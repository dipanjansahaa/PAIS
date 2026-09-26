from dataclasses import dataclass
import uuid


@dataclass(slots=True)
class RetrievalResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    similarity: float
    metadata: dict | None