# PAIS — Personal Decision & Action Intelligence System

PAIS is a personal intelligence system that turns unstructured information into **searchable, traceable, structured, and actionable knowledge**.

It combines document ingestion, semantic and lexical retrieval, grounded LLM generation, structured intelligence extraction, provenance tracking, and actionable domain models to help transform information into useful context and decisions.

The core idea behind PAIS is:

> **Use the LLM for reasoning and generation, while keeping the source data and application state authoritative.**

PAIS does not treat an LLM's output as the source of truth. Original documents and persisted application data remain authoritative, while generated information is grounded in retrieved evidence and linked back to its sources wherever applicable.

---

## What PAIS Does

At a high level, PAIS takes information such as documents, notes, and other textual content and turns it into a structured personal knowledge system.

```text
                             ┌──────────────────────┐
                             │   Source Documents   │
                             └──────────┬───────────┘
                                        │
                                        ▼
                             ┌───────────────────────┐
                             │  Ingestion & Parsing  │
                             └──────────┬────────────┘
                                        │
                                        ▼
                             ┌───────────────────────┐
                             │  Chunking & Embedding │
                             └──────────┬────────────┘
                                        │
                           ┌────────────┴─────────────┐
                           │                          │
                           ▼                          ▼
                 ┌──────────────────┐        ┌────────────────┐
                 │ Vector Retrieval │        │ Lexical Search │
                 └─────────┬────────┘        └────────┬───────┘
                           └────────────┬─────────────┘
                                        │
                                        ▼
                              ┌────────────────────┐
                              │  Hybrid Retrieval  │
                              │    + RRF Fusion    │
                              └─────────┬──────────┘
                                        │
                            ┌───────────┴───────────┐
                            │                       │
                            ▼                       ▼
                      ┌────────────┐       ┌─────────────────┐
                      │   Search   │       │  Grounded Query │
                      └────────────┘       └────────┬────────┘
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │  LLM Generation │
                                           └────────┬────────┘
                                                    │
                                                    ▼
                                        ┌─────────────────────────┐
                                        │ Structured Intelligence │
                                        └───────────┬─────────────┘
                                                    │
           ┌───────────────────┬────────────────────┼───────────────────┬──────────────────┐
           ▼                   ▼                    ▼                   ▼                  ▼
     ┌───────────┐      ┌─────────────┐      ┌─────────────┐      ┌───────────┐      ┌───────────┐
     │   Tasks   │      │ Commitments │      │  Decisions  │      │ Projects  │      │   Risks   │
     └───────────┘      └─────────────┘      └─────────────┘      └───────────┘      └───────────┘
                                                    │
                                                    │
                                                    ▼
                                         ┌──────────────────────┐
                                         │  Daily Intelligence  │
                                         └──────────────────────┘
```

---

## Key Features

### Document Intelligence

* Document ingestion, parsing, normalization, and chunking
* Embedding generation and persistence with PostgreSQL + pgvector
* Configurable upload limits

### Hybrid Search

* Semantic search using `BAAI/bge-small-en-v1.5`
* PostgreSQL full-text lexical search
* Hybrid retrieval using Reciprocal Rank Fusion (RRF)
* Optional Cross-Encoder reranking

### Grounded LLM Query

* Retrieval-augmented generation
* Source-grounded answers
* Document/chunk references
* Configurable retrieval and project filtering

### Structured Intelligence

* Extracts tasks, commitments, decisions, projects, people, and risks
* Schema-validated structured LLM output
* Deduplication and source provenance

### Daily Intelligence

* Combines tasks, commitments, decisions, projects, people, and risks
* Deterministic priority calculation
* LLM-generated daily intelligence summary

### Observability

* LLM model-run tracking
* Token usage and latency metadata
* Provider/model information
* Failure tracking

### Security

* JWT authentication
* User/tenant isolation
* Upload-size enforcement
* Security headers
* Production configuration validation

---

## Architecture

PAIS follows a layered architecture.

```text
┌─────────────────────────────────────────────┐
│                  API Layer                  │
│       FastAPI / Authentication / HTTP       │
├─────────────────────────────────────────────┤
│              Application Layer              │
│       Services / Query / Daily / Tasks      │
├─────────────────────────────────────────────┤
│              Intelligence Layer             │
│     LLM / Structured LLM / Retrieval        │
├─────────────────────────────────────────────┤
│               Domain Layer                  │
│ Tasks / Commitments / Decisions / Projects  │
│       People / Risks / Provenance           │
├─────────────────────────────────────────────┤
│              Persistence Layer              │
│       SQLAlchemy / PostgreSQL / pgvector    │
└─────────────────────────────────────────────┘
```

