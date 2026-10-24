# PAIS V2 — Product Requirements & Technical Architecture

**Product:** Personal Decision & Action Intelligence System
**Version:** V2.0
**Architecture style:** Modular monolith with clearly separated API, application, domain, AI, and persistence responsibilities
**Primary API:** FastAPI
**Primary database:** PostgreSQL + pgvector
**Deployment:** Docker Compose for local development
**Primary interface:** React frontend + REST API + OpenAPI/Swagger
**AI architecture:** Provider abstractions for LLMs, embeddings, and reranking
**Current milestone:** V2.1 — Foundation and V1 Feature Parity

PAIS V2 evolves the completed V1 system rather than replacing it with a smaller or unrelated product. Existing capabilities remain part of the V2 baseline. New capabilities are delivered milestone by milestone, with persistent personal memory introduced in V2.2 and later roadmap items kept explicitly separate from the current implementation.

Implementation status must be reported honestly: implemented, planned, and verified are different states. Architecture descriptions in this document define design intent; the repository and its tests remain the source of truth for what is currently implemented.

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
                Extraction        │
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

V2 currently uses Docker Compose for local development.

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

Redis, Kafka, Kubernetes, separate vector databases, etc. are **not required for the current V2 baseline**.

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

## 5.2 Document Service

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

## 5.3 Ingestion Pipeline

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

## 5.4 Retrieval Layer

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

## 5.5 Query Analyzer

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

## 5.6 Dense Retriever

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

## 5.7 Lexical Retriever

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

## 5.8 Retrieval Fusion

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

## 5.9 Reranker

The reranker receives candidate chunks and scores their relevance against the query.

```text
Top 20 candidates
       ↓
    Reranker
       ↓
Top 5 relevant chunks
```

This reduces the amount of irrelevant context sent to the LLM.

## 5.10 Context Builder

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

## 5.11 Answer Generator

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

## 5.12 Intelligence Extraction

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

## 5.13 Task Service

Owns task business logic.

It should know:

* task lifecycle
* statuses
* priority
* deadlines
* provenance
* relationship to commitments

It should NOT know how embeddings are generated.

## 5.14 Decision Service

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

## 5.15 Commitment Service

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

## 5.16 Provenance Service

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

## 5.17 Memory Layer

The current baseline separates source knowledge, persisted user state, and short-term conversation context. Durable personal memory is planned for V2.2.

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

| User request | Primary mechanism |
| --- | --- |
| "What tasks are overdue?" | SQL |
| "What commitments do I have?" | SQL |
| "What did I discuss about deployment?" | Hybrid retrieval + RAG |
| "What decision did I make about DB?" | Structured DB + retrieval |
| "Why does this task exist?" | Provenance + source retrieval |
| "Summarize Project X" | Structured DB + RAG |
| "What changed recently?" | Temporal DB query + retrieval |
| "What should I focus on?" | Structured state + reasoning |

This prevents us from building a giant RAG hammer and treating every problem like a nail.

---

# 19. Agent vs Workflow Boundary

PAIS should primarily use **deterministic workflows** where the execution path is known.

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

MCP is **not part of the core domain model**; it belongs at the integration/tool boundary.

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

Kubernetes is not required for the current local-development baseline.

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

The PAIS architecture can be understood as two major pipelines. The diagram is conceptual and does not imply that every future V2 capability has already been implemented.

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
ADR-002 — PostgreSQL + pgvector as the persistence and retrieval foundation
ADR-003 — Provider abstraction for LLMs
ADR-004 — Hybrid retrieval
ADR-005 — Reranking strategy
ADR-006 — Workflow before autonomous agents
ADR-007 — Provenance as a first-class concept
ADR-008 — Async document processing
```

This will make the GitHub repository much stronger because it demonstrates **engineering reasoning**, not just code.

---

# 32. V2 Implementation Sequence

PAIS V2 is delivered through the agreed milestone roadmap. Existing V1 capabilities are retained and regression-tested; future milestones must not be described as implemented before their acceptance criteria are met.

```text
V2.1 — Foundation and V1 Feature Parity
        ↓
