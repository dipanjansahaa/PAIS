# PAIS V1 — Technical Architecture

**Product:** Personal Decision & Action Intelligence System
**Version:** V1.0
**Architecture style:** Modular monolith + asynchronous background workers
**Primary API:** FastAPI
**Primary database:** PostgreSQL
**Vector search:** pgvector
**Deployment:** Docker Compose initially
**Primary interface:** REST API + OpenAPI/Swagger
**AI architecture:** Provider-agnostic LLM and embedding abstractions

---

# 1. Architecture Goals

The architecture must satisfy five requirements:

1. **Modularity** — individual components can evolve independently.
2. **Provider independence** — changing the LLM or embedding provider should not require rewriting business logic.
3. **Traceability** — every AI-generated fact/action must be traceable to source information.
4. **Evaluability** — retrieval, extraction, and generation must be independently measurable.
5. **Production discipline** — errors, latency, costs, and model behavior must be observable.

The architecture deliberately avoids premature complexity.

---

# 2. High-Level Architecture

```text
                         ┌──────────────────┐
                         │      Client      │
                         │ CLI / Swagger /  │
                         │ Future Frontend  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     FastAPI      │
                         │    API Layer     │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              Document       Query Service   Task Service
              Service
                    │             │
                    ▼             ▼
              Ingestion       Retrieval
                 Pipeline       Pipeline
                    │             │
                    ▼             ▼
              Intelligence   Reranker
                Extraction       │
                    │             ▼
                    │        Context Builder
                    │             │
                    │             ▼
                    │          LLM Layer
                    │             │
                    └──────┬──────┘
                           │
                           ▼
                    Persistence Layer
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
            PostgreSQL            pgvector
                 │
                 ▼
          Provenance / State
```

---

# 3. Deployment Architecture

V1 will run as a small number of containers.

```text
┌───────────────────────────────────────────────┐
│                  Docker Host                  │
│                                               │
│  ┌───────────────┐                            │
│  │    FastAPI    │                            │
│  │   Application │                            │
│  └───────┬───────┘                            │
│          │                                    │
│          ├───────────────┐                    │
│          ▼               ▼                    │
│  ┌───────────────┐ ┌───────────────┐          │
│  │  PostgreSQL   │ │ Worker        │          │
│  │   + pgvector  │ │ / Background  │          │
│  └───────────────┘ │ Jobs          │          │
│                    └───────────────┘          │
│                                               │
└───────────────────────────────────────────────┘
                         │
                         ▼
                External AI Provider
```

Initially:

* FastAPI
* Worker
* PostgreSQL + pgvector

are enough.

Redis, Kafka, Kubernetes, separate vector databases, etc. are **not required for V1**.

---

# 4. Logical Component Architecture

The application will be divided into these modules:

```text
app/
│
├── api/
│
├── core/
│
├── ingestion/
│
├── retrieval/
│
├── intelligence/
│
├── tasks/
│
├── decisions/
│
├── commitments/
│
├── projects/
│
├── memory/
│
├── llm/
│
├── embeddings/
│
├── reranking/
│
├── database/
│
├── evaluation/
│
├── observability/
│
└── workers/
```

The important distinction is:

> **API modules expose capabilities. Domain modules own business logic. Infrastructure modules implement external technology.**

---

# 5. Component Responsibilities

## 5.1 API Layer

### Responsibility

Expose the system through REST endpoints.

### Does

* Request validation
* Authentication boundary
* Serialization
* HTTP error handling
* Request IDs
* API versioning

### Does NOT

* Perform vector search directly
* Call the LLM directly
* contain business logic

Example:

```text
POST /api/v1/query
        ↓
QueryRequest validation
        ↓
QueryService
```

---

# 5.2 Document Service

Responsible for document lifecycle.

```text
Upload
Retrieve
List
Delete
```

It delegates actual processing to the ingestion pipeline.

