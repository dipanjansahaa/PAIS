# PAIS V2 — Personal Decision & Action Intelligence System

PAIS is a personal intelligence system that turns unstructured information into **searchable, traceable, structured, and actionable knowledge**.

It combines document ingestion, semantic and lexical retrieval, grounded LLM generation, structured intelligence extraction, provenance tracking, and actionable domain models to help transform information into useful context and decisions.

> **Core principle:** Use the LLM for reasoning and generation while keeping source data and application state authoritative.

PAIS does not treat an LLM's output as the source of truth. Original documents and persisted application data remain authoritative, while generated information is grounded in retrieved evidence and linked back to its sources wherever applicable.

**PAIS V2 status:** V2 evolves the completed V1 baseline. The V2 roadmap is organized into milestones V2.1--V2.9; features described as future roadmap work are not necessarily implemented in the current codebase.

---

## Table of Contents

- [What PAIS Does](#what-pais-does)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Clone the Repository](#1-clone-the-repository)
  - [Configure Environment](#2-configure-environment)
  - [Configure Ollama](#3-configure-ollama)
  - [Start the Backend and Database](#4-start-the-backend-and-database)
  - [Run Database Migrations](#5-run-database-migrations)
  - [Start the Frontend](#6-start-the-frontend)
  - [Verify the Application](#7-verify-the-application)
- [Frontend Pages](#frontend-pages)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Testing](#testing)
- [Design Principles](#design-principles)
- [Current Project Status](#current-project-status)
- [License](#license)

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

- Document upload, parsing, normalization, and chunking.
- Embedding generation and persistence with PostgreSQL and pgvector.
- Configurable upload limits.

### Hybrid Search

- Semantic retrieval using `BAAI/bge-small-en-v1.5`.
- PostgreSQL full-text lexical search.
- Hybrid retrieval using Reciprocal Rank Fusion (RRF).
- Optional cross-encoder reranking.

### Grounded LLM Query

- Retrieval-augmented generation (RAG).
- Answers grounded in retrieved document context.
- Document and chunk references.
- Configurable retrieval and project filtering.
- Query response metadata, including model and latency.

### Structured Intelligence

Extracts and persists:

- Tasks
- Commitments
- Decisions
- Projects
- People
- Risks

The extraction workflow uses schema-validated LLM output, deduplication, and source provenance.

### Daily Intelligence

- Combines tasks, commitments, decisions, projects, people, and risks.
- Calculates priorities using deterministic application logic.
- Generates an LLM-assisted daily summary from structured context.
- Supports a selected date and timezone.

### Observability

- LLM model-run tracking.
- Token usage and latency metadata where provided by the model provider.
- Provider/model information.
- Failure tracking.

### Security

- JWT bearer authentication for protected endpoints.
- User-level data isolation.
- Upload-size enforcement.
- Security headers.
- Production configuration validation.

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

- HTTP concerns
- Authentication
- Business services
- Retrieval
- LLM providers
- Structured extraction
- Domain models
- Persistence
- Observability

---

## Technology Stack

### Backend

- Python 3.12+
- FastAPI and Uvicorn
- Pydantic and Pydantic Settings
- SQLAlchemy 2.x
- `asyncpg`
- Alembic

### Database

- PostgreSQL
- pgvector

### AI and Retrieval

- Sentence Transformers
- `BAAI/bge-small-en-v1.5` embeddings
- `BAAI/bge-reranker-base` cross-encoder reranker
- Ollama
- Llama 3.2 3B

### Frontend

- React 19
- TypeScript
- Vite
- React Router

### Testing and Development

- pytest and pytest-asyncio
- HTTPX and FastAPI/ASGI testing
- Integration tests against PostgreSQL
- Ruff
- Docker and Docker Compose
- Git

---

## Project Structure

The main application structure is organized around infrastructure, APIs, frontend, domain services, retrieval, LLMs, and tests.

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
│   │       ├── intelligence.py
│   │       ├── query.py
│   │       ├── router.py
│   │       └── search.py
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
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── pages/
│   │   │   ├── DailyPage.tsx
│   │   │   ├── DocumentsPage.tsx
│   │   │   ├── IntelligencePage.tsx
│   │   │   ├── QueryPage.tsx
│   │   │   └── SearchPage.tsx
│   │   └── ...
│   ├── package.json
│   └── vite.config.ts
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── evaluation/
│
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

The tree highlights the main areas; individual modules and tests may be added as the project evolves.

---

## Getting Started

### Prerequisites

Install the following:

- Python 3.12 or later.
- Docker Desktop with Docker Compose.
- Node.js and npm (compatible with the installed Vite version).
- Ollama.
- The configured Ollama model, `llama3.2:3b`.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd PAIS/version_2
```

Replace `<repository-url>` with the actual repository URL.

### 2. Configure Environment

Copy the example environment file.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux**

```bash
cp .env.example .env
```

Review `.env` and configure the values for your environment. In particular:

- `DATABASE_URL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `AUTH_JWT_SECRET`
- `LLM_PROVIDER`
- `LLM_MODEL`

Use a strong, randomly generated JWT secret. Do not commit `.env` or publish secrets, tokens, or database credentials.

The example configuration is intended for local development. Do not reuse its sample database credentials in a public deployment.

### 3. Configure Ollama

Start Ollama and download the configured model:

```bash
ollama pull llama3.2:3b
```

Verify that the model is available:

```bash
ollama list
```

The supplied Docker Compose configuration points the API container to Ollama on the host through `host.docker.internal:11434`. Keep Ollama running while using AI features.

### 4. Start the Backend and Database

From the repository root:

```bash
docker compose up -d --build
```

Check service status:

```bash
docker compose ps
```

View logs when troubleshooting:

```bash
docker compose logs -f api
```

The V2 Docker Compose configuration exposes the API at host port `8001` and PostgreSQL at host port `5433`. Inside the Compose network, the API listens on port `8000` and connects to PostgreSQL through the `db:5432` service address.

### 5. Run Database Migrations

Run migrations using the project's configured Python environment. If dependencies are not installed locally, install the project development dependencies first:

```bash
python -m pip install -e ".[dev]"
```

Then run:

```bash
alembic upgrade head
```

Ensure the `DATABASE_URL` used by the migration command points to the database address reachable from the environment where Alembic runs. The example `.env` uses `localhost` for host-side commands; the API container uses the Compose database service name.

### 6. Start the Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the frontend at:

```text
http://localhost:5173
```

The Vite development server should proxy requests beginning with `/api` to the V2 API at `http://localhost:8001`, so the frontend can use the backend without a separate API URL during local development. Check `frontend/vite.config.ts` if the configured proxy differs.

To create a production frontend build:

```bash
npm run build
```

To run TypeScript checking separately:

```bash
npm run typecheck
```

The production build is written to `frontend/dist/`. This repository does not yet define a complete public production deployment in this README.

### 7. Verify the Application

Backend liveness:

```text
http://localhost:8001/api/v1/health
```

Backend readiness (including database connectivity):

```text
http://localhost:8001/api/v1/ready
```

Interactive API documentation:

```text
http://localhost:8001/docs
```

Frontend:

```text
http://localhost:5173
```

Protected API operations require a valid JWT bearer token.

---

## Frontend Pages

The React application provides the following pages:

| Page | Purpose |
|---|---|
| **Intelligence** | View persisted tasks, commitments, decisions, projects, people, and risks. |
| **Daily** | View date- and timezone-specific daily intelligence, including summary, priorities, decisions, changes, and risks. |
| **Search** | Retrieve relevant document chunks using hybrid search. |
| **Query** | Ask questions over retrieved documents and inspect the answer and source evidence. |
| **Documents** | Upload documents for ingestion and indexing. |

Shared feedback components provide loading, empty, and error states. The frontend also includes API error handling and retry affordances for relevant workflows.

### Frontend API behavior

The frontend API client uses the relative prefix `/api/v1`. During local development, Vite should proxy `/api` requests to the V2 backend at `http://localhost:8001`; verify the target in `frontend/vite.config.ts`.

If the frontend and backend are hosted separately in a future deployment, the API routing and browser security configuration will need to be updated accordingly.

---

## API Reference

The PAIS REST API is exposed under the `/api/v1` prefix.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness check |
| `GET` | `/api/v1/ready` | Readiness check with database connectivity |
| `POST` | `/api/v1/documents` | Upload and ingest a document |
| `POST` | `/api/v1/search` | Perform hybrid document retrieval |
| `POST` | `/api/v1/query` | Generate a grounded answer using retrieved context |
| `GET` | `/api/v1/daily` | Generate daily intelligence from structured information |
| `GET` | `/api/v1/intelligence` | Retrieve persisted structured intelligence. |

---

## Authentication

Protected endpoints use JWT bearer authentication:

```http
Authorization: Bearer <token>
```

Authentication configuration is supplied through environment variables, including `AUTH_JWT_SECRET` and, when configured, issuer and audience values.

Tokens must be valid and unexpired. The frontend attaches its available token to API requests. A complete public deployment should use a deliberate authentication and token-renewal flow, keep signing secrets server-side, and avoid exposing protected endpoints or credentials.

Do not paste real tokens or secrets into source control, issue trackers, screenshots, or public documentation.

---

## Testing

### Backend

Run the full suite:

```bash
pytest
```

Concise output:

```bash
pytest -q
```

Run unit tests:

```bash
pytest tests/unit
```

Run integration tests on Windows PowerShell:

```powershell
$env:RUN_INTEGRATION_TESTS="1"
pytest tests/integration -m integration
```

Run integration tests on macOS/Linux:

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/integration -m integration
```

Run linting:

```bash
ruff check .
```

Check formatting:

```bash
ruff format --check .
```

To apply formatting:

```bash
ruff format .
```

### Frontend

From `frontend/`:

```bash
npm run typecheck
npm run build
```

The build script runs TypeScript project checks before creating the Vite production bundle.

### Latest reported test result

The latest reported V2 backend result during development was:

```text
471 passed, 1 skipped
```

This is a development-time result, not a guarantee that every environment or deployment configuration has been tested. The skipped test requires `RUN_INTEGRATION_TESTS=1`; review the test's setup requirements before treating it as a production verification.

---

## Design Principles

- Source data remains authoritative over generated LLM output.
- Retrieval grounds LLM generation.
- Source-derived information maintains provenance.
- Deterministic business rules remain in application code.
- LLM providers are accessed through abstractions.
- Authentication and user ownership are enforced at application boundaries.
- Observability is separated from business state.
- Tests validate behavior at unit, integration, end-to-end, and evaluation levels where applicable.

---

## Current Project Status

PAIS V2 is being developed milestone by milestone, preserving the completed V1 feature baseline. The latest reported V2 backend test run completed with 471 passed and 1 skipped. V2.1 is still subject to the remaining review and acceptance checks; it should not be described as formally complete until those checks are finished.

The planned V2 roadmap is:

- **V2.1 --- Foundation and V1 Feature Parity**
- **V2.2 --- Persistent Personal Memory**
- **V2.3 --- Knowledge Graph and Temporal Intelligence**
- **V2.4 --- Advanced Retrieval and Evidence-Grounded Reasoning**
- **V2.5 --- Proactive Intelligence Engine**
- **V2.6 --- Controlled AI Agents and Workflows**
- **V2.7 --- Evaluation and Continuous Improvement**
- **V2.8 --- Unified Frontend and User Experience**
- **V2.9 --- Production Readiness and Release**

The roadmap describes planned milestones, not a claim that every capability is already implemented.

**Public production deployment is not yet completed.** The current V2 development setup uses Docker Compose, PostgreSQL with pgvector, and local Ollama inference. V2 is being built on top of the V1 feature baseline; planned roadmap capabilities should not be interpreted as already implemented. A future deployment must explicitly address hosting, secrets, authentication lifecycle, persistent storage, network exposure, and LLM inference availability.

---

## License

This project is licensed under the MIT License.

Built by [Dipanjan Saha](https://github.com/dipanjansahaa).