V2.2 — Persistent Personal Memory
        ↓
V2.3 — Knowledge Graph and Temporal Intelligence
        ↓
V2.4 — Advanced Retrieval and Evidence-Grounded Reasoning
        ↓
V2.5 — Proactive Intelligence Engine
        ↓
V2.6 — Controlled AI Agents and Workflows
        ↓
V2.7 — Evaluation and Continuous Improvement
        ↓
V2.8 — Unified Frontend and User Experience
        ↓
V2.9 — Production Readiness and Release
```

## V2.1 — Foundation and V1 Feature Parity

Establish a stable V2 foundation while preserving the capabilities implemented in V1. This includes application configuration, authentication and user isolation, PostgreSQL/pgvector persistence, database migrations, Docker Compose, document ingestion, hybrid retrieval, query and grounded question answering, structured intelligence, tasks and commitments, daily intelligence, observability, and the existing frontend workflows.

The objective is to ensure that V2 provides a reliable foundation for future development without losing the functionality established in V1. Backend and frontend checks, migration validation, regression testing, and documentation review should establish that the retained capabilities continue to work as expected.

**Exit condition:** A verified V1 baseline and a concrete, repository-specific implementation plan.

## V2.2 — Persistent Personal Memory

Introduce a persistent memory system that allows PAIS to retain useful information about a user's preferences, goals, constraints, and established facts across interactions. Memory records should include appropriate provenance, timestamps, confidence where justified, and mechanisms for handling updates and changing information. Users should be able to inspect, correct, and delete stored memories.

The objective is to move beyond retrieving information from documents toward maintaining a durable, user-controlled representation of relevant personal context. Memory retrieval must preserve source attribution and user isolation.

**Exit condition:** PAIS can maintain and retrieve useful context over time without treating every extracted statement as a permanent fact.

## V2.3 — Knowledge Graph and Temporal Intelligence

Introduce explicit relationships between entities such as projects, people, decisions, tasks, commitments, risks, documents, and personal memories. Build on these relationships to support temporal reasoning, including how information changes over time, how decisions relate to subsequent actions, and how commitments evolve.

The objective is to help PAIS understand not only individual pieces of information but also their relationships and historical context. Temporal conclusions must be supported by stored evidence and clearly defined data semantics.

**Exit condition:** PAIS can answer relationship-based and historical questions across its knowledge.

## V2.4 — Advanced Retrieval and Evidence-Grounded Reasoning

Improve retrieval quality and answer generation by building on the existing hybrid retrieval and reranking foundation. Explore improvements to evidence selection, query understanding, retrieval strategies, reranking, and context construction. Evaluate these changes against repeatable benchmarks to determine whether they produce measurable improvements.

The objective is to make PAIS more effective at finding relevant information and producing answers supported by reliable evidence. Answers should retain source attribution, and improvements should be demonstrated through evaluation rather than assumed from architectural complexity.

**Exit condition:** Complex answers are evidence-grounded, traceable, and measurably evaluated.

## V2.5 — Proactive Intelligence Engine

Extend PAIS from responding to explicit queries toward identifying relevant developments and actionable information proactively. Use persisted information, deadlines, commitments, tasks, project changes, and recent activity to identify upcoming obligations, emerging risks, relevant changes, and potential next actions.

The objective is to help users understand what requires attention without having to manually search for every development. Prioritization should be deterministic where practical, recommendations should be explainable, and notifications or suggestions should be grounded in available evidence.

**Exit condition:** PAIS can surface important developments without requiring the user to ask the exact question first.

## V2.6 — Controlled AI Agents and Workflows

Introduce agentic capabilities for workflows that benefit from dynamic tool selection, multi-step reasoning, or coordinated actions. Build on the existing application services and integrations, with bounded tool access, explicit permissions, traceable execution, and appropriate error handling. Consequential actions should require user confirmation where necessary.

The objective is to enable PAIS to assist with more complex workflows without sacrificing control, security, or transparency. Agents should operate within defined boundaries rather than receiving unrestricted access to application data or external systems.

**Exit condition:** PAIS can execute useful, bounded workflows safely, with traceability and appropriate human approval.

## V2.7 — Evaluation and Continuous Improvement

Establish a systematic evaluation framework covering retrieval, structured extraction, grounded generation, persistent memory, proactive recommendations, agent execution, and end-to-end workflows. Introduce repeatable test datasets, evaluation metrics, regression checks, and model-run tracking where appropriate. Use evaluation results to identify weaknesses and guide subsequent improvements.

The objective is to make quality measurable across the system as its capabilities become more sophisticated. Offline evaluation results, automated test outcomes, and actual production behavior should remain distinct, with regressions identified before changes are accepted.

**Exit condition:** Improvements are measurable and model changes do not silently degrade existing capabilities.

## V2.8 — Unified Frontend and User Experience

Evolve the existing React frontend to support the expanding capabilities of PAIS while preserving established workflows for Intelligence, Daily, Search, Query, and Documents. Introduce interfaces for persistent memory, entity relationships, proactive recommendations, and agent-assisted workflows as their underlying APIs and functionality become available.

The objective is to provide a coherent user experience across the entire application rather than presenting each new capability as an isolated feature. Frontend workflows should reflect implemented backend functionality, preserve user isolation, and communicate the evidence behind important information and recommendations.

**Exit condition:** V2 capabilities are accessible through a coherent, usable frontend.

## V2.9 — Production Readiness and Release

Prepare PAIS V2 for a controlled release by completing security and data-handling reviews, operational documentation, deployment configuration, monitoring, backup and restore procedures, and full regression testing. Validate authentication and authorization boundaries, database migrations, failure handling, configuration management, logging, and recovery procedures. Review performance and resource requirements under representative workloads.

The objective is to establish that the system can be operated and maintained reliably, not merely that it works in a development environment. Production readiness should be claimed only after the defined release criteria have been verified in the intended deployment environment.

**Exit condition:** A reproducible and deployable V2 release with verified V1 feature parity and tested new capabilities.


---

# 33. Final Architecture Principle

The most important architectural principle for PAIS V2 is:

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

# 34. PAIS V2 Architecture in One Diagram

```text
                          USER
                           │
                           ▼
                      ┌─────────┐
                      │ FastAPI │
                      └────┬────┘
                           │
             ┌─────────────┼────────────┐
             │             │            │
             ▼             ▼            ▼
        Documents        Query        Tasks
             │             │
             ▼             │
        INGESTION          │
             │             │
      ┌──────┴──────┐      │
      ▼             ▼      │
    Chunks      Extraction │
      │             │      │
      ▼             ▼      │
  Embeddings    Structured │
      │          Entities  │
      ▼             │      │
