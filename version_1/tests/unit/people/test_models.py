from uuid import uuid4

from app.intelligence.models import IntelligenceSource, PersonCandidate
from app.people.models import Person, PersonSource


def test_person_candidate_accepts_valid_data() -> None:
    chunk_id = uuid4()

    candidate = PersonCandidate(
        name="Alice Smith",
        email="alice@example.com",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    assert candidate.name == "Alice Smith"
    assert candidate.email == "alice@example.com"
    assert candidate.sources[0].chunk_id == chunk_id


def test_person_domain_model_accepts_valid_data() -> None:
    person_id = uuid4()
    user_id = uuid4()
    chunk_id = uuid4()

    person = Person(
        id=person_id,
        user_id=user_id,
        name="Alice Smith",
        email="alice@example.com",
        sources=[
            PersonSource(chunk_id=chunk_id),
        ],
    )

    assert person.id == person_id
    assert person.user_id == user_id
    assert person.name == "Alice Smith"
    assert person.email == "alice@example.com"
    assert person.sources[0].chunk_id == chunk_id