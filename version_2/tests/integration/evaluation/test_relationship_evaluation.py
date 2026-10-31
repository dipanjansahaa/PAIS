"""Database-backed deterministic evaluation of temporal relationship retrieval."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.database.models.project import Project
from app.database.models.user import User
from app.evaluation.relationships import RelationshipContextEvaluator
from app.relationships.service import RelationshipService
from sqlalchemy.ext.asyncio import AsyncSession
from tests.evaluation.quality_gates import assert_quality_gate
from tests.evaluation.relationship_dataset import build_relationship_evaluation_cases

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_relationship_context_evaluation_respects_validity_and_user_scope(
    db_session: AsyncSession,
) -> None:
    """Known-valid edges are retrieved; an expired edge is not counted."""
    user = User(
        email=f"relationship-evaluation-{uuid4()}@pais.local",
        display_name="Relationship Evaluation User",
    )
    foreign_user = User(
        email=f"relationship-evaluation-foreign-{uuid4()}@pais.local",
        display_name="Foreign Evaluation User",
    )
    db_session.add_all([user, foreign_user])
    await db_session.flush()

    source = Project(user_id=user.id, name="PAIS")
    target_a = Project(user_id=user.id, name="Knowledge graph")
    target_b = Project(user_id=user.id, name="Temporal querying")
    expired_target = Project(user_id=user.id, name="Expired target")
    foreign_source = Project(user_id=foreign_user.id, name="Foreign project")
    foreign_target = Project(user_id=foreign_user.id, name="Foreign relationship")
    db_session.add_all([source, target_a, target_b, expired_target, foreign_source, foreign_target])
    await db_session.flush()

    as_of = datetime(2026, 10, 31, 12, tzinfo=UTC)
    service = RelationshipService()
    first = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=target_a.id,
        valid_from=as_of - timedelta(days=2),
        valid_until=as_of + timedelta(days=2),
    )
    second = await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="supports",
        target_type="project",
        target_id=target_b.id,
        valid_from=as_of,
        valid_until=as_of + timedelta(days=1),
    )
    await service.create_relationship(
        db_session,
        user_id=user.id,
        source_type="project",
        source_id=source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=expired_target.id,
        valid_from=as_of - timedelta(days=4),
        valid_until=as_of,
    )
    await service.create_relationship(
        db_session,
        user_id=foreign_user.id,
        source_type="project",
        source_id=foreign_source.id,
        relationship_type="related_to",
        target_type="project",
        target_id=foreign_target.id,
    )

    cases = build_relationship_evaluation_cases(
        source_entity_id=source.id,
        target_entity_id=target_a.id,
        first_relationship_id=first.id,
        second_relationship_id=second.id,
    )

    result = await RelationshipContextEvaluator().evaluate(
        db_session,
        cases,
        user_id=user.id,
        k=5,
        as_of=as_of,
    )

    assert result.recall_at_k == pytest.approx(1.0)
    assert result.mrr == pytest.approx(1.0)
    assert result.ndcg_at_k == pytest.approx(1.0)
    assert_quality_gate("relationships", result)

    print(
        "\\nRelationship context evaluation"
        f"\\nCases: {len(cases)}"
        "\\nK: 5"
        f"\\nRecall@5: {result.recall_at_k:.4f}"
        f"\\nMRR: {result.mrr:.4f}"
        f"\\nNDCG@5: {result.ndcg_at_k:.4f}"
    )