```text
DocumentService
       │
       ▼
IngestionService
```

---

# 5.3 Ingestion Pipeline

The ingestion pipeline converts raw information into searchable knowledge.

```text
Raw File
   ↓
Loader
   ↓
Parser
   ↓
Normalizer
   ↓
Chunker
   ↓
Metadata Enricher
   ↓
Embedding Generator
   ↓
Vector Repository
```

Each stage has one responsibility.

### Loader

Understands file types.

```text
PDF
DOCX
TXT
Markdown
```

### Parser

Extracts text.

### Normalizer

Handles:

* whitespace
* encoding
* malformed text
* repeated artifacts

### Chunker

Splits text into retrieval units.

### Metadata Enricher

Adds:

```text
document_id
chunk_id
source_type
project
timestamps
```

### Embedding Generator

Converts text into vectors.

### Vector Repository

Stores embeddings and searchable metadata.

---

# 5.4 Retrieval Layer

Retrieval is deliberately separated from generation.

```text
Query
 ↓
Query Analyzer
 ↓
┌─────────────────┐
│                 │
▼                 ▼
Dense Search    Lexical Search
│                 │
└────────┬────────┘
         ▼
      Fusion
         ▼
     Reranker
         ▼
   RetrievalResult
```

This allows us to evaluate retrieval independently.

---

# 5.5 Query Analyzer

The query analyzer determines what kind of query the user submitted.

Example:

```text
"What did I decide about PostgreSQL?"
```

could become:

```json
{
  "intent": "decision_search",
  "entities": ["PostgreSQL"],
  "filters": {},
  "requires_generation": true
}
```

Not every query requires the same retrieval strategy.

---

# 5.6 Dense Retriever

Uses embeddings to find semantically similar chunks.

Interface:

```python
class DenseRetriever(Protocol):

    def search(
        self,
        query: str,
        top_k: int = 20
    ) -> list[RetrievalResult]:
        ...
```

---

# 5.7 Lexical Retriever

Handles exact terminology and keyword-sensitive searches.

Interface:

```python
class LexicalRetriever(Protocol):

    def search(
        self,
        query: str,
        top_k: int = 20
    ) -> list[RetrievalResult]:
        ...
```

---

# 5.8 Retrieval Fusion

Combines results from different retrievers.

For example:

```text
Dense:
A, B, C, D

Lexical:
B, D, E, F

Fusion:
B, D, A, E, C, F
```

The exact fusion algorithm will be an implementation decision that we evaluate rather than assume upfront.

---

# 5.9 Reranker

The reranker receives candidate chunks and scores their relevance against the query.

```text
Top 20 candidates
       ↓
    Reranker
       ↓
Top 5 relevant chunks
```

This reduces the amount of irrelevant context sent to the LLM.

---

# 5.10 Context Builder

This component is extremely important.

It converts retrieval results into model-ready context.

Responsibilities:

* deduplication
* ordering
* source grouping
* token budgeting
* context truncation
* citation mapping

Output:

```text
Context
├── Source A
│   ├── Chunk 1
│   └── Chunk 4
│
├── Source B
│   └── Chunk 7
│
└── Source C
    └── Chunk 2
```

The context builder should not contain LLM reasoning.

---

# 5.11 Answer Generator

Responsible for producing the final response from:

```text
User Query
+
Retrieved Context
+
System Instructions
```

Output:

```text
Answer
Sources
Metadata
```

---

# 5.12 Intelligence Extraction

This is one of the defining components of PAIS.

It processes information and extracts structured entities.

```text
Document
   ↓
Relevant Chunks
   ↓
Extraction Prompt
   ↓
LLM
   ↓
Structured Output
   ↓
Schema Validation
   ↓
Deduplication
   ↓
Persistence
```

Entities:

```text
Task
Commitment
Decision
Deadline
Project
Person
Risk
Follow-up
```

---

# 5.13 Task Service

Owns task business logic.

