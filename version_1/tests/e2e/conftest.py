from __future__ import annotations

from uuid import uuid4

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.api.v1.documents import get_document_ingestion_service
from app.api.v1.search import get_search_service
from app.database.models.user import User
from app.embeddings.base import EmbeddingProvider
from app.ingestion.chunker import DocumentChunker
from app.ingestion.document_service import DocumentIngestionService
from app.ingestion.normalizer import DocumentNormalizer
from app.ingestion.service import IngestionService
from app.main import app
from app.retrieval.fusion import RRFFusion
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.lexical import LexicalRetriever
from app.retrieval.service import SearchService
from app.retrieval.vector import VectorRetriever


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for E2E workflow tests."""

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
        return [
            [1.0] + [0.0] * 383
            for _ in texts
        ]

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return [1.0] + [0.0] * 383


@pytest_asyncio.fixture
async def e2e_api_client(
    db_session: AsyncSession,
):
    """Create an API client wired to the real application workflow."""

    test_user = User(
        email=f"e2e-{uuid4()}@example.com",
        display_name="E2E Test User",
    )

    db_session.add(test_user)
    await db_session.flush()

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
        ),
    )

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    def override_get_document_ingestion_service():
        return ingestion_service

    def override_get_search_service():
        return search_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[
        get_document_ingestion_service
    ] = override_get_document_ingestion_service
    app.dependency_overrides[
        get_search_service
    ] = override_get_search_service

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, test_user

    app.dependency_overrides.clear()

    await db_session.delete(test_user)
    await db_session.commit()