┌───────────┐       │      │
│ pgvector  │       │      │
└─────┬─────┘       │      │
      │             │      │
      ▼             ▼      ▼
   Retrieval       PostgreSQL
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

---

# 35. Database Architecture

The current V2 persistence design uses:

```text
PostgreSQL
    │
    ├── Relational application state
    │
    ├── Full-text / lexical search
    │
    └── pgvector
          └── Embeddings
```

The database has three conceptual layers:

```text
┌──────────────────────────────────────┐
│          Source Knowledge            │
│                                      │
│  documents → chunks → embeddings     │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│        Structured Intelligence        │
│                                      │
│ projects / people / decisions /      │
│ commitments / tasks / risks           │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          System / Evaluation         │
│                                      │
│ jobs / evaluations / model metadata   │
└──────────────────────────────────────┘
```

The database is the **source of truth** for structured application state.

The vector store is an index, not the source of truth.

---

# 36. Entity Relationship Overview

```text
                         users
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
         projects        tasks      commitments
             │             │             │
             │             └──────┬──────┘
             │                    │
             │                    ▼
             │               decisions
             │
             ▼
        documents
             │
             ▼
          chunks
             │
             ▼
        embeddings

documents
   │
   ├──────────────► tasks
   ├──────────────► commitments
   ├──────────────► decisions
   ├──────────────► risks
   └──────────────► people

All AI-generated entities retain
document/chunk provenance.
```

---