It should know:

* task lifecycle
* statuses
* priority
* deadlines
* provenance
* relationship to commitments

It should NOT know how embeddings are generated.

---

# 5.14 Decision Service

Owns decision lifecycle.

It manages:

```text
Decision
Alternative
Context
Project
Date
Source
Status
```

---

# 5.15 Commitment Service

Owns commitments extracted from information.

Example:

```text
"I'll review the deployment tomorrow."

        ↓

Commitment
├── action
├── owner
├── deadline
├── status
└── source
```

---

# 5.16 Provenance Service

Every important AI-generated object should have a source chain.

```text
Task
 ↓
Commitment
 ↓
Chunk
 ↓
Document
```

The provenance service manages these relationships.

This should be treated as a first-class capability rather than scattered foreign keys throughout arbitrary code.

---

# 5.17 Memory Layer

V1 memory is intentionally simple.

We distinguish between:

### Knowledge

Information extracted from sources.

### User state

Current state such as:

```text
open tasks
preferences
projects
decisions
commitments
```

### Conversation state

Short-term context required for a conversation.

We should **not** treat all three as the same type of "memory."

---

# 6. Model / Provider Abstractions

This is a critical architectural decision.

Business logic should never contain code like:

```python
ChatOpenAI(...)
```

or:

```python
ChatOllama(...)
```

throughout the application.

Instead:

```text
Business Logic
      │
      ▼
LLM Interface
      │
      ├── OpenAI Adapter
      ├── Ollama Adapter
      └── Other Adapter
```

---

# 7. LLM Abstraction

Conceptual interface:

```python
class LLMProvider(Protocol):

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        response_schema: type | None = None,
    ) -> LLMResponse:
        ...
```

The application interacts with:

```text
LLMProvider
```

rather than a specific vendor.

---

# 8. LLM Response Model

We standardize responses.

```python
class LLMResponse:
    content: str
    model: str
    usage: TokenUsage | None
    latency_ms: float
    finish_reason: str | None
```

This gives us provider-independent observability.

---

# 9. Structured Generation

Extraction requires structured output.

Conceptually:

```python
class StructuredLLMProvider:

    async def generate_structured(
        self,
        messages,
        schema,
    ) -> StructuredResult:
        ...
```

Pipeline:

```text
LLM
 ↓
Raw response
 ↓
Schema parser
 ↓
Validation
 ↓
Business object
```

Invalid output must fail explicitly.

---

# 10. Embedding Abstraction

```python
class EmbeddingProvider(Protocol):

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...

    async def embed_query(
        self,
        query: str,
    ) -> list[float]:
        ...
```

Possible adapters:

```text
SentenceTransformers
OpenAI Embeddings
Ollama embeddings
Other provider
```

The rest of the application doesn't care which one is active.

---

# 11. Reranker Abstraction

```python
class Reranker(Protocol):

    async def rerank(
        self,
        query: str,
        documents: list[DocumentChunk],
        top_k: int,
    ) -> list[RankedDocument]:
        ...
```

Possible implementation:

```text
Cross Encoder
LLM-based reranker
External reranking API
```

Again, provider-independent.

---

# 12. Repository Abstractions

Business logic should not directly depend on SQLAlchemy queries.

For example:

```python
class TaskRepository(Protocol):

    async def create(self, task: Task) -> Task:
        ...

    async def get(self, task_id: UUID) -> Task | None:
        ...

    async def update(self, task: Task) -> Task:
        ...
```

Implementation:

```text
TaskRepository
      │
      ▼
PostgresTaskRepository
```

The same pattern applies to:

```text
DocumentRepository
ChunkRepository
TaskRepository
DecisionRepository
CommitmentRepository
ProjectRepository
```

---

# 13. Complete Query Request Flow

Consider:

> "What commitments do I have this week?"

The request flow should be:

