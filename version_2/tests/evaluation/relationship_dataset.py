"""Deterministic labels for relationship and temporal evaluation."""

from uuid import UUID

from app.evaluation.cases import RelationshipEvaluationCase


def build_relationship_evaluation_cases(
    *,
    source_entity_id: UUID,
    target_entity_id: UUID,
    first_relationship_id: UUID,
    second_relationship_id: UUID,
) -> list[RelationshipEvaluationCase]:
    """Build labelled cases from IDs assigned to seeded database entities.

    The fixture's first seed has two relevant relationships, while the second
    seed observes the first relationship as an incoming edge. The integration
    fixture includes an expired distractor that must not be returned at as_of.
    """
    return [
        RelationshipEvaluationCase(
            entity_type="project",
            entity_id=source_entity_id,
            relevant_ids={first_relationship_id, second_relationship_id},
            relevance={first_relationship_id: 3, second_relationship_id: 3},
        ),
        RelationshipEvaluationCase(
            entity_type="project",
            entity_id=target_entity_id,
            relevant_ids={first_relationship_id},
            relevance={first_relationship_id: 3},
        ),
    ]
