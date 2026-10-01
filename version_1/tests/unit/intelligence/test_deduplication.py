"""Tests for deterministic intelligence deduplication."""

from datetime import datetime
from uuid import uuid4

from app.intelligence.deduplication import (
    deduplicate_commitments,
    deduplicate_decisions,
    deduplicate_intelligence,
    deduplicate_people,
    deduplicate_projects,
    deduplicate_risks,
    deduplicate_tasks,
    normalize_text,
)
from app.intelligence.models import (
    CommitmentCandidate,
    DecisionCandidate,
    IntelligenceSource,
    PersonCandidate,
    ProjectCandidate,
    RiskCandidate,
    StructuredIntelligence,
    TaskCandidate,
)


def source(chunk_id=None):
    """Create an intelligence source."""

    return IntelligenceSource(
        chunk_id=chunk_id or uuid4(),
    )


def test_normalize_text_is_deterministic():
    """Normalization should collapse equivalent textual forms."""

    assert normalize_text(
        "  Review   THE API  "
    ) == "review the api"


def test_normalize_text_preserves_meaningful_words():
    """Normalization should not remove meaningful words."""

    assert normalize_text(
        "Review the API"
    ) != normalize_text(
        "Do not review the API"
    )


def test_task_deduplication_merges_normalized_duplicates():
    """Equivalent task identities should merge."""

    first_source = source()
    second_source = source()

    tasks = [
        TaskCandidate(
            description=" Review   the API ",
            owner="Dipanjan",
            sources=[first_source],
        ),
        TaskCandidate(
            description="review the api",
            owner="dipanjan",
            sources=[second_source],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 1
    assert result[0].description == " Review   the API "
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_task_deduplication_does_not_merge_different_owners():
    """Different explicit owners represent different candidates."""

    tasks = [
        TaskCandidate(
            description="Review the API",
            owner="Alice",
            sources=[source()],
        ),
        TaskCandidate(
            description="Review the API",
            owner="Bob",
            sources=[source()],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 2


def test_task_deduplication_does_not_merge_missing_owner_with_named_owner():
    """Unknown ownership must not be treated as a wildcard."""

    tasks = [
        TaskCandidate(
            description="Review the API",
            owner=None,
            sources=[source()],
        ),
        TaskCandidate(
            description="Review the API",
            owner="Dipanjan",
            sources=[source()],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 2


def test_task_deduplication_fills_missing_due_date():
    """A missing field may be filled by a duplicate candidate."""

    chunk_a = source()
    chunk_b = source()

    due_at = datetime(2026, 10, 5, 12, 0)

    tasks = [
        TaskCandidate(
            description="Review API",
            owner="Dipanjan",
            due_at=None,
            priority="high",
            sources=[chunk_a],
        ),
        TaskCandidate(
            description="review api",
            owner="dipanjan",
            due_at=due_at,
            priority="high",
            sources=[chunk_b],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 1
    assert result[0].due_at == due_at
    assert result[0].priority == "high"
    assert result[0].sources == [chunk_a, chunk_b]


def test_task_deduplication_preserves_conflicting_due_dates():
    """Conflicting due dates must not be silently merged."""

    tasks = [
        TaskCandidate(
            description="Review API",
            owner="Dipanjan",
            due_at=datetime(2026, 10, 5),
            sources=[source()],
        ),
        TaskCandidate(
            description="review api",
            owner="dipanjan",
            due_at=datetime(2026, 10, 7),
            sources=[source()],
        ),
    ]

    result = deduplicate_tasks(tasks)

    assert len(result) == 2


def test_commitment_deduplication_merges_duplicates():
    """Equivalent commitments should merge."""

    first_source = source()
    second_source = source()

    commitments = [
        CommitmentCandidate(
            description="Finish the migration",
            owner="Dipanjan",
            sources=[first_source],
        ),
        CommitmentCandidate(
            description=" finish   THE migration ",
            owner="dipanjan",
            sources=[second_source],
        ),
    ]

    result = deduplicate_commitments(commitments)

    assert len(result) == 1
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_commitment_deduplication_preserves_conflicting_deadlines():
    """Conflicting deadlines must remain separate."""

    commitments = [
        CommitmentCandidate(
            description="Finish migration",
            owner="Dipanjan",
            deadline_at=datetime(2026, 10, 5),
            sources=[source()],
        ),
        CommitmentCandidate(
            description="finish migration",
            owner="dipanjan",
            deadline_at=datetime(2026, 10, 8),
            sources=[source()],
        ),
    ]

    result = deduplicate_commitments(commitments)

    assert len(result) == 2


def test_decision_deduplication_merges_exact_normalized_decisions():
    """Equivalent decisions should merge."""

    first_source = source()
    second_source = source()

    decisions = [
        DecisionCandidate(
            title="Database Choice",
            description="Use PostgreSQL",
            sources=[first_source],
        ),
        DecisionCandidate(
            title=" database   choice ",
            description="use postgresql",
            sources=[second_source],
        ),
    ]

    result = deduplicate_decisions(decisions)

    assert len(result) == 1
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_decision_deduplication_keeps_different_decisions():
    """Different decision descriptions must remain separate."""

    decisions = [
        DecisionCandidate(
            title="Database",
            description="Use PostgreSQL",
            sources=[source()],
        ),
        DecisionCandidate(
            title="Database",
            description="Use MySQL",
            sources=[source()],
        ),
    ]

    result = deduplicate_decisions(decisions)

    assert len(result) == 2


def test_decision_deduplication_preserves_conflicting_dates():
    """Conflicting decision dates must not be silently merged."""

    decisions = [
        DecisionCandidate(
            title="Database",
            description="Use PostgreSQL",
            decision_date=datetime(2026, 10, 5),
            sources=[source()],
        ),
        DecisionCandidate(
            title="database",
            description="use postgresql",
            decision_date=datetime(2026, 10, 7),
            sources=[source()],
        ),
    ]

    result = deduplicate_decisions(decisions)

    assert len(result) == 2


def test_project_deduplication_merges_normalized_duplicates():
    """Equivalent project identities should merge."""

    first_source = source()
    second_source = source()

    projects = [
        ProjectCandidate(
            name=" PAIS V1 ",
            description="Personal intelligence system",
            sources=[first_source],
        ),
        ProjectCandidate(
            name="pais   v1",
            description="Personal intelligence system",
            sources=[second_source],
        ),
    ]

    result = deduplicate_projects(projects)

    assert len(result) == 1
    assert result[0].name == " PAIS V1 "
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_project_deduplication_fills_missing_description():
    """A missing project description may be filled."""

    first_source = source()
    second_source = source()

    projects = [
        ProjectCandidate(
            name="PAIS V1",
            description=None,
            sources=[first_source],
        ),
        ProjectCandidate(
            name="pais v1",
            description="Personal intelligence system",
            sources=[second_source],
        ),
    ]

    result = deduplicate_projects(projects)

    assert len(result) == 1
    assert result[0].description == "Personal intelligence system"


def test_project_deduplication_preserves_conflicting_descriptions():
    """Conflicting descriptions must not be silently merged."""

    projects = [
        ProjectCandidate(
            name="PAIS V1",
            description="Personal intelligence system",
            sources=[source()],
        ),
        ProjectCandidate(
            name="pais v1",
            description="Analytics platform",
            sources=[source()],
        ),
    ]

    result = deduplicate_projects(projects)

    assert len(result) == 2


def test_person_deduplication_merges_normalized_duplicates():
    """Equivalent person identities should merge."""

    first_source = source()
    second_source = source()

    people = [
        PersonCandidate(
            name=" Alice Smith ",
            email="Alice@example.com",
            sources=[first_source],
        ),
        PersonCandidate(
            name="alice   smith",
            email="alice@EXAMPLE.COM",
            sources=[second_source],
        ),
    ]

    result = deduplicate_people(people)

    assert len(result) == 1
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_person_deduplication_does_not_merge_missing_email_with_email():
    """Missing email must not act as a wildcard."""

    people = [
        PersonCandidate(
            name="Alice Smith",
            email=None,
            sources=[source()],
        ),
        PersonCandidate(
            name="alice smith",
            email="alice@example.com",
            sources=[source()],
        ),
    ]

    result = deduplicate_people(people)

    assert len(result) == 2


def test_person_deduplication_does_not_merge_different_emails():
    """Different explicit emails represent separate identities."""

    people = [
        PersonCandidate(
            name="Alice Smith",
            email="alice@example.com",
            sources=[source()],
        ),
        PersonCandidate(
            name="alice smith",
            email="alice.smith@example.com",
            sources=[source()],
        ),
    ]

    result = deduplicate_people(people)

    assert len(result) == 2


def test_person_deduplication_does_not_merge_same_email_with_different_names():
    """A conflicting explicit name must not be silently merged."""

    people = [
        PersonCandidate(
            name="Alice Smith",
            email="alice@example.com",
            sources=[source()],
        ),
        PersonCandidate(
            name="Bob Smith",
            email="alice@example.com",
            sources=[source()],
        ),
    ]

    result = deduplicate_people(people)

    assert len(result) == 2


def test_risk_deduplication_merges_normalized_duplicates():
    """Equivalent risk identities should merge."""

    first_source = source()
    second_source = source()

    risks = [
        RiskCandidate(
            title=" API instability ",
            description="The API may fail under load.",
            severity="high",
            sources=[first_source],
        ),
        RiskCandidate(
            title="api   instability",
            description="the api may fail under load.",
            severity="high",
            sources=[second_source],
        ),
    ]

    result = deduplicate_risks(risks)

    assert len(result) == 1
    assert result[0].sources == [
        first_source,
        second_source,
    ]


def test_risk_deduplication_fills_missing_severity():
    """A missing severity may be filled."""

    risks = [
        RiskCandidate(
            title="API instability",
            description="The API may fail under load.",
            severity=None,
            sources=[source()],
        ),
        RiskCandidate(
            title="api instability",
            description="the api may fail under load.",
            severity="high",
            sources=[source()],
        ),
    ]

    result = deduplicate_risks(risks)

    assert len(result) == 1
    assert result[0].severity == "high"


def test_risk_deduplication_preserves_conflicting_severity():
    """Conflicting severity values must not be silently merged."""

    risks = [
        RiskCandidate(
            title="API instability",
            description="The API may fail under load.",
            severity="high",
            sources=[source()],
        ),
        RiskCandidate(
            title="api instability",
            description="the api may fail under load.",
            severity="low",
            sources=[source()],
        ),
    ]

    result = deduplicate_risks(risks)

    assert len(result) == 2


def test_risk_deduplication_keeps_different_descriptions():
    """Different risk descriptions must remain separate."""

    risks = [
        RiskCandidate(
            title="API instability",
            description="The API may fail under load.",
            sources=[source()],
        ),
        RiskCandidate(
            title="API instability",
            description="The API may fail because of network failures.",
            sources=[source()],
        ),
    ]

    result = deduplicate_risks(risks)

    assert len(result) == 2


# def test_deduplicate_intelligence_only_changes_supported_categories():
#     """The aggregate function should preserve all other categories."""

#     intelligence = StructuredIntelligence(
#         tasks=[
#             TaskCandidate(
#                 description="Review API",
#                 sources=[source()],
#             ),
#             TaskCandidate(
#                 description="review api",
#                 sources=[source()],
#             ),
#         ],
#         commitments=[
#             CommitmentCandidate(
#                 description="Finish migration",
#                 sources=[source()],
#             ),
#         ],
#     )

#     result = deduplicate_intelligence(intelligence)

#     assert len(result.tasks) == 1
#     assert len(result.commitments) == 1
#     assert result.decisions == []
#     assert result.projects == []
#     assert result.people == []
#     assert result.risks == []
#     assert result.follow_ups == []
#     assert result.deadlines == []


def test_deduplicate_intelligence_deduplicates_supported_categories():
    """Aggregate deduplication should process supported categories."""

    intelligence = StructuredIntelligence(
        tasks=[
            TaskCandidate(
                description="Review API",
                sources=[source()],
            ),
            TaskCandidate(
                description="review api",
                sources=[source()],
            ),
        ],
        commitments=[
            CommitmentCandidate(
                description="Finish migration",
                sources=[source()],
            ),
            CommitmentCandidate(
                description="finish migration",
                sources=[source()],
            ),
        ],
        decisions=[
            DecisionCandidate(
                title="Database Choice",
                description="Use PostgreSQL",
                sources=[source()],
            ),
            DecisionCandidate(
                title="database choice",
                description="use postgresql",
                sources=[source()],
            ),
        ],
        projects=[
            ProjectCandidate(
                name="PAIS V1",
                sources=[source()],
            ),
            ProjectCandidate(
                name="pais v1",
                sources=[source()],
            ),
        ],
        people=[
            PersonCandidate(
                name="Alice Smith",
                email="alice@example.com",
                sources=[source()],
            ),
            PersonCandidate(
                name="alice smith",
                email="alice@example.com",
                sources=[source()],
            ),
        ],
        risks=[
            RiskCandidate(
                title="API instability",
                description="API may fail under load",
                sources=[source()],
            ),
            RiskCandidate(
                title="api instability",
                description="api may fail under load",
                sources=[source()],
            ),
        ],
    )

    result = deduplicate_intelligence(intelligence)

    assert len(result.tasks) == 1
    assert len(result.commitments) == 1
    assert len(result.decisions) == 1
    assert len(result.projects) == 1
    assert len(result.people) == 1
    assert len(result.risks) == 1

    assert result.follow_ups == []
    assert result.deadlines == []