```text
Client
  │
  ▼
POST /api/v1/query
  │
  ▼
FastAPI
  │
  ▼
QueryService
  │
  ▼
Query Analyzer
  │
  ├── intent = commitment_search
  ├── date range = current week
  └── entity filters
  │
  ▼
Retrieval Service
  │
  ├── Structured DB query
  │
  └── Knowledge retrieval if necessary
  │
  ▼
Candidate Results
  │
  ▼
Reranker
  │
  ▼
Context Builder
  │
  ▼
LLM Provider
  │
  ▼
Answer + Sources
  │
  ▼
API Response
```

Important:

**We don't automatically use RAG for everything.**

If the question is:

> "What open tasks are due tomorrow?"

we should query PostgreSQL directly.

Using embeddings for that would be architecturally stupid.

---

# 14. Document Ingestion Flow

```text
POST /documents
       │
       ▼
Validate File
       │
       ▼
Create Document Record
       │
       ▼
Background Job
       │
       ▼
Loader
       │
       ▼
Parser
       │
       ▼
Normalizer
       │
       ▼
Chunker
       │
       ▼
Metadata Enrichment
       │
       ▼
Embedding Provider
       │
       ▼
Store Chunks + Vectors
       │
       ▼
Intelligence Extraction
       │
       ├── Commitments
       ├── Decisions
       ├── Tasks
       ├── Projects
       └── Other entities
       │
       ▼
Persist Structured Data
       │
       ▼
Mark Document READY
```

The upload request itself should **not block while the entire pipeline runs**.

---

# 15. Intelligence Extraction Flow

```text
Document
   │
   ▼
Chunk Selection
   │
   ▼
Extraction Prompt
   │
   ▼
LLM Provider
   │
   ▼
Structured JSON
   │
   ▼
Pydantic Validation
   │
   ├── Invalid → retry / failure
   │
   ▼
Deduplication
   │
   ▼
Entity Persistence
   │
   ▼
Provenance Links
```

---

# 16. Daily Intelligence Flow

Request:

```text
GET /api/v1/intelligence/daily
```

Flow:

```text
                 Daily Intelligence
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
      Open Tasks     Commitments     Deadlines
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Recent Changes
                         │
                         ▼
                  Priority Engine
                         │
                         ▼
                  Context Builder
                         │
                         ▼
                    LLM Provider
                         │
                         ▼
                  Daily Intelligence
```

The priority engine should first produce structured facts.

The LLM should **explain and summarize**, rather than inventing priorities from nothing.

---

# 17. Task Creation Flow

Example:

```text
Commitment detected
       │
       ▼
"Review API by Friday"
       │
       ▼
Create proposed Task
       │
       ▼
User confirmation
       │
       ├──── Reject
       │
       └──── Confirm
              │
              ▼
         Persist Task
              │
              ▼
         Link Provenance
```

This keeps the user in control.

---

# 18. Search vs RAG vs Structured Query

This distinction will be central to the architecture.

| User request                           | Primary mechanism             |
| -------------------------------------- | ----------------------------- |
| "What tasks are overdue?"              | SQL                           |
| "What commitments do I have?"          | SQL                           |
| "What did I discuss about deployment?" | Hybrid retrieval + RAG        |
| "What decision did I make about DB?"   | Structured DB + retrieval     |
| "Why does this task exist?"            | Provenance + source retrieval |
| "Summarize Project X"                  | Structured DB + RAG           |
| "What changed recently?"               | Temporal DB query + retrieval |
| "What should I focus on?"              | Structured state + reasoning  |

This prevents us from building a giant RAG hammer and treating every problem like a nail.

---

# 19. Agent vs Workflow Boundary

V1 should primarily use **deterministic workflows**.

Example:

```text
Daily intelligence
    ↓
Fetch tasks
    ↓
Fetch commitments
    ↓
Fetch deadlines
    ↓
Fetch changes
    ↓
Build context
    ↓
Generate summary
```

No agent is necessary.

