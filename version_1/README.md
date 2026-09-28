# PAIS — Personal Decision & Action Intelligence System

PAIS is a production-oriented personal intelligence system that transforms unstructured personal information into searchable, traceable, and actionable knowledge.

The system is designed around a simple principle:

> The LLM is a reasoning and generation component, not the source of truth.

PostgreSQL and the original source documents remain the system of record.

AI-generated information is designed to remain traceable to its source.

## Current Status

PAIS V1 is under active development.

### Completed

- Project foundation and application architecture
- PostgreSQL + pgvector database layer
- Alembic migrations
- Document ingestion pipeline
- Document API
- Text normalization and chunking
- Local embedding generation
- Vector retrieval
- PostgreSQL lexical retrieval
- Reciprocal Rank Fusion
- Hybrid retrieval
- Cross-Encoder reranking implementation
- Retrieval evaluation and benchmarking
- `/search` API
- Search API unit and integration tests
- Search user-isolation and project-filter validation
- Full test-suite validation in the host environment
- Full test-suite validation inside Docker

### Test Status

The current test suite has been validated in both the local host environment and the Docker API environment.

| Environment | Result |
|---|---:|
| Host / local Python environment | **178 passed, 1 skipped** |
| Docker API container | **178 passed, 1 skipped** |

The skipped test is the database integration health test, which is intentionally disabled unless `RUN_INTEGRATION_TESTS=1` is set.

The current suite also includes integration coverage for the `/search` API, including:

- Returning real search results
- User-level result isolation
- Project-level filtering

## Current Retrieval Strategy

The current default retrieval pipeline is:

Vector Retrieval

+

Lexical Retrieval

↓

Reciprocal Rank Fusion

↓

Hybrid Retrieval

Cross-Encoder reranking is currently implemented as an experimental optional stage. The current evaluation dataset shows that the present reranking configuration does not improve the Hybrid + RRF baseline, so it is not currently treated as the default production retrieval strategy.

## Search API

The `/search` milestone is currently complete.

The search API builds on the retrieval pipeline and provides:

- Hybrid vector + lexical retrieval
- RRF-based result fusion
- User isolation
- Project filtering
- Optional document and source-type filtering
- Configurable `top_k`
- Retrieval results with document and chunk provenance

The retrieval layer and `/search` API have been validated through unit tests, integration tests, and retrieval evaluation benchmarks.

## V1 Roadmap

1. ~~Query / Search API~~ — `/search` completed
2. Query API and grounded LLM answers with citations
3. Structured intelligence extraction
4. Tasks and commitments
5. Decisions and provenance
6. Projects, people, risks and follow-ups
7. Daily intelligence
8. Observability and model-run tracking
9. Security and hardening
10. Production-readiness cleanup
11. End-to-end testing
12. V1 documentation and demo
