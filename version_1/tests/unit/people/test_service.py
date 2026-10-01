from uuid import uuid4

from app.intelligence.models import IntelligenceSource, PersonCandidate
from app.people.service import PersonService


def test_person_service_deduplicates_source_chunk_ids() -> None:
    chunk_id = uuid4()

    candidate = PersonCandidate(
        name="Alice Smith",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    result = PersonService._unique_source_chunk_ids(candidate)

    assert result == [chunk_id]


def test_person_service_preserves_source_order() -> None:
    first = uuid4()
    second = uuid4()

    candidate = PersonCandidate(
        name="Alice Smith",
        sources=[
            IntelligenceSource(chunk_id=first),
            IntelligenceSource(chunk_id=second),
            IntelligenceSource(chunk_id=first),
        ],
    )

    result = PersonService._unique_source_chunk_ids(candidate)

    assert result == [first, second]