An agent becomes appropriate when the system needs to dynamically decide which tools to invoke.

For example:

```text
User:
"Find everything related to Project X and tell me
whether there are unresolved commitments."

Agent
 ├── Search projects
 ├── Search documents
 ├── Search commitments
 ├── Search decisions
 └── Synthesize
```

Even then, we should benchmark whether a deterministic workflow is simpler.

---

# 20. MCP Boundary

MCP is **not part of the core V1 domain model**.

It belongs at the tool/integration boundary.

```text
PAIS
 │
 ▼
Tool Interface
 │
 ├── Local Tool
 ├── REST Tool
 └── MCP Tool
```

This means our business logic can say:

```python
calendar.get_events(...)
```

without caring whether the implementation eventually uses:

```text
REST API
MCP
local database
```

This prevents MCP from infecting the entire architecture.

---

# 21. Background Processing

Document processing should happen asynchronously.

Potential jobs:

```text
document.ingest
document.embed
document.extract_entities
document.reindex
evaluation.run
```

Initial architecture:

```text
FastAPI
   │
   ▼
Job Queue
   │
   ▼
Worker
```

The exact queue technology can initially remain simple.

We should only introduce Redis/Celery/RQ/etc. once the asynchronous execution model requires it.

---

# 22. Error Boundaries

Failures should be isolated.

```text
File Parser Failure
        ↓
Document = PROCESSING_FAILED
```

not:

```text
Entire API crashes
```

Likewise:

```text
Embedding Failure
        ↓
Retry
        ↓
Failure state
        ↓
Observability event
```

LLM failure:

```text
LLM timeout
   ↓
Retry policy
   ↓
Fallback if configured
   ↓
Controlled error
```

---

# 23. Observability Architecture

Every major request receives:

```text
request_id
trace_id
```

Example:

```text
request_id = abc123

API
 │
 ├── QueryService
 │
 ├── Retrieval
 │    ├── Dense search
 │    ├── BM25
 │    └── Reranker
 │
 ├── LLM
 │
 └── Database
```

We record:

```text
latency
token usage
model
retrieval count
reranking count
errors
```

This allows us to answer:

> "Why did this query take 6 seconds?"

instead of guessing.

---

# 24. Evaluation Boundary

Evaluation should not be embedded directly into production logic.

```text
Production System
        │
        ▼
Evaluation Dataset
        │
        ▼
Evaluation Runner
        │
        ├── Retrieval metrics
        ├── Extraction metrics
        ├── Generation metrics
        └── Latency/cost
```

This gives us reproducible experiments.

---

# 25. Deployment Boundaries

## Local development

```text
Docker Compose

├── api
├── worker
└── postgres + pgvector
```

External:

```text
LLM
Embedding
Reranker
```

depending on configuration.

---

## Future staging

```text
Load Balancer
      │
      ▼
FastAPI instances
      │
      ├─────────────┐
      ▼             ▼
   Workers      PostgreSQL
                    │
                    ▼
                 pgvector
```

---

## Future production

Only if justified:

```text
                    Load Balancer
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
          API Instance        API Instance
               │                   │
               └─────────┬─────────┘
                         ▼
                    Queue / Broker
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
            Worker 1            Worker 2
               │                   │
               └─────────┬─────────┘
                         ▼
                    PostgreSQL
```

We don't need Kubernetes for V1.

---

# 26. Configuration Architecture

Configuration should be centralized.

```text
Environment
     │
     ▼
Settings
     │
     ├── LLM provider
     ├── model
     ├── embedding provider
     ├── embedding model
     ├── database URL
     ├── retrieval parameters
     ├── reranker
     └── logging
```

Example:

```text
LLM_PROVIDER=ollama
LLM_MODEL=...
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=...
DATABASE_URL=...
```

The application should never contain API keys or provider credentials.

---

# 27. Repository Structure

The architecture translates into:

