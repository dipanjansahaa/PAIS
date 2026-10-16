from uuid import uuid4

from app.risks.models import Risk
from app.intelligence.models import IntelligenceSource, RiskCandidate


def test_risk_candidate_accepts_valid_data() -> None:
    chunk_id = uuid4()

    candidate = RiskCandidate(
        title="Deployment delay",
        description="The deployment may be delayed.",
        severity="high",
        sources=[
            IntelligenceSource(chunk_id=chunk_id),
        ],
    )

    assert candidate.title == "Deployment delay"
    assert candidate.description == "The deployment may be delayed."
    assert candidate.severity == "high"
    assert candidate.sources[0].chunk_id == chunk_id


def test_risk_domain_model_accepts_valid_data() -> None:
    risk_id = uuid4()
    user_id = uuid4()
    chunk_id = uuid4()

    risk = Risk(
        id=risk_id,
        user_id=user_id,
        title="Deployment delay",
        description="The deployment may be delayed.",
        severity="high",
        sources=[
            {
                "chunk_id": chunk_id,
            }
        ],
    )

    assert risk.id == risk_id
    assert risk.user_id == user_id
    assert risk.title == "Deployment delay"
    assert risk.severity == "high"
    assert risk.sources[0].chunk_id == chunk_id