# 37. Core Tables

The core schema is expected to contain these primary tables, subject to the actual migrations:

```text
users
projects
people
documents
document_chunks
tasks
commitments
decisions
risks
task_sources
commitment_sources
decision_sources
jobs
model_runs
```

We will deliberately avoid creating tables for every conceivable concept.

---

# 38. `users`

Even in local development, the schema includes user identity and ownership so that user-level isolation remains part of the design.

This costs almost nothing and prevents us from having to redesign every table later.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(320) UNIQUE,
    display_name VARCHAR(255),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Why?

Every user-owned object can eventually be scoped by:

```text
user_id
```

This gives us a clean path toward multi-user support without prematurely building multi-tenancy infrastructure.

---

# 39. `projects`

Projects provide an important organizational dimension for retrieval and intelligence.

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    description TEXT,

    status VARCHAR(50) NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Recommended statuses:

```text
active
paused
completed
archived
```

---

# 40. `people`

People mentioned in documents can eventually become useful entities.

```sql
CREATE TABLE people (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    email VARCHAR(320),

    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

We should **not** attempt sophisticated identity resolution before a concrete V2 requirement justifies it.

For example:

```text
"Rahul"
"Rahul Sharma"
"Rahul S."
```

should not automatically be assumed to be the same person unless there is sufficient evidence.

---

# 41. `documents`

This is the root of our knowledge ingestion system.

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,

    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(50) NOT NULL,

    mime_type VARCHAR(255),
    file_name VARCHAR(500),

    content_hash VARCHAR(128) NOT NULL,

    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processing_error TEXT,

    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `source_type`

Examples:

```text
pdf
docx
markdown
text
meeting_transcript
note
```

### `processing_status`

```text
pending
processing
ready
failed
```

---

# 42. Document Deduplication

The combination:

```text
user_id + content_hash
```

should be indexed.

```sql
CREATE UNIQUE INDEX uq_documents_user_content_hash
ON documents(user_id, content_hash);
```

This prevents accidentally ingesting the exact same document multiple times.

---

# 43. `document_chunks`

A document is split into retrieval units.

```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    chunk_index INTEGER NOT NULL,

    text TEXT NOT NULL,

    token_count INTEGER,

    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Constraint:

```sql
CREATE UNIQUE INDEX uq_document_chunk_index
ON document_chunks(document_id, chunk_index);
```

---

# 44. Embeddings

We will use pgvector.

Assuming the chosen embedding model produces `1536`-dimensional vectors:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then:

```sql
ALTER TABLE document_chunks
ADD COLUMN embedding vector(1536);
```

However, there is an important design issue here.

**The vector dimension is model-dependent.**

Therefore, we should not hard-code `1536` until we select the actual embedding model.

The embedding column dimension must match the configured embedding model and any migration must account for that compatibility.

---

# 45. Embedding Metadata

We should store the embedding model used.

```sql
ALTER TABLE document_chunks
ADD COLUMN embedding_model VARCHAR(255);
```

Why?

Suppose later we change:

```text
Embedding Model A
        ↓
Embedding Model B
```

The vector spaces are not necessarily compatible.

We need to know which model generated each vector.

---

# 46. Vector Index

After selecting the embedding model, we can create an ANN index.

For example:

```sql
CREATE INDEX idx_document_chunks_embedding
ON document_chunks
USING hnsw (embedding vector_cosine_ops);
```

We will benchmark the index configuration rather than blindly assume HNSW is optimal.

---

# 47. Lexical Search

We should also support PostgreSQL full-text search.

Rather than storing another duplicated text field, we can derive a search vector.

Conceptually:

```sql
ALTER TABLE document_chunks
ADD COLUMN search_vector tsvector;
```

Then index it:

```sql
CREATE INDEX idx_document_chunks_search_vector
ON document_chunks
USING GIN(search_vector);
```

The ingestion pipeline will maintain it.

This gives us:

```text
Dense search
+
Lexical search
```

inside the same database.

---

# 48. `tasks`