```text
pais/
│
├── app/
│   │
│   ├── api/
│   │   ├── v1/
│   │   │   ├── documents.py
│   │   │   ├── query.py
│   │   │   ├── tasks.py
│   │   │   ├── commitments.py
│   │   │   ├── decisions.py
│   │   │   └── intelligence.py
│   │   └── dependencies.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── exceptions.py
│   │   └── security.py
│   │
│   ├── domain/
│   │   ├── documents/
│   │   ├── tasks/
│   │   ├── commitments/
│   │   ├── decisions/
│   │   ├── projects/
│   │   └── intelligence/
│   │
│   ├── ingestion/
│   │   ├── loaders/
│   │   ├── parsers/
│   │   ├── chunking/
│   │   └── pipeline.py
│   │
│   ├── retrieval/
│   │   ├── dense.py
│   │   ├── lexical.py
│   │   ├── fusion.py
│   │   ├── reranking.py
│   │   └── service.py
│   │
│   ├── llm/
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── providers/
│   │   └── schemas.py
│   │
│   ├── embeddings/
│   │   ├── base.py
│   │   └── providers/
│   │
│   ├── intelligence/
│   │   ├── extraction.py
│   │   ├── prompts/
│   │   └── schemas.py
│   │
│   ├── database/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── session.py
│   │   └── migrations/
│   │
│   ├── workers/
│   │   ├── jobs/
│   │   └── worker.py
│   │
│   ├── evaluation/
│   │   ├── datasets/
│   │   ├── metrics/
│   │   └── runner.py
│   │
│   └── observability/
│       ├── tracing.py
│       └── metrics.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── retrieval/
│   └── evaluation/
│
├── scripts/
│
├── docker/
│
├── data/
│
├── .env.example
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

This is the **target architecture**, not a command to create every directory immediately.

---

# 28. Dependency Direction

One rule should govern the entire codebase:

```text
API
 ↓
Application / Services
 ↓
Domain
 ↓
Interfaces
 ↓
Infrastructure
```

Not:

```text
API
 ↓
SQLAlchemy
 ↓
LLM
 ↓
Vector DB
 ↓
random utility
```

Infrastructure should implement interfaces.

For example:

```text
                    Domain
                      │
                      ▼
             EmbeddingProvider
                      ▲
                      │
          ┌───────────┴───────────┐
          │                       │
 SentenceTransformer          Ollama
```

This makes changing models an engineering decision rather than a rewrite.

---

# 29. The Critical Data Flow

The entire V1 can ultimately be understood as two major pipelines.

## Knowledge pipeline

```text
             RAW INFORMATION
                    │
                    ▼
                INGESTION
                    │
                    ▼
                  CHUNKS
                    │
             ┌──────┴──────┐
             ▼             ▼
        EMBEDDINGS     METADATA
             │             │
             └──────┬──────┘
                    ▼
             SEARCHABLE DATA
                    │
                    ▼
             INTELLIGENCE
             EXTRACTION
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       Tasks    Decisions  Commitments
```

## Question pipeline

```text
USER QUESTION
      │
      ▼
QUERY ANALYSIS
      │
      ├───────────────┐
      ▼               ▼
STRUCTURED        KNOWLEDGE
QUERY             RETRIEVAL
      │               │
      │          Dense + Lexical
      │               │
      │            Reranker
      │               │
      └───────┬───────┘
              ▼
       CONTEXT BUILDER
              │
              ▼
          LLM PROVIDER
              │
              ▼
       ANSWER + SOURCES
