from uuid import uuid4

import pytest

from app.intelligence.models import IntelligenceSource, ProjectCandidate
from app.projects.models import ProjectStatus
from app.projects.service import ProjectService


def test_project_candidate_model_accepts_valid_candidate() -> None:
    chunk_id = uuid4()

    candidate = ProjectCandidate(
        name="PAIS Development",
        description="Build the Personal Decision & Action Intelligence System.",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    assert candidate.name == "PAIS Development"
    assert candidate.description == (
        "Build the Personal Decision & Action Intelligence System."
    )
    assert candidate.sources[0].chunk_id == chunk_id


def test_project_status_defaults_to_active() -> None:
    assert ProjectStatus.ACTIVE.value == "active"


def test_project_service_deduplicates_source_chunk_ids() -> None:
    chunk_id = uuid4()

    candidate = ProjectCandidate(
        name="PAIS Development",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    result = ProjectService._unique_source_chunk_ids(candidate)

    assert result == [chunk_id]


def test_project_service_preserves_source_order() -> None:
    first = uuid4()
    second = uuid4()

    candidate = ProjectCandidate(
        name="PAIS Development",
        sources=[
            IntelligenceSource(chunk_id=first),
            IntelligenceSource(chunk_id=second),
            IntelligenceSource(chunk_id=first),
        ],
    )

    result = ProjectService._unique_source_chunk_ids(candidate)

    assert result == [first, second]


# @pytest.mark.asyncio
# async def test_project_service_rejects_missing_sources() -> None:
#     candidate = ProjectCandidate(
#         name="PAIS Development",
#         sources=[],
#     )

#     with pytest.raises(
#         ValueError,
#         match="Project must contain at least one source chunk.",
#     ):
#         await ProjectService()._validate_source_chunks(
#             None,
#             user_id=uuid4(),
#             chunk_ids=[],
#         )