The architecture intentionally separates:

* HTTP concerns
* Authentication
* Business services
* Retrieval
* LLM providers
* Structured extraction
* Domain models
* Persistence
* Observability

---

## Technology Stack

### Backend

* Python 3.12+
* FastAPI
* Uvicorn
* Pydantic
* Pydantic Settings

### Database

* PostgreSQL
* pgvector
* SQLAlchemy 2.x
* asyncpg
* Alembic

### AI / Retrieval

* Sentence Transformers
* `BAAI/bge-small-en-v1.5`
* `BAAI/bge-reranker-base`
* Ollama
* Llama 3.2 3B

### Testing

* pytest
* pytest-asyncio
* HTTPX
* FastAPI/ASGI testing
* Integration tests against PostgreSQL

### Development

* Docker
* Docker Compose
* Ruff
* Git

---

## Project Structure

The main application structure is organized around infrastructure, APIs, domain services, retrieval, LLMs, and tests.

```text
PAIS/
│
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── daily.py
│   │       ├── documents.py
│   │       ├── health.py
│   │       ├── query.py
│   │       ├── search.py
│   │       └── router.py
│   │
│   ├── auth/
│   │   ├── models.py
│   │   └── service.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   ├── database/
│   │   ├── models/
│   │   └── session.py
│   │
│   ├── daily/
│   ├── decisions/
│   ├── embeddings/
│   ├── evaluation/
│   ├── ingestion/
│   ├── intelligence/
│   ├── llm/
│   ├── observability/
│   ├── people/
│   ├── projects/
│   ├── query/
│   ├── reranking/
│   ├── retrieval/
│   ├── risks/
│   └── tasks/
│
├── alembic/
│   └── versions/
│
├── docker/
│   └── api/
│       └── Dockerfile
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
│
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## API

The PAIS REST API is exposed under the `/api/v1` prefix.

| Method | Endpoint            | Description                                             |
| ------ | ------------------- | ------------------------------------------------------- |
| `GET`  | `/api/v1/health`    | Liveness check                                          |
| `GET`  | `/api/v1/ready`     | Readiness check with database connectivity              |
| `POST` | `/api/v1/documents` | Upload and ingest a document                            |
| `POST` | `/api/v1/search`    | Perform hybrid document retrieval                       |
| `POST` | `/api/v1/query`     | Generate a grounded answer using retrieved context      |
| `GET`  | `/api/v1/daily`     | Generate daily intelligence from structured information |

### Authentication

Protected endpoints use JWT bearer authentication.

```http
Authorization: Bearer <token>
```

Authentication is configured through environment variables.

---

## Getting Started

### Requirements

* Python 3.12+
* Docker Desktop with Docker Compose
* Ollama with the configured LLM model

Docker Compose provides the PostgreSQL database with pgvector.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd PAIS/version_1
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Update the required values in `.env`, including authentication and LLM configuration.

Do not commit `.env` to source control.

### 3. Install Dependencies

For local development:

```bash
python -m pip install -e ".[dev]"
```

### 4. Start the Application

Start PostgreSQL and the PAIS API:

```bash
docker compose up -d --build
```

Run database migrations:

```bash
alembic upgrade head
```

The API will be available at:

```text
http://localhost:8000
```

### 5. Verify the Application

Check liveness:

```bash
curl http://localhost:8000/api/v1/health
```

Check database readiness:

```bash
curl http://localhost:8000/api/v1/ready
```

FastAPI's generated API documentation is available at:

```text
http://localhost:8000/docs
```

---

## Testing

Run the complete test suite:

```bash
pytest
```

For concise output:

```bash
pytest -q
```

Run only unit tests:

```bash
pytest tests/unit
```

Run integration tests:

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/integration -m integration
```

On Windows PowerShell:

```powershell
$env:RUN_INTEGRATION_TESTS="1"
pytest tests/integration -m integration
```

Run linting:

```bash
ruff check .
```

Format the code:

```bash
ruff format .
```

---

## Design Principles

* Source data remains authoritative over generated LLM output.
* Retrieval grounds LLM generation.
* Source-derived information maintains provenance.
* Deterministic business rules remain in application code.
* LLM providers are accessed through abstractions.
* Authentication and user ownership are enforced at application boundaries.
* Observability is separated from business state.

---

## License

This project is licensed under the MIT License.

Built by [Dipanjan Saha](https://github.com/dipanjansahaa).
