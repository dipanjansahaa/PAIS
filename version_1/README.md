# PAIS — Personal Decision & Action Intelligence System

Milestone 1 repository skeleton.

This milestone establishes the production-oriented application structure, configuration boundary, FastAPI entry point, PostgreSQL/pgvector infrastructure, Alembic migrations, health/readiness endpoints, tests, and Docker setup.

AI/RAG functionality is intentionally not implemented in this milestone.

## Milestone 1 — Database Foundation

The database layer uses SQLAlchemy 2.x with the async PostgreSQL driver.

- `app/database/base.py` provides the central `Base` metadata object.
- `app/database/session.py` owns the async engine and session factory.
- `app/api/dependencies.py` exposes `get_db()` to the API layer.
- `app/database/models/base_model.py` contains reusable UUID and timestamp mixins.
- PostgreSQL is the source of truth; pgvector will be enabled through Alembic.
- Domain models are intentionally not introduced until the relevant milestones.

The application expects a PostgreSQL async URL such as:

```text
postgresql+asyncpg://pais:pais@localhost:5432/pais
```

Do not use `Base.metadata.create_all()` for production schema management. Alembic will own schema migrations.

## Health and Readiness

PAIS exposes two operational endpoints:

- `GET /health` is a liveness probe. It returns `200` when the API process is running and deliberately performs no database call.
- `GET /ready` is a readiness probe. It executes `SELECT 1` through the request-scoped async SQLAlchemy session. It returns `200` when PostgreSQL is reachable and `503` when the database check fails.

Example healthy responses:

```json
{"status": "ok"}
```

```json
{"status": "ready", "database": "ok"}
```

The readiness endpoint does not expose database exception details to clients.

## Docker and PostgreSQL

Milestone 1 runs two containers:

- `api` — FastAPI application.
- `db` — PostgreSQL 16 with the `pgvector` extension available.

Start the stack:

```bash
cp .env.example .env
docker compose up -d --build
```

Check service status:

```bash
docker compose ps
```

Verify the API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

The PostgreSQL container has a healthcheck, and the API waits for the database to become healthy before starting.

The PostgreSQL volume is named `pais_postgres_data` and persists database data across container restarts.

For a real database integration test:

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/integration -m integration
```

On Windows PowerShell:

```powershell
$env:RUN_INTEGRATION_TESTS="1"
pytest tests/integration -m integration
```

Schema management is still handled by Alembic; Docker Compose only provides the database infrastructure in this milestone.
