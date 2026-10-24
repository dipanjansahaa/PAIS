# PAIS V2 — Evaluation Guide

## Purpose

PAIS V2 includes evaluation utilities for checking retrieval quality. The evaluation suite measures whether relevant results are retrieved and how highly those results are ranked.

The current memory retrieval benchmark uses a deterministic, labeled dataset. It is intended for regression testing, not as a statistically representative measure of real-world performance.

## Memory Retrieval Benchmark

The benchmark dataset is defined in `tests/evaluation/memory_dataset.py`.

Each evaluation case contains:
- A query.
- The identifiers of relevant memories.
- Graded relevance labels for those memories.

The database-backed evaluation test seeds the fixture memories, executes the labeled queries through the memory retrieval evaluator, and reports retrieval metrics.

## Running the Benchmark

Run the memory evaluation integration test:

```powershell
pytest tests/integration/evaluation/test_memory_evaluation.py -q -s
```

Run the evaluation and memory test groups:

```powershell
pytest tests/unit/evaluation tests/unit/memory tests/integration/memory tests/integration/evaluation -q
```

## Metrics

### Recall@K

Measures the proportion of labeled relevant memories retrieved within the top K results.

Higher values indicate that more relevant memories are being retrieved.

### Mean Reciprocal Rank (MRR)

Measures how highly the first relevant result appears. Each query receives the reciprocal of the rank of its first relevant result, and the values are averaged.

Higher values indicate that users are more likely to encounter a relevant result near the top.

### Normalized Discounted Cumulative Gain (NDCG@K)

Evaluates ranking quality using graded relevance labels while discounting relevant results that appear lower in the ranking.

Higher values indicate better ordering of results according to their relevance grades.

## Current Baseline

The current eight-case memory benchmark reported:

| Metric | Result |
|---|---:|
| Recall@3 | 0.9375 |
| MRR | 1.0000 |
| NDCG@3 | 0.9897 |

These numbers are the baseline for this specific dataset and configuration. They should not be interpreted as guarantees of production retrieval quality.

## Regression Testing

Run the focused evaluation tests after modifying memory retrieval, ranking, filtering, or evaluation logic.

Before considering the evaluation milestone complete, run the complete host test suite and the Docker test suite. Investigate any regressions before accepting changes.