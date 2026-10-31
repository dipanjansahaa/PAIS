"""Measured evaluation baselines and tolerant regression gates.

Baselines are tied to the small, deterministic datasets documented in
``docs/evaluation.md``. They are regression tripwires, not production SLAs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.evaluation.runner import RetrievalEvaluationResult


@dataclass(frozen=True)
class QualityBaseline:
    """Observed metrics plus an allowed absolute regression per metric."""

    cases: int
    k: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    tolerance: float


BASELINES: dict[str, QualityBaseline] = {
    "vector": QualityBaseline(
        cases=15,
        k=5,
        recall_at_k=0.8667,
        mrr=0.7667,
        ndcg_at_k=0.7906,
        tolerance=0.05,
    ),
    "lexical": QualityBaseline(
        cases=15,
        k=5,
        recall_at_k=0.8444,
        mrr=0.7667,
        ndcg_at_k=0.7751,
        tolerance=0.05,
    ),
    "hybrid_rrf": QualityBaseline(
        cases=15,
        k=5,
        recall_at_k=0.8556,
        mrr=0.8389,
        ndcg_at_k=0.8345,
        tolerance=0.05,
    ),
    "hybrid_reranked": QualityBaseline(
        cases=15,
        k=5,
        recall_at_k=0.7889,
        mrr=0.7800,
        ndcg_at_k=0.7172,
        tolerance=0.05,
    ),
    "memory": QualityBaseline(
        cases=8,
        k=3,
        recall_at_k=0.9375,
        mrr=1.0000,
        ndcg_at_k=0.9897,
        tolerance=0.10,
    ),
    "relationships": QualityBaseline(
        cases=2,
        k=5,
        recall_at_k=1.0000,
        mrr=1.0000,
        ndcg_at_k=1.0000,
        tolerance=0.05,
    ),
}


def assert_quality_gate(
    name: str,
    result: RetrievalEvaluationResult,
) -> None:
    """Fail when a measured metric drops below its baseline minus tolerance."""
    try:
        baseline = BASELINES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown evaluation baseline: {name}") from exc

    actual_metrics = {
        "recall_at_k": result.recall_at_k,
        "mrr": result.mrr,
        "ndcg_at_k": result.ndcg_at_k,
    }

    for metric_name, actual in actual_metrics.items():
        expected = getattr(baseline, metric_name)
        floor = max(0.0, expected - baseline.tolerance)
        if actual < floor:
            raise AssertionError(
                f"{name} quality gate failed for {metric_name}: "
                f"observed={actual:.4f}, minimum={floor:.4f}, "
                f"baseline={expected:.4f}, "
                f"allowed_regression={baseline.tolerance:.2f}"
            )
