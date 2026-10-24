from __future__ import annotations

from uuid import uuid4

import httpx
import pytest_asyncio
from app.api.dependencies import get_current_user, get_db
from app.api.v1.documents import (
    get_document_ingestion_service,
    get_intelligence_workflow_service,
)
from app.api.v1.search import get_search_service
from app.database.models.user import User
from app.embeddings.base import EmbeddingProvider
from app.ingestion.chunker import DocumentChunker
from app.ingestion.document_service import DocumentIngestionService
from app.ingestion.normalizer import DocumentNormalizer
from app.ingestion.service import IngestionService
from app.intelligence.models import (
    CommitmentCandidate,
    DecisionCandidate,
    IntelligenceSource,
    PersonCandidate,
    ProjectCandidate,
    RiskCandidate,
    StructuredIntelligence,
    TaskCandidate,
)
from app.intelligence.persistence_service import (
    IntelligencePersistenceService,
)
from app.intelligence.service import IntelligenceExtractionResult
from app.intelligence.workflow import IntelligenceWorkflowService
from app.main import app
from app.retrieval.fusion import RRFFusion
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.service import SearchService
from app.retrieval.vector import VectorRetriever
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Provide deterministic embeddings for E2E tests."""

    @property
    def model_name(self) -> str:
        return "e2e-deterministic"

    @property
    def dimension(self) -> int:
        return 384

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [[1.0] + [0.0] * 383 for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 383


class DeterministicExtractionService:
    """Provide deterministic intelligence without calling an external LLM."""

    async def extract(self, results) -> IntelligenceExtractionResult:
        if not results:
            raise AssertionError(
                "Expected document chunks for intelligence extraction."
            )

        chunk_id = results[0].chunk_id

        def sources() -> list[IntelligenceSource]:
            return [IntelligenceSource(chunk_id=chunk_id)]

        intelligence = StructuredIntelligence(
            tasks=[
                TaskCandidate(
                    description="Complete the API deployment review",
                    owner="Dipanjan",
                    sources=sources(),
                )
            ],
            commitments=[
                CommitmentCandidate(
                    description="Deliver the deployment plan",
                    owner="Dipanjan",
                    sources=sources(),
                )
            ],
            decisions=[
                DecisionCandidate(
                    title="Use PostgreSQL for PAIS",
                    description=(
                        "PAIS will use PostgreSQL with pgvector."
                    ),
                    sources=sources(),
                )
            ],
            projects=[
                ProjectCandidate(
                    name="PAIS Productionization",
                    description=(
                        "Prepare PAIS for real personal daily use."
                    ),
                    sources=sources(),
                )
            ],
            people=[
                PersonCandidate(
                    name="Alice",
                    email="alice@example.com",
                    sources=sources(),
                )
            ],
            risks=[
                RiskCandidate(
                    title="Deployment risk",
                    description=(
                        "The deployment plan still needs review."
                    ),
                    severity="medium",
                    sources=sources(),
                )
            ],
        )

        return IntelligenceExtractionResult(
            intelligence=intelligence,
            model="e2e-extraction-model",
            latency_ms=2.0,
        )


@pytest_asyncio.fixture
async def e2e_api_client(db_session: AsyncSession):
    """Create an authenticated E2E client with deterministic services."""

    test_user = User(
        email=f"e2e-{uuid4()}@example.com",
        display_name="E2E Test User",
    )

    db_session.add(test_user)
    await db_session.flush()

    # Capture the ID before rollback can expire ORM attributes.
    test_user_id = test_user.id

    embedding_provider = DeterministicEmbeddingProvider()

    ingestion_service = DocumentIngestionService(
        ingestion_service=IngestionService(
            embedding_provider=embedding_provider,
        ),
        normalizer=DocumentNormalizer(),
        chunker=DocumentChunker(),
    )

    search_service = SearchService(
        retriever=HybridRetriever(
            vector_retriever=VectorRetriever(
                embedding_provider=embedding_provider,
            ),
            lexical_retriever=LexicalRetriever(),
            fusion=RRFFusion(k=60),
        )
    )

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    def override_get_document_ingestion_service():
        return ingestion_service

    def override_get_search_service():
        return search_service

    def override_get_intelligence_workflow_service():
        return IntelligenceWorkflowService(
            extraction_service=DeterministicExtractionService(),
            persistence_service=IntelligencePersistenceService(),
        )

    # Register dependency overrides before issuing requests.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )
    app.dependency_overrides[
        get_document_ingestion_service
    ] = override_get_document_ingestion_service
    app.dependency_overrides[
        get_search_service
    ] = override_get_search_service
    app.dependency_overrides[
        get_intelligence_workflow_service
    ] = override_get_intelligence_workflow_service

    assert get_current_user in app.dependency_overrides

    try:
        transport = ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client, test_user

    finally:
        app.dependency_overrides.clear()

        # Roll back test-session changes before cleaning up the test user.
        await db_session.rollback()

        persisted_user = await db_session.get(User, test_user_id)

        if persisted_user is not None:
            await db_session.delete(persisted_user)
            await db_session.commit()