Tasks represent actionable work.

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY,

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    project_id UUID
        REFERENCES projects(id)
        ON DELETE SET NULL,

    title VARCHAR(500) NOT NULL,
    description TEXT,

    status VARCHAR(50) NOT NULL DEFAULT 'open',
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',

    due_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ
);
```

Recommended status:

```text
open
in_progress
completed
cancelled
```

Priority:

```text
low
medium
high
```

---

# 49. Task Provenance

A task can originate from:

* a commitment
* a document
* a specific chunk
* a user directly creating it

Rather than stuffing all of this into unrelated columns, provenance should be represented explicitly where required by the domain model.

```sql
CREATE TABLE task_sources (
    task_id UUID NOT NULL
        REFERENCES tasks(id)
        ON DELETE CASCADE,

    document_id UUID
        REFERENCES documents(id)
        ON DELETE SET NULL,

    chunk_id UUID
        REFERENCES document_chunks(id)
        ON DELETE SET NULL,

    source_type VARCHAR(50) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (task_id, document_id, chunk_id)
);
```

`source_type` could be:

```text
direct
commitment
document
ai_extraction
```

This gives us traceability without coupling the task table to one particular origin.

---

# 50. `commitments`

A commitment represents something the user/person committed to doing.

```sql
CREATE TABLE commitments (
    id UUID PRIMARY KEY,

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    project_id UUID
        REFERENCES projects(id)
        ON DELETE SET NULL,

    description TEXT NOT NULL,

    owner_person_id UUID
        REFERENCES people(id)
        ON DELETE SET NULL,

    deadline_at TIMESTAMPTZ,

    status VARCHAR(50) NOT NULL DEFAULT 'open',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ
);
```

Recommended status:

```text
open
completed
cancelled
expired
```

---

# 51. Commitment Provenance

```sql
CREATE TABLE commitment_sources (
    commitment_id UUID NOT NULL
        REFERENCES commitments(id)
        ON DELETE CASCADE,

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    chunk_id UUID
        REFERENCES document_chunks(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (commitment_id, document_id, chunk_id)
);
```

This lets us answer:

> "Where did this commitment come from?"

---

# 52. `decisions`

A decision is different from a task.

Example:

> "We decided to use PostgreSQL."

That should become:

```sql
CREATE TABLE decisions (
    id UUID PRIMARY KEY,

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    project_id UUID
        REFERENCES projects(id)
        ON DELETE SET NULL,

    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,

    decision_date TIMESTAMPTZ,

    status VARCHAR(50) NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Recommended statuses:

```text
active
superseded
reversed
archived
```

---

# 53. Decision Provenance

```sql
CREATE TABLE decision_sources (
    decision_id UUID NOT NULL
        REFERENCES decisions(id)
        ON DELETE CASCADE,

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    chunk_id UUID
        REFERENCES document_chunks(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (decision_id, document_id, chunk_id)
);
```

---

# 54. Decision Alternatives

This is optional for the first migration, but I recommend including it because it makes the decision model significantly more useful.

```sql
CREATE TABLE decision_alternatives (
    id UUID PRIMARY KEY,

    decision_id UUID NOT NULL
        REFERENCES decisions(id)
        ON DELETE CASCADE,

    name VARCHAR(500) NOT NULL,
    description TEXT,

    selected BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Example:

```text
Decision:
Use PostgreSQL

Alternatives:
├── PostgreSQL       selected = true
├── MongoDB          selected = false
└── MySQL            selected = false
```

We should **not** infer why an alternative was rejected unless the source explicitly provides that information.

---

# 55. `risks`

Risks were included in the product requirements, so they need a minimal representation.

```sql
CREATE TABLE risks (
    id UUID PRIMARY KEY,

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    project_id UUID
        REFERENCES projects(id)
        ON DELETE SET NULL,

    title VARCHAR(500) NOT NULL,
    description TEXT,

    status VARCHAR(50) NOT NULL DEFAULT 'open',
    severity VARCHAR(50),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

We should keep this intentionally simple.

---

# 56. Why We Don't Create an `entities` Table Yet

It may be tempting to build:

```text
entities
relationships
entity_types
entity_mentions
```

and create a full knowledge graph.

**Don't.**

That is a classic scope trap.

The current domain model should use explicit domain entities for the capabilities it supports:

```text
Project
Person
Task
Commitment
Decision
Risk
Document
Chunk
```

If later evaluation shows that a graph materially improves the product, we can introduce one.

---

# 57. `jobs`

Because ingestion is asynchronous, we need persistent job state.

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY,

    user_id UUID
        REFERENCES users(id)
        ON DELETE CASCADE,

    job_type VARCHAR(100) NOT NULL,

    status VARCHAR(50) NOT NULL DEFAULT 'pending',

    payload JSONB NOT NULL DEFAULT '{}',

    error_message TEXT,

    attempts INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
```

Example:

```text
job_type = document.ingest
```

Status:

```text
pending
running
completed
failed
```

---

# 58. `model_runs`

This table is important for AI observability and evaluation.

Every significant model invocation can optionally be recorded.

```sql
CREATE TABLE model_runs (
    id UUID PRIMARY KEY,

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    job_id UUID
        REFERENCES jobs(id)
        ON DELETE SET NULL,

    operation VARCHAR(100) NOT NULL,

    provider VARCHAR(100) NOT NULL,
    model VARCHAR(255) NOT NULL,

    input_tokens INTEGER,
    output_tokens INTEGER,

    latency_ms INTEGER,

    status VARCHAR(50) NOT NULL,

    error_message TEXT,

    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Examples of `operation`:

```text
query_generation
entity_extraction
embedding
reranking
daily_intelligence
```

This will eventually allow us to answer:

> Which model is costing us the most?

> Which operation is slow?

> How many tokens did this query consume?

---

# 59. Evaluation Tables

We don't need a huge evaluation schema initially.

A minimal design:

```sql
CREATE TABLE evaluation_runs (
    id UUID PRIMARY KEY,

    name VARCHAR(255) NOT NULL,

    evaluation_type VARCHAR(100) NOT NULL,

    model VARCHAR(255),

    metrics JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

And:

```sql
CREATE TABLE evaluation_cases (
    id UUID PRIMARY KEY,

    evaluation_run_id UUID NOT NULL
        REFERENCES evaluation_runs(id)
        ON DELETE CASCADE,

    input JSONB NOT NULL,
    expected JSONB NOT NULL,
    actual JSONB,

    metrics JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

This keeps evaluation data separate from production business state.

---

# 60. Important Indexes

The first migration should include indexes for common access patterns.

```sql
CREATE INDEX idx_documents_user
ON documents(user_id);

CREATE INDEX idx_documents_project
ON documents(project_id);

CREATE INDEX idx_documents_status
ON documents(processing_status);

CREATE INDEX idx_chunks_document
ON document_chunks(document_id);

CREATE INDEX idx_tasks_user_status
ON tasks(user_id, status);

CREATE INDEX idx_tasks_due_at
ON tasks(due_at);

CREATE INDEX idx_commitments_user_status
ON commitments(user_id, status);

CREATE INDEX idx_commitments_deadline
ON commitments(deadline_at);

CREATE INDEX idx_decisions_user_status
ON decisions(user_id, status);

CREATE INDEX idx_jobs_status
ON jobs(status);

CREATE INDEX idx_model_runs_operation
ON model_runs(operation);
```

We should add indexes based on actual query patterns rather than indexing every column.

---

# 61. Important Constraints

The database should enforce basic invariants.

Examples:

```sql
CHECK (attempts >= 0)
```

and appropriate enum/check constraints for fields such as:

```text
task.status
task.priority
commitment.status
decision.status
document.processing_status
job.status
```

We can implement these as PostgreSQL enums or constrained strings.

Prefer **constrained strings/check constraints** over PostgreSQL enums where this makes application-level evolution easier.

---

# 62. Timestamps

All timestamps should use:

```sql
TIMESTAMPTZ
```

not:

```sql
TIMESTAMP
```

The application should store timestamps in UTC and convert them to the user's local timezone at the presentation layer.

This matters for:

* deadlines
* daily intelligence
* recent changes
* commitments
* task scheduling

---

# 63. Soft Delete

We should **not implement soft deletion everywhere without a concrete retention or recovery requirement**.

For source documents, deleting the document should normally cascade to its chunks.

For structured entities, deletion semantics should be explicit.

We don't need:

```text
deleted_at
deleted_by
deletion_reason
```

on every table until the product actually requires recovery/audit behavior.

---

# 64. JSONB Usage

JSONB is useful, but it should not become an excuse to avoid proper relational modeling.

Good:

```text
documents.metadata
people.metadata
model_runs.metadata
evaluation.metrics
```

Bad:

```text
tasks.data = {
    "title": "...",
    "status": "...",
    "due_date": "..."
}
```

Core business fields should remain typed relational columns.

---

# 65. Full Schema Relationship Diagram

```text
                                      ┌──────────────┐
                                      │    users     │
                                      └──────┬───────┘
                                             │
             ┌───────────────────────────────┼────────────────────┐
             │                               │                    │
             ▼                               ▼                    ▼
       ┌────────────┐                  ┌──────────┐        ┌─────────────┐
       │  projects  │                  │  people  │        │    jobs     │
       └─────┬──────┘                  └──────────┘        └──────┬──────┘
             │                                                    │
             │                                                    ▼
             │                                             ┌─────────────┐
             │                                             │ model_runs  │
             │                                             └─────────────┘
             │
             ▼
       ┌────────────┐
       │ documents  │
       └─────┬──────┘
             │
             ▼
     ┌──────────────────┐
     │ document_chunks  │
     │                  │
     │ text             │
     │ embedding        │
     │ search_vector    │
     └────────┬─────────┘
              │
              │ provenance
      ┌───────┼───────────────┐
      │       │               │
      ▼       ▼               ▼
   tasks  commitments     decisions
      │       │               │
      │       │               ▼
      │       │        decision_alternatives
      │       │
      │       ▼
      │  commitment_sources
      │
      ▼
   task_sources

              projects
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
      tasks  commitments decisions
                 │
                 ▼
              people
```

---

# 66. Provenance Model

The critical relationship is:

```text
                     DOCUMENT
                         │
                         ▼
                       CHUNK
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
             TASK   COMMITMENT   DECISION
```

For example:

```text
Task #123
   │
   └── task_sources
          │
          ├── document_id = meeting-42
          └── chunk_id = chunk-17
```

We can therefore answer:

> "Why was Task #123 created?"

with:

```text
Task #123
   ↓
Commitment #54
   ↓
Meeting transcript
   ↓
Chunk #17
```

That is one of the strongest features of the architecture.

---

# 67. Migration Strategy

We should use Alembic.

Migration sequence:

```text
001_initial_extensions
       ↓
002_users_projects
       ↓
003_documents_chunks
       ↓
004_vector_search
       ↓
005_tasks_commitments_decisions
       ↓
006_provenance
       ↓
007_jobs_model_runs
       ↓
008_evaluation
```

We don't necessarily need eight physical migration files on day one; this is the logical dependency order.

---

# 68. V2 Database Rules

The database architecture follows six rules across V2:

### Rule 1

**PostgreSQL is the source of truth.**

### Rule 2

**pgvector is an index, not a knowledge store.**

### Rule 3

**Every AI-generated actionable entity must have provenance.**

### Rule 4

**Structured facts belong in typed columns.**

### Rule 5

**JSONB is for genuinely flexible metadata, not core business state.**

### Rule 6

**The schema should represent today's product, not hypothetical V5 functionality.**

---

# 69. Recommended Initial Schema

The core schema dependency graph is:

```text
users
  │
  ├── projects
  │
  └── documents
         │
         └── document_chunks
                │
                └── embedding

users
  │
  ├── tasks
  ├── commitments
  ├── decisions
  └── people

documents/chunks
  │
  ├── task_sources
  ├── commitment_sources
  └── decision_sources

users
  │
  └── jobs
         │
         └── model_runs
```

This is the baseline relational structure. Any additional V2 tables must be introduced through reviewed Alembic migrations and justified by the active milestone.
