EVALUATION_DOCUMENTS = [
    # Relevant documents
    {
        "title": "PostgreSQL Database",
        "content": (
            "The project uses PostgreSQL as its primary relational database "
            "for persistent application data."
        ),
        "relevant_case": "database",
    },
    {
        "title": "Application Deployment",
        "content": (
            "The application is deployed using Docker containers. "
            "Production deployments use a versioned container image."
        ),
        "relevant_case": "deployment",
    },
    {
        "title": "Project Meeting Decision",
        "content": (
            "During the architecture meeting, the team decided to use "
            "PostgreSQL for persistent storage."
        ),
        "relevant_case": "meeting_decision",
    },
    {
        "title": "Authentication Strategy",
        "content": (
            "The API uses token-based authentication to protect "
            "authenticated endpoints."
        ),
        "relevant_case": "authentication",
    },
    {
        "title": "API Error Handling",
        "content": (
            "The backend returns structured error responses with request "
            "identifiers and appropriate HTTP status codes."
        ),
        "relevant_case": "error_handling",
    },
    {
        "title": "Background Processing",
        "content": (
            "Long-running document processing tasks are executed by "
            "background workers rather than directly inside API requests."
        ),
        "relevant_case": "background_processing",
    },
    {
        "title": "Document Chunking",
        "content": (
            "Documents are divided into overlapping text chunks before "
            "embedding and vector indexing."
        ),
        "relevant_case": "chunking",
    },
    {
        "title": "Semantic Search",
        "content": (
            "Semantic retrieval uses BAAI sentence embeddings and "
            "pgvector similarity search to find conceptually related chunks."
        ),
        "relevant_case": "semantic_search",
    },
    {
        "title": "Lexical Search",
        "content": (
            "Lexical retrieval uses PostgreSQL full-text search with "
            "tsvector and ts_rank_cd to match important query terms."
        ),
        "relevant_case": "lexical_search",
    },
    {
        "title": "Hybrid Retrieval",
        "content": (
            "The retrieval pipeline combines semantic vector search and "
            "lexical search, then uses Reciprocal Rank Fusion to combine "
            "their ranked results."
        ),
        "relevant_case": "hybrid_retrieval",
    },
    {
        "title": "Retrieval Evaluation",
        "content": (
            "Retrieval quality is measured using Recall@K, Mean Reciprocal "
            "Rank, and NDCG@K."
        ),
        "relevant_case": "retrieval_evaluation",
    },
    {
        "title": "Health and Readiness",
        "content": (
            "The API exposes separate health and readiness endpoints. "
            "The readiness check verifies database connectivity."
        ),
        "relevant_case": "readiness",
    },
    {
        "title": "Database Connection Pool",
        "content": (
            "The application uses an asynchronous SQLAlchemy connection "
            "pool with connection health checks."
        ),
        "relevant_case": "connection_pool",
    },
    {
        "title": "Observability",
        "content": (
            "Application observability includes request identifiers, "
            "latency measurements, model information, and error logging."
        ),
        "relevant_case": "observability",
    },
    {
        "title": "Configuration",
        "content": (
            "Application configuration is managed through environment "
            "variables using Pydantic Settings."
        ),
        "relevant_case": "configuration",
    },

    # Distractors
    {
        "title": "Frontend Components",
        "content": (
            "The frontend uses reusable component-based user interface "
            "elements for rendering application screens."
        ),
        "relevant_case": None,
    },
    {
        "title": "Frontend State Management",
        "content": (
            "Client-side state is managed through predictable application "
            "state transitions and reusable state containers."
        ),
        "relevant_case": None,
    },
    {
        "title": "Redis Cache",
        "content": (
            "A Redis cache can be used to store frequently accessed "
            "application responses and reduce repeated database queries."
        ),
        "relevant_case": None,
    },
    {
        "title": "Database Migration",
        "content": (
            "Database schema changes are managed through versioned "
            "Alembic migrations."
        ),
        "relevant_case": None,
    },
    {
        "title": "Docker Build",
        "content": (
            "The Docker image installs application dependencies and "
            "starts the API server inside a container."
        ),
        "relevant_case": None,
    },
    {
        "title": "Unit Testing",
        "content": (
            "Unit tests validate individual application components "
            "without requiring the complete application stack."
        ),
        "relevant_case": None,
    },
    {
        "title": "Integration Testing",
        "content": (
            "Integration tests verify interactions between the API, "
            "database, retrieval components, and other services."
        ),
        "relevant_case": None,
    },
    {
        "title": "Logging Configuration",
        "content": (
            "Logging configuration controls log levels and formatting "
            "for development and production environments."
        ),
        "relevant_case": None,
    },
    {
        "title": "API Documentation",
        "content": (
            "The FastAPI application automatically exposes interactive "
            "OpenAPI documentation for its endpoints."
        ),
        "relevant_case": None,
    },
    {
        "title": "SQL Query Optimization",
        "content": (
            "Database queries can be optimized through appropriate indexes, "
            "query plans, and selective filtering."
        ),
        "relevant_case": None,
    },
]


def get_relevant_document_count() -> int:
    return sum(
        1
        for document in EVALUATION_DOCUMENTS
        if document["relevant_case"] is not None
    )