```

That is the heart of PAIS.

---

# 30. What We Will NOT Do Architecturally

We will explicitly avoid these mistakes:

### ❌ Everything goes into a vector database

Structured state belongs in PostgreSQL.

### ❌ LLM controls the entire application

Business rules remain deterministic where possible.

### ❌ Agent everywhere

Workflows are preferred when the path is known.

### ❌ LangChain everywhere

Frameworks are implementation details, not architecture.

### ❌ MCP everywhere

MCP belongs at the integration/tool boundary.

### ❌ Microservices from day one

Modular monolith first.

### ❌ Fine-tuning because it's on the resume

Only if evaluation demonstrates a real problem.

### ❌ Arbitrary "confidence scores"

We'll measure actual accuracy instead.

### ❌ AI-generated data without provenance

Every important generated entity should have a source chain.

---

# 31. Architectural Decision Records

As we build, important decisions should be documented as ADRs.

Examples:

```text
ADR-001 — Modular monolith instead of microservices
ADR-002 — PostgreSQL + pgvector for V1
ADR-003 — Provider abstraction for LLMs
ADR-004 — Hybrid retrieval
ADR-005 — Reranking strategy
ADR-006 — Workflow before autonomous agents
ADR-007 — Provenance as a first-class concept
ADR-008 — Async document processing
```

This will make the GitHub repository much stronger because it demonstrates **engineering reasoning**, not just code.

---

# 32. Initial Implementation Sequence

We should build in this order:

```text
Phase 1
Project skeleton
        ↓
Configuration
        ↓
Database
        ↓
Document model
        ↓
Document ingestion
        ↓
Chunking
        ↓
Embeddings
        ↓
pgvector

Phase 2
Dense retrieval
        ↓
Lexical retrieval
        ↓
Fusion
        ↓
Reranking
        ↓
Search API

Phase 3
LLM abstraction
        ↓
Context builder
        ↓
Grounded QA
        ↓
Source attribution

Phase 4
Structured extraction
        ↓
Commitments
        ↓
Decisions
        ↓
Tasks
        ↓
Provenance

Phase 5
Daily intelligence
        ↓
Evaluation
        ↓
Observability
        ↓
Testing

Phase 6
Docker
        ↓
Production hardening
        ↓
Deployment

Phase 7
MCP / external integrations
```

This order is deliberate.

We establish the **knowledge and retrieval foundation** before introducing agentic behavior.

---

# 33. Final Architecture Principle

The most important architectural principle for PAIS V1 is:

```text
                    ┌─────────────────────┐
                    │       LLM           │
                    │                     │
                    │ Reason / Generate   │
                    └──────────┬──────────┘
                               │
                     NOT THE SOURCE OF TRUTH
                               │
                               ▼
              ┌────────────────────────────────┐
              │       Application State        │
              │                                │
              │ PostgreSQL + Source Documents  │
              └────────────────────────────────┘
```

The LLM is a **reasoning and generation component**.

It is not the database.

It is not the task manager.

It is not the source of truth.

It is not allowed to silently invent state.

The source of truth is the persisted application state and the original source information.

That single distinction will prevent a huge number of architectural problems later.

---

# 34. V1 Architecture in One Diagram

```text
                         USER
                          │
                          ▼
                     ┌─────────┐
                     │ FastAPI │
                     └────┬────┘
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
        Documents       Query        Tasks
             │            │
             ▼            │
        INGESTION         │
             │            │
      ┌──────┴──────┐     │
      ▼             ▼     │
    Chunks      Extraction│
      │             │     │
      ▼             ▼     │
  Embeddings    Structured │
      │          Entities  │
      ▼             │     │
┌───────────┐       │     │
│ pgvector  │       │     │
└─────┬─────┘       │     │
      │             │     │
      ▼             ▼     ▼
   Retrieval    PostgreSQL
      │             │
 ┌────┴────┐        │
 ▼         ▼        │
Dense    Lexical    │
 │         │        │
 └────┬────┘        │
      ▼             │
   Fusion           │
      │             │
      ▼             │
  Reranker          │
      │             │
      └──────┬──────┘
             ▼
       Context Builder
             │
             ▼
        LLM Provider
             │
             ▼
      Answer / Intelligence
             │
             ▼
       Sources + Provenance
             │
             ▼
          Response
```
