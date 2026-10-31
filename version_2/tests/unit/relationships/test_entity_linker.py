from types import SimpleNamespace
from uuid import uuid4

from app.relationships.entity_linker import EntityLinkingService


def test_resolves_name_case_and_whitespace_insensitively():
    person_id = uuid4()
    person = SimpleNamespace(id=person_id, name="  Ada   Lovelace ", email=None)

    result = EntityLinkingService().resolve_person_reference("ada lovelace", people=[person])

    assert result.status == "matched"
    assert result.person_id == person_id
    assert result.matched_by == "name"


def test_email_reference_matches_email_only():
    person_id = uuid4()
    person = SimpleNamespace(id=person_id, name="Ada Lovelace", email="ADA@Example.com")

    result = EntityLinkingService().resolve_person_reference(" ada@example.com ", people=[person])

    assert result.status == "matched"
    assert result.person_id == person_id
    assert result.matched_by == "email"


def test_duplicate_names_are_reported_as_ambiguous():
    first = SimpleNamespace(id=uuid4(), name="Alex Kim", email=None)
    second = SimpleNamespace(id=uuid4(), name="Alex Kim", email=None)

    result = EntityLinkingService().resolve_person_reference("Alex Kim", people=[first, second])

    assert result.status == "ambiguous"
    assert set(result.candidate_ids) == {first.id, second.id}
    assert result.person_id is None


def test_does_not_use_substring_or_fuzzy_matching():
    person = SimpleNamespace(id=uuid4(), name="Alex Kim", email="alex@example.com")

    result = EntityLinkingService().resolve_person_reference("Alex", people=[person])

    assert result.status == "not_found"
    assert result.person_id is None


def test_empty_reference_is_not_found():
    person = SimpleNamespace(id=uuid4(), name="Alex Kim", email=None)

    result = EntityLinkingService().resolve_person_reference("  ", people=[person])

    assert result.status == "not_found"
