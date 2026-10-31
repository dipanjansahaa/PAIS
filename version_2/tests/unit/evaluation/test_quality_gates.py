"""Tests for evaluation benchmark regression gates."""

from types import SimpleNamespace

import pytest
from tests.evaluation.quality_gates import assert_quality_gate


def test_quality_gate_accepts_metrics_within_tolerance() -> None:
    result = SimpleNamespace(
        recall_at_k=0.82,
        mrr=0.72,
        ndcg_at_k=0.75,
    )

    assert_quality_gate("vector", result)


def test_quality_gate_rejects_regression_below_floor() -> None:
    result = SimpleNamespace(
        recall_at_k=0.70,
        mrr=0.72,
        ndcg_at_k=0.75,
    )

    with pytest.raises(AssertionError, match="vector quality gate failed"):
        assert_quality_gate("vector", result)


def test_quality_gate_rejects_unknown_baseline() -> None:
    result = SimpleNamespace(recall_at_k=1.0, mrr=1.0, ndcg_at_k=1.0)

    with pytest.raises(ValueError, match="Unknown evaluation baseline"):
        assert_quality_gate("unknown", result)
