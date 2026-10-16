from math import log2
from uuid import UUID


def recall_at_k(
    retrieved_ids: list[UUID],
    relevant_ids: set[UUID],
    k: int,
) -> float:
    """
    Recall@K = number of relevant items retrieved in top K
               / total number of relevant items.
    """
    if k <= 0:
        raise ValueError("k must be greater than zero.")

    if not relevant_ids:
        return 0.0

    retrieved_at_k = set(retrieved_ids[:k])

    relevant_retrieved = retrieved_at_k.intersection(
        relevant_ids
    )

    return len(relevant_retrieved) / len(relevant_ids)


def reciprocal_rank(
    retrieved_ids: list[UUID],
    relevant_ids: set[UUID],
) -> float:
    """
    Reciprocal Rank:

        1 / rank

    of the first relevant result.
    """
    if not relevant_ids:
        return 0.0

    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def mrr(
    result_lists: list[list[UUID]],
    relevant_id_sets: list[set[UUID]],
) -> float:
    """
    Mean Reciprocal Rank across multiple queries.
    """
    if len(result_lists) != len(relevant_id_sets):
        raise ValueError(
            "result_lists and relevant_id_sets must have "
            "the same length."
        )

    if not result_lists:
        return 0.0

    reciprocal_ranks = [
        reciprocal_rank(results, relevant_ids)
        for results, relevant_ids
        in zip(result_lists, relevant_id_sets)
    ]

    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def dcg_at_k(
    retrieved_ids: list[UUID],
    relevance: dict[UUID, int],
    k: int,
) -> float:
    """
    Discounted Cumulative Gain@K.

    gain = 2^relevance - 1
    discount = log2(rank + 1)
    """
    if k <= 0:
        raise ValueError("k must be greater than zero.")

    score = 0.0

    for rank, item_id in enumerate(retrieved_ids[:k], start=1):
        relevance_grade = relevance.get(item_id, 0)

        score += (
            (2**relevance_grade - 1)
            / log2(rank + 1)
        )

    return score


def ndcg_at_k(
    retrieved_ids: list[UUID],
    relevance: dict[UUID, int],
    k: int,
) -> float:
    """
    Normalized Discounted Cumulative Gain@K.
    """
    if k <= 0:
        raise ValueError("k must be greater than zero.")

    actual_dcg = dcg_at_k(
        retrieved_ids,
        relevance,
        k,
    )

    ideal_ids = sorted(
        relevance,
        key=lambda item_id: relevance[item_id],
        reverse=True,
    )

    ideal_dcg = dcg_at_k(
        ideal_ids,
        relevance,
        k,
    )

    if ideal_dcg == 0.0:
        return 0.0

    return actual_dcg / ideal_dcg