from uuid import uuid4

from app.intelligence.models import IntelligenceSource, RiskCandidate
from app.risks.service import RiskService


def test_risk_service_deduplicates_source_chunk_ids() -> None:
    chunk_id = uuid4()

    candidate = RiskCandidate(
        title="Deployment delay",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    result = RiskService._unique_source_chunk_ids(candidate)

    assert result == [chunk_id]


def test_risk_service_preserves_source_order() -> None:
    first_chunk_id = uuid4()
    second_chunk_id = uuid4()
    third_chunk_id = uuid4()

    candidate = RiskCandidate(
        title="Deployment delay",
        sources=[
            IntelligenceSource(chunk_id=first_chunk_id),
            IntelligenceSource(chunk_id=second_chunk_id),
            IntelligenceSource(chunk_id=first_chunk_id),
            IntelligenceSource(chunk_id=third_chunk_id),
        ],
    )

    result = RiskService._unique_source_chunk_ids(candidate)

    assert result == [
        first_chunk_id,
        second_chunk_id,
        third_chunk_id,
    ]