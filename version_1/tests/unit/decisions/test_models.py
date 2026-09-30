from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.decisions.models import Decision, DecisionSource, DecisionStatus


def test_decision_accepts_valid_values() -> None:
    decision = Decision(
        id=uuid4(),
        user_id=uuid4(),
        title="Use PostgreSQL",
        description="Use PostgreSQL as the primary database.",
        decision_date=datetime(
            2026,
            9,
            30,
            tzinfo=timezone.utc,
        ),
        sources=[
            DecisionSource(chunk_id=uuid4()),
        ],
    )

    assert decision.status is DecisionStatus.ACTIVE
    assert len(decision.sources) == 1


def test_decision_allows_optional_project_and_date() -> None:
    decision = Decision(
        id=uuid4(),
        user_id=uuid4(),
        title="Database choice",
        description="Use PostgreSQL.",
        sources=[
            DecisionSource(chunk_id=uuid4()),
        ],
    )

    assert decision.project_id is None
    assert decision.decision_date is None


@pytest.mark.parametrize(
    "field",
    ["title", "description"],
)
def test_decision_rejects_empty_required_text(field: str) -> None:
    values = {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Valid title",
        "description": "Valid description",
        "sources": [
            DecisionSource(chunk_id=uuid4()),
        ],
    }

    values[field] = ""

    with pytest.raises(ValidationError):
        Decision(**values)


def test_decision_requires_at_least_one_source() -> None:
    with pytest.raises(ValidationError):
        Decision(
            id=uuid4(),
            user_id=uuid4(),
            title="Database choice",
            description="Use PostgreSQL.",
            sources=[],
        )