# PAIS — Personal Decision & Action Intelligence System

PAIS is a production-oriented personal intelligence system that transforms unstructured personal information into searchable, traceable, and actionable knowledge.

The system is designed around a simple principle:

> **The LLM is a reasoning and generation component, not the source of truth.**

PostgreSQL and the original source documents remain the system of record.

AI-generated information is designed to remain traceable to its source wherever the system derives information from retrieved document evidence.

---

## Current Status

PAIS V1 is under active development.

The project has progressed from document ingestion and retrieval into grounded generation, structured intelligence, actionable domain modeling, and daily intelligence.

### Completed

- Project foundation and application architecture
- PostgreSQL + pgvector database layer
- SQLAlchemy async database access
- Alembic migration workflow
- User isolation at the application/data-access boundaries
- Document ingestion pipeline
- Document API
- Text normalization
- Text chunking
- Local embedding generation
- Vector retrieval
- PostgreSQL lexical retrieval
- Reciprocal Rank Fusion (RRF)
- Hybrid retrieval
- Cross-Encoder reranking implementation
- Retrieval evaluation and benchmarking
- `/api/v1/search` API
- Search API unit and integration tests
- Search user-isolation validation
- Search project-filter validation

### Query and Grounded Generation

- `/api/v1/query` API
- Query context construction
- Hybrid retrieval-backed query workflow
- Grounded LLM answer generation
- Source/chunk citations in query responses
- Configurable retrieval filters and `top_k`
- LLM model and latency metadata in query responses

The query workflow is designed so that retrieved source material is the grounding context for generation rather than allowing the LLM to act as the system of record.

### Structured Intelligence

Structured intelligence extraction is implemented using a provider-independent structured LLM layer and Pydantic schemas.

Current extraction categories include:

- Tasks
- Commitments
- Decisions
- Projects
- People
- Risks
- Follow-ups
- Deadlines

The extraction layer includes:

- Structured LLM response validation
- Source-chunk provenance validation
- Deduplication for supported intelligence categories
- Model metadata
- Generation latency metadata
- Tests for models, extraction, provenance, and deduplication

### Actionable Domain Modeling

Persisted domain slices currently include:

- Tasks
- Commitments
- Decisions
- Projects
- People
- Risks

These domain objects maintain provenance back to source chunks where applicable.

The current implementation deliberately keeps domain modeling separate from the LLM extraction layer so that generated candidates can be validated and persisted through application services.

### Daily Intelligence

Daily Intelligence is complete.

The current workflow contains:

1. Daily snapshot construction
2. Open-task and open-commitment selection
3. Recent decision/change detection
4. Deterministic priority calculation
5. Structured context construction
6. Project/person/risk context enrichment
7. Structured LLM generation
8. Daily intelligence API response

The Daily workflow includes an explainable deterministic priority engine. The LLM does not calculate or override priority; it generates the human-readable intelligence brief from the prepared context.

The API endpoint is:

```text
GET /api/v1/daily
```

Daily API validation includes timezone validation and current-user isolation.

---

## Current API Surface

| Endpoint | Purpose | Status |
|---|---|---|
| `GET /api/v1/health` | Application health | Complete |
| `GET /api/v1/ready` | Readiness check | Complete |
| `POST /api/v1/documents` | Document ingestion | Complete |
| `GET /api/v1/search` | Hybrid retrieval | Complete |
| `POST /api/v1/query` | Grounded LLM answers | Complete |
| `GET /api/v1/daily` | Daily intelligence | Complete |

---

## Current Retrieval Strategy

The current default retrieval pipeline is:

```text
Vector Retrieval
       +
Lexical Retrieval
       ↓
Reciprocal Rank Fusion
       ↓
Hybrid Retrieval
```

Cross-Encoder reranking is implemented as an experimental optional stage.

The current retrieval evaluation showed that the present reranking configuration does not improve the Hybrid + RRF baseline, so reranking is **not currently the default production retrieval strategy**.

---

## Source Traceability

PAIS treats source traceability as a core architectural property.

For source-derived intelligence, the system preserves references to the document chunks from which information was obtained.

The current provenance model covers:

- Retrieval results → document/chunk provenance
- Structured intelligence → source chunk IDs
- Tasks → task source chunks
- Commitments → commitment source chunks
- Decisions → decision source chunks
- Projects → project source chunks
- People → person source chunks
- Risks → risk source chunks

The LLM is therefore used to interpret, structure, or generate information while PostgreSQL and source documents remain authoritative.

---

## LLM Architecture

PAIS currently uses a provider-independent LLM abstraction.

The current implementation includes:

```text
Application Service
       ↓
LLM Provider Interface
       ↓
Configured Provider
       ↓
Ollama
       ↓
Configured Model
```

