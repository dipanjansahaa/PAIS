# PAIS V2 — Evaluation Guide

## Purpose and limitations

PAIS V2 has deterministic labelled benchmarks for document retrieval, personal-memory retrieval, and relationship context. These evaluate retrieval and ranking on small, curated fixtures. They are useful regression signals, not statistically representative estimates of production performance and not evaluations of generated-answer correctness.

The evaluation suite reports Recall@K, Mean Reciprocal Rank (MRR), and NDCG@K. The quality gates compare each measured metric with a recorded baseline and allow a small absolute drop. They do not require a newer retrieval method to outperform an older one.

## Run the benchmarks

Run all three benchmark reports:

```powershell
pytest tests/integration/evaluation/test_retrieval_evaluation.py -q -s
pytest tests/integration/evaluation/test_memory_evaluation.py -q -s
pytest tests/integration/evaluation/test_relationship_evaluation.py -q -s
```

Run evaluation unit tests:

```powershell
pytest tests/unit/evaluation -q
```

Run the complete host suite after changes:

```powershell
pytest -q
```

The document retrieval benchmark loads the configured embedding and reranking models and may make Hugging Face Hub requests if model files are not cached. A `HF_TOKEN` can improve Hub rate limits; it is not required when the models are already available locally.

## Metrics

- **Recall@K**: fraction of labelled relevant items retrieved within the first K results.
- **MRR**: average reciprocal rank of the first relevant result for each query.
- **NDCG@K**: ranking quality using graded relevance, with lower-ranked results discounted.

Higher values are better for all three metrics.

## Recorded baseline and gates

These baselines were recorded from the local benchmark run on 2026-11-01. Scores are rounded to four decimal places as printed by the benchmark.

### Document retrieval

Dataset: 15 labelled query cases, K=5.

| Retriever | Recall@5 | MRR | NDCG@5 | Allowed absolute drop |
|---|---:|---:|---:|---:|
| Vector | 0.8667 | 0.7667 | 0.7906 | 0.05 |
| Lexical | 0.8444 | 0.7667 | 0.7751 | 0.05 |
| Hybrid + RRF | 0.8556 | 0.8389 | 0.8345 | 0.05 |
| Hybrid + RRF + Cross-Encoder | 0.7889 | 0.7800 | 0.7172 | 0.05 |

### Personal-memory retrieval

Dataset: 8 labelled cases, K=3.

| Metric | Baseline | Allowed absolute drop |
|---|---:|---:|
| Recall@3 | 0.9375 | 0.10 |
| MRR | 1.0000 | 0.10 |
| NDCG@3 | 0.9897 | 0.10 |

### Relationship context

Dataset: 2 labelled seed-entity cases, K=5.

| Metric | Baseline | Allowed absolute drop |
|---|---:|---:|
| Recall@5 | 1.0000 | 0.05 |
| MRR | 1.0000 | 0.05 |
| NDCG@5 | 1.0000 | 0.05 |

The relationship fixture is intentionally small and verifies known, temporally valid relationships and user isolation. Its perfect score must not be interpreted as evidence of broad graph-retrieval performance.

## How the gates work

The baselines are in `tests/evaluation/quality_gates.py`. For each metric, the gate requires:

`observed metric >= max(0, baseline metric - allowed absolute drop)`

The tolerance is an initial regression allowance, not a statistically derived confidence interval. It was selected to permit modest run-to-run variation while catching material drops. Revisit the tolerance if the dataset, model, dependency versions, or retrieval configuration changes. Do not silently update baselines just to make a failing test pass: inspect the per-query ranking differences first and record why a baseline change is justified.

## Interpretation and known gaps

- The document benchmark has only 15 labelled cases. It is a smoke/regression benchmark, not a robust comparison across query distributions.
- The reranked pipeline currently scores below hybrid RRF on Recall@5 and NDCG@5 in this run. Reranking is not automatically an improvement; inspect the cases before changing it.
- Memory metrics come from eight labelled queries against seeded memory fixtures. Their high scores do not establish real-user performance.
- Relationship metrics come from two deterministic cases. Broader entity and relationship coverage is needed before making quality claims.
- These benchmarks measure retrieval only. They do not measure generated answer faithfulness, citation correctness, extraction quality, latency, or production outcomes.
- Keep user isolation and temporal validity covered by integration tests independently of aggregate ranking metrics.
