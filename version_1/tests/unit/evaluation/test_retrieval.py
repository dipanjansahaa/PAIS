from uuid import uuid4

import pytest

from math import log2

from app.evaluation.retrieval import (
    dcg_at_k,
    mrr,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k():
    a = uuid4()
    b = uuid4()
    c = uuid4()

    retrieved = [a, b, c]
    relevant = {a, c}

    result = recall_at_k(
        retrieved,
        relevant,
        k=2,
    )

    assert result == pytest.approx(0.5)


def test_recall_at_k_all_relevant_found():
    a = uuid4()
    b = uuid4()

    result = recall_at_k(
        [a, b],
        {a, b},
        k=5,
    )

    assert result == pytest.approx(1.0)


def test_recall_at_k_no_relevant_found():
    a = uuid4()
    b = uuid4()

    result = recall_at_k(
        [a],
        {b},
        k=1,
    )

    assert result == pytest.approx(0.0)


def test_recall_at_k_empty_relevant_set():
    a = uuid4()

    result = recall_at_k(
        [a],
        set(),
        k=5,
    )

    assert result == 0.0


def test_reciprocal_rank_first_result():
    a = uuid4()
    b = uuid4()

    result = reciprocal_rank(
        [a, b],
        {a},
    )

    assert result == pytest.approx(1.0)


def test_reciprocal_rank_second_result():
    a = uuid4()
    b = uuid4()

    result = reciprocal_rank(
        [a, b],
        {b},
    )

    assert result == pytest.approx(0.5)


def test_reciprocal_rank_no_relevant_result():
    a = uuid4()
    b = uuid4()
    c = uuid4()

    result = reciprocal_rank(
        [a, b],
        {c},
    )

    assert result == 0.0


def test_mrr():
    a = uuid4()
    b = uuid4()
    c = uuid4()

    result_lists = [
        [a, b],
        [c, a],
        [b, c],
    ]

    relevant_sets = [
        {a},
        {a},
        {b},
    ]

    result = mrr(
        result_lists,
        relevant_sets,
    )

    expected = (
        1.0
        + 0.5
        + 1.0
    ) / 3

    assert result == pytest.approx(expected)


def test_dcg_at_k():
    a = uuid4()
    b = uuid4()

    relevance = {
        a: 3,
        b: 2,
    }

    result = dcg_at_k(
        [a, b],
        relevance,
        k=2,
    )

    expected = (
        (2**3 - 1) / log2(2)
        + (2**2 - 1) / log2(3)
    )

    assert result == pytest.approx(expected)


def test_ndcg_perfect_ranking():
    a = uuid4()
    b = uuid4()
    c = uuid4()

    relevance = {
        a: 3,
        b: 2,
        c: 1,
    }

    result = ndcg_at_k(
        [a, b, c],
        relevance,
        k=3,
    )

    assert result == pytest.approx(1.0)


def test_ndcg_worse_ranking():
    a = uuid4()
    b = uuid4()
    c = uuid4()

    relevance = {
        a: 3,
        b: 2,
        c: 1,
    }

    result = ndcg_at_k(
        [c, b, a],
        relevance,
        k=3,
    )

    assert 0.0 < result < 1.0


def test_ndcg_zero_when_no_relevant_items():
    a = uuid4()
    b = uuid4()

    relevance = {
        a: 0,
        b: 0,
    }

    result = ndcg_at_k(
        [a, b],
        relevance,
        k=2,
    )

    assert result == 0.0


def test_metrics_reject_invalid_k():
    a = uuid4()

    with pytest.raises(ValueError):
        recall_at_k([a], {a}, 0)

    with pytest.raises(ValueError):
        dcg_at_k([a], {a: 1}, 0)

    with pytest.raises(ValueError):
        ndcg_at_k([a], {a: 1}, 0)