Current default configuration includes:

- Provider: `ollama`
- Model: `llama3.2:3b`
- Temperature: `0.0`
- Configurable request timeout

The normalized LLM response currently exposes:

- Generated content
- Model name
- Prompt token usage, when provided by the provider
- Completion token usage, when provided by the provider
- Total token usage
- Latency
- Finish reason

Structured generation is handled through a dedicated `StructuredLLMProvider`, which validates provider output against Pydantic schemas.

This existing metadata and abstraction layer will form the foundation for the upcoming **Observability / Model Runs** milestone.

---

## Test Status

The latest full host-environment regression run after completing Daily Intelligence is:

```text
409 passed, 1 skipped, 1 warning
```

The skipped test is the database integration health test, which is intentionally disabled unless:

```text
RUN_INTEGRATION_TESTS=1
```

is enabled.

The current test suite contains coverage across:

- API endpoints
- Retrieval
- Reranking
- Evaluation
- Ingestion
- Embeddings
- Query
- Structured intelligence
- Tasks
- Commitments
- Decisions
- Projects
- People
- Risks
- Daily intelligence
- LLM providers and structured generation

Earlier in V1 development, the retrieval/search milestone was also validated in the Docker API environment.

---

## V1 Roadmap

### Completed

1. ~~Project foundation and application architecture~~
2. ~~PostgreSQL + pgvector database layer~~
3. ~~Document ingestion and document API~~
4. ~~Chunking and embeddings~~
5. ~~Vector + lexical retrieval~~
6. ~~RRF hybrid retrieval~~
7. ~~Cross-Encoder reranking implementation and evaluation~~
8. ~~`/search` API~~
9. ~~Query API and grounded LLM answers with citations~~
10. ~~Structured intelligence extraction~~
11. ~~Tasks and commitments~~
12. ~~Decisions and provenance~~
13. ~~Projects, people and risks~~
14. ~~Daily intelligence~~

### Next

15. **Observability and model-run tracking**

### Remaining

16. **Security and hardening**
17. **Production-readiness cleanup**
18. **End-to-end testing**
19. **V1 documentation and demo**

---

## Observability / Model Runs — Next Milestone

The next milestone is to make LLM execution observable and persist model-run information without turning observability into a second source of truth.

The current codebase already provides a useful foundation:

- Provider-independent `LLMProvider`
- Normalized `LLMResponse`
- Model identification
- Token usage when available
- Latency measurement
- Finish reason
- Structured generation through `StructuredLLMProvider`
- Multiple application-level LLM consumers such as Query, Structured Intelligence, and Daily Intelligence

The upcoming milestone will therefore build on the existing abstractions rather than introducing a separate LLM architecture.

The exact model-run schema, persistence boundary, correlation with application operations, failure handling, and API/operational visibility will be designed from the current implementation before code changes are made.

No observability milestone is considered complete until the implementation, tests, and full regression validation are complete.

---

## Architectural Principles

### 1. LLM is not the source of truth

LLMs interpret and generate information.

PostgreSQL and original source documents remain authoritative.

### 2. Retrieval before generation

When generation depends on personal source material, relevant information should be retrieved and supplied as explicit context.

### 3. Provenance is first-class

Source-derived information should remain traceable to the source chunks that support it.

### 4. Deterministic logic stays outside the LLM

Rules such as priority calculation, filtering, ownership validation, provenance validation, and deduplication should be handled by application code where practical.

### 5. User isolation is enforced explicitly

User-owned data must be filtered by the authenticated user at the application/data-access boundary.

### 6. Services own business behavior

Application services coordinate domain operations while database transactions remain controlled by the surrounding application layer.

### 7. Provider independence

LLM-dependent application code should depend on the provider abstraction rather than directly coupling business logic to a specific LLM vendor or runtime.

### 8. Tests are part of the milestone

A feature is not considered complete merely because its implementation exists.

The milestone is complete after:

```text
Implementation
      ↓
Unit / Integration Tests
      ↓
Regression Validation
      ↓
Checkpoint
```

---

## Development Status

PAIS V1 is currently at:

```text
Retrieval
    ↓
Grounded Query
    ↓
Structured Intelligence
    ↓
Actionable Domain Modeling
    ↓
Daily Intelligence
    ↓
>>> Observability / Model Runs
    ↓
Security / Hardening
    ↓
Production Cleanup
    ↓
End-to-End Testing
    ↓
Documentation / Demo
```

The current implementation should be treated as the source of truth for future milestone design. The roadmap describes the intended progression, but implementation decisions may evolve when the existing architecture or production requirements provide a concrete reason to change them.
