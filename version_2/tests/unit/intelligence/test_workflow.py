
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.intelligence.models import StructuredIntelligence
from app.intelligence.persistence_service import (
    IntelligencePersistenceResult,
)
from app.intelligence.workflow import IntelligenceWorkflowService


@pytest.mark.asyncio
async def test_extracts_and_persists_document_chunks():
    session = AsyncMock()
    chunk = SimpleNamespace(
        id=uuid4(),
        document_id=uuid4(),
        content="Review the API deployment plan by October 20.",
        chunk_metadata=None,
    )

    result_proxy = MagicMock()
    result_proxy.all.return_value = [chunk]
    session.scalars.return_value = result_proxy

    intelligence = StructuredIntelligence()
    extraction_service = AsyncMock()
    extraction_service.extract.return_value = SimpleNamespace(
        intelligence=intelligence,
    )

    expected = IntelligencePersistenceResult()
    persistence_service = AsyncMock()
    persistence_service.persist.return_value = expected

    workflow = IntelligenceWorkflowService(
        extraction_service=extraction_service,
        persistence_service=persistence_service,
    )

    user_id = uuid4()

    result = await workflow.extract_and_persist(
        session,
        user_id=user_id,
        document_id=chunk.document_id,
    )

    assert result == expected
    extraction_service.extract.assert_awaited_once()

    retrieved_chunks = extraction_service.extract.await_args.args[0]
    assert len(retrieved_chunks) == 1
    assert retrieved_chunks[0].chunk_id == chunk.id
    assert retrieved_chunks[0].document_id == chunk.document_id
    assert retrieved_chunks[0].content == chunk.content

    persistence_service.persist.assert_awaited_once_with(
        session,
        user_id=user_id,
        intelligence=intelligence,
    )


@pytest.mark.asyncio
async def test_empty_document_skips_extraction():
    session = AsyncMock()

    result_proxy = MagicMock()
    result_proxy.all.return_value = []
    session.scalars.return_value = result_proxy

    extraction_service = AsyncMock()
    persistence_service = AsyncMock()

    workflow = IntelligenceWorkflowService(
        extraction_service=extraction_service,
        persistence_service=persistence_service,
    )

    result = await workflow.extract_and_persist(
        session,
        user_id=uuid4(),
        document_id=uuid4(),
    )

    assert result == IntelligencePersistenceResult()
    extraction_service.extract.assert_not_awaited()
    persistence_service.persist.assert